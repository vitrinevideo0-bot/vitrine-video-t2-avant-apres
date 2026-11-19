"""T2 complete-plan adapter, modelled on T1 without changing T2's domain.

The adapter enriches the existing Avant / Après RenderJob. It never rewrites
merchant_payload, captures, scene timing, text motion, the selected B music, or
the four registered voice files.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIX_CONFIG = ROOT / "config/T2_complete_voice_mix_v0_5_0.json"
SHORTLIST = ROOT / "music/T2_music_shortlist_v0_4_0.json"
SOURCE_LOCK = ROOT / "config/T2_music_source_lock_v0_4_0.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_music_candidate(
    shortlist: dict[str, Any],
    source_lock: dict[str, Any],
    *,
    render_job_id: str,
    requested_candidate_id: str = "B",
    previous_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Select one of the unchanged T2 candidates deterministically.

    The current approved exemplar asks explicitly for B. ``auto`` exists for the
    future control plane and follows T1's deterministic no-immediate-repeat
    mechanic without making any candidate the template default.
    """
    candidates = shortlist.get("candidates", [])
    if [item.get("id") for item in candidates] != ["A", "B", "C", "D"]:
        raise ValueError("La présélection T2 A/B/C/D n'est pas intacte.")
    locks = {item["id"]: item for item in source_lock.get("candidates", [])}
    if set(locks) != {"A", "B", "C", "D"}:
        raise ValueError("Le verrou musical doit couvrir exactement A/B/C/D.")
    by_id = {item["id"]: item for item in candidates}
    if previous_candidate_id is not None and previous_candidate_id not in by_id:
        raise ValueError(f"Candidat précédent inconnu : {previous_candidate_id}")
    if requested_candidate_id != "auto":
        if requested_candidate_id not in by_id:
            raise ValueError(f"Candidat musical inconnu : {requested_candidate_id}")
        selected = by_id[requested_candidate_id]
        mode = "explicit_user_choice"
    else:
        if not render_job_id:
            raise ValueError("render_job_id est obligatoire pour la sélection déterministe.")
        eligible = [item for item in candidates if item["id"] != previous_candidate_id]
        value = int.from_bytes(hashlib.sha256(render_job_id.encode("utf-8")).digest()[:8], "big")
        selected = eligible[value % len(eligible)]
        mode = "deterministic_no_immediate_repeat"
    if mode == "deterministic_no_immediate_repeat" and selected["id"] == previous_candidate_id:
        raise ValueError("La sélection automatique ne doit jamais répéter immédiatement la musique précédente.")
    return {
        **copy.deepcopy(selected),
        "source_sha256": locks[selected["id"]]["sha256"],
        "source_bytes": locks[selected["id"]]["bytes"],
        "selection_mode": mode,
        "requested_candidate_id": requested_candidate_id,
        "previous_candidate_id": previous_candidate_id,
    }


def attach_music_track(
    job: dict[str, Any],
    *,
    requested_candidate_id: str = "B",
    previous_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Attach the selected existing T2 music to the same RenderJob."""
    config = load_json(MIX_CONFIG)
    selected = select_music_candidate(
        load_json(SHORTLIST),
        load_json(SOURCE_LOCK),
        render_job_id=job["job_id"],
        requested_candidate_id=requested_candidate_id,
        previous_candidate_id=previous_candidate_id,
    )
    # The production exemplar remains B exactly as selected by the user.
    if selected["id"] != config["music_selection"]["candidate_id"]:
        raise ValueError("Le mix de production actuel est verrouillé sur le choix utilisateur B.")
    config_selection = config["music_selection"]
    for key in ("source_page", "source_audio_url", "source_sha256", "content_id_status"):
        if selected[key] != config_selection[key]:
            raise ValueError(f"La source musicale B diverge du contrat : {key}")
    job.setdefault("audio_plan", {})["music"] = {
        "selection_mode": selected["selection_mode"],
        "requested_candidate_id": selected["requested_candidate_id"],
        "selected_candidate_id": selected["id"],
        "previous_candidate_id": selected["previous_candidate_id"],
        "candidate_count": 4,
        "source_page": selected["source_page"],
        "source_audio_url": selected["source_audio_url"],
        "source_sha256": selected["source_sha256"],
        "content_id_status": selected["content_id_status"],
        "template_default_selection": False,
        "source_audio_publish": False,
    }
    return job


def attach_voice_track(job: dict[str, Any], *, mode: str = "registered_voice_clips") -> dict[str, Any]:
    """Attach registered clips and the explicit captured-audio strategy."""
    allowed = {"registered_voice_clips", "captured_scene_audio", "captured_or_registered_fallback"}
    if mode not in allowed:
        raise ValueError(f"Mode voix inconnu : {mode}")
    config = load_json(MIX_CONFIG)
    voice = config["voice"]
    fallback = {
        "registered_voice_clips": "registered_clips_are_explicitly_selected_for_this_exemplar",
        "captured_scene_audio": "no_fallback",
        "captured_or_registered_fallback": "registered_clips_when_capture_has_no_usable_speech",
    }[mode]
    if mode == "captured_scene_audio" and not all(job["captures"][slot]["has_audio"] for slot in ("S1", "S2", "S3", "S4")):
        raise ValueError("Le mode captured_scene_audio exige quatre prises audio acceptées.")
    job.setdefault("audio_plan", {})["voice"] = {
        "mode": mode,
        "fallback_policy": fallback,
        "source_speed": voice["source_speed"],
        "audio_time_map": voice["audio_time_map"],
        "automatic_subtitles": voice["automatic_subtitles"],
        "clips": copy.deepcopy(voice["clips"]),
    }
    job["audio_contract"]["voice_source_mode"] = mode
    return job


def attach_complete_audio(
    job: dict[str, Any],
    *,
    requested_candidate_id: str = "B",
    previous_candidate_id: str | None = None,
    voice_mode: str = "registered_voice_clips",
) -> dict[str, Any]:
    """Attach voice, music and ducking while proving visual data did not move."""
    before = {
        "merchant_payload": copy.deepcopy(job["merchant_payload"]),
        "captures": copy.deepcopy(job["captures"]),
        "text_motion_config": job["text_motion_config"],
    }
    config = load_json(MIX_CONFIG)
    job["audio_plan"] = {
        "config": str(MIX_CONFIG.relative_to(ROOT)),
        "config_sha256": digest(MIX_CONFIG),
    }
    attach_music_track(
        job,
        requested_candidate_id=requested_candidate_id,
        previous_candidate_id=previous_candidate_id,
    )
    attach_voice_track(job, mode=voice_mode)
    job["audio_plan"]["mix"] = copy.deepcopy(config["mix_contract"])
    job["audio_plan"]["publication"] = {
        "output_file": config["publication"]["output_file"],
        "publish_exactly_one_mp4": config["publication"]["publish_exactly_one_mp4"],
        "publish_standalone_audio": config["publication"]["publish_standalone_audio"],
    }
    job["audio_mode"] = "voice_music_ducking"
    job["render_audio"] = True
    job["audio_contract"].update(
        {
            "current_output_audio": True,
            "music_status": "selected_for_single_validation_exemplar",
            "future_mix": "active_voice_plus_selected_T2_music_with_ducking",
        }
    )
    after = {
        "merchant_payload": job["merchant_payload"],
        "captures": job["captures"],
        "text_motion_config": job["text_motion_config"],
    }
    if after != before:
        raise AssertionError("L'adaptateur audio a modifié les données ou le visuel T2.")
    return job
