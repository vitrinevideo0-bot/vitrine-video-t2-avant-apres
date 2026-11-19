#!/usr/bin/env python3
"""Execute the unified T2 Avant / Après RenderJob on GitHub Actions only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "audio/scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "audio/scripts"))

from engine.render_text_motion import render as render_visual
from mix_t2_voice_music_v0_5 import (
    is_reference_exemplar,
    only_streams,
    probe,
    reference_visual_integrity,
    sha256,
    stream_hash,
)
from tools.verify_visual_pipeline import verify as verify_visual_pipeline

JOB_SCHEMA = ROOT / "schemas/render_job.schema.json"
RESULT_SCHEMA = ROOT / "schemas/render_result.schema.json"
ERROR_SCHEMA = ROOT / "schemas/render_error.schema.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate(schema_path: Path, payload: dict[str, Any]) -> None:
    Draft202012Validator(
        load(schema_path), format_checker=FormatChecker()
    ).validate(payload)


def write_error(
    output_dir: Path,
    job: dict[str, Any],
    *,
    stage: str,
    code: str,
    error: Exception,
) -> Path:
    payload = {
        "schema_version": "1.0.0",
        "status": "FAILED",
        "job_id": job.get("job_id", "unknown-t2-job"),
        "template_id": "restaurants_maquis_T2_avant_apres_v0_1_0",
        "code": code,
        "message": str(error) or error.__class__.__name__,
        "retryable": code not in {"T2_INVALID_RENDER_JOB", "T2_MUSIC_CHECKSUM_MISMATCH"},
        "stage": stage,
        "control_plane": job.get("provenance", {}).get("control_plane", "github_actions_manual"),
        "render_plane": "github_actions",
        "details": {"exception_type": error.__class__.__name__},
    }
    validate(ERROR_SCHEMA, payload)
    path = output_dir / "T2_RENDER_ERROR.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _ratio(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    numerator, separator, denominator = value.partition("/")
    return float(numerator) / float(denominator) if separator and float(denominator) else float(value)


def observed_media_duration(path: Path, metadata: dict[str, Any], video: dict[str, Any]) -> float:
    for candidate in (metadata.get("format", {}).get("duration"), video.get("duration")):
        try:
            value = float(candidate)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    try:
        duration_ts = int(video.get("duration_ts"))
        time_base = _ratio(video.get("time_base"))
        if duration_ts > 0 and time_base > 0:
            return duration_ts * time_base
    except (TypeError, ValueError):
        pass
    counted = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_packets,r_frame_rate", "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(counted.stdout)["streams"][0]
    fps = _ratio(stream.get("r_frame_rate"))
    packets = int(stream.get("nb_read_packets") or 0)
    return packets / fps if packets and fps else 0.0


def validate_capture_files(job: dict[str, Any]) -> None:
    codec_aliases = {"avc1": "h264", "avc": "h264", "hevc": "hevc", "h265": "hevc"}
    for slot in ("S1", "S2", "S3", "S4"):
        capture = job["captures"][slot]
        path = ROOT / capture["uri"]
        if not path.is_file():
            raise FileNotFoundError(f"Capture {slot} absente : {capture['uri']}")
        if sha256(path) != capture["sha256"]:
            raise RuntimeError(f"Capture {slot} corrompue : SHA-256 invalide.")
        metadata = probe(path)
        videos = only_streams(metadata, "video")
        audios = only_streams(metadata, "audio")
        if len(videos) != 1:
            raise RuntimeError(f"Capture {slot} : un unique flux vidéo est requis.")
        video = videos[0]
        actual_codec = codec_aliases.get(str(video.get("codec_name", "")).lower(), str(video.get("codec_name", "")).lower())
        declared_codec = codec_aliases.get(str(capture.get("video_codec", "")).lower(), str(capture.get("video_codec", "")).lower())
        if declared_codec not in {actual_codec, "browser_mediarecorder"}:
            raise RuntimeError(f"Capture {slot} : codec déclaré {declared_codec}, observé {actual_codec}.")
        actual_width = int(video.get("width", 0))
        actual_height = int(video.get("height", 0))
        if {actual_width, actual_height} != {int(capture["width"]), int(capture["height"])}:
            raise RuntimeError(f"Capture {slot} : dimensions déclarées et observées différentes.")
        duration = observed_media_duration(path, metadata, video)
        required = (int(capture["source_in_ms"]) + int(capture["duration_ms"])) / 1000.0
        if duration + 0.55 < required:
            raise RuntimeError(f"Capture {slot} trop courte : {duration:.3f} s pour {required:.3f} s.")
        if capture["has_audio"] and not audios:
            raise RuntimeError(f"Capture {slot} déclare une voix mais ne contient aucun flux audio.")


def execute(job_path: Path, output_dir: Path) -> Path:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Le rendu complet de production est interdit hors GitHub Actions.")
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    job = load(job_path)
    stage = "VALIDATING"
    try:
        validate(JOB_SCHEMA, job)
        if job["render_stage"] != "complete_voice_music_render":
            raise ValueError("Le job n'est pas le profil complet T2.")
        expected_output_dir = (ROOT / job["output"]["uri"]).parent.resolve()
        if output_dir.resolve() != expected_output_dir:
            raise ValueError(f"Répertoire de sortie différent du RenderJob: {output_dir} != {expected_output_dir}")

        stage = "MATERIALIZING_CAPTURES"
        validate_capture_files(job)

        stage = "RENDERING_VISUAL"
        verify_visual_pipeline()
        visual = ROOT / job["visual_plan"]["intermediate_uri"]
        visual.parent.mkdir(parents=True, exist_ok=True)
        render_visual(job_path, output_override=visual)
        observed_file_hash = sha256(visual)
        observed_stream_hash = stream_hash(visual, "0:v:0")
        reference_exemplar = is_reference_exemplar(job)
        if reference_exemplar:
            reference_visual_integrity(
                observed_file_sha256=observed_file_hash,
                observed_video_stream_sha256=observed_stream_hash,
                approved_file_sha256=job["visual_plan"]["approved_file_sha256"],
                approved_video_stream_sha256=job["visual_plan"]["approved_video_stream_sha256"],
            )

        stage = "MIXING_AUDIO"
        config = ROOT / job["audio_plan"]["config"]
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "audio/scripts/mix_t2_voice_music_v0_5.py"),
                "--config",
                str(config),
                "--job",
                str(job_path),
                "--visual-source",
                str(visual),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            check=True,
        )

        stage = "VALIDATING_OUTPUT"
        proof_path = output_dir / "T2_GITHUB_SERVER_VALIDATION_V0_6_0.json"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/validate_complete_voice_mix.py"),
                "--config",
                str(config),
                "--output-dir",
                str(output_dir),
                "--proof",
                str(proof_path),
                "--job",
                str(job_path),
                "--visual-source",
                str(visual),
            ],
            cwd=ROOT,
            check=True,
        )
        proof = load(proof_path)
        mix_config = load(config)
        report = load(output_dir / mix_config["publication"]["validation_report"])
        final = proof["mp4"]
        result = {
            "schema_version": "1.0.0",
            "status": "COMPLETED",
            "job_id": job["job_id"],
            "idempotency_key": job["idempotency_key"],
            "job_sha256": sha256(job_path),
            "template_id": job["template_id"],
            "template_version": job["template_version"],
            "profile_used": job["execution_profile"],
            "control_plane": job["provenance"]["control_plane"],
            "render_plane": "github_actions",
            "inputs": {
                "merchant_payload_sha256": canonical_hash(job["merchant_payload"]),
                "capture_sha256": {
                    slot: job["captures"][slot]["sha256"]
                    for slot in ("S1", "S2", "S3", "S4")
                },
                "music_source_sha256": job["audio_plan"]["music"]["source_sha256"],
                "voice_source_sha256": [
                    item["source_sha256"] for item in report["voice"]["clips"]
                ],
            },
            "output": {
                "uri": job["output"]["uri"],
                "mime_type": "video/mp4",
                "width": final["width"],
                "height": final["height"],
                "fps": final["fps"],
                "frames": final["frames"],
                "duration_ms": int(round(float(final["duration_s"]) * 1000)),
                "bytes": final["bytes"],
                "sha256": final["sha256"],
                "video_stream_sha256": final["video_stream_sha256"],
                "audio_present": True,
                "audio_codec": final["audio_codec"],
                "sample_rate_hz": final["sample_rate_hz"],
                "channels": final["channels"],
            },
            "quality": {
                "status": "PASS",
                "visual_900_frames": final["frames"] == 900,
                "voice_speed_1x": all(item["source_speed"] == 1.0 for item in report["voice"]["clips"]),
                "ducking_pass": (
                    report["ducking"]["minimum_music_gain_db"] == -10.0
                    and report["ducking"]["maximum_music_gain_db"] == -3.0
                ),
                "no_clipping": final["clipped_sample_count"] == 0,
                "no_standalone_audio": proof["standalone_audio_published"] is False,
            },
            "artifacts": {
                "mix_report": "T2_VOICE_MUSIC_LEVELS_VALIDATION_V0_5_0.json",
                "server_validation": proof_path.name,
                "render_job": job_path.name,
            },
            "metrics": {
                "elapsed_ms": int(round((time.monotonic() - started) * 1000)),
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            },
            "warnings": [
                "La musique B reste limitée à cet exemplaire et sa page indique Content ID Registered."
            ],
        }
        validate(RESULT_SCHEMA, result)
        result_path = output_dir / "T2_RENDER_RESULT_V0_6_0.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("T2_UNIFIED_RENDER_OK", result["job_id"], result["output"]["sha256"])
        return result_path
    except Exception as error:
        code = {
            "VALIDATING": "T2_INVALID_RENDER_JOB",
            "MATERIALIZING_CAPTURES": "T2_CAPTURE_CORRUPT",
            "RENDERING_VISUAL": "T2_VISUAL_RENDER_FAILED",
            "MIXING_AUDIO": "T2_AUDIO_MIX_FAILED",
            "VALIDATING_OUTPUT": "T2_OUTPUT_VALIDATION_FAILED",
        }.get(stage, "T2_RENDER_FAILED")
        error_path = write_error(output_dir, job, stage=stage, code=code, error=error)
        print("T2_UNIFIED_RENDER_FAILED", error_path, file=sys.stderr)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    execute(args.job.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
