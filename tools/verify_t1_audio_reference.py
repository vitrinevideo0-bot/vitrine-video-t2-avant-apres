#!/usr/bin/env python3
"""Vérifie sans écriture la référence audio T1 exacte utilisée par T2."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "baseline/T1_AUDIO_REFERENCE.lock.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    reference = args.path.resolve()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    head = subprocess.check_output(
        ["git", "-C", str(reference), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != lock["commit"]:
        raise SystemExit(f"Commit T1 inattendu: {head} != {lock['commit']}")
    for relative, expected in lock["files"].items():
        path = reference / relative
        if not path.is_file():
            raise SystemExit(f"Référence audio T1 absente: {relative}")
        actual = digest(path)
        if actual != expected:
            raise SystemExit(f"Référence audio T1 modifiée: {relative}: {actual} != {expected}")
        print("T1_AUDIO_FILE_OK", relative, actual)
    status = subprocess.check_output(
        ["git", "-C", str(reference), "status", "--porcelain"], text=True
    )
    if status:
        raise SystemExit("La copie T1 de référence a été modifiée.")
    print("T1_AUDIO_REFERENCE_READ_ONLY_OK", head)


if __name__ == "__main__":
    main()
