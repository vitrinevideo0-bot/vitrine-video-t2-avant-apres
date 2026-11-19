from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_music_shortlist import validate_manifest


class T2MusicShortlistTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "music/T2_music_shortlist_v0_4_0.json"
        cls.manifest = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_manifest_contract_is_valid(self):
        validate_manifest(self.manifest)

    def test_exactly_four_distinct_candidates_are_declared(self):
        candidates = self.manifest["candidates"]
        self.assertEqual([item["id"] for item in candidates], ["A", "B", "C", "D"])
        self.assertEqual(len({item["source_page"] for item in candidates}), 4)
        self.assertEqual(len({item["output_file"] for item in candidates}), 4)

    def test_every_source_is_official_pixabay_and_license_is_recorded(self):
        self.assertEqual(
            self.manifest["provider"]["license_url"],
            "https://pixabay.com/service/license-summary/",
        )
        for item in self.manifest["candidates"]:
            self.assertTrue(item["source_page"].startswith("https://pixabay.com/music/"))
            self.assertTrue(item["source_audio_url"].startswith("https://cdn.pixabay.com/download/audio/"))
            self.assertIn(item["content_id_status"], {"registered", "not_displayed_on_source_page"})

    def test_source_audio_is_never_a_release_asset(self):
        contract = self.manifest["audition_contract"]
        self.assertFalse(contract["publish_source_audio"])
        self.assertTrue(contract["publish_derivative_video_only"])
        self.assertTrue(self.manifest["provider"]["standalone_redistribution_forbidden"])
        self.assertTrue(all(item["output_file"].endswith(".mp4") for item in self.manifest["candidates"]))

    def test_approved_visual_is_the_user_validated_v03(self):
        base = self.manifest["approved_visual_base"]
        self.assertEqual(base["release_tag"], "t2-avant-apres-v0.3.0-text-motion")
        self.assertEqual(
            base["sha256"],
            "67c447dae81241fc9ecc34ee9edfbf8c354a6ddf76e7fa465a62cdac59550ada",
        )
        self.assertEqual((base["width"], base["height"], base["fps"], base["frames"]), (720, 1280, 30, 900))
        self.assertEqual(base["audio_streams"], 0)

    def test_no_music_is_selected_before_user_vote(self):
        contract = self.manifest["audition_contract"]
        self.assertIsNone(contract["final_selection"])
        self.assertTrue(contract["selection_required_before_final_mix"])
        self.assertEqual(self.manifest["status"], "audition_only_no_selection")

    def test_future_voice_remains_at_one_times_and_ducks_music(self):
        mix = self.manifest["future_mix_contract"]
        self.assertTrue(mix["preserve_captured_voice"])
        self.assertEqual(mix["captured_voice_speed"], 1.0)
        self.assertEqual(mix["source_time_map"], "identity")
        self.assertEqual(mix["audio_time_map"], "identity")
        self.assertTrue(mix["music_ducking_when_speech_present"])
        self.assertFalse(mix["active_in_current_auditions"])

    def test_all_auditions_compare_the_same_thirty_seconds(self):
        audition = self.manifest["audition_contract"]
        self.assertEqual(audition["preview_duration_seconds"], 30.0)
        self.assertEqual(audition["visual_stream_policy"], "bitstream_copy_from_approved_v0_3")
        for item in self.manifest["candidates"]:
            self.assertEqual(item["preview_start_seconds"], 0.0)
            self.assertEqual(item["preview_duration_seconds"], 30.0)


if __name__ == "__main__":
    unittest.main()
