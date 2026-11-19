#!/usr/bin/env python3
"""Planche GitHub de contrôle des textes, de leur police et de leurs mouvements."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TIMES = [0.60, 1.00, 1.60, 2.40, 4.80, 7.00, 7.80, 9.00, 11.50, 15.00, 16.00, 17.50, 19.50, 22.00, 23.00, 24.50, 26.00, 28.00, 29.50]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    args = parser.parse_args()
    path = Path(args.video)
    if not path.is_absolute():
        path = ROOT / path

    label_font = ImageFont.truetype(str(ROOT / "assets/fonts/DejaVuSans.ttf"), 17)
    cap = cv2.VideoCapture(str(path))
    cards = []
    for time_seconds in TIMES:
        cap.set(cv2.CAP_PROP_POS_MSEC, time_seconds * 1000)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"Image illisible à {time_seconds:.2f} s")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame).resize((216, 384))
        card = Image.new("RGB", (216, 414), "white")
        card.paste(image, (0, 30))
        ImageDraw.Draw(card).text((7, 5), f"{time_seconds:05.2f} s", font=label_font, fill="black")
        cards.append(card)
    cap.release()

    columns = 5
    rows = math.ceil(len(cards) / columns)
    board = Image.new("RGB", (columns * 216, rows * 414), (225, 220, 211))
    for index, card in enumerate(cards):
        board.paste(card, ((index % columns) * 216, (index // columns) * 414))
    output = ROOT / "proofs/T2_TEXTES_POLICE_MOTION_CONTACT_SHEET.jpg"
    output.parent.mkdir(exist_ok=True)
    board.save(output, quality=94)
    print(output)


if __name__ == "__main__":
    main()
