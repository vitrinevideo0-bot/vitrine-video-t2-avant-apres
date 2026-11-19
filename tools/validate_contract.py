#!/usr/bin/env python3
"""Contrôle rapide et bloquant du contrat T2."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"ERREUR: {message}")


def main() -> None:
    cfg = json.loads((ROOT / "config/T2_avant_apres_template_v0_1_0.json").read_text(encoding="utf-8"))
    guide = json.loads((ROOT / "capture-guide/consignes_T2.json").read_text(encoding="utf-8"))
    job = json.loads((ROOT / "demo/input_demo.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "rushes/manifest.json").read_text(encoding="utf-8"))

    if [x["seconds"] for x in cfg["scenes"]] != [6, 8, 7, 9]:
        fail("durées des scènes")
    if sum(x["seconds"] for x in cfg["scenes"]) != 30:
        fail("durée totale")
    if cfg["stable_screen_count"] != 12 or len(cfg["scenes"]) * len(cfg["capture_states"]) != 12:
        fail("exactement 12 écrans stables")
    events = cfg["transition_budget"]["events"]
    if len(events) != 6:
        fail("six transitions requises")
    refs = [x["reference"] for x in events]
    if any(refs.count(ref) != 2 for ref in (1, 2, 3)):
        fail("deux transitions par référence")
    if abs(cfg["transition_budget"]["duration_each_seconds"] * 2 - 0.84) > 1e-9:
        fail("équilibre 0,84 s par référence")
    if cfg["output"] != {"width": 720, "height": 1280, "fps": 30, "frames": 900, "duration_seconds": 30, "pixel_format": "yuv420p", "audio_sample_rate": 44100}:
        fail("contrat de sortie")

    mention = "Tu peux parler pendant que tu filmes, dans la langue que tu veux : fon, yoruba, français, anglais ou une autre langue que tu maîtrises."
    if guide["mention_langues_commune"] != mention:
        fail("mention linguistique exacte")
    if len(guide["scenes"]) != 4 or [x["secondes"] for x in guide["scenes"]] != [6, 8, 7, 9]:
        fail("quatre guides")
    if guide["audio"] != {"parole_obligatoire": False, "conserver_voix_capturee": True, "sous_titres_automatiques": False}:
        fail("règles audio")
    if any(not x["exemple_facultatif"].strip() for x in guide["scenes"]):
        fail("exemple par scène")

    props = cfg["merchant_fields"]["properties"]
    for key, value in job["business"].items():
        rule = props[key]
        if not rule.get("minLength", 0) <= len(value) <= rule["maxLength"]:
            fail(f"longueur {key}")
    if not re.fullmatch(props["prix"]["pattern"], job["business"]["prix"]):
        fail("format prix")
    if len(manifest["sources"]) != 4 or [x["scene"] for x in manifest["sources"]] != [1, 2, 3, 4]:
        fail("quatre rushes")

    print("T2_CONTRACT_OK")


if __name__ == "__main__":
    main()
