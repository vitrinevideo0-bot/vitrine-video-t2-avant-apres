#!/usr/bin/env python3
"""Moteur Python de référence T2 « Avant / Après ».

Il assemble exactement quatre rushes en 30 secondes verticales, applique six
transitions originales et produit une démonstration H.264/AAC. Les vidéos de
référence CapCut ne sont jamais lues, importées ni redistribuées.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.audio import generate_demo_music
from engine.media import ClipSpec, SequentialClip, cover_9x16, warm_grade
from engine.transitions import (
    center_window_expand,
    diagonal_desaturated_to_color,
    intro_oblique,
    oblique_shutters,
    staggered_bands,
    warm_flash,
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def format_price(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return value.strip()
    return f"{int(digits):,}".replace(",", " ") + " FCFA"


def blend_rgba(frame: np.ndarray, overlay: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    opacity = float(np.clip(opacity, 0, 1))
    alpha = overlay[..., 3:4].astype(np.float32) / 255.0 * opacity
    bgr = overlay[..., :3][..., ::-1].astype(np.float32)
    out = frame.astype(np.float32) * (1 - alpha) + bgr * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def event_alpha(t: float, start: float, end: float, fade: float = 0.24) -> float:
    if t < start or t >= end:
        return 0.0
    return min(1.0, (t - start) / fade, (end - t) / fade)


class OverlayComposer:
    def __init__(self, width: int, height: int, business: dict[str, str]):
        self.w, self.h = width, height
        self.business = business
        self.display_path = ROOT / "assets/fonts/PlayfairDisplay[wght].ttf"
        self.sans_path = ROOT / "assets/fonts/DejaVuSans.ttf"
        self.bold_path = ROOT / "assets/fonts/DejaVuSans-Bold.ttf"
        self.layers: list[tuple[float, float, np.ndarray]] = []
        self._build()

    def _font(self, path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
        font = ImageFont.truetype(str(path), size)
        if weight is not None:
            try:
                font.set_variation_by_axes([weight])
            except Exception:
                pass
        return font

    def _canvas(self) -> Image.Image:
        return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))

    def _condensed_title(self, text: str, y: int, size: int = 100) -> np.ndarray:
        canvas = self._canvas()
        font = self._font(self.display_path, size, 900)
        probe = Image.new("L", (2400, 300), 0)
        pd = ImageDraw.Draw(probe)
        box = pd.textbbox((0, 0), text, font=font, stroke_width=1)
        pd.text((-box[0] + 8, -box[1] + 8), text, font=font, fill=255, stroke_width=1)
        crop = probe.crop(probe.getbbox())
        crop = crop.resize((max(1, int(crop.width * 0.66)), crop.height), Image.Resampling.LANCZOS)
        max_w = self.w - 80
        if crop.width > max_w:
            scale = max_w / crop.width
            crop = crop.resize((max_w, max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
        x = (self.w - crop.width) // 2
        # Ombre et voile local pour une lecture constante.
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((28, y - 25, self.w - 28, y + crop.height + 27), radius=25, fill=(8, 7, 6, 112))
        shadow = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        shadow.paste((0, 0, 0, 175), (0, 0, crop.width, crop.height), crop)
        canvas.alpha_composite(shadow, (x + 3, y + 4))
        white = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        white.paste((255, 249, 242, 255), (0, 0, crop.width, crop.height), crop)
        canvas.alpha_composite(white, (x, y))
        return np.array(canvas)

    def _pill(self, lines: list[str], y: int, accent: tuple[int, int, int] = (232, 164, 72), size: int = 38) -> np.ndarray:
        canvas = self._canvas()
        draw = ImageDraw.Draw(canvas)
        font = self._font(self.bold_path, size)
        small = self._font(self.sans_path, max(24, size - 9))
        heights = []
        widths = []
        for i, line in enumerate(lines):
            f = font if i == 0 else small
            b = draw.textbbox((0, 0), line, font=f)
            widths.append(b[2] - b[0])
            heights.append(b[3] - b[1])
        card_h = sum(heights) + 24 * (len(lines) - 1) + 44
        draw.rounded_rectangle((36, y, self.w - 36, y + card_h), radius=26, fill=(12, 10, 9, 185), outline=accent + (235,), width=3)
        cy = y + 22
        for i, (line, th) in enumerate(zip(lines, heights)):
            f = font if i == 0 else small
            color = (255, 248, 239, 255) if i == 0 else (238, 226, 213, 255)
            tw = draw.textlength(line, font=f)
            draw.text(((self.w - tw) / 2, cy), line, font=f, fill=color)
            cy += th + 24
        return np.array(canvas)

    def _cta(self) -> np.ndarray:
        b = self.business
        return self._pill(
            [
                "COMMANDES WHATSAPP",
                b["whatsapp"],
                f"{b['produit']} · {format_price(b['prix'])}",
                b["quartier"],
            ],
            y=865,
            accent=(226, 121, 58),
            size=39,
        )

    def _build(self) -> None:
        b = self.business
        self.layers.extend(
            [
                (0.42, 1.80, self._condensed_title("AVANT", 175, 122)),
                (1.80, 5.58, self._pill([b["produit"]], 1020, size=42)),
                (6.24, 9.58, self._condensed_title("LA TRANSFORMATION", 158, 84)),
                (10.24, 13.58, self._pill([b.get("accroche", "")], 1010, size=38)) if b.get("accroche") else None,
                (14.24, 16.48, self._condensed_title("APRÈS", 175, 122)),
                (16.48, 20.62, self._pill([b["produit"], format_price(b["prix"])], 955, size=42)),
                (21.24, 24.78, self._condensed_title(b["nom"].upper(), 160, 92)),
                (24.78, 26.98, self._pill([b["quartier"]], 1020, size=36)),
                (27.00, 30.00, self._cta()),
            ]
        )
        self.layers = [x for x in self.layers if x is not None]

    def apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        out = frame
        for start, end, layer in self.layers:
            a = event_alpha(t, start, end)
            if a > 0:
                out = blend_rgba(out, layer, a)
        return out


def load_job(job_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config/T2_avant_apres_template_v0_1_0.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / job["rush_manifest"]).read_text(encoding="utf-8"))
    return job, config, manifest


def render(job_path: Path, keep_intermediates: bool = False) -> Path:
    job, config, manifest = load_job(job_path)
    out_cfg = config["output"]
    width, height = int(out_cfg["width"]), int(out_cfg["height"])
    fps, frame_total = int(out_cfg["fps"]), int(out_cfg["frames"])
    output = ROOT / job["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_video = output.with_suffix(".silent.mp4")
    temp_audio = output.with_suffix(".wav")

    clips: list[SequentialClip] = []
    for src in sorted(manifest["sources"], key=lambda x: x["scene"]):
        path = ROOT / src["local_file"]
        actual = sha256(path)
        if actual != src["sha256"]:
            raise ValueError(f"SHA-256 inattendu pour {path.name}: {actual}")
        clips.append(
            SequentialClip(
                ClipSpec(path=path, start=float(src["edit"]["start"]), duration=float(src["edit"]["duration"]))
            )
        )

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Impossible d'ouvrir VideoWriter")
    overlay = OverlayComposer(width, height, job["business"])
    scene_durations = [6.0, 8.0, 7.0, 9.0]
    scene_starts = [0.0, 6.0, 14.0, 21.0]

    def scene_frame(index: int, local: float) -> np.ndarray:
        duration = scene_durations[index]
        p = np.clip(local / duration, 0, 1)
        zooms = [(1.015, 1.070), (1.035, 1.055), (1.020, 1.055), (1.018, 1.050)]
        z0, z1 = zooms[index]
        pan_x = [(-0.12 + 0.22 * p), (0.08 - 0.12 * p), (-0.06 + 0.12 * p), 0.0][index]
        pan_y = [0.02, (-0.08 + 0.14 * p), 0.01, (-0.03 + 0.07 * p)][index]
        raw = clips[index].frame(local)
        return warm_grade(cover_9x16(raw, width, height, z0 + (z1 - z0) * p, pan_x, pan_y))

    try:
        for frame_index in range(frame_total):
            t = frame_index / fps
            if t < 6.0:
                idx = 0
            elif t < 14.0:
                idx = 1
            elif t < 21.0:
                idx = 2
            else:
                idx = 3
            frame = scene_frame(idx, t - scene_starts[idx])

            if 0.0 <= t < 0.42:
                frame = intro_oblique(frame, t / 0.42)
            if 5.79 <= t < 6.21:
                a = scene_frame(0, min(5.999, t))
                b = scene_frame(1, max(0.0, t - 6.0))
                frame = center_window_expand(a, b, (t - 5.79) / 0.42)
            if 9.79 <= t < 10.21:
                frame = warm_flash(frame, (t - 9.79) / 0.42)
            if 13.79 <= t < 14.21:
                a = scene_frame(1, min(7.999, max(0.0, t - 6.0)))
                b = scene_frame(2, max(0.0, t - 14.0))
                frame = oblique_shutters(a, b, (t - 13.79) / 0.42)
            if 17.29 <= t < 17.71:
                frame = staggered_bands(frame, (t - 17.29) / 0.42)
            if 20.79 <= t < 21.21:
                a = scene_frame(2, min(6.999, max(0.0, t - 14.0)))
                b = scene_frame(3, max(0.0, t - 21.0))
                frame = diagonal_desaturated_to_color(a, b, (t - 20.79) / 0.42)

            frame = overlay.apply(frame, t)
            writer.write(frame)
            if frame_index % 90 == 0:
                print(f"rendu {frame_index:03d}/{frame_total}", flush=True)
    finally:
        writer.release()
        for clip in clips:
            clip.close()

    generate_demo_music(temp_audio, duration=30.0, sr=int(out_cfg["audio_sample_rate"]))
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("imageio-ffmpeg est requis pour encoder H.264/AAC") from exc

    cmd = [
        ffmpeg,
        "-y",
        "-i", str(temp_video),
        "-i", str(temp_audio),
        "-t", "30.000",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-metadata", "title=T2 Avant Apres - demonstration transitions",
        "-metadata", "comment=Montage original Vitrine Video T2 v0.1.0",
        str(output),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"Échec ffmpeg\n{proc.stderr[-4000:]}")

    cap = cv2.VideoCapture(str(output))
    observed = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": float(cap.get(cv2.CAP_PROP_FPS)),
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    observed["duration_seconds"] = observed["frames"] / observed["fps"]
    report = {
        "template_id": config["render_template_id"],
        "version": config["version"],
        "output": str(output.relative_to(ROOT)),
        "sha256": sha256(output),
        "bytes": output.stat().st_size,
        "observed": observed,
        "transition_events": config["transition_budget"]["events"],
        "transition_balance_seconds": {"reference_1": 0.84, "reference_2": 0.84, "reference_3": 0.84},
        "source_rushes_verified": [
            {"scene": x["scene"], "pexels_id": x["pexels_id"], "sha256": x["sha256"]}
            for x in manifest["sources"]
        ],
        "audio": {
            "music": "original_programmatic_120_bpm",
            "source_samples": 0,
            "production_contract_preserves_merchant_voice": True,
            "automatic_subtitles": False,
        },
    }
    proofs = ROOT / "proofs"
    proofs.mkdir(exist_ok=True)
    (proofs / "render_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not keep_intermediates:
        temp_video.unlink(missing_ok=True)
        temp_audio.unlink(missing_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", default="demo/input_demo.json")
    parser.add_argument("--keep-intermediates", action="store_true")
    args = parser.parse_args()
    path = Path(args.job)
    if not path.is_absolute():
        path = ROOT / path
    output = render(path, args.keep_intermediates)
    print(f"OK {output}")


if __name__ == "__main__":
    main()
