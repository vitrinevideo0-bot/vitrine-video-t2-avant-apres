from __future__ import annotations

import hashlib
import json
import sys
import unittest
import wave
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "audio/scripts"))

from mix_t2_voice_music_v0_5 import duck_envelope


class T2CompleteVoiceMixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_path = ROOT / "config/T2_complete_voice_mix_v0_5_0.json"
        cls.config = json.loads(cls.config_path.read_text(encoding="utf-8"))
        cls.schema = json.loads(
            (ROOT / "schemas/T2_complete_voice_mix.schema.json").read_text(encoding="utf-8")
        )
        cls.shortlist = json.loads(
            (ROOT / "music/T2_music_shortlist_v0_4_0.json").read_text(encoding="utf-8")
        )
        cls.guide = json.loads(
            (ROOT / "capture-guide/consignes_T2.json").read_text(encoding="utf-8")
        )

    def test_contract_matches_strict_schema(self):
        Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        ).validate(self.config)

    def test_user_choice_b_is_locked_only_for_this_single_exemplar(self):
        selection = self.config["music_selection"]
        shortlist_b = next(item for item in self.shortlist["candidates"] if item["id"] == "B")
        self.assertEqual(selection["candidate_id"], "B")
        self.assertEqual(selection["title"], shortlist_b["title"])
        self.assertEqual(selection["artist"], shortlist_b["artist"])
        self.assertEqual(selection["source_page"], shortlist_b["source_page"])
        self.assertEqual(selection["source_audio_url"], shortlist_b["source_audio_url"])
        self.assertTrue(selection["user_selected_for_this_exemplar"])
        self.assertEqual(selection["scope"], "this_single_validation_exemplar_only")
        self.assertFalse(selection["template_default_selection"])
        self.assertFalse(selection["source_audio_publish"])
        self.assertEqual(selection["content_id_status"], "registered")

    def test_four_voice_texts_are_the_four_capture_examples(self):
        expected = [scene["exemple_facultatif"] for scene in self.guide["scenes"]]
        clips = self.config["voice"]["clips"]
        self.assertEqual([item["text"] for item in clips], expected)
        self.assertEqual([item["scene"] for item in clips], [1, 2, 3, 4])
        self.assertEqual(
            [item["scene_window_s"] for item in clips],
            [[0.0, 6.0], [6.0, 14.0], [14.0, 21.0], [21.0, 30.0]],
        )
        self.assertEqual([item["start_s"] for item in clips], [1.2, 6.8, 14.7, 21.8])
        self.assertEqual(self.config["voice"]["source_speed"], 1.0)
        self.assertEqual(self.config["voice"]["audio_time_map"], "identity")
        self.assertTrue(self.config["voice"]["same_identity_for_all_scenes"])
        self.assertFalse(self.config["voice"]["automatic_subtitles"])

    def test_registered_voice_sources_are_deterministic_and_fit_scenes(self):
        for item in self.config["voice"]["clips"]:
            path = ROOT / item["source"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["source_sha256"])
            with wave.open(str(path), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getsampwidth(), 2)
                self.assertEqual(stream.getframerate(), 44_100)
                duration = stream.getnframes() / stream.getframerate()
            self.assertAlmostEqual(duration, item["source_duration_s"], places=5)
            self.assertLessEqual(item["start_s"] + duration, item["scene_window_s"][1])

    def test_mix_is_the_exact_t1_level_and_ducking_contract(self):
        mix = self.config["mix_contract"]
        self.assertEqual(mix["music_open_gain_db"], -3.0)
        self.assertEqual(mix["music_under_voice_gain_db"], -10.0)
        self.assertEqual(mix["duck_depth_db"], -7.0)
        self.assertEqual(mix["duck_attack_ms"], 120)
        self.assertEqual(mix["duck_release_ms"], 450)
        self.assertEqual(mix["duck_attack_curve"], "linear_db")
        self.assertEqual(mix["duck_release_curve"], "linear_db")
        self.assertEqual(mix["voice_gain_db"], 0.0)
        self.assertEqual(mix["master_target_lufs"], -16.0)
        self.assertEqual(mix["master_true_peak_dbtp_max"], -2.0)
        self.assertEqual(mix["sfx"], "none")

    def test_duck_envelope_reaches_exact_open_and_under_voice_levels(self):
        spans = [(1.2, 5.46), (6.8, 10.42), (14.7, 17.89), (21.8, 27.0)]
        envelope = duck_envelope(spans, 0.120, 0.450)
        gains = -3.0 + (-10.0 - -3.0) * envelope
        self.assertAlmostEqual(float(gains.max()), -3.0, places=6)
        self.assertAlmostEqual(float(gains.min()), -10.0, places=6)
        self.assertAlmostEqual(float(gains[int(1.2 * 48_000)]), -10.0, places=6)
        self.assertGreater(float(gains[int(1.10 * 48_000)]), -10.0)
        self.assertLess(float(gains[int(1.10 * 48_000)]), -3.0)
        self.assertGreater(float(gains[int(5.70 * 48_000)]), -10.0)
        self.assertLess(float(gains[int(5.70 * 48_000)]), -3.0)

    def test_t1_audio_reference_is_hash_locked_and_read_only(self):
        lock = json.loads(
            (ROOT / "baseline/T1_AUDIO_REFERENCE.lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(lock["commit"], "c656510ab81d31d413dc4dfd74b42671532cd978")
        self.assertEqual(lock["mode"], "read_only")
        self.assertEqual(
            set(lock["files"]),
            {
                "config/T1_special_menu_voice_mix_v1_0_0.json",
                "schemas/T1_voice_mix.schema.json",
                "audio/scripts/mix_t1_voice_music_v1.py",
                ".github/workflows/render_t1_complete_voice.yml",
            },
        )
        self.assertEqual(self.config["reference_t1"]["commit"], lock["commit"])
        self.assertEqual(
            self.config["reference_t1"]["mode"],
            "read_only_exact_audio_architecture_reference",
        )

    def test_approved_visual_v03_is_immutable(self):
        visual = self.config["visual_source"]
        shortlist_visual = self.shortlist["approved_visual_base"]
        self.assertEqual(visual["release_tag"], shortlist_visual["release_tag"])
        self.assertEqual(visual["asset_name"], shortlist_visual["asset_name"])
        self.assertEqual(visual["sha256"], shortlist_visual["sha256"])
        self.assertEqual(
            visual["video_stream_sha256"],
            "2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5",
        )
        self.assertEqual(visual["policy"], "bitstream_copy_no_visual_reencode")

    def test_publication_contract_has_one_mp4_and_no_standalone_audio(self):
        publication = self.config["publication"]
        self.assertTrue(publication["publish_exactly_one_mp4"])
        self.assertFalse(publication["publish_standalone_audio"])
        self.assertEqual(self.config["quality_gates"]["exact_output_video_count"], 1)
        self.assertTrue(publication["output_file"].endswith(".mp4"))
        self.assertEqual(
            publication["output_file"],
            "VIDEO_T2_COMPLET_VOIX_MUSIQUE_B_A_VALIDER.mp4",
        )

    def test_mixer_is_server_only_and_copies_the_video_stream(self):
        source = (ROOT / "audio/scripts/mix_t2_voice_music_v0_5.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("GITHUB_ACTIONS") != "true"', source)
        self.assertIn('"-c:v",\n                "copy"', source)
        self.assertIn("duck_envelope", source)
        self.assertIn("frame_speech_metrics", source)
        self.assertIn("master_audio", source)
        self.assertNotIn("--allow-local", source)

    def test_workflow_publishes_exactly_one_mp4_and_reports(self):
        workflow = (
            ROOT / ".github/workflows/server-render-complete-voice.yml"
        ).read_text(encoding="utf-8")
        output = self.config["publication"]["output_file"]
        self.assertIn(output, workflow)
        self.assertIn("verify_t1_audio_reference.py", workflow)
        self.assertIn("validate_complete_voice_mix.py", workflow)
        self.assertIn("sha256sum", workflow)
        self.assertNotIn("*.mp4", workflow)
        self.assertNotIn("*.mp3", workflow)
        self.assertNotIn("*.wav", workflow)


if __name__ == "__main__":
    unittest.main()
