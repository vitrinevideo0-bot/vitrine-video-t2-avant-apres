from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from audio.scripts.mix_t2_voice_music_v0_5 import validate_source_config
from engine.complete_adapter import (
    load_music_selection_state,
    record_music_render_result,
    select_music_candidate,
    select_music_candidate_from_state,
)
from tools.build_render_job import build_job

ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / "config/T2_music_pool_v1_0_0.json"


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class T2MusicRotationV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pool = load("config/T2_music_pool_v1_0_0.json")

    def test_pool_and_state_contracts_are_strict(self) -> None:
        pairs = [
            ("schemas/T2_music_pool_v1_0_0.schema.json", "config/T2_music_pool_v1_0_0.json"),
        ]
        pairs.extend(
            ("schemas/T2_complete_voice_mix_v1_0_0.schema.json", f"config/T2_complete_voice_mix_v1_0_0_{candidate}.json")
            for candidate in "ABCD"
        )
        for schema_path, document_path in pairs:
            schema = load(schema_path)
            Draft202012Validator.check_schema(schema)
            document = load(document_path)
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
            if "complete_voice_mix_v1_0_0" in document_path:
                validate_source_config(document)
        selection_contract = self.pool["selection_contract"]
        self.assertEqual(selection_contract["allowed_candidate_ids"], ["A", "B", "C", "D"])
        self.assertEqual(selection_contract["explicit_selection_policy"], "exact_successor_only")
        self.assertEqual(selection_contract["state_update_policy"], "after_success_only")
        self.assertEqual(selection_contract["idempotency_ledger_key"], "successful_render_jobs")
        self.assertEqual(selection_contract["failed_render_state_policy"], "unchanged")
        state_schema = load("schemas/T2_music_selection_state.schema.json")
        Draft202012Validator.check_schema(state_schema)
        Draft202012Validator(state_schema).validate(
            {
                "schema_version": "1.0.0",
                "last_successful_music_id": "A",
                "last_successful_render_job_id": "t2-contract-job-0001",
                "successful_render_count": 1,
                "successful_render_jobs": {"t2-contract-job-0001": "A"},
            }
        )

    def test_owner_approval_and_rights_history_remain_separate(self) -> None:
        approval = load("approvals/T2_MUSIC_POOL_APPROVAL_2026-11-18.json")
        historical = load("music/T2_music_shortlist_v0_4_0.json")
        self.assertEqual(approval["approved_candidate_ids"], ["A", "B", "C", "D"])
        self.assertTrue(approval["activation_authorized"])
        self.assertEqual([item["id"] for item in self.pool["candidates"]], ["A", "B", "C", "D"])
        self.assertTrue(all(item["owner_approved"] and item["production_eligible"] for item in self.pool["candidates"]))
        self.assertTrue(all(item["content_id_status"] == "not_displayed_on_source_page" for item in self.pool["candidates"]))
        self.assertEqual([item["content_id_status"] for item in historical["candidates"][:3]], ["registered"] * 3)
        self.assertNotEqual(
            [item["title"] for item in historical["candidates"][:3]],
            [item["title"] for item in self.pool["candidates"][:3]],
        )
        self.assertTrue(approval["historical_protection"]["historical_auditions_remain_audit_only"])
        self.assertEqual(approval["historical_protection"]["replaced_pixabay_id"], 300338)
        self.assertEqual(approval["historical_protection"]["replacement_pixabay_id"], 328624)

    def test_clean_instrumentals_and_mix_configs_match_locked_hashes(self) -> None:
        self.assertEqual([item["pixabay_id"] for item in self.pool["candidates"]], [300340, 293956, 300333, 328624])
        for item in self.pool["candidates"]:
            instrumental = ROOT / item["file"]
            mix_config = ROOT / item["mix_config"]
            self.assertTrue(instrumental.is_file())
            self.assertEqual(sha256(instrumental), item["sha256"])
            self.assertEqual(instrumental.stat().st_size, item["bytes"])
            self.assertEqual(item["duration_s"], 30.0)
            self.assertFalse(item["contains_voice"])
            self.assertEqual(sha256(mix_config), item["mix_config_sha256"])
        publication = self.pool["publication_contract"]
        self.assertTrue(publication["adapted_30s_instrumentals_bundled"])
        self.assertFalse(publication["instrumentals_contain_voice"])
        self.assertFalse(publication["historical_auditions_are_production_assets"])
        self.assertFalse(publication["full_pixabay_sources_bundled"])
        self.assertFalse(publication["source_audio_publish"])

    def test_auto_selection_follows_the_strict_A_B_C_D_cycle(self) -> None:
        previous = None
        observed = []
        for index in range(10_000):
            selected = select_music_candidate(
                self.pool,
                render_job_id=f"t2-rotation-{index:05d}",
                requested_candidate_id="auto",
                previous_candidate_id=previous,
            )
            observed.append(selected["id"])
            previous = selected["id"]
        self.assertEqual(observed, list("ABCD") * 2500)
        self.assertTrue(all(left != right for left, right in zip(observed, observed[1:])))
        with self.assertRaisesRegex(ValueError, "cycle T2 strict attend C"):
            select_music_candidate(
                self.pool,
                render_job_id="t2-explicit-repeat-0001",
                requested_candidate_id="B",
                previous_candidate_id="B",
            )
        with self.assertRaisesRegex(ValueError, "cycle T2 strict attend B"):
            select_music_candidate(
                self.pool,
                render_job_id="t2-explicit-skip-0001",
                requested_candidate_id="D",
                previous_candidate_id="A",
            )

    def test_state_advances_after_success_only_and_survives_reload(self) -> None:
        state_schema = load("schemas/T2_music_selection_state.schema.json")
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            first = select_music_candidate_from_state(render_job_id="t2-state-0001", state_path=state_path)
            self.assertEqual(first["id"], "A")
            initial = record_music_render_result(
                state_path=state_path,
                render_job_id="t2-state-0001",
                selected_music_id=first["id"],
                succeeded=False,
            )
            self.assertIsNone(initial["last_successful_music_id"])
            self.assertFalse(state_path.exists())
            committed = record_music_render_result(
                state_path=state_path,
                render_job_id="t2-state-0001",
                selected_music_id=first["id"],
                succeeded=True,
            )
            Draft202012Validator(state_schema).validate(committed)
            self.assertEqual(load_music_selection_state(state_path), committed)
            replay = record_music_render_result(
                state_path=state_path,
                render_job_id="t2-state-0001",
                selected_music_id=first["id"],
                succeeded=True,
            )
            self.assertEqual(replay, committed)
            second = select_music_candidate_from_state(render_job_id="t2-state-0002", state_path=state_path)
            self.assertEqual(second["id"], "B")
            record_music_render_result(
                state_path=state_path,
                render_job_id="t2-state-0002",
                selected_music_id=second["id"],
                succeeded=False,
            )
            self.assertEqual(load_music_selection_state(state_path), committed)

    def test_old_success_replay_remains_idempotent_after_a_full_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"
            committed_jobs: list[tuple[str, str]] = []
            for index, expected_music in enumerate("ABCDA", start=1):
                job_id = f"t2-full-cycle-{index:04d}"
                selected = select_music_candidate_from_state(render_job_id=job_id, state_path=state_path)
                self.assertEqual(selected["id"], expected_music)
                snapshot = record_music_render_result(
                    state_path=state_path,
                    render_job_id=job_id,
                    selected_music_id=selected["id"],
                    succeeded=True,
                )
                committed_jobs.append((job_id, selected["id"]))
            self.assertEqual(snapshot["successful_render_count"], 5)
            self.assertEqual(snapshot["successful_render_jobs"], dict(committed_jobs))
            replayed = record_music_render_result(
                state_path=state_path,
                render_job_id=committed_jobs[0][0],
                selected_music_id=committed_jobs[0][1],
                succeeded=True,
            )
            self.assertEqual(replayed, snapshot)
            with self.assertRaisesRegex(ValueError, "ne peut pas changer de musique"):
                record_music_render_result(
                    state_path=state_path,
                    render_job_id=committed_jobs[0][0],
                    selected_music_id="B",
                    succeeded=True,
                )

    def test_concurrent_duplicate_success_cannot_advance_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "state.json"

            def commit(job: str) -> str:
                try:
                    record_music_render_result(
                        state_path=state_path,
                        render_job_id=job,
                        selected_music_id="A",
                        succeeded=True,
                    )
                    return "committed"
                except ValueError:
                    return "rejected"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(commit, ["t2-concurrent-0001", "t2-concurrent-0002"]))
            self.assertEqual(sorted(outcomes), ["committed", "rejected"])
            state = load_music_selection_state(state_path)
            self.assertEqual(state["last_successful_music_id"], "A")
            self.assertEqual(state["successful_render_count"], 1)

    def test_each_approved_track_builds_a_strict_runtime_job(self) -> None:
        answers = load("demo/reponses_textes_demo.json")
        schema = load("schemas/render_job.schema.json")
        predecessors = {"A": "D", "B": "A", "C": "B", "D": "C"}
        for candidate in "ABCD":
            previous = predecessors[candidate]
            job = build_job(
                answers,
                stage="complete_voice_music_render",
                requested_music=candidate,
                previous_music=previous,
                voice_mode="registered_voice_clips",
                control_plane="github_actions_manual",
            )
            Draft202012Validator(schema).validate(job)
            music = job["audio_plan"]["music"]
            self.assertEqual(music["selected_candidate_id"], candidate)
            self.assertEqual(music["last_successful_music_id"], previous)
            self.assertEqual(job["audio_plan"]["config"], f"config/T2_complete_voice_mix_v1_0_0_{candidate}.json")
            self.assertEqual(job["runtime_contract"], "config/T2_runtime_contract_v1_0_0.json")
            self.assertTrue(job["idempotency_key"].startswith("t2-avant-apres-v1.0.0-music-rotation-"))

    def test_rotation_job_uses_pool_while_historical_D_remains_byte_stable(self) -> None:
        answers = load("demo/reponses_textes_demo.json")
        job = build_job(
            answers,
            stage="complete_voice_music_render",
            requested_music="auto",
            previous_music="A",
            voice_mode="registered_voice_clips",
            control_plane="github_actions_manual",
        )
        Draft202012Validator(load("schemas/render_job.schema.json")).validate(job)
        music = job["audio_plan"]["music"]
        self.assertEqual(music["selected_candidate_id"], "B")
        self.assertEqual(music["last_successful_music_id"], "A")
        self.assertEqual(music["state_update_policy"], "after_success_only")
        self.assertEqual(job["runtime_contract"], "config/T2_runtime_contract_v1_0_0.json")
        self.assertEqual(job["audio_contract"]["music_status"], "selected_from_owner_approved_four_track_rotation")
        self.assertTrue(job["output"]["uri"].startswith(f"output/runtime/{job['job_id']}/"))

        historical = build_job(
            answers,
            stage="complete_voice_music_render",
            requested_music="D",
            voice_mode="registered_voice_clips",
            control_plane="github_actions_manual",
            historical_exemplar=True,
        )
        self.assertEqual(historical, load("demo/render_job_complete_demo.json"))


if __name__ == "__main__":
    unittest.main()
