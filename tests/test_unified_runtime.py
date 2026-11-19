from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
AUDIO_SCRIPTS = ROOT / "audio/scripts"
if str(AUDIO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUDIO_SCRIPTS))

from mix_t2_voice_music_v0_5 import SR, captured_audio_qc
from tools.cloudflare_runtime import validate_api_base
from tools.render_complete_job import execute
from tools.verify_visual_pipeline import verify as verify_visual_pipeline


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class T2UnifiedRuntimeTest(unittest.TestCase):
    def test_all_pre_v06_tests_are_byte_identical(self) -> None:
        lock = load("baseline/T2_EXISTING_TESTS.lock.json")
        for relative, expected in lock["files"].items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_complete_job_is_schema_valid_and_preserves_visual_inputs(self) -> None:
        schema = load("schemas/render_job.schema.json")
        complete = load("demo/render_job_complete_demo.json")
        dynamic = load("demo/render_job_textes_demo.json")
        Draft202012Validator(schema).validate(complete)
        self.assertEqual(complete["schema_version"], "1.1.0")
        self.assertEqual(complete["render_stage"], "complete_voice_music_render")
        self.assertEqual(complete["merchant_payload"], dynamic["merchant_payload"])
        for slot in ("S1", "S2", "S3", "S4"):
            for key in ("uri", "duration_ms", "source_in_ms", "has_audio", "sha256"):
                self.assertEqual(complete["captures"][slot][key], dynamic["captures"][slot][key])
        self.assertEqual(complete["text_motion_config"], dynamic["text_motion_config"])
        self.assertEqual(complete["runtime_contract"], "config/T2_runtime_contract_v0_6_0.json")
        self.assertTrue(complete["visual_plan"]["rebuild_from_job"])
        self.assertTrue(complete["visual_plan"]["preserve_900_frames"])

    def test_complete_job_has_voice_music_ducking_and_one_output(self) -> None:
        job = load("demo/render_job_complete_demo.json")
        self.assertEqual(job["audio_plan"]["music"]["selected_candidate_id"], "B")
        self.assertFalse(job["audio_plan"]["music"]["template_default_selection"])
        self.assertFalse(job["audio_plan"]["music"]["source_audio_publish"])
        self.assertEqual(job["audio_plan"]["voice"]["source_speed"], 1.0)
        self.assertEqual(len(job["audio_plan"]["voice"]["clips"]), 4)
        self.assertEqual(job["audio_plan"]["mix"]["music_open_gain_db"], -3.0)
        self.assertEqual(job["audio_plan"]["mix"]["music_under_voice_gain_db"], -10.0)
        self.assertTrue(job["audio_plan"]["publication"]["publish_exactly_one_mp4"])
        self.assertFalse(job["audio_plan"]["publication"]["publish_standalone_audio"])

    def test_result_and_error_contracts_are_strict_and_fixtures_pass(self) -> None:
        pairs = (
            ("schemas/render_result.schema.json", "fixtures/t2-avant-apres/render_result.valid.json"),
            ("schemas/render_error.schema.json", "fixtures/t2-avant-apres/render_error.unsupported_media.json"),
        )
        for schema_path, fixture_path in pairs:
            schema = load(schema_path)
            self.assertFalse(schema["additionalProperties"])
            Draft202012Validator(schema).validate(load(fixture_path))

    def test_capture_flow_is_executable_and_consumed_by_the_app(self) -> None:
        flow = load("config/T2_capture_flow_v1_0_0.json")
        screens = flow["screens"]
        self.assertEqual(flow["counts"], {"scenes": 4, "states_per_scene": 3, "stable_capture_screens": 12})
        self.assertEqual(len(screens), 12)
        self.assertEqual([item["ordinal"] for item in screens], list(range(1, 13)))
        self.assertEqual([item["state"] for item in screens], ["A_GUIDE", "B_RECORDING", "C_REVIEW"] * 4)
        self.assertEqual([item["capture_duration_ms"] for item in screens[::3]], [6000, 8000, 7000, 9000])
        self.assertFalse(flow["transient_states"][0]["counted_in_12_stable_screens"])
        app = (ROOT / "cloudflare/public/app.js").read_text(encoding="utf-8")
        self.assertIn("/v1/contracts/capture-flow", app)
        self.assertIn("MediaRecorder", app)
        self.assertIn("state.flow.transient_states[0].sequence", app)
        self.assertIn("await sleep(duration)", app)
        self.assertIn("video.muted = false", app)
        self.assertIn("'x-has-audio': String(state.capture.hasAudio)", app)
        self.assertNotIn("subtitle", app.lower())

    def test_form_contract_is_consumed_without_changing_six_business_fields(self) -> None:
        form = load("form/questions_T2.json")
        self.assertEqual([field["id"] for field in form["fields"]], ["nom", "produit", "prix", "whatsapp", "quartier", "accroche"])
        app = (ROOT / "cloudflare/public/app.js").read_text(encoding="utf-8")
        worker = (ROOT / "cloudflare/src/index.ts").read_text(encoding="utf-8")
        self.assertIn("/v1/contracts/form", app)
        self.assertIn("FORM_CONTRACT.fields", worker)
        self.assertIn("merchant_payload: state.merchant", app)

    def test_cloudflare_is_control_plane_only_and_github_is_render_plane(self) -> None:
        worker = (ROOT / "cloudflare/src/index.ts").read_text(encoding="utf-8")
        self.assertIn('event_type: "t2_render_job"', worker)
        self.assertIn("T2_MEDIA: R2Bucket", worker)
        self.assertIn("CLIENT_API_TOKEN", worker)
        self.assertIn("CALLBACK_TOKEN", worker)
        self.assertIn("buildRenderJob(state)", worker)
        for forbidden in ("ffmpeg", "opencv", "render_text_motion.py", "mix_t2_voice_music_v0_5.py"):
            self.assertNotIn(forbidden, worker.lower())
        workflow = (ROOT / ".github/workflows/server-render-unified.yml").read_text(encoding="utf-8")
        self.assertIn("repository_dispatch", workflow)
        self.assertIn("tools/render_complete_job.py", workflow)
        self.assertIn("tools/cloudflare_runtime.py fetch", workflow)
        self.assertIn("T2_RENDER_RESULT_V0_6_0.json", workflow)

    def test_browser_webm_and_mobile_mp4_are_accepted_additively(self) -> None:
        schema = load("schemas/render_job.schema.json")
        mime = schema["$defs"]["captureBase"]["properties"]["mime_type"]["enum"]
        self.assertEqual(mime, ["video/mp4", "video/webm", "video/quicktime"])
        worker = (ROOT / "cloudflare/src/index.ts").read_text(encoding="utf-8")
        self.assertIn('"video/webm"', worker)
        self.assertIn('"video/quicktime"', worker)

    def test_cloudflare_generated_contracts_are_exact_canonical_snapshots(self) -> None:
        targets = (
            ("cloudflare/src/render_job_template.ts", "demo/render_job_complete_demo.json"),
            ("cloudflare/src/capture_flow_contract.ts", "config/T2_capture_flow_v1_0_0.json"),
            ("cloudflare/src/form_contract.ts", "form/questions_T2.json"),
        )
        for ts_path, json_path in targets:
            text = (ROOT / ts_path).read_text(encoding="utf-8")
            encoded = json.dumps(load(json_path), ensure_ascii=False, indent=2)
            self.assertIn(encoded, text)
            self.assertTrue(text.rstrip().endswith("as const;"))

    def test_visual_pipeline_lock_preserves_v03_mechanics(self) -> None:
        lock = verify_visual_pipeline()
        self.assertEqual(lock["approved_reference"]["frames"], 900)
        self.assertEqual(lock["approved_reference"]["video_stream_sha256"], "2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5")

    def test_captured_voice_usability_gate_falls_back_on_silence(self) -> None:
        silence = np.zeros(SR, dtype=np.float64)
        self.assertFalse(captured_audio_qc(silence)["usable"])
        seconds = 1.0
        time = np.arange(int(SR * seconds)) / SR
        speech_like = 0.08 * np.sin(2 * np.pi * 190 * time)
        self.assertTrue(captured_audio_qc(speech_like)["usable"])

    def test_production_orchestrator_refuses_local_render(self) -> None:
        previous = os.environ.pop("GITHUB_ACTIONS", None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(RuntimeError, "interdit hors GitHub Actions"):
                    execute(ROOT / "demo/render_job_complete_demo.json", Path(directory))
        finally:
            if previous is not None:
                os.environ["GITHUB_ACTIONS"] = previous

    def test_cloudflare_callback_origin_is_https_and_pinned(self) -> None:
        previous = os.environ.get("CF_EXPECTED_API_BASE")
        os.environ["CF_EXPECTED_API_BASE"] = "https://t2.example.workers.dev"
        try:
            self.assertEqual(validate_api_base("https://t2.example.workers.dev/"), "https://t2.example.workers.dev")
            with self.assertRaises(ValueError):
                validate_api_base("http://t2.example.workers.dev")
            with self.assertRaises(ValueError):
                validate_api_base("https://evil.example")
            with self.assertRaises(ValueError):
                validate_api_base("https://t2.example.workers.dev/path")
        finally:
            if previous is None:
                os.environ.pop("CF_EXPECTED_API_BASE", None)
            else:
                os.environ["CF_EXPECTED_API_BASE"] = previous

    def test_cloudflare_runtime_never_publishes_audio_sources(self) -> None:
        workflow = (ROOT / ".github/workflows/server-render-unified.yml").read_text(encoding="utf-8")
        self.assertIn("Enforce one MP4 and no standalone audio", workflow)
        self.assertIn("assert audio == []", workflow)
        runtime = load("config/T2_runtime_contract_v0_6_0.json")
        self.assertFalse(runtime["audio_handoff"]["source_audio_publish"])
        self.assertTrue(runtime["server_handoff"]["cloudflare_never_renders_video"])


if __name__ == "__main__":
    unittest.main()
