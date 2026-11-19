import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class T2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "config/T2_avant_apres_template_v0_1_0.json").read_text())
        cls.guide = json.loads((ROOT / "capture-guide/consignes_T2.json").read_text())
        cls.job = json.loads((ROOT / "demo/input_demo.json").read_text())

    def test_exactly_four_scenes_and_thirty_seconds(self):
        self.assertEqual([x["seconds"] for x in self.cfg["scenes"]], [6, 8, 7, 9])
        self.assertEqual(sum(x["seconds"] for x in self.cfg["scenes"]), 30)

    def test_exactly_twelve_stable_screens(self):
        self.assertEqual(self.cfg["stable_screen_count"], 12)
        self.assertEqual(len(self.cfg["scenes"]) * len(self.cfg["capture_states"]), 12)
        self.assertTrue(self.cfg["countdown_is_transient"])

    def test_transition_balance(self):
        events = self.cfg["transition_budget"]["events"]
        self.assertEqual(len(events), 6)
        self.assertEqual([x["reference"] for x in events].count(1), 2)
        self.assertEqual([x["reference"] for x in events].count(2), 2)
        self.assertEqual([x["reference"] for x in events].count(3), 2)
        self.assertAlmostEqual(self.cfg["transition_budget"]["duration_each_seconds"] * 2, 0.84)

    def test_language_notice_and_examples(self):
        expected = "Tu peux parler pendant que tu filmes, dans la langue que tu veux : fon, yoruba, français, anglais ou une autre langue que tu maîtrises."
        self.assertEqual(self.guide["mention_langues_commune"], expected)
        self.assertEqual(len(self.guide["scenes"]), 4)
        self.assertTrue(all(x["exemple_facultatif"] for x in self.guide["scenes"]))

    def test_voice_optional_preserved_no_auto_subtitles(self):
        audio = self.guide["audio"]
        self.assertFalse(audio["parole_obligatoire"])
        self.assertTrue(audio["conserver_voix_capturee"])
        self.assertFalse(audio["sous_titres_automatiques"])

    def test_output_geometry(self):
        out = self.cfg["output"]
        self.assertEqual((out["width"], out["height"], out["fps"], out["frames"]), (720, 1280, 30, 900))

    def test_demo_price(self):
        rule = self.cfg["merchant_fields"]["properties"]["prix"]
        self.assertRegex(self.job["business"]["prix"], re.compile(rule["pattern"]))

    def test_ui_manifest_has_exactly_twelve_unique_screens(self):
        ui = json.loads((ROOT / "ui-screens/manifest.json").read_text())
        self.assertEqual(ui["stable_screen_count"], 12)
        self.assertEqual(len(ui["screens"]), 12)
        self.assertEqual(len({x["file"] for x in ui["screens"]}), 12)
        self.assertTrue(all(x["size"] == [720, 1280] for x in ui["screens"]))

    def test_render_manifest_is_exact(self):
        render = json.loads((ROOT / "proofs/render_manifest.json").read_text())
        observed = render["observed"]
        self.assertEqual((observed["width"], observed["height"]), (720, 1280))
        self.assertEqual(observed["frames"], 900)
        self.assertEqual(observed["fps"], 30.0)
        self.assertEqual(observed["duration_seconds"], 30.0)
        self.assertEqual(render["sha256"], "0688a821ed0072e2bbb42e46b6fc0b5486ce36d878c116f5d2b0656fbe42ea64")


if __name__ == "__main__":
    unittest.main()
