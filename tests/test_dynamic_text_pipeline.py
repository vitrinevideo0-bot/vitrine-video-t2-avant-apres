from __future__ import annotations

import hashlib
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_render_job import build_job
from engine.audio_contract import build_voice_timeline
from engine.text_motion import render_text_motion, validate_text_config


class T2DynamicTextPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = json.loads((ROOT / "config/T2_runtime_contract_v0_3_0.json").read_text())
        cls.text_config = json.loads((ROOT / "config/T2_text_motion_v0_3_0.json").read_text())
        cls.answers = json.loads((ROOT / "demo/reponses_textes_demo.json").read_text())
        cls.job = json.loads((ROOT / "demo/render_job_textes_demo.json").read_text())
        cls.schema = json.loads((ROOT / "schemas/render_job.schema.json").read_text())
        cls.base = np.full((1280, 720, 3), (92, 118, 146), dtype=np.uint8)

    def test_reference_is_locked_t1_without_write_back(self):
        reference = self.runtime["reference"]
        self.assertEqual(reference["commit"], "c656510ab81d31d413dc4dfd74b42671532cd978")
        self.assertEqual(reference["mode"], "read_only_architecture_reference")

    def test_form_capture_render_order_is_explicit(self):
        self.assertEqual(
            [item["id"] for item in self.runtime["runtime_order"]],
            [
                "MERCHANT_INPUT",
                "GUIDED_CAPTURE",
                "DETERMINISTIC_VISUAL_RENDER",
                "VOICE_AND_MUSIC_ASSEMBLY_AFTER_APPROVAL",
            ],
        )
        self.assertEqual(self.runtime["runtime_order"][1]["stable_screens"], 12)

    def test_every_merchant_field_has_scene_graphic_targets(self):
        expected = ["nom", "produit", "prix", "whatsapp", "quartier", "accroche"]
        bindings = self.runtime["merchant_bindings"]
        self.assertEqual([item["source"] for item in bindings], [f"merchant_payload.{x}" for x in expected])
        self.assertTrue(all(item["targets"] for item in bindings))
        declared_blocks = {item["id"] for item in self.text_config["graphics"]}
        self.assertTrue(
            all(target in declared_blocks for item in bindings for target in item["targets"])
        )

    def test_four_camera_captures_share_exact_video_and_audio_clock(self):
        bindings = self.runtime["capture_bindings"]
        self.assertEqual([item["duration_ms"] for item in bindings], [6000, 8000, 7000, 9000])
        self.assertEqual([item["timeline_start_ms"] for item in bindings], [0, 6000, 14000, 21000])
        self.assertTrue(all(item["source_time_map"] == "identity" for item in bindings))
        self.assertTrue(all(item["audio_time_map"] == "identity" for item in bindings))

    def test_answers_and_captures_build_the_text_render_job(self):
        rebuilt = build_job(self.answers, stage="dynamic_text_validation")
        self.assertEqual(rebuilt, self.job)
        self.assertEqual(self.job["merchant_payload"], self.answers)
        self.assertTrue(self.job["render_business_text"])
        self.assertFalse(self.job["render_audio"])
        Draft202012Validator(self.schema).validate(self.job)

    def test_requested_calligraphic_font_is_bundled_and_locked(self):
        validate_text_config(self.text_config)
        signature = self.text_config["fonts"]["signature"]
        self.assertEqual(signature["family"], "Pinyon Script")
        self.assertEqual(signature["license"], "SIL OFL 1.1")
        path = ROOT / signature["file"]
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), signature["sha256"])

    def test_each_scene_has_a_dynamic_text_block(self):
        blocks = self.text_config["graphics"]
        self.assertEqual([item["scene"] for item in blocks], ["S1", "S2", "S3", "S4"])
        for block in blocks:
            self.assertLess(block["start_f"], block["reveal_end_f"])
            self.assertLess(block["reveal_end_f"], block["end_f_exclusive"])
            self.assertTrue(block["fields"])
        self.assertEqual(blocks[-1]["hold_through_frame"], 899)

    def test_real_fields_change_real_pixels_in_their_scenes(self):
        checks = [
            (72, "T2_G01_IDENTITY", "nom", "Autre Restaurant"),
            (270, "T2_G02_OFFER", "prix", "3 000"),
            (525, "T2_G03_REVEAL", "accroche", "Servi avec passion"),
            (780, "T2_G04_FINAL", "whatsapp", "01 11 22 33 44"),
        ]
        for frame, expected_id, field, replacement in checks:
            original, active = render_text_motion(
                self.base.copy(), frame, self.answers, self.text_config
            )
            modified_fields = deepcopy(self.answers)
            modified_fields[field] = replacement
            modified, active_modified = render_text_motion(
                self.base.copy(), frame, modified_fields, self.text_config
            )
            self.assertIn(expected_id, active)
            self.assertEqual(active, active_modified)
            self.assertGreater(np.count_nonzero(np.any(original != self.base, axis=2)), 1000)
            self.assertGreater(np.count_nonzero(np.any(original != modified, axis=2)), 100)

    def test_voice_timeline_is_ready_for_camera_speech_without_mixing_it_yet(self):
        job = deepcopy(self.job)
        job["captures"]["S1"]["has_audio"] = True
        job["captures"]["S3"]["has_audio"] = True
        timeline = build_voice_timeline(job)
        self.assertEqual(timeline["scene_boundaries_ms"], [0, 6000, 14000, 21000, 30000])
        self.assertEqual([item["source_speed"] for item in timeline["segments"]], [1.0] * 4)
        self.assertEqual([item["has_audio"] for item in timeline["segments"]], [True, False, True, False])
        self.assertFalse(timeline["automatic_subtitles"])
        self.assertFalse(timeline["current_preview_output_audio"])

    def test_no_unrelated_fixed_demo_copy_is_injected(self):
        source = (ROOT / "engine/text_motion.py").read_text(encoding="utf-8")
        for forbidden in ("AVANT", "LA TRANSFORMATION", "LA RÉVÉLATION", "APRÈS", "COMMANDER MAINTENANT"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
