#!/usr/bin/env python3
"""Vérifie la référence T1 sans jamais y écrire."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED = "c656510ab81d31d413dc4dfd74b42671532cd978"
REQUIRED = [
    "capture-guide/consignes_T1.json",
    "config/T1_special_menu_reference_v3_1.json",
    "config/T1_special_menu_template_v1_0_0.json",
    "schemas/T1_render_job.schema.json",
    "tools",
    ".github/workflows",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    root = Path(args.path)
    head = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if head != EXPECTED:
        raise SystemExit(f"Commit T1 inattendu : {head} != {EXPECTED}")
    for relative in REQUIRED:
        if not (root / relative).exists():
            raise SystemExit(f"Référence T1 absente : {relative}")
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain"],
        text=True,
    )
    if status:
        raise SystemExit("La copie de référence T1 a été modifiée.")
    print("T1_BASELINE_READ_ONLY_OK", head)


if __name__ == "__main__":
    main()
