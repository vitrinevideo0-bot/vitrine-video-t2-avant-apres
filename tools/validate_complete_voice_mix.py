#!/usr/bin/env python3
"""Independent server-side validation of the single T2 complete MP4."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/T2_complete_voice_mix.schema.json"
SR = 48_000


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, **kwargs)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    return json.loads(
        run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True,
            text=True,
        ).stdout
    )


def stream_hash(path: Path, stream: str) -> str:
    value = run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-map", stream,
            "-c", "copy", "-f", "hash", "-hash", "sha256", "-",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not value.startswith("SHA256="):
        raise RuntimeError(f"Hash de flux invalide: {value}")
    return value.split("=", 1)[1].lower()


def loudness(path: Path) -> dict[str, Any]:
    completed = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
            "-af", "loudnorm=I=-16:TP=-1:LRA=7:print_format=json", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    blocks = re.findall(r'\{\s*"input_i".*?\}', completed.stderr, re.S)
    if not blocks:
        raise RuntimeError("La mesure indépendante loudnorm n’a pas renvoyé de JSON.")
    return json.loads(blocks[-1])


def decoded_qc(path: Path) -> dict[str, Any]:
    raw = run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
            "-ar", str(SR), "-ac", "2", "-f", "f32le", "-",
        ],
        capture_output=True,
    ).stdout
    audio = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
    return {
        "decoded_samples_per_channel": len(audio),
        "decoded_duration_s": len(audio) / SR,
        "clipped_sample_count": int(np.count_nonzero(np.abs(audio) >= 0.999999)),
        "nan_count": int(np.isnan(audio).sum()),
        "inf_count": int(np.isinf(audio).sum()),
        "sample_peak_dbfs": round(
            float(20 * np.log10(max(float(np.max(np.abs(audio))), 1e-12))), 3
        ),
    }


def validate_automation(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 3001:
        raise ValueError(f"Automation attendue sur 3001 points, obtenu {len(rows)}")
    times = [float(row["time_s"]) for row in rows]
    gains = [float(row["music_gain_db"]) for row in rows]
    active = [int(row["voice_clip_active"]) for row in rows]
    if times[0] != 0.0 or times[-1] != 30.0:
        raise ValueError("L’automation ne couvre pas exactement 0–30 s.")
    if abs(min(gains) + 10.0) > 0.001 or abs(max(gains) + 3.0) > 0.001:
        raise ValueError("L’automation ne respecte pas les gains −3/−10 dB.")
    active_starts = sum(1 for previous, current in zip([0] + active[:-1], active) if previous == 0 and current == 1)
    if active_starts != 4:
        raise ValueError(f"Quatre fenêtres de voix attendues, obtenu {active_starts}")
    return {
        "rows": len(rows),
        "start_s": times[0],
        "end_s": times[-1],
        "minimum_gain_db": min(gains),
        "maximum_gain_db": max(gains),
        "active_voice_blocks": active_starts,
        "sha256": digest(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Validation de production interdite hors GitHub Actions.")

    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    proof_path = args.proof.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(config)
    publication = config["publication"]
    gates = config["quality_gates"]

    mp4s = sorted(output_dir.glob("*.mp4"))
    if len(mp4s) != 1 or mp4s[0].name != publication["output_file"]:
        raise ValueError(f"Un unique MP4 final est exigé: {[path.name for path in mp4s]}")
    standalone_audio = [
        path.name
        for pattern in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.flac", "*.ogg", "*.opus")
        for path in output_dir.glob(pattern)
    ]
    if standalone_audio:
        raise ValueError(f"Audio autonome interdit dans la sortie: {standalone_audio}")

    report_path = output_dir / publication["validation_report"]
    human_report_path = output_dir / publication["human_report"]
    automation_path = output_dir / publication["automation_csv"]
    plot_path = output_dir / publication["timeline_plot"]
    for required in (report_path, human_report_path, automation_path, plot_path):
        if not required.is_file() or required.stat().st_size == 0:
            raise ValueError(f"Preuve absente: {required.name}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("generated_on_github_actions") is not True:
        raise ValueError("Le rapport de mixage GitHub n’est pas PASS.")
    if not report.get("checks") or not all(report["checks"].values()):
        raise ValueError("Au moins un contrôle du mixeur n’est pas validé.")
    if report["music"]["candidate_id"] != "B":
        raise ValueError("Le choix utilisateur B n’a pas été respecté.")
    if report["music"]["template_default_selection"] is not False:
        raise ValueError("Le morceau B a été défini à tort comme défaut du gabarit.")
    if report["music"]["content_id_status"] != "registered":
        raise ValueError("L’avertissement Content ID doit rester visible.")
    if report["publication"]["source_music_published"] or report["publication"]["voice_stem_published"]:
        raise ValueError("Une source audio autonome est marquée publiée.")

    mp4 = mp4s[0]
    metadata = probe(mp4)
    videos = [item for item in metadata["streams"] if item.get("codec_type") == "video"]
    audios = [item for item in metadata["streams"] if item.get("codec_type") == "audio"]
    subtitles = [item for item in metadata["streams"] if item.get("codec_type") == "subtitle"]
    if len(videos) != 1 or len(audios) != 1 or subtitles:
        raise ValueError("Flux MP4 invalides.")
    video, audio = videos[0], audios[0]
    duration = float(metadata["format"]["duration"])
    video_hash = stream_hash(mp4, "0:v:0")
    independent_loudness = loudness(mp4)
    qc = decoded_qc(mp4)
    observed_bitrate = int(audio.get("bit_rate") or 0)
    target_bitrate = int(gates["required_audio_bitrate_bps"])

    checks = {
        "sha256_matches_mixer_report": digest(mp4) == report["final_mp4"]["sha256"],
        "duration_30s": abs(duration - float(config["duration_s"])) <= float(gates["duration_tolerance_s"]),
        "width": int(video.get("width", 0)) == int(gates["required_width"]),
        "height": int(video.get("height", 0)) == int(gates["required_height"]),
        "fps": video.get("r_frame_rate") == gates["required_video_fps"],
        "frames": int(video.get("nb_frames", 0)) == int(gates["required_video_frames"]),
        "visual_bitstream": video_hash == config["visual_source"]["video_stream_sha256"],
        "audio_codec": audio.get("codec_name") == gates["required_audio_codec"],
        "audio_sample_rate": int(audio.get("sample_rate", 0)) == int(gates["required_audio_sample_rate_hz"]),
        "audio_channels": int(audio.get("channels", 0)) == int(gates["required_audio_channels"]),
        "audio_bitrate_near_target": (
            observed_bitrate > 0 and abs(observed_bitrate - target_bitrate) / target_bitrate <= 0.12
        ),
        "integrated_loudness": (
            float(gates["integrated_lufs_min"])
            <= float(independent_loudness["input_i"])
            <= float(gates["integrated_lufs_max"])
        ),
        "aac_true_peak": float(independent_loudness["input_tp"]) <= float(gates["aac_true_peak_dbtp_max"]),
        "no_clipping": qc["clipped_sample_count"] <= int(gates["clipped_sample_count_max"]),
        "no_non_finite_samples": qc["nan_count"] == qc["inf_count"] == 0,
        "speech_to_music": (
            float(report["intelligibility_proxy"]["aggregate_speech_to_music_db"])
            >= float(gates["minimum_active_speech_to_music_db"])
        ),
        "four_voice_clips": len(report["voice"]["clips"]) == 4,
        "voice_stem_30s": int(report["voice"]["stem"]["decoded_samples"]) == 1_440_000,
        "duck_open_minus_3": report["ducking"]["maximum_music_gain_db"] == -3.0,
        "duck_under_minus_10": report["ducking"]["minimum_music_gain_db"] == -10.0,
        "duck_attack_120ms": report["ducking"]["duck_attack_ms"] == 120,
        "duck_release_450ms": report["ducking"]["duck_release_ms"] == 450,
        "one_mp4_no_standalone_audio": len(mp4s) == 1 and not standalone_audio,
    }
    automation = validate_automation(automation_path)
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ValueError(f"Validation indépendante échouée: {failed}")

    proof = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_on_github_actions": True,
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "commit": os.environ.get("GITHUB_SHA"),
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": digest(config_path),
        "mix_report": report_path.name,
        "mix_report_sha256": digest(report_path),
        "human_report_sha256": digest(human_report_path),
        "timeline_plot_sha256": digest(plot_path),
        "automation": automation,
        "one_mp4_only": True,
        "standalone_audio_published": False,
        "music_candidate": "B",
        "music_template_default": False,
        "content_id_status": "registered",
        "mp4": {
            "file": mp4.name,
            "sha256": digest(mp4),
            "bytes": mp4.stat().st_size,
            "duration_s": duration,
            "video_stream_sha256": video_hash,
            "width": int(video["width"]),
            "height": int(video["height"]),
            "fps": video["r_frame_rate"],
            "frames": int(video["nb_frames"]),
            "audio_codec": audio["codec_name"],
            "sample_rate_hz": int(audio["sample_rate"]),
            "channels": int(audio["channels"]),
            "requested_audio_bitrate_bps": target_bitrate,
            "observed_audio_bitrate_bps": observed_bitrate,
            "integrated_lufs": float(independent_loudness["input_i"]),
            "true_peak_dbtp": float(independent_loudness["input_tp"]),
            **qc,
        },
        "speech_to_music_db": report["intelligibility_proxy"]["aggregate_speech_to_music_db"],
        "checks": checks,
    }
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("T2_COMPLETE_VOICE_MIX_VALIDATION_OK", json.dumps(proof["mp4"], ensure_ascii=False))


if __name__ == "__main__":
    main()
