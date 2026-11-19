"""Contrat de continuité voix T2, sans effectuer le mixage avant validation."""
from __future__ import annotations

from typing import Any

SCENE_STARTS_MS = {"S1": 0, "S2": 6000, "S3": 14000, "S4": 21000}
EXPECTED_DURATIONS_MS = {"S1": 6000, "S2": 8000, "S3": 7000, "S4": 9000}


def build_voice_timeline(job: dict[str, Any]) -> dict[str, Any]:
    contract = job["audio_contract"]
    if contract["preserve_captured_voice"] is not True:
        raise ValueError("La voix capturée doit rester préservée.")
    if contract["source_speed"] != 1.0:
        raise ValueError("La voix capturée ne doit jamais être accélérée ou ralentie.")
    if contract["audio_time_map"] != "identity":
        raise ValueError("Le remappage audio doit rester identique à la caméra.")
    if contract["automatic_subtitles"] is not False:
        raise ValueError("Les sous-titres automatiques sont interdits.")

    segments = []
    for scene in ("S1", "S2", "S3", "S4"):
        capture = job["captures"][scene]
        duration_ms = int(capture["duration_ms"])
        if duration_ms != EXPECTED_DURATIONS_MS[scene]:
            raise ValueError(f"Durée voix/caméra invalide pour {scene}")
        start_ms = SCENE_STARTS_MS[scene]
        segments.append(
            {
                "scene": scene,
                "capture_uri": capture["uri"],
                "timeline_start_ms": start_ms,
                "timeline_end_ms": start_ms + duration_ms,
                "duration_ms": duration_ms,
                "has_audio": bool(capture["has_audio"]),
                "include_captured_voice_when_present": True,
                "source_speed": 1.0,
                "source_time_map": "identity",
                "audio_time_map": "identity",
            }
        )
    return {
        "segments": segments,
        "scene_boundaries_ms": [0, 6000, 14000, 21000, 30000],
        "automatic_subtitles": False,
        "current_preview_output_audio": bool(contract["current_output_audio"]),
        "future_mix": contract["future_mix"],
        "music_status": contract["music_status"],
    }
