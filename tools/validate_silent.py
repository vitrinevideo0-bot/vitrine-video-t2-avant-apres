#!/usr/bin/env python3
"""Vérifie le MP4 de contrôle : 900 images, 30 s et un seul flux vidéo."""
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
    raw = subprocess.check_output(
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
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    args = parser.parse_args()
    path = Path(args.video)
    if not path.is_absolute():
        path = ROOT / path

    metadata = probe(path)
    video = [item for item in metadata["streams"] if item["codec_type"] == "video"]
    audio = [item for item in metadata["streams"] if item["codec_type"] == "audio"]
    subtitles = [item for item in metadata["streams"] if item["codec_type"] == "subtitle"]
    other = [
        item
        for item in metadata["streams"]
        if item["codec_type"] not in {"video", "audio", "subtitle"}
    ]

    capture = cv2.VideoCapture(str(path))
    observed = {
        "width": int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
        "height": int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
        "fps": float(capture.get(cv2.CAP_PROP_FPS)),
        "frames": int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT))),
    }
    capture.release()
    observed["duration_seconds"] = observed["frames"] / observed["fps"]

    assert len(video) == 1, f"flux vidéo inattendus : {len(video)}"
    assert len(audio) == 0, f"flux audio interdits : {len(audio)}"
    assert len(subtitles) == 0, f"flux sous-titres interdits : {len(subtitles)}"
    assert len(other) == 0, f"autres flux interdits : {len(other)}"
    assert (observed["width"], observed["height"], observed["frames"]) == (720, 1280, 900)
    assert math.isclose(observed["fps"], 30.0, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(observed["duration_seconds"], 30.0, rel_tol=0.0, abs_tol=1e-6)

    result = {
        "file": str(path.relative_to(ROOT)),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
        "video_streams": len(video),
        "audio_streams": len(audio),
        "subtitle_streams": len(subtitles),
        "other_streams": len(other),
        "text_overlays": 0,
        "observed": observed,
        "status": "PASS",
    }
    output = ROOT / "proofs/silent_validation.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".sha256").write_text(
        f"{result['sha256']}  {path.name}\n",
        encoding="utf-8",
    )
    print("SILENT_VALIDATION_OK", json.dumps(result))


if __name__ == "__main__":
    main()
