#!/usr/bin/env python3
"""Transforme formulaire + captures T2 en RenderJob reproductible."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.complete_adapter import attach_complete_audio

QUESTIONS = ROOT / "form/questions_T2.json"
MANIFEST = ROOT / "rushes/manifest.json"
SCHEMA = ROOT / "schemas/render_job.schema.json"
CAPTURE_MEDIA = ROOT / "config/T2_capture_media_reference_v1_0_0.json"

STAGES: dict[str, dict[str, Any]] = {
    "silent_transition_validation": {
        "job_prefix": "t2-silent",
        "release_version": "v0.2.0-silent",
        "execution_profile": "T2_GITHUB_ACTIONS_SILENT",
        "render_business_text": False,
        "text_motion_config": None,
        "output_uri": "output/T2_AVANT_APRES_TRANSITIONS_SILENT_V0_2_0.mp4",
    },
    "dynamic_text_validation": {
        "job_prefix": "t2-text",
        "release_version": "v0.3.0-text-motion",
        "execution_profile": "T2_GITHUB_ACTIONS_TEXT_MOTION",
        "render_business_text": True,
        "text_motion_config": "config/T2_text_motion_v0_3_0.json",
        "output_uri": "output/T2_AVANT_APRES_TEXTES_DYNAMIQUES_V0_3_0.mp4",
    },
    "complete_voice_music_render": {
        "job_prefix": "t2-complete",
        "release_version": "v0.6.0-unified-runtime",
        "execution_profile": "T2_GITHUB_ACTIONS_COMPLETE",
        "render_business_text": True,
        "text_motion_config": "config/T2_text_motion_v0_3_0.json",
        "output_uri": "output/t2-complete-v0.6.0/VIDEO_T2_COMPLET_VOIX_MUSIQUE_B_A_VALIDER.mp4",
    },
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def normalize_answers(raw: dict[str, Any], questions: dict[str, Any]) -> dict[str, str]:
    fields = questions["fields"]
    allowed = {field["id"] for field in fields}
    extras = set(raw) - allowed
    if extras:
        raise ValueError(f"Champs inconnus : {sorted(extras)}")

    cleaned: dict[str, str] = {}
    for field in fields:
        key = field["id"]
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"Le champ {key!r} doit être du texte.")
        value = re.sub(r"\s+", " ", value.strip())
        if key in {"nom", "produit", "accroche"}:
            value = value.rstrip(".")
        if field["required"] and not value:
            raise ValueError(f"Champ obligatoire manquant : {key}")
        if len(value) < field.get("minLength", 0) or len(value) > field["maxLength"]:
            raise ValueError(f"Longueur invalide pour {key}")
        if field.get("pattern") and not re.fullmatch(field["pattern"], value):
            raise ValueError(f"Format invalide pour {key}")
        if value or field["required"]:
            cleaned[key] = value
    return cleaned


def build_job(
    raw_answers: dict[str, Any],
    stage: str = "silent_transition_validation",
    *,
    capture_overrides: dict[str, dict[str, Any]] | None = None,
    capture_manifest: str = "rushes/manifest.json",
    requested_music: str = "B",
    previous_music: str | None = None,
    voice_mode: str = "registered_voice_clips",
    control_plane: str = "github_actions_manual",
    cloudflare_job_id: str | None = None,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"Étape inconnue : {stage}")
    stage_spec = STAGES[stage]
    questions = _read(QUESTIONS)
    manifest = _read(MANIFEST)
    answers = normalize_answers(raw_answers, questions)

    sources = sorted(manifest["sources"], key=lambda item: item["scene"])
    if [item["scene"] for item in sources] != [1, 2, 3, 4]:
        raise ValueError("Le manifeste doit contenir exactement S1, S2, S3 et S4.")

    captures: dict[str, dict[str, Any]] = {}
    expected_ms = [6000, 8000, 7000, 9000]
    for index, (source, duration_ms) in enumerate(zip(sources, expected_ms), start=1):
        observed_ms = int(round(float(source["edit"]["duration"]) * 1000))
        if observed_ms != duration_ms:
            raise ValueError(f"Durée invalide pour S{index}: {observed_ms} ms")
        captures[f"S{index}"] = {
            "uri": source["local_file"],
            "duration_ms": duration_ms,
            "source_in_ms": int(round(float(source["edit"]["start"]) * 1000)),
            "has_audio": bool(source.get("source_metadata", {}).get("has_audio", False)),
            "sha256": source["sha256"],
        }

    if capture_overrides is not None:
        if stage != "complete_voice_music_render":
            raise ValueError("Les captures runtime ne sont acceptées que par le profil complet.")
        if set(capture_overrides) != {"S1", "S2", "S3", "S4"}:
            raise ValueError("Les captures runtime doivent fournir exactement S1, S2, S3 et S4.")
        captures = {slot: dict(capture_overrides[slot]) for slot in ("S1", "S2", "S3", "S4")}

    if stage == "complete_voice_music_render" and capture_overrides is None:
        media = _read(CAPTURE_MEDIA)["captures"]
        for slot in ("S1", "S2", "S3", "S4"):
            technical = {key: value for key, value in media[slot].items() if key != "source_has_audio"}
            captures[slot].update(technical)

    fingerprint_payload: dict[str, Any] = {
        "stage": stage,
        "merchant_payload": answers,
        "captures": captures,
    }
    if stage == "complete_voice_music_render":
        fingerprint_payload.update(
            {
                "requested_music": requested_music,
                "previous_music": previous_music,
                "voice_mode": voice_mode,
                "control_plane": control_plane,
            }
        )
    fingerprint_input = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    token = hashlib.sha256(fingerprint_input).hexdigest()[:16]

    job: dict[str, Any] = {
        "schema_version": "1.1.0" if stage == "complete_voice_music_render" else "1.0.0",
        "job_id": f"{stage_spec['job_prefix']}-{token}",
        "idempotency_key": f"t2-avant-apres-{stage_spec['release_version']}-{token}",
        "template_id": "restaurants_maquis_T2_avant_apres_v0_1_0",
        "template_version": "0.1.0",
        "execution_profile": stage_spec["execution_profile"],
        "network_policy": "declared_sources_only",
        "merchant_payload": answers,
        "captures": captures,
        "capture_manifest": capture_manifest if stage == "complete_voice_music_render" else "rushes/manifest.json",
        "runtime_contract": (
            "config/T2_runtime_contract_v0_6_0.json"
            if stage == "complete_voice_music_render"
            else "config/T2_runtime_contract_v0_3_0.json"
        ),
        "text_motion_config": stage_spec["text_motion_config"],
        "audio_contract": {
            "capture_voice_mode": "optional_per_scene",
            "preserve_captured_voice": True,
            "source_speed": 1.0,
            "source_time_map": "identity",
            "audio_time_map": "identity",
            "automatic_subtitles": False,
            "current_output_audio": False,
            "music_status": "deferred_until_visual_and_music_approval",
            "future_mix": "captured_voice_plus_selected_T2_music_with_ducking",
        },
        "audio_mode": "silent_no_audio_stream",
        "render_stage": stage,
        "render_business_text": stage_spec["render_business_text"],
        "render_audio": False,
        "output": {
            "uri": stage_spec["output_uri"],
            "container": "mp4",
            "video_mime": "video/avc",
            "width": 720,
            "height": 1280,
            "fps": 30,
            "frames": 900,
            "duration_ms": 30000,
            "target_video_bitrate_bps": 5000000,
            "overwrite": True,
        },
    }
    if stage == "complete_voice_music_render":
        if control_plane not in {"github_actions_manual", "cloudflare_worker"}:
            raise ValueError(f"Plan de contrôle inconnu : {control_plane}")
        if control_plane == "cloudflare_worker" and not cloudflare_job_id:
            raise ValueError("cloudflare_job_id est obligatoire avec le plan de contrôle Cloudflare.")
        job.update(
            {
                "capture_flow_contract": "config/T2_capture_flow_v1_0_0.json",
                "visual_plan": {
                    "renderer": "engine/render_text_motion.py",
                    "intermediate_uri": "output/T2_AVANT_APRES_TEXTES_DYNAMIQUES_V0_3_0.mp4",
                    "approved_release_tag": "t2-avant-apres-v0.3.0-text-motion",
                    "approved_file_sha256": "67c447dae81241fc9ecc34ee9edfbf8c354a6ddf76e7fa465a62cdac59550ada",
                    "approved_video_stream_sha256": "2ed8b3813410df8b9497da7b00877b208bed115038965f73989f00550d3941f5",
                    "rebuild_from_job": True,
                    "preserve_900_frames": True,
                },
                "provenance": {
                    "t1_reference_commit": "c656510ab81d31d413dc4dfd74b42671532cd978",
                    "t1_mode": "read_only",
                    "control_plane": control_plane,
                    "render_plane": "github_actions",
                    "cloudflare_job_id": cloudflare_job_id,
                },
            }
        )
        job["output"].update(
            {
                "audio_sample_rate_hz": 48000,
                "audio_channels": 2,
                "target_audio_bitrate_bps": 192000,
            }
        )
        attach_complete_audio(
            job,
            requested_candidate_id=requested_music,
            previous_candidate_id=previous_music,
            voice_mode=voice_mode,
        )
    Draft202012Validator(_read(SCHEMA)).validate(job)
    return job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--stage",
        choices=sorted(STAGES),
        default="silent_transition_validation",
    )
    parser.add_argument("--captures-json", help="Complete S1…S4 capture map supplied by the runtime control plane.")
    parser.add_argument("--capture-manifest", default="rushes/manifest.json")
    parser.add_argument("--music", choices=["A", "B", "C", "D", "auto"], default="B")
    parser.add_argument("--previous-music", choices=["A", "B", "C", "D"])
    parser.add_argument(
        "--voice-mode",
        choices=["registered_voice_clips", "captured_scene_audio", "captured_or_registered_fallback"],
        default="registered_voice_clips",
    )
    parser.add_argument("--control-plane", choices=["github_actions_manual", "cloudflare_worker"], default="github_actions_manual")
    parser.add_argument("--cloudflare-job-id")
    args = parser.parse_args()

    answers_path = _resolve(args.answers)
    output_path = _resolve(args.output)
    capture_overrides = _read(_resolve(args.captures_json)) if args.captures_json else None
    job = build_job(
        _read(answers_path),
        stage=args.stage,
        capture_overrides=capture_overrides,
        capture_manifest=args.capture_manifest,
        requested_music=args.music,
        previous_music=args.previous_music,
        voice_mode=args.voice_mode,
        control_plane=args.control_plane,
        cloudflare_job_id=args.cloudflare_job_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(job, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        display_path = output_path.relative_to(ROOT)
    except ValueError:
        display_path = output_path
    print("RENDER_JOB_OK", job["job_id"], display_path)


if __name__ == "__main__":
    main()
