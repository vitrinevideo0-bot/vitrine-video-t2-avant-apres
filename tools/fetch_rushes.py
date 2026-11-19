#!/usr/bin/env python3
"""Télécharge les quatre rushes Pexels autorisés et vérifie leurs empreintes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "rushes/manifest.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for src in data["sources"]:
        target = ROOT / src["local_file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target) == src["sha256"]:
            print(f"OK cache {target.name}")
            continue
        temp = target.with_suffix(".part")
        request = urllib.request.Request(src["download"], headers={"User-Agent": "Mozilla/5.0 VitrineVideoT2/0.1"})
        print(f"Téléchargement S{src['scene']} — {src['title']}")
        with urllib.request.urlopen(request, timeout=90) as response, temp.open("wb") as out:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                out.write(block)
        actual = digest(temp)
        if actual != src["sha256"]:
            temp.unlink(missing_ok=True)
            raise SystemExit(f"SHA-256 incorrect pour {src['pexels_id']}: {actual}")
        temp.replace(target)
        print(f"OK {target.name} {actual}")


if __name__ == "__main__":
    main()
