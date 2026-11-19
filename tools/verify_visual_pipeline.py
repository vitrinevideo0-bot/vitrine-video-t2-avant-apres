#!/usr/bin/env python3
"""Verify that dynamic jobs still execute the approved T2 v0.3 visual mechanics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "baseline/T2_VISUAL_PIPELINE.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(lock_path: Path = LOCK) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for relative, expected in lock["files"].items():
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"Composant visuel verrouillé absent : {relative}")
        actual = digest(path)
        if actual == expected:
            continue
        if relative == "config/T2_avant_apres_template_v0_1_0.json":
            # ``audio_profile`` is approved non-visual metadata. Removing that
            # one key must reconstruct the byte-locked v0.3 visual contract.
            canonical = json.loads(path.read_text(encoding="utf-8"))
            if canonical.get("audio_profile") != "afrobeat_restaurants_maquis":
                raise RuntimeError("Le profil audio canonique T2 est absent ou inattendu.")
            del canonical["audio_profile"]
            historical = hashlib.sha256(
                (json.dumps(canonical, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ).hexdigest()
            if historical == expected:
                continue
        raise RuntimeError(f"Composant visuel T2 modifié : {relative}: {actual} != {expected}")
    config = json.loads((ROOT / "config/T2_text_motion_v0_3_0.json").read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / "config/T2_runtime_contract_v0_7_0.json").read_text(encoding="utf-8"))
    runtime_sections = {
        "merchant_bindings": runtime["merchant_bindings"],
        "capture_bindings": runtime["capture_bindings"],
    }
    runtime_hash = hashlib.sha256(
        json.dumps(runtime_sections, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if runtime_hash != lock["runtime_visual_sections_sha256"]:
        raise RuntimeError("Les liaisons dynamiques commerçant/captures du visuel T2 ont changé.")
    reference = lock["approved_reference"]
    canvas = config["canvas"]
    if (canvas["width"], canvas["height"], canvas["fps"], canvas["frames"]) != (
        reference["width"], reference["height"], 30, reference["frames"]
    ):
        raise RuntimeError("Le canevas 720×1280, 30 i/s, 900 images a changé.")
    for font in config["fonts"].values():
        if digest(ROOT / font["file"]) != font["sha256"]:
            raise RuntimeError(f"Police visuelle modifiée : {font['file']}")
    return lock


def main() -> None:
    lock = verify()
    print("T2_VISUAL_PIPELINE_LOCK_OK", len(lock["files"]), lock["approved_reference"]["video_stream_sha256"])


if __name__ == "__main__":
    main()
