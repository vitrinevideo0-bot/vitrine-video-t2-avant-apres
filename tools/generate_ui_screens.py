#!/usr/bin/env python3
"""Produit les états B/C et la planche de contrôle des 12 écrans stables."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engine.media import cover_9x16, warm_grade

W, H = 720, 1280
OUT = ROOT / "ui-screens"
FONT = ROOT / "assets/fonts/DejaVuSans.ttf"
BOLD = ROOT / "assets/fonts/DejaVuSans-Bold.ttf"
SCENES = [
    (1, 6, "L'AVANT", "VOIT-ON CLAIREMENT L'AVANT ?", "SCÈNE SUIVANTE"),
    (2, 8, "LA TRANSFORMATION", "VOIT-ON LE GESTE DU DÉBUT À LA FIN ?", "SCÈNE SUIVANTE"),
    (3, 7, "LA RÉVÉLATION", "VOIT-ON LE PLAT FINI AU MOINS 2 SECONDES ?", "SCÈNE SUIVANTE"),
    (4, 9, "L'APRÈS", "LE PLAT FINI ET LA PERSONNE SONT-ILS BIEN VISIBLES ?", "VOIR MON AVANT / APRÈS"),
]


def source_frame(scene: int):
    manifest = json.loads((ROOT / "rushes/manifest.json").read_text())
    src = manifest["sources"][scene - 1]
    path = ROOT / src["local_file"]
    cap = cv2.VideoCapture(str(path))
    at = src["edit"]["start"] + src["edit"]["duration"] * 0.58
    cap.set(cv2.CAP_PROP_POS_MSEC, at * 1000)
    ok, frame = cap.read(); cap.release()
    if not ok:
        raise RuntimeError(path)
    frame = warm_grade(cover_9x16(frame, W, H, 1.035))
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def text_center(draw, y, text, font, fill="white"):
    width = draw.textlength(text, font=font)
    draw.text(((W - width) / 2, y), text, font=font, fill=fill)


def recording(scene, seconds, title):
    im = source_frame(scene).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 20)); im.alpha_composite(shade)
    d = ImageDraw.Draw(im)
    bold = ImageFont.truetype(str(BOLD), 25); timer = ImageFont.truetype(str(BOLD), 52)
    d.rounded_rectangle((25, 24, 202, 70), 22, fill=(8, 8, 8, 178))
    d.text((43, 34), f"SCÈNE {scene}/4", font=bold, fill="white")
    d.rounded_rectangle((W - 145, 24, W - 25, 70), 22, fill=(160, 20, 18, 230))
    d.ellipse((W - 130, 42, W - 117, 55), fill="white")
    d.text((W - 106, 34), "REC", font=bold, fill="white")
    elapsed = seconds // 2
    text_center(d, H - 160, f"0:{elapsed:02d} / 0:{seconds:02d}", timer)
    x0, x1, y = 44, W - 44, H - 82
    d.rounded_rectangle((x0, y, x1, y + 12), 6, fill=(255, 255, 255, 95))
    d.rounded_rectangle((x0, y, x0 + (x1-x0) * (elapsed/seconds), y + 12), 6, fill=(232, 79, 50, 255))
    return im.convert("RGB")


def review(scene, seconds, title, question, positive):
    im = source_frame(scene).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 155), fill=(8, 8, 8, 188))
    od.rectangle((0, H - 340, W, H), fill=(8, 8, 8, 205))
    im.alpha_composite(overlay)
    d = ImageDraw.Draw(im)
    bold = ImageFont.truetype(str(BOLD), 27); small = ImageFont.truetype(str(FONT), 21)
    text_center(d, 35, f"PRISE {scene} · 0:{seconds:02d}", bold)
    text_center(d, 82, "🔊  SON ACTIVÉ", small, fill=(230, 232, 225))
    # Question sur deux lignes si nécessaire.
    words = question.split(); lines=[]; cur=""
    for word in words:
        test = word if not cur else cur+" "+word
        if d.textlength(test, font=bold) < W-70: cur=test
        else: lines.append(cur);cur=word
    if cur: lines.append(cur)
    y=H-300
    for line in lines:
        text_center(d,y,line,bold);y+=38
    d.rounded_rectangle((34,H-165,255,H-87),24,fill=(70,64,60,245),outline=(235,225,213,255),width=2)
    d.text((79,H-139),"REFAIRE",font=bold,fill="white")
    d.rounded_rectangle((275,H-165,W-34,H-87),24,fill=(190,62,37,255))
    pfont = ImageFont.truetype(str(BOLD), 21 if scene<4 else 18)
    pw=d.textlength(positive,font=pfont);d.text((275+(W-34-275-pw)/2,H-137),positive,font=pfont,fill="white")
    return im.convert("RGB")


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    records=[]
    for scene, seconds, title, question, positive in SCENES:
        a=OUT/f"T2_CAPTURE_S{scene}_A_GUIDE.png"
        if not a.exists(): raise SystemExit(f"Guide absent: {a}")
        b=OUT/f"T2_CAPTURE_S{scene}_B_RECORDING.png";recording(scene,seconds,title).save(b,optimize=True)
        c=OUT/f"T2_CAPTURE_S{scene}_C_REVIEW.png";review(scene,seconds,title,question,positive).save(c,optimize=True)
        for state,p in (("A_GUIDE",a),("B_RECORDING",b),("C_REVIEW",c)):
            records.append({"scene":scene,"state":state,"file":p.name,"size":[W,H],"sha256":sha(p)})

    # Planche 4 lignes × 3 états, chaque écran réduit à 270 × 480.
    tw,th=270,480;pad=22;header=86
    board=Image.new("RGB",(3*tw+4*pad,4*th+5*pad+header),(235,227,216));d=ImageDraw.Draw(board)
    tf=ImageFont.truetype(str(BOLD),28);sf=ImageFont.truetype(str(FONT),17)
    d.text((pad,18),"T2 — EXACTEMENT 12 ÉCRANS STABLES",font=tf,fill=(42,32,28))
    d.text((pad,56),"4 scènes × A Guide · B Enregistrement · C Validation",font=sf,fill=(94,76,65))
    for i,r in enumerate(records):
        row=i//3;col=i%3;x=pad+col*(tw+pad);y=header+pad+row*(th+pad)
        im=Image.open(OUT/r["file"]).resize((tw,th),Image.Resampling.LANCZOS);board.paste(im,(x,y))
    board_path=OUT/"T2_PLANCHE_12_ECRANS.png";board.save(board_path,optimize=True)
    manifest={"stable_screen_count":12,"states":["A_GUIDE","B_RECORDING","C_REVIEW"],"screens":records,"board":board_path.name,"board_sha256":sha(board_path)}
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print("UI_12_SCREENS_OK")


if __name__ == "__main__":
    main()
