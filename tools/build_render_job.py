#!/usr/bin/env python3
"""Transforme les réponses du formulaire T2 en RenderJob reproductible."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "form/questions_T2.json"
MANIFEST = ROOT / "rushes/manifest.json"
SCHEMA = ROOT / "schemas/render_job.schema.json"


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


def build_job(raw_answers: dict[str, Any]) -> dict[str, Any]:
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

    fingerprint_input = json.dumps(
        {"merchant_payload": answers, "captures": captures},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    token = hashlib.sha256(fingerprint_input).hexdigest()[:16]

    job: dict[str, Any] = {
        "schema_version": "1.0.0",
        "job_id": f"t2-silent-{token}",
        "idempotency_key": f"t2-avant-apres-v0.2.0-silent-{token}",
        "template_id": "restaurants_maquis_T2_avant_apres_v0_1_0",
        "template_version": "0.1.0",
        "execution_profile": "T2_GITHUB_ACTIONS_SILENT",
        "network_policy": "declared_sources_only",
        "merchant_payload": answers,
        "captures": captures,
        "capture_manifest": "rushes/manifest.json",
        "audio_mode": "silent_no_audio_stream",
        "render_stage": "silent_transition_validation",
        "render_business_text": False,
        "render_audio": False,
        "output": {
            "uri": "output/T2_AVANT_APRES_TRANSITIONS_SILENT_V0_2_0.mp4",
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
    Draft202012Validator(_read(SCHEMA)).validate(job)
    return job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    answers_path = _resolve(args.answers)
    output_path = _resolve(args.output)
    job = build_job(_read(answers_path))
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
