#!/usr/bin/env python3
"""Validation indépendante des quatre auditions produites sur GitHub Actions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from build_music_shortlist import validate_manifest


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def validate(manifest_path: Path, output_dir: Path, proof_path: Path) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Validation de production interdite hors GitHub Actions.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    if proof.get("status") != "valid" or proof.get("generated_on_github_actions") is not True:
        raise ValueError("Preuve GitHub Actions invalide.")
    if proof.get("source_audio_published") is not False:
        raise ValueError("Aucun MP3 source ne doit être publié.")
    if proof.get("final_selection") is not None or proof.get("future_voice_mix_active") is not False:
        raise ValueError("Une sélection ou un mix final a été activé trop tôt.")
    if proof.get("manifest_sha256") != sha256_file(manifest_path):
        raise ValueError("Le manifeste ne correspond pas à la preuve.")

    expected = {item["output_file"] for item in manifest["candidates"]}
    actual_media = {path.name for path in output_dir.glob("*.mp4")}
    if actual_media != expected:
        raise ValueError(f"Sorties inattendues: attendu={expected}, obtenu={actual_media}")
    if list(output_dir.glob("*.mp3")) or list(output_dir.glob("*.wav")) or list(output_dir.glob("*.m4a")):
        raise ValueError("Une source audio autonome a été trouvée dans les sorties.")

    auditions = proof.get("auditions", [])
    if [item.get("id") for item in auditions] != ["A", "B", "C", "D"]:
        raise ValueError("Les quatre preuves A/B/C/D sont requises.")
    base_hash = proof["approved_visual_base"]["video_stream_sha256"]
    for item in auditions:
        path = output_dir / item["output_file"]
        if sha256_file(path) != item["output_sha256"]:
            raise ValueError(f"SHA-256 invalide pour {path.name}")
        if item["video_stream_sha256"] != base_hash:
            raise ValueError(f"Le montage v0.3 a changé dans {path.name}")
        if item["video_frames"] != 900 or item["video_fps"] != "30/1":
            raise ValueError(f"Timeline invalide dans {path.name}")
        if item["audio_codec"] != "aac" or item["audio_sample_rate"] != 48000:
            raise ValueError(f"Audio d'audition invalide dans {path.name}")
        if not 29.95 <= float(item["duration_seconds"]) <= 30.05:
            raise ValueError(f"Durée d'audition invalide dans {path.name}")
    print("Shortlist T2 valide: 4 auditions dérivées, visuel v0.3 inchangé, aucune sélection finale.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    validate(args.manifest, args.output_dir, args.proof)
