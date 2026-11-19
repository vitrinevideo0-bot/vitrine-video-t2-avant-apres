#!/usr/bin/env python3
"""Build the executable T2 12-screen capture contract without changing its images.

The existing PNG files remain the visual proofs. This module adds the programmer
handoff that makes A/B/C a deterministic state machine for the T2 Avant / Après
capture domain.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "capture-guide/consignes_T2.json"
UI_MANIFEST = ROOT / "ui-screens/manifest.json"
RUNTIME = ROOT / "config/T2_runtime_contract_v0_3_0.json"
OUTPUT = ROOT / "config/T2_capture_flow_v1_0_0.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def screen_triplet(scene: dict[str, Any], proof_by_state: dict[str, str]) -> list[dict[str, Any]]:
    n = int(scene["n"])
    total = int(scene["total"])
    seconds = int(scene["secondes"])
    scene_id = f"S{n}"
    common = {
        "scene_id": scene_id,
        "scene_index": n,
        "scene_total": total,
        "capture_duration_ms": seconds * 1000,
        "capture_slot": f"captures.{scene_id}",
    }
    next_guide = f"T2_CAPTURE_S{n + 1}_A_GUIDE" if n < total else "T2_RENDER_STATUS"
    accept_label = "SCÈNE SUIVANTE" if n < total else "VOIR MON AVANT / APRÈS"

    guide = {
        **common,
        "ordinal": (n - 1) * 3 + 1,
        "screen_id": f"T2_CAPTURE_S{n}_A_GUIDE",
        "route_key": f"t2.capture.s{n}.guide",
        "state": "A_GUIDE",
        "purpose": "expliquer la prise Avant / Après avant d'ouvrir l'enregistrement",
        "bindings": {
            "title": f"capture-guide/consignes_T2.json#/scenes/{n - 1}/titre",
            "instruction": f"capture-guide/consignes_T2.json#/scenes/{n - 1}/consigne",
            "film_list": f"capture-guide/consignes_T2.json#/scenes/{n - 1}/a_filmer",
            "avoid_list": f"capture-guide/consignes_T2.json#/scenes/{n - 1}/a_eviter",
            "action": "capture-guide/consignes_T2.json#/bouton_principal",
        },
        "resolved_text": {
            "scene_counter": f"SCÈNE {n}/{total}",
            "duration": f"{seconds} secondes",
            "title": scene["titre"],
            "instruction": scene["consigne"],
            "film_list": scene["a_filmer"],
            "avoid_list": scene["a_eviter"],
            "required_action": scene["ce_que_tu_dois_faire"],
            "voice_note": load(GUIDE)["mention_langues_commune"],
            "silence_note": load(GUIDE)["mention_silence_facultatif"],
            "optional_example": scene["exemple_facultatif"],
            "primary_action": load(GUIDE)["bouton_principal"],
        },
        "visible_components": [
            "camera_preview_dimmed",
            "scene_progress",
            "instruction_sheet",
            "film_list",
            "avoid_list",
            "voice_note",
            "optional_example",
            "start_recording_button",
        ],
        "forbidden_components": ["recording_timer", "review_actions", "subtitles"],
        "actions": [
            {
                "event": "START_RECORDING",
                "effects": ["request_camera_permission", "request_microphone_permission", "run_COUNTDOWN_3_2_1"],
                "next_screen_id": f"T2_CAPTURE_S{n}_B_RECORDING",
            }
        ],
        "proof_png": f"ui-screens/{proof_by_state['A_GUIDE']}",
    }
    recording = {
        **common,
        "ordinal": (n - 1) * 3 + 2,
        "screen_id": f"T2_CAPTURE_S{n}_B_RECORDING",
        "route_key": f"t2.capture.s{n}.recording",
        "state": "B_RECORDING",
        "purpose": "capturer exactement la durée T2, image et microphone à vitesse naturelle",
        "bindings": {
            "elapsed_ms": "runtime.capture.elapsed_ms",
            "progress_0_to_1": "runtime.capture.progress",
            "output_uri": f"runtime.captures.{scene_id}.uri",
        },
        "visible_components": ["camera_preview", "microphone_active", "recording_timer", "recording_progress"],
        "forbidden_components": [
            "instruction_sheet",
            "merchant_fields",
            "example_text",
            "manual_stop_button",
            "review_actions",
            "subtitles",
        ],
        "capture": {
            "starts_after": "COUNTDOWN_3_2_1_COMPLETE",
            "video": True,
            "microphone_audio": True,
            "source_speed": 1.0,
            "source_time_map": "identity",
            "audio_time_map": "identity",
            "duration_ms": seconds * 1000,
            "auto_stop": True,
            "manual_stop": False,
            "write_to": f"runtime.captures.{scene_id}.uri",
        },
        "actions": [
            {
                "event": "CAPTURE_DURATION_REACHED",
                "effects": ["stop_recorder", "finalize_capture_file", "probe_capture_metadata", "open_audio_review"],
                "next_screen_id": f"T2_CAPTURE_S{n}_C_REVIEW",
            }
        ],
        "proof_png": f"ui-screens/{proof_by_state['B_RECORDING']}",
    }
    review = {
        **common,
        "ordinal": (n - 1) * 3 + 3,
        "screen_id": f"T2_CAPTURE_S{n}_C_REVIEW",
        "route_key": f"t2.capture.s{n}.review",
        "state": "C_REVIEW",
        "purpose": "relire avec le son et accepter ou refaire la prise",
        "bindings": {
            "preview_uri": f"runtime.captures.{scene_id}.uri",
            "capture_metadata": f"runtime.captures.{scene_id}.metadata",
        },
        "visible_components": [
            "captured_video_preview",
            "captured_audio_playback",
            "take_label",
            "redo_button",
            "accept_button",
        ],
        "forbidden_components": ["instruction_sheet", "recording_timer", "recording_progress", "subtitles"],
        "playback": {"audio": True, "loop": True, "source_speed": 1.0},
        "actions": [
            {
                "event": "RETAKE",
                "label": "REFAIRE",
                "effects": [f"delete:runtime.captures.{scene_id}", "reset_scene_capture_state"],
                "next_screen_id": f"T2_CAPTURE_S{n}_A_GUIDE",
            },
            {
                "event": "ACCEPT_CAPTURE",
                "label": accept_label,
                "effects": [f"persist:runtime.captures.{scene_id}", "mark_capture_accepted"],
                "next_screen_id": next_guide,
            },
        ],
        "proof_png": f"ui-screens/{proof_by_state['C_REVIEW']}",
    }
    return [guide, recording, review]


def build_contract() -> dict[str, Any]:
    guide = load(GUIDE)
    ui = load(UI_MANIFEST)
    runtime = load(RUNTIME)
    proof_lookup: dict[int, dict[str, str]] = {}
    for item in ui["screens"]:
        proof_lookup.setdefault(int(item["scene"]), {})[item["state"]] = item["file"]
    screens: list[dict[str, Any]] = []
    for scene in guide["scenes"]:
        screens.extend(screen_triplet(scene, proof_lookup[int(scene["n"])]))
    return {
        "schema_version": "1.0.0",
        "id": "restaurants_maquis_T2_avant_apres_capture_flow_v1_0_0",
        "template_id": "restaurants_maquis_T2_avant_apres_v0_1_0",
        "domain": "AVANT_APRES",
        "source_guide": {"path": "capture-guide/consignes_T2.json", "sha256": sha256(GUIDE)},
        "visual_proof_manifest": {"path": "ui-screens/manifest.json", "sha256": sha256(UI_MANIFEST)},
        "counts": {"scenes": 4, "states_per_scene": 3, "stable_capture_screens": 12},
        "transient_states": [
            {
                "id": "COUNTDOWN_3_2_1",
                "counted_in_12_stable_screens": False,
                "sequence": [3, 2, 1],
                "trigger": "START_RECORDING",
                "then": "B_RECORDING",
                "must_not_be_written_into_capture": True,
            }
        ],
        "screens": screens,
        "session_model": {
            "name": "T2AvantApresSession",
            "fields": ["merchant_payload", "captures", "current_screen_id", "accepted_scene_ids"],
            "persistence": "persist accepted content URIs and probed media metadata until RenderJob submission",
        },
        "events": [
            "START_RECORDING",
            "COUNTDOWN_COMPLETE",
            "CAPTURE_DURATION_REACHED",
            "RETAKE",
            "ACCEPT_CAPTURE",
        ],
        "renderer_handoff": {
            "entry_point": "submit the unified RenderJob after S4 ACCEPT_CAPTURE",
            "merchant_bindings": runtime["merchant_bindings"],
            "capture_bindings": runtime["capture_bindings"],
            "required_capture_metadata": [
                "uri",
                "mime_type",
                "video_codec",
                "width",
                "height",
                "fps",
                "frame_count",
                "duration_ms",
                "rotation_degrees",
                "has_audio",
                "audio_codec",
                "sha256",
            ],
        },
        "acceptance_gates": [
            "exactly 12 unique stable screen IDs in S1A,S1B,S1C ... S4A,S4B,S4C order",
            "countdown is transient and never a thirteenth stable screen",
            "recording auto-stops at 6000, 8000, 7000 and 9000 ms",
            "review always plays with sound at 1x and offers RETAKE plus ACCEPT_CAPTURE",
            "S4 acceptance routes to T2_RENDER_STATUS",
            "all four accepted captures include complete media metadata before RenderJob submission",
            "no automatic subtitles",
        ],
    }


def main() -> None:
    contract = build_contract()
    OUTPUT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("T2_CAPTURE_FLOW_CONTRACT_OK", OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
