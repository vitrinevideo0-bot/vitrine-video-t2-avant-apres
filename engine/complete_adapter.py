"""T2 complete-plan adapter, modelled on T1 without changing T2's domain.

The adapter enriches the existing Avant / Après RenderJob. It never rewrites
merchant_payload, captures, scene timing, text motion, or the four registered
voice files. Historical B and current user-approved D contracts stay explicit.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIX_CONFIGS = {
    "A": ROOT / "config/T2_complete_voice_mix_v1_0_0_A.json",
    "B": ROOT / "config/T2_complete_voice_mix_v1_0_0_B.json",
    "C": ROOT / "config/T2_complete_voice_mix_v1_0_0_C.json",
    "D": ROOT / "config/T2_complete_voice_mix_v1_0_0_D.json",
}
MUSIC_POOL = ROOT / "config/T2_music_pool_v1_0_0.json"
HISTORICAL_MIX_CONFIGS = {
    "B": ROOT / "config/T2_complete_voice_mix_v0_5_0.json",
    "D": ROOT / "config/T2_complete_voice_mix_v0_7_0.json",
}
HISTORICAL_SHORTLIST = ROOT / "music/T2_music_shortlist_v0_4_0.json"
HISTORICAL_SOURCE_LOCK = ROOT / "config/T2_music_source_lock_v0_4_0.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_music_candidate(
    pool: dict[str, Any],
    *,
    render_job_id: str,
    requested_candidate_id: str = "auto",
    previous_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Select one owner-approved T2 track in the strict A → B → C → D cycle."""
    candidates = pool.get("candidates", [])
    contract = pool.get("selection_contract", {})
    if [item.get("id") for item in candidates] != ["A", "B", "C", "D"]:
        raise ValueError("Le pool T2 doit contenir exactement A/B/C/D dans cet ordre.")
    if contract.get("allowed_candidate_ids") != ["A", "B", "C", "D"]:
        raise ValueError("Le contrat de sélection T2 ne couvre pas exactement A/B/C/D.")
    if (
        contract.get("automatic_algorithm") != "strict approved order A→B→C→D→A from last successful music"
        or contract.get("explicit_selection_policy") != "exact_successor_only"
        or contract.get("no_immediate_repeat") is not True
        or contract.get("state_update_policy") != "after_success_only"
        or contract.get("idempotency_ledger_key") != "successful_render_jobs"
        or contract.get("failed_render_state_policy") != "unchanged"
        or contract.get("first_render_pool") != "candidate_A_only"
        or contract.get("subsequent_pool_size") != 1
    ):
        raise ValueError("Le pool T2 doit imposer le successeur exact et avancer seulement après succès.")
    if any(
        not item.get("owner_approved")
        or not item.get("production_eligible")
        or item.get("content_id_status") != "not_displayed_on_source_page"
        or item.get("contains_voice") is not False
        or item.get("duration_s") != 30.0
        for item in candidates
    ):
        raise ValueError("Les quatre instrumentales T2 doivent être approuvées, propres et éligibles à la production.")
    for item in candidates:
        program = ROOT / item["file"]
        if not program.is_file() or digest(program) != item["sha256"] or program.stat().st_size != item["bytes"]:
            raise ValueError(f"L’instrumentale T2 {item['id']} ne correspond pas à son verrou local.")
    by_id = {item["id"]: item for item in candidates}
    if previous_candidate_id is not None and previous_candidate_id not in by_id:
        raise ValueError(f"Candidat précédent inconnu : {previous_candidate_id}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", render_job_id):
        raise ValueError("render_job_id est obligatoire et doit être valide pour la sélection cyclique.")
    previous_index = -1 if previous_candidate_id is None else contract["allowed_candidate_ids"].index(previous_candidate_id)
    expected = candidates[(previous_index + 1) % len(candidates)]
    if requested_candidate_id != "auto":
        if requested_candidate_id not in by_id:
            raise ValueError(f"Candidat musical inconnu : {requested_candidate_id}")
        if requested_candidate_id != expected["id"]:
            raise ValueError(
                f"Le cycle T2 strict attend {expected['id']} ; {requested_candidate_id} ne peut pas le contourner."
            )
        selected = expected
        mode = "explicit_user_choice"
    else:
        selected = expected
        mode = "strict_success_cycle"
    return {
        **copy.deepcopy(selected),
        "selection_mode": mode,
        "requested_candidate_id": requested_candidate_id,
        "previous_candidate_id": previous_candidate_id,
    }


MUSIC_STATE_SCHEMA_VERSION = "1.0.0"


