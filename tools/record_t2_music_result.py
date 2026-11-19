#!/usr/bin/env python3
"""Persist the selected T2 music only when the render succeeded."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.complete_adapter import record_music_render_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--render-job-id", required=True)
    parser.add_argument("--selected-music-id", choices=["A", "B", "C", "D"], required=True)
    parser.add_argument("--status", choices=["success", "failed"], required=True)
    args = parser.parse_args()
    state = record_music_render_result(
        state_path=args.state,
        render_job_id=args.render_job_id,
        selected_music_id=args.selected_music_id,
        succeeded=args.status == "success",
    )
    print(json.dumps(state, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
