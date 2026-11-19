from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_render_job import build_job


class T2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/T2_avant_apres_template_v0_1_0.json").read_text())
        cls.guide = json.loads((ROOT / "capture-guide/consignes_T2.json").read_text())
        cls.questions = json.loads((ROOT / "form/questions_T2.json").read_text())
        cls.answers = json.loads((ROOT / "demo/reponses_demo.json").read_text())
        cls.job = json.loads((ROOT / "demo/input_demo.json").read_text())
        cls.schema = json.loads((ROOT / "schemas/render_job.schema.json").read_text())

    def test_four_scenes(self):
        self.assertEqual([item["seconds"] for item in self.config["scenes"]], [6, 8, 7, 9])
        self.assertEqual(sum(item["seconds"] for item in self.config["scenes"]), 30)

    def test_twelve_screens(self):
        self.assertEqual(self.config["stable_screen_count"], 12)
        self.assertEqual(len(self.config["scenes"]) * len(self.config["capture_states"]), 12)

    def test_six_transitions(self):
        events = self.config["transition_budget"]["events"]
        self.assertEqual(len(events), 6)
        for reference in (1, 2, 3):
            self.assertEqual([item["reference"] for item in events].count(reference), 2)

    def test_questions_use_t1_merchant_payload_mechanism(self):
        expected = ["nom", "produit", "prix", "whatsapp", "quartier", "accroche"]
        self.assertEqual([item["id"] for item in self.questions["fields"]], expected)
        self.assertEqual(
            [item["json_target"] for item in self.questions["fields"]],
            [f"merchant_payload.{key}" for key in expected],
        )
        self.assertEqual(
            [item["required"] for item in self.questions["fields"]],
            [True, True, True, True, True, False],
        )

    def test_answers_build_the_canonical_render_job(self):
        self.assertEqual(build_job(self.answers), self.job)
        self.assertEqual(self.job["merchant_payload"], self.answers)
        Draft202012Validator(self.schema).validate(self.job)

    def test_captures_drive_four_exact_scene_durations(self):
        self.assertEqual(
            [self.job["captures"][slot]["duration_ms"] for slot in ("S1", "S2", "S3", "S4")],
            [6000, 8000, 7000, 9000],
        )

    def test_current_stage_is_silent_and_without_text(self):
        self.assertFalse(self.job["render_audio"])
        self.assertEqual(self.job["audio_mode"], "silent_no_audio_stream")
        self.assertFalse(self.job["render_business_text"])
        self.assertEqual(self.job["render_stage"], "silent_transition_validation")
        source = (ROOT / "engine/render_silent.py").read_text()
        transitions = (ROOT / "engine/transitions.py").read_text()
        for forbidden in ("cv2.putText", "ImageDraw", "draw.text"):
            self.assertNotIn(forbidden, source)
            self.assertNotIn(forbidden, transitions)

    def test_language_and_voice_capture_rules(self):
        self.assertIn("fon, yoruba, français, anglais", self.guide["mention_langues_commune"])
        self.assertFalse(self.guide["audio"]["parole_obligatoire"])
        self.assertTrue(self.guide["audio"]["conserver_voix_capturee"])
        self.assertFalse(self.guide["audio"]["sous_titres_automatiques"])

    def test_ui_manifest(self):
        manifest = json.loads((ROOT / "ui-screens/manifest.json").read_text())
        self.assertEqual(manifest["stable_screen_count"], 12)
        self.assertEqual(len(manifest["screens"]), 12)


if __name__ == "__main__":
    unittest.main()
