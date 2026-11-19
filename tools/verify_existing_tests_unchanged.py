#!/usr/bin/env python3
"""Fail if any of the four tests that predate the unified runtime was edited."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "baseline/T2_EXISTING_TESTS.lock.json"


def main() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    for relative, expected in lock["files"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"TEST_EXISTANT_MODIFIE {relative} {actual} != {expected}")
        print("T2_EXISTING_TEST_UNCHANGED", relative, actual)


if __name__ == "__main__":
    main()
