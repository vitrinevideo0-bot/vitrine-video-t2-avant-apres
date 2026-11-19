"""Textes dynamiques T2 liés au merchant_payload du RenderJob."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IVORY = (250, 247, 239, 255)
SOFT = (235, 226, 211, 245)
GREEN = (37, 211, 102, 255)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_text_config(config: dict[str, Any]) -> None:
    canvas = config["canvas"]
    if (canvas["width"], canvas["height"], canvas["fps"], canvas["frames"]) != (720, 1280, 30, 900):
        raise ValueError("Canevas texte T2 invalide.")
    graphics = config["graphics"]
    if [item["id"] for item in graphics] != [
        "T2_G01_IDENTITY",
        "T2_G02_OFFER",
        "T2_G03_REVEAL",
        "T2_G04_FINAL",
    ]:
        raise ValueError("Les quatre blocs de textes T2 sont incomplets.")
    for font in config["fonts"].values():
        path = ROOT / font["file"]
        if not path.is_file():
            raise FileNotFoundError(f"Police absente : {path}")
        if _sha256(path) != font["sha256"]:
            raise ValueError(f"Empreinte de police invalide : {path}")


def active_graphics(config: dict[str, Any], frame_index: int) -> list[dict[str, Any]]:
    return [
        item
        for item in config["graphics"]
        if int(item["start_f"]) <= frame_index < int(item["end_f_exclusive"])
    ]


def _font(config: dict[str, Any], key: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / config["fonts"][key]["file"]), size=int(size))


def _smoothstep(value: float) -> float:
    x = float(np.clip(value, 0.0, 1.0))
    return x * x * (3.0 - 2.0 * x)


def _progress(block: dict[str, Any], frame_index: int) -> float:
    start = int(block["start_f"])
    reveal_end = int(block["reveal_end_f"])
    return _smoothstep((frame_index - start + 1) / max(1, reveal_end - start))


def _opacity_envelope(block: dict[str, Any], frame_index: int) -> float:
    reveal = _progress(block, frame_index)
    end = int(block["end_f_exclusive"])
    if end == 900:
        return reveal
    fade_start = end - 18
    fade = 1.0 if frame_index < fade_start else _smoothstep((end - frame_index) / 18.0)
    return float(np.clip(reveal * fade, 0.0, 1.0))


def _fit_single(
    text: str,
    config: dict[str, Any],
    font_key: str,
    maximum: int,
    minimum: int,
    max_width: int,
) -> ImageFont.FreeTypeFont:
    size = maximum
    while size > minimum:
        font = _font(config, font_key, size)
        if font.getlength(text) <= max_width:
            return font
        size -= 1
    return _font(config, font_key, minimum)


def _balanced_lines(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if font.getlength(text) <= max_width:
        return [text]
    words = text.split()
    if len(words) < 2:
        return [text]
    best: tuple[float, list[str]] | None = None
    for cut in range(1, len(words)):
        lines = [" ".join(words[:cut]), " ".join(words[cut:])]
        widths = [font.getlength(line) for line in lines]
        score = max(widths) + abs(widths[0] - widths[1]) * 0.35
        if max(widths) <= max_width and (best is None or score < best[0]):
            best = (score, lines)
    return best[1] if best else [text]


def _draw_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: float,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int] = IVORY,
    stroke_width: int = 1,
) -> None:
    width = draw.textlength(text, font=font)
    x = (720 - width) / 2
    draw.text(
        (x + 3, y + 4),
        text,
        font=font,
        fill=(0, 0, 0, 145),
        stroke_width=stroke_width,
        stroke_fill=(0, 0, 0, 145),
    )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=(20, 14, 9, 190),
    )


def _format_price(value: str) -> str:
    clean = " ".join(value.strip().split())
    return clean if "FCFA" in clean.upper() else f"{clean} FCFA"


def _apply_scrim(frame_bgr: np.ndarray, top: float, bottom: float) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    top_curve = np.clip(1.0 - y / 0.55, 0.0, 1.0) * float(top)
    bottom_curve = np.clip((y - 0.45) / 0.55, 0.0, 1.0) * float(bottom)
    alpha = np.maximum(top_curve, bottom_curve)[..., None]
    dark = np.zeros((height, width, 3), dtype=np.float32)
    return np.clip(frame_bgr.astype(np.float32) * (1.0 - alpha) + dark * alpha, 0, 255).astype(np.uint8)


def _animate_layer(layer: Image.Image, progress: float, opacity: float, rise_px: int = 18) -> Image.Image:
    width, height = layer.size
    revealed = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    reveal_width = int(round(width * float(np.clip(progress, 0.0, 1.0))))
    if reveal_width > 0:
        revealed.paste(layer.crop((0, 0, reveal_width, height)), (0, 0))
    shift = int(round((1.0 - progress) * rise_px))
    if shift:
        moved = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        moved.alpha_composite(revealed, (0, shift))
        revealed = moved
    alpha = revealed.getchannel("A").point(lambda value: int(value * float(np.clip(opacity, 0.0, 1.0))))
    revealed.putalpha(alpha)
    return revealed


def _opening_layer(fields: dict[str, str], config: dict[str, Any]) -> Image.Image:
    layer = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    name = fields["nom"]
    signature = _fit_single(name, config, "signature", 106, 56, 620)
    _draw_center(draw, name, 170, signature, stroke_width=1)
    product = fields["produit"]
    display = _fit_single(product, config, "display", 48, 32, 580)
    _draw_center(draw, product, 345, display, fill=SOFT, stroke_width=1)
    return layer


def _offer_layer(fields: dict[str, str], config: dict[str, Any], progress: float) -> Image.Image:
    layer = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    product = fields["produit"]
    font = _fit_single(product, config, "display", 57, 36, 600)
    lines = _balanced_lines(product, font, 600)
    line_height = int(font.size * 1.08)
    start_y = 175 - int((1.0 - progress) * 18)
    for index, line in enumerate(lines):
        _draw_center(draw, line, start_y + index * line_height, font)
    price = _format_price(fields["prix"])
    price_font = _fit_single(price, config, "utility_bold", 66, 42, 560)
    scale_shift = int(round((1.0 - progress) * 22))
    _draw_center(draw, price, 870 + scale_shift, price_font, fill=IVORY, stroke_width=1)
    return layer


def _reveal_layer(fields: dict[str, str], config: dict[str, Any]) -> Image.Image:
    layer = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    hook = fields.get("accroche", "")
    if hook:
        font = _fit_single(hook, config, "display", 58, 38, 610)
        lines = _balanced_lines(hook, font, 610)
        for index, line in enumerate(lines):
            _draw_center(draw, line, 190 + index * int(font.size * 1.05), font)
    name_font = _fit_single(fields["nom"], config, "signature", 66, 44, 560)
    _draw_center(draw, fields["nom"], 385, name_font, fill=SOFT, stroke_width=1)
    return layer


def _final_layer(fields: dict[str, str], config: dict[str, Any], progress: float) -> Image.Image:
    layer = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    name_font = _fit_single(fields["nom"], config, "signature", 98, 52, 620)
    _draw_center(draw, fields["nom"], 105, name_font, stroke_width=1)

    product_font = _fit_single(fields["produit"], config, "display", 47, 31, 590)
    _draw_center(draw, fields["produit"], 295, product_font, fill=SOFT, stroke_width=1)

    price_font = _fit_single(_format_price(fields["prix"]), config, "utility_bold", 54, 38, 520)
    _draw_center(draw, _format_price(fields["prix"]), 850, price_font, stroke_width=1)

    support_font = _fit_single(fields["quartier"], config, "utility", 24, 18, 560)
    _draw_center(draw, fields["quartier"], 940, support_font, fill=SOFT, stroke_width=1)

    phone_font = _fit_single(fields["whatsapp"], config, "utility_bold", 32, 24, 500)
    phone_width = draw.textlength(fields["whatsapp"], font=phone_font)
    total_width = 18 + 14 + phone_width
    start_x = (720 - total_width) / 2
    phone_y = 1002
    draw.ellipse((start_x, phone_y + 10, start_x + 18, phone_y + 28), fill=GREEN)
    draw.text(
        (start_x + 32, phone_y),
        fields["whatsapp"],
        font=phone_font,
        fill=IVORY,
        stroke_width=1,
        stroke_fill=(20, 14, 9, 190),
    )
    return layer


def render_text_motion(
    frame_bgr: np.ndarray,
    frame_index: int,
    fields: dict[str, str],
    config: dict[str, Any],
) -> tuple[np.ndarray, list[str]]:
    """Applique les textes actifs après les transitions, donc toujours nets."""
    blocks = active_graphics(config, frame_index)
    if not blocks:
        return frame_bgr, []

    active_ids = [item["id"] for item in blocks]
    block = blocks[0]
    progress = _progress(block, frame_index)
    opacity = _opacity_envelope(block, frame_index)

    if block["id"] == "T2_G01_IDENTITY":
        frame_bgr = _apply_scrim(frame_bgr, top=0.48, bottom=0.05)
        layer = _opening_layer(fields, config)
        layer = _animate_layer(layer, progress, opacity, rise_px=20)
    elif block["id"] == "T2_G02_OFFER":
        frame_bgr = _apply_scrim(frame_bgr, top=0.42, bottom=0.52)
        layer = _offer_layer(fields, config, progress)
        layer = _animate_layer(layer, progress, opacity, rise_px=14)
    elif block["id"] == "T2_G03_REVEAL":
        frame_bgr = _apply_scrim(frame_bgr, top=0.52, bottom=0.08)
        layer = _reveal_layer(fields, config)
        layer = _animate_layer(layer, progress, opacity, rise_px=16)
    else:
        frame_bgr = _apply_scrim(frame_bgr, top=0.50, bottom=0.58)
        layer = _final_layer(fields, config, progress)
        layer = _animate_layer(layer, progress, opacity, rise_px=12)

    base = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    result = Image.alpha_composite(base, layer).convert("RGB")
    return cv2.cvtColor(np.asarray(result), cv2.COLOR_RGB2BGR), active_ids
