#!/usr/bin/env python3
"""Valide le MP4 texte T2 et les preuves de liaison JSON → scènes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--job", default="demo/render_job_textes_server.json")
    args = parser.parse_args()
    video_path = Path(args.video)
    if not video_path.is_absolute():
        video_path = ROOT / video_path
    job_path = Path(args.job)
    if not job_path.is_absolute():
        job_path = ROOT / job_path

    metadata = probe(video_path)
    video = [item for item in metadata["streams"] if item["codec_type"] == "video"]
    audio = [item for item in metadata["streams"] if item["codec_type"] == "audio"]
    subtitles = [item for item in metadata["streams"] if item["codec_type"] == "subtitle"]

    capture = cv2.VideoCapture(str(video_path))
    observed = {
        "width": int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
        "height": int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
        "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        "frames": int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT))),
    }
    capture.release()
    observed["duration_seconds"] = observed["frames"] / observed["fps"]

    assert len(video) == 1
    assert len(audio) == 0
    assert len(subtitles) == 0
    assert (observed["width"], observed["height"], observed["frames"]) == (720, 1280, 900)
    assert math.isclose(observed["fps"], 30.0, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(observed["duration_seconds"], 30.0, rel_tol=0.0, abs_tol=1e-6)

    job = json.loads(job_path.read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "proofs/text_motion_render_manifest.json").read_text(encoding="utf-8"))
    expected_fields = {"nom", "produit", "prix", "whatsapp", "quartier", "accroche"}
    assert job["render_business_text"] is True
    assert job["render_audio"] is False
    assert manifest["rendered_merchant_payload"] == job["merchant_payload"]
    assert {key.split(".")[-1] for key in manifest["merchant_bindings"]} == expected_fields
    assert set(manifest["text_evidence"]) == {
        "T2_G01_IDENTITY",
        "T2_G02_OFFER",
        "T2_G03_REVEAL",
        "T2_G04_FINAL",
    }
    assert all(item["changed_pixels"] > 1000 for item in manifest["text_evidence"].values())
    assert manifest["font_reference"]["selected_open_font"] == "Pinyon Script"

    result = {
        "file": str(video_path.relative_to(ROOT)),
        "sha256": digest(video_path),
        "bytes": video_path.stat().st_size,
        "video_streams": len(video),
        "audio_streams": len(audio),
        "subtitle_streams": len(subtitles),
        "dynamic_merchant_fields": sorted(expected_fields),
        "graphic_blocks": sorted(manifest["text_evidence"]),
        "font": "Pinyon Script",
        "observed": observed,
        "status": "PASS",
    }
    output = ROOT / "proofs/text_motion_validation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    video_path.with_suffix(".sha256").write_text(
        f"{result['sha256']}  {video_path.name}\n",
        encoding="utf-8",
    )
    print("TEXT_MOTION_VALIDATION_OK", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
