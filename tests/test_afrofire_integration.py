from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from tools.build_render_job import build_job

ROOT = Path(__file__).resolve().parents[1]
AFROFIRE_SHA256 = "24e9606e14e4708e8c8ffa3a6a97429dbfc95049d388481392d72b971e932c61"
VISUAL_STREAM_SHA256 = "2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5"


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def digest(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


class T2AfrofireIntegrationTest(unittest.TestCase):
    def test_canonical_template_identity_and_semantic_audio_profile(self) -> None:
        template = load("config/T2_avant_apres_template_v0_1_0.json")
        self.assertEqual(template["template_id"], "T2")
        self.assertEqual(template["version"], "0.1.0")
        self.assertEqual(template["audio_profile"], "afrobeat_restaurants_maquis")
        self.assertNotIn(".mp3", template["audio_profile"].lower())
        self.assertNotIn("afrofire", template["audio_profile"].lower())

    def test_selection_and_mix_evidence_are_strict_and_consistent(self) -> None:
        pairs = (
            ("schemas/T2_music_selection_v0_7_0.schema.json", "config/T2_music_selection_v0_7_0.json"),
            ("schemas/T2_complete_voice_mix_v0_7_0.schema.json", "config/T2_complete_voice_mix_v0_7_0.json"),
        )
        for schema_path, document_path in pairs:
            schema = load(schema_path)
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(load(document_path))

        decision = load("config/T2_music_selection_v0_7_0.json")
        selection = decision["selection"]
        self.assertEqual(decision["template_id"], "T2")
        self.assertEqual(decision["template_version"], "0.1.0")
        self.assertEqual(decision["audio_profile"], "afrobeat_restaurants_maquis")
        self.assertEqual(selection["candidate_id"], "D")
        self.assertEqual(selection["title"], "Afrofire")
        self.assertEqual(selection["artist"], "DPStudioMusic")
        self.assertEqual(selection["source_sha256"], AFROFIRE_SHA256)
        self.assertEqual(selection["source_bytes"], 7_680_768)
        self.assertEqual(selection["source_page_checked_on"], "2026-11-19")
        self.assertEqual(selection["content_id_status"], "not_displayed_on_source_page")
        self.assertEqual(selection["ai_generated_badge"], "displayed")
        self.assertFalse(selection["source_audio_publish"])
        self.assertTrue(decision["rights_evidence"]["commercial_use_permitted_under_license_summary"])
        self.assertFalse(decision["rights_evidence"]["attribution_required"])
        self.assertTrue(decision["rights_evidence"]["adaptation_permitted"])
        self.assertTrue(decision["rights_evidence"]["standalone_redistribution_forbidden"])
        self.assertFalse(decision["replaces"]["production_selectable"])
        self.assertEqual(decision["replaces"]["candidate_id"], "B")
        self.assertEqual(decision["replaces"]["content_id_status"], "registered")

        runtime = load("config/T2_runtime_contract_v0_7_0.json")
        self.assertEqual(runtime["domain"], "AVANT_APRES")
        self.assertEqual(runtime["audio_profile"], "afrobeat_restaurants_maquis")
        self.assertEqual(runtime["music_selection_contract"], "config/T2_music_selection_v0_7_0.json")

        mix = load("config/T2_complete_voice_mix_v0_7_0.json")
        self.assertEqual(mix["music_selection"]["source_sha256"], AFROFIRE_SHA256)
        self.assertEqual(mix["visual_source"]["video_stream_sha256"], VISUAL_STREAM_SHA256)
        self.assertEqual([clip["source_speed"] if "source_speed" in clip else mix["voice"]["source_speed"] for clip in mix["voice"]["clips"]], [1.0] * 4)
        self.assertEqual(mix["mix_contract"]["music_open_gain_db"], -3.0)
        self.assertEqual(mix["mix_contract"]["music_under_voice_gain_db"], -10.0)
        self.assertEqual(mix["mix_contract"]["duck_attack_ms"], 120)
        self.assertEqual(mix["mix_contract"]["duck_release_ms"], 450)
        self.assertFalse(mix["publication"]["publish_standalone_audio"])

    def test_current_demo_renderjob_is_correlated_to_afrofire_contract(self) -> None:
        schema = load("schemas/render_job.schema.json")
        job = load("demo/render_job_complete_demo.json")
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(job)
        self.assertEqual(job["runtime_contract"], "config/T2_runtime_contract_v0_7_0.json")
        self.assertEqual(job["audio_plan"]["config"], "config/T2_complete_voice_mix_v0_7_0.json")
        self.assertEqual(job["audio_plan"]["music"]["selected_candidate_id"], "D")
        self.assertEqual(job["audio_plan"]["music"]["source_sha256"], AFROFIRE_SHA256)
        self.assertFalse(job["audio_plan"]["music"]["source_audio_publish"])
        self.assertEqual(job["output"]["uri"], "output/t2-complete-v0.7.0/VIDEO_T2_COMPLET_VOIX_AFROFIRE_A_VALIDER.mp4")

        invalid = copy.deepcopy(job)
        invalid["audio_plan"]["config"] = "config/T2_complete_voice_mix_v0_5_0.json"
        invalid["audio_plan"]["config_sha256"] = "6f58c9fbbd4f9305ba9a2f46e84a002db5577499f94e6933a0f8fc54cec620db"
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema).validate(invalid)

        wrong_source = copy.deepcopy(job)
        wrong_source["audio_plan"]["music"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema).validate(wrong_source)

    def test_historical_b_contracts_remain_byte_identical_and_buildable(self) -> None:
        expected = {
            "config/T2_complete_voice_mix_v0_5_0.json": "6f58c9fbbd4f9305ba9a2f46e84a002db5577499f94e6933a0f8fc54cec620db",
            "schemas/T2_complete_voice_mix.schema.json": "6e7913f6f786fdae209e603831abe25290bb45c3058f0ae50669d386d0bcf9ba",
            "config/T2_runtime_contract_v0_6_0.json": "e5d341fb2b7b20461f9760ea0d7d93ab4e482321935f3201698ff64c9ee7ad12",
        }
        for relative, locked_sha256 in expected.items():
            self.assertEqual(digest(relative), locked_sha256)

        historical = build_job(
            load("demo/reponses_textes_demo.json"),
            stage="complete_voice_music_render",
            requested_music="B",
            voice_mode="registered_voice_clips",
            control_plane="github_actions_manual",
        )
        self.assertEqual(historical["audio_plan"]["music"]["selected_candidate_id"], "B")
        self.assertEqual(historical["runtime_contract"], "config/T2_runtime_contract_v0_6_0.json")
        Draft202012Validator(load("schemas/render_job.schema.json")).validate(historical)

    def test_workflow_never_overwrites_release_or_publishes_source_audio(self) -> None:
        workflow = (ROOT / ".github/workflows/server-render-unified.yml").read_text(encoding="utf-8")
        self.assertIn("--music D", workflow)
        self.assertIn("T2_RENDER_RESULT_V0_7_0.json", workflow)
        self.assertIn("VIDEO_T2_COMPLET_VOIX_AFROFIRE_A_VALIDER.mp4", workflow)
        self.assertIn("gh release view", workflow)
        self.assertNotIn("gh release delete", workflow)
        self.assertIn("assert audio == []", workflow)
        worker = (ROOT / "cloudflare/src/index.ts").read_text(encoding="utf-8")
        self.assertIn("inputs.music_source_sha256 !== expectedMusic.source_sha256", worker)
        self.assertIn("output.uri !== expectedOutput.uri", worker)


if __name__ == "__main__":
    unittest.main()
