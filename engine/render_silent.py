#!/usr/bin/env python3
"""Rendu serveur T2 : rushes et transitions, sans texte ni flux audio."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.media import ClipSpec, SequentialClip, cover_9x16, warm_grade
from engine.transitions import (
    center_window_expand,
    diagonal_desaturated_to_color,
    intro_oblique,
    oblique_shutters,
    staggered_bands,
    warm_flash,
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render(job_path: Path) -> Path:
    job = load_json(job_path)
    schema = load_json(ROOT / "schemas/render_job.schema.json")
    Draft202012Validator(schema).validate(job)

    if job["render_audio"] is not False or job["audio_mode"] != "silent_no_audio_stream":
        raise ValueError("Cette étape doit produire exactement zéro flux audio.")
    if job["render_business_text"] is not False:
        raise ValueError("Cette étape ne doit afficher aucun texte commerçant.")

    output_spec = job["output"]
    width = int(output_spec["width"])
    height = int(output_spec["height"])
    fps = int(output_spec["fps"])
    frame_count = int(output_spec["frames"])
    if (width, height, fps, frame_count, output_spec["duration_ms"]) != (720, 1280, 30, 900, 30000):
        raise ValueError("Contrat de sortie T2 silencieux invalide.")

    config = load_json(ROOT / "config/T2_avant_apres_template_v0_1_0.json")
    manifest = load_json(ROOT / job["capture_manifest"])
    manifest_by_path = {item["local_file"]: item for item in manifest["sources"]}

    slots = ["S1", "S2", "S3", "S4"]
    durations = [job["captures"][slot]["duration_ms"] / 1000.0 for slot in slots]
    if durations != [6.0, 8.0, 7.0, 9.0]:
        raise ValueError(f"Durées de captures invalides : {durations}")

    clips: list[SequentialClip] = []
    for slot in slots:
        capture = job["captures"][slot]
        source = manifest_by_path.get(capture["uri"])
        if source is None or source["sha256"] != capture["sha256"]:
            raise ValueError(f"Capture {slot} absente du manifeste verrouillé.")
        path = ROOT / capture["uri"]
        actual = digest(path)
        if actual != capture["sha256"]:
            raise ValueError(f"SHA-256 invalide pour {slot}: {actual}")
        clips.append(
            SequentialClip(
                ClipSpec(
                    path=path,
                    start=capture["source_in_ms"] / 1000.0,
                    duration=capture["duration_ms"] / 1000.0,
                )
            )
        )

    output = ROOT / output_spec["uri"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".server-silent.mp4")
    writer = cv2.VideoWriter(
        str(temporary),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError("VideoWriter indisponible")

    starts = [0.0, 6.0, 14.0, 21.0]

    def scene_frame(index: int, local_seconds: float) -> np.ndarray:
        progress = float(np.clip(local_seconds / durations[index], 0.0, 1.0))
        zooms = [(1.015, 1.070), (1.035, 1.055), (1.020, 1.055), (1.018, 1.050)]
        pan_x = [-0.12 + 0.22 * progress, 0.08 - 0.12 * progress, -0.06 + 0.12 * progress, 0.0]
        pan_y = [0.02, -0.08 + 0.14 * progress, 0.01, -0.03 + 0.07 * progress]
        zoom = zooms[index][0] + (zooms[index][1] - zooms[index][0]) * progress
        source_frame = clips[index].frame(local_seconds)
        return warm_grade(cover_9x16(source_frame, width, height, zoom, pan_x[index], pan_y[index]))

    try:
        for frame_number in range(frame_count):
            time_seconds = frame_number / fps
            scene_index = 0 if time_seconds < 6 else 1 if time_seconds < 14 else 2 if time_seconds < 21 else 3
            image = scene_frame(scene_index, time_seconds - starts[scene_index])

            if time_seconds < 0.42:
                image = intro_oblique(image, time_seconds / 0.42)
            if 5.79 <= time_seconds < 6.21:
                image = center_window_expand(
                    scene_frame(0, min(5.999, time_seconds)),
                    scene_frame(1, max(0.0, time_seconds - 6.0)),
                    (time_seconds - 5.79) / 0.42,
                )
            if 9.79 <= time_seconds < 10.21:
                image = warm_flash(image, (time_seconds - 9.79) / 0.42)
            if 13.79 <= time_seconds < 14.21:
                image = oblique_shutters(
                    scene_frame(1, min(7.999, max(0.0, time_seconds - 6.0))),
                    scene_frame(2, max(0.0, time_seconds - 14.0)),
                    (time_seconds - 13.79) / 0.42,
                )
            if 17.29 <= time_seconds < 17.71:
                image = staggered_bands(image, (time_seconds - 17.29) / 0.42)
            if 20.79 <= time_seconds < 21.21:
                image = diagonal_desaturated_to_color(
                    scene_frame(2, min(6.999, max(0.0, time_seconds - 14.0))),
                    scene_frame(3, max(0.0, time_seconds - 21.0)),
                    (time_seconds - 20.79) / 0.42,
                )

            writer.write(image)
            if frame_number % 90 == 0:
                print(f"frame {frame_number}/{frame_count}", flush=True)
    finally:
        writer.release()
        for clip in clips:
            clip.close()

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(temporary),
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-frames:v",
        str(frame_count),
        "-movflags",
        "+faststart",
        "-metadata",
        "title=T2 transitions silencieuses serveur",
        str(output),
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    temporary.unlink(missing_ok=True)

    proof = {
        "job_id": job["job_id"],
        "output": str(output.relative_to(ROOT)),
        "sha256": digest(output),
        "bytes": output.stat().st_size,
        "width": width,
        "height": height,
        "fps": fps,
        "frames": frame_count,
        "duration_seconds": 30.0,
        "video_streams_expected": 1,
        "audio_streams_expected": 0,
        "subtitle_streams_expected": 0,
        "text_overlays": 0,
        "merchant_fields_stored_not_rendered": sorted(job["merchant_payload"].keys()),
        "generated_by": "GitHub Actions",
        "transitions": config["transition_budget"]["events"],
    }
    proofs = ROOT / "proofs"
    proofs.mkdir(exist_ok=True)
    (proofs / "server_render_manifest.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("SERVER_SILENT_RENDER_OK", output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="demo/input_demo.json")
    args = parser.parse_args()
    job_path = Path(args.job)
    if not job_path.is_absolute():
        job_path = ROOT / job_path
    render(job_path)


if __name__ == "__main__":
    main()