def load_music_selection_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {
            "schema_version": MUSIC_STATE_SCHEMA_VERSION,
            "last_successful_music_id": None,
            "last_successful_render_job_id": None,
            "successful_render_count": 0,
            "successful_render_jobs": {},
        }
    state = load_json(state_path)
    required = {
        "schema_version",
        "last_successful_music_id",
        "last_successful_render_job_id",
        "successful_render_count",
        "successful_render_jobs",
    }
    if set(state) != required or state["schema_version"] != MUSIC_STATE_SCHEMA_VERSION:
        raise ValueError("État persistant de rotation T2 invalide.")
    if state["last_successful_music_id"] not in {None, "A", "B", "C", "D"}:
        raise ValueError("Dernière musique réussie T2 inconnue.")
    if not isinstance(state["successful_render_count"], int) or state["successful_render_count"] < 0:
        raise ValueError("Compteur de réussites T2 invalide.")
    receipts = state["successful_render_jobs"]
    if (
        not isinstance(receipts, dict)
        or any(not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", job_id) or music_id not in {"A", "B", "C", "D"} for job_id, music_id in receipts.items())
        or len(receipts) != state["successful_render_count"]
    ):
        raise ValueError("Registre idempotent des réussites T2 invalide.")
    if (state["last_successful_music_id"] is None) != (state["last_successful_render_job_id"] is None):
        raise ValueError("L'état T2 doit associer musique et job réussis.")
    if state["last_successful_render_job_id"] is not None and receipts.get(state["last_successful_render_job_id"]) != state["last_successful_music_id"]:
        raise ValueError("La dernière réussite T2 doit être présente dans le registre idempotent.")
    return state


def select_music_candidate_from_state(
    *,
    render_job_id: str,
    state_path: Path,
    requested_candidate_id: str = "auto",
    pool: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_music_selection_state(state_path)
    return select_music_candidate(
        pool or load_json(MUSIC_POOL),
        render_job_id=render_job_id,
        requested_candidate_id=requested_candidate_id,
        previous_candidate_id=state["last_successful_music_id"],
    )


def _record_music_render_result_unlocked(
    *,
    state_path: Path,
    render_job_id: str,
    selected_music_id: str,
    succeeded: bool,
    pool: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_pool = pool or load_json(MUSIC_POOL)
    allowed = set(selected_pool["selection_contract"]["allowed_candidate_ids"])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", render_job_id) or selected_music_id not in allowed:
        raise ValueError("Résultat musical T2 invalide.")
    current = load_music_selection_state(state_path)
    if not succeeded:
        return current
    if render_job_id in current["successful_render_jobs"]:
        if current["successful_render_jobs"][render_job_id] != selected_music_id:
            raise ValueError("Un callback T2 rejoué ne peut pas changer de musique.")
        return current
    ordered_ids = list(selected_pool["selection_contract"]["allowed_candidate_ids"])
    previous_id = current["last_successful_music_id"]
    expected_id = ordered_ids[0] if previous_id is None else ordered_ids[(ordered_ids.index(previous_id) + 1) % len(ordered_ids)]
    if selected_music_id != expected_id:
        raise ValueError(
            f"Le succès T2 doit respecter le cycle strict : {expected_id} attendu, {selected_music_id} reçu."
        )
    updated = {
        "schema_version": MUSIC_STATE_SCHEMA_VERSION,
        "last_successful_music_id": selected_music_id,
        "last_successful_render_job_id": render_job_id,
        "successful_render_count": current["successful_render_count"] + 1,
        "successful_render_jobs": {**current["successful_render_jobs"], render_job_id: selected_music_id},
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{state_path.name}.", dir=state_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, state_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return updated


def record_music_render_result(
    *,
    state_path: Path,
    render_job_id: str,
    selected_music_id: str,
    succeeded: bool,
    pool: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize callbacks across processes before applying the atomic update."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state_path.parent / f".{state_path.name}.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            return _record_music_render_result_unlocked(
                state_path=state_path,
                render_job_id=render_job_id,
                selected_music_id=selected_music_id,
                succeeded=succeeded,
                pool=pool,
            )
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def select_historical_music_candidate(candidate_id: str) -> dict[str, Any]:
    """Read-only compatibility path for the locked historical B/D exemplars."""
    if candidate_id not in HISTORICAL_MIX_CONFIGS:
        raise ValueError("Seuls les exemplaires historiques B et D sont conservés.")
    shortlist = load_json(HISTORICAL_SHORTLIST)
    source_lock = load_json(HISTORICAL_SOURCE_LOCK)
    by_id = {item["id"]: item for item in shortlist["candidates"]}
    locks = {item["id"]: item for item in source_lock["candidates"]}
    selected = by_id[candidate_id]
    return {
        **copy.deepcopy(selected),
        "source_sha256": locks[candidate_id]["sha256"],
        "source_bytes": locks[candidate_id]["bytes"],
        "selection_mode": "explicit_user_choice",
        "requested_candidate_id": candidate_id,
        "previous_candidate_id": None,
    }


def mix_config_path_for_candidate(candidate_id: str) -> Path:
    """Resolve an approved production mix without altering historical contracts."""
    try:
        return MIX_CONFIGS[candidate_id]
    except KeyError as error:
        raise ValueError(
            f"Aucun contrat de mixage de production approuvé pour le candidat {candidate_id}."
        ) from error


def attach_music_track(
    job: dict[str, Any],
    *,
    requested_candidate_id: str = "auto",
    previous_candidate_id: str | None = None,
    selected_candidate: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    rotation_contract: bool = True,
) -> dict[str, Any]:
    """Attach one owner-approved T2 music selection to the same RenderJob."""
    selected = selected_candidate or select_music_candidate(
        load_json(MUSIC_POOL),
        render_job_id=job["job_id"],
        requested_candidate_id=requested_candidate_id,
        previous_candidate_id=previous_candidate_id,
    )
    selected_config = config or load_json(mix_config_path_for_candidate(selected["id"]))
    config_selection = selected_config["music_selection"]
    if selected["id"] != config_selection["candidate_id"]:
        raise ValueError("Le candidat musical diverge du contrat de mixage approuvé.")
    for key in ("source_page", "source_audio_url", "source_sha256", "content_id_status"):
        if selected[key] != config_selection[key]:
            raise ValueError(f"La source musicale {selected['id']} diverge du contrat : {key}")
    if "source_bytes" in config_selection and selected["source_bytes"] != config_selection["source_bytes"]:
        raise ValueError(f"La taille de la source musicale {selected['id']} diverge du contrat.")
    if rotation_contract:
        program_bindings = {
            "file": "program_file",
            "sha256": "program_sha256",
            "bytes": "program_bytes",
            "duration_s": "program_duration_s",
            "sample_rate_hz": "program_sample_rate_hz",
            "channels": "program_channels",
            "bitrate_kbps": "program_bitrate_kbps",
            "contains_voice": "program_contains_voice",
        }
        for pool_key, config_key in program_bindings.items():
            if selected[pool_key] != config_selection[config_key]:
                raise ValueError(f"L’instrumentale locale {selected['id']} diverge du contrat : {pool_key}")
    music_plan = {
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
    if rotation_contract:
        music_plan.update(
            {
                "source_bytes": selected["source_bytes"],
                "file": selected["file"],
                "sha256": selected["sha256"],
                "bytes": selected["bytes"],
                "duration_s": selected["duration_s"],
                "sample_rate_hz": selected["sample_rate_hz"],
                "channels": selected["channels"],
                "contains_voice": selected["contains_voice"],
                "owner_approved": selected["owner_approved"],
                "last_successful_music_id": selected["previous_candidate_id"],
                "state_update_policy": "after_success_only",
            }
        )
    job.setdefault("audio_plan", {})["music"] = music_plan
    return job


def attach_voice_track(
    job: dict[str, Any],
    *,
    mode: str = "registered_voice_clips",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach registered clips and the explicit captured-audio strategy."""
    allowed = {"registered_voice_clips", "captured_scene_audio", "captured_or_registered_fallback"}
    if mode not in allowed:
        raise ValueError(f"Mode voix inconnu : {mode}")
    selected_config = config or load_json(MIX_CONFIGS["D"])
    voice = selected_config["voice"]
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
    requested_candidate_id: str = "auto",
    previous_candidate_id: str | None = None,
    voice_mode: str = "registered_voice_clips",
    historical_exemplar: bool = False,
) -> dict[str, Any]:
    """Attach voice, approved music and ducking while proving visual data did not move."""
    before = {
        "merchant_payload": copy.deepcopy(job["merchant_payload"]),
        "captures": copy.deepcopy(job["captures"]),
        "text_motion_config": job["text_motion_config"],
    }
    if historical_exemplar:
        if previous_candidate_id is not None or requested_candidate_id == "auto":
            raise ValueError("Un exemplaire historique doit être un choix B ou D explicite sans état de rotation.")
        selected = select_historical_music_candidate(requested_candidate_id)
        config_path = HISTORICAL_MIX_CONFIGS[selected["id"]]
    else:
        selected = select_music_candidate(
            load_json(MUSIC_POOL),
            render_job_id=job["job_id"],
            requested_candidate_id=requested_candidate_id,
            previous_candidate_id=previous_candidate_id,
        )
        config_path = mix_config_path_for_candidate(selected["id"])
    config = load_json(config_path)
    job["audio_plan"] = {
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": digest(config_path),
    }
    attach_music_track(
        job,
        requested_candidate_id=requested_candidate_id,
        previous_candidate_id=previous_candidate_id,
        selected_candidate=selected,
        config=config,
        rotation_contract=not historical_exemplar,
    )
    attach_voice_track(job, mode=voice_mode, config=config)
    job["audio_plan"]["mix"] = copy.deepcopy(config["mix_contract"])
    job["audio_plan"]["publication"] = {
        "output_file": config["publication"]["output_file"],
        "publish_exactly_one_mp4": config["publication"]["publish_exactly_one_mp4"],
        "publish_standalone_audio": config["publication"]["publish_standalone_audio"],
    }
    if not historical_exemplar:
        job["output"]["uri"] = f"output/runtime/{job['job_id']}/{config['publication']['output_file']}"
    job["audio_mode"] = "voice_music_ducking"
    job["render_audio"] = True
    job["audio_contract"].update(
        {
            "current_output_audio": True,
            "music_status": (
                "selected_for_single_validation_exemplar"
                if historical_exemplar and selected["id"] == "B"
                else "selected_for_current_production"
                if historical_exemplar
                else "selected_from_owner_approved_four_track_rotation"
            ),
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
