"""Lecture déterministe des rushes et adaptation plein cadre 9:16."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np


@dataclass
class ClipSpec:
    path: Path
    start: float
    duration: float


class SequentialClip:
    """Lecteur monotone : évite 900 recherches aléatoires dans des sources 4K."""

    def __init__(self, spec: ClipSpec):
        self.spec = spec
        self.cap = cv2.VideoCapture(str(spec.path))
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Rush illisible : {spec.path}")
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if self.fps <= 0 or self.frame_count <= 0:
            raise ValueError(f"Métadonnées vidéo invalides : {spec.path}")
        self.start_frame = int(round(spec.start * self.fps))
        self.current_index = self.start_frame - 1
        self.current = None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

    def frame(self, local_seconds: float) -> np.ndarray:
        local_seconds = min(max(0.0, float(local_seconds)), self.spec.duration - 1e-4)
        wanted = self.start_frame + int(local_seconds * self.fps)
        wanted = min(wanted, self.frame_count - 1)
        if wanted < self.current_index:
            raise ValueError(
                f"Lecture non monotone de {self.spec.path.name}: {wanted} < {self.current_index}"
            )
        while self.current_index < wanted:
            ok, frame = self.cap.read()
            if not ok:
                break
            self.current = frame
            self.current_index += 1
        if self.current is None:
            ok, self.current = self.cap.read()
            if not ok:
                raise RuntimeError(f"Aucune image décodable : {self.spec.path}")
            self.current_index = wanted
        return self.current.copy()

    def close(self) -> None:
        self.cap.release()


def cover_9x16(
    frame: np.ndarray,
    width: int,
    height: int,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
) -> np.ndarray:
    """Recadre sans bandes noires puis applique un léger mouvement borné."""
    h, w = frame.shape[:2]
    target_ratio = width / height
    source_ratio = w / h
    if source_ratio > target_ratio:
        crop_h = h
        crop_w = int(round(h * target_ratio))
    else:
        crop_w = w
        crop_h = int(round(w / target_ratio))

    zoom = max(1.0, float(zoom))
    crop_w = max(2, int(crop_w / zoom))
    crop_h = max(2, int(crop_h / zoom))
    max_x = max(0, w - crop_w)
    max_y = max(0, h - crop_h)
    cx = w / 2 + np.clip(pan_x, -1, 1) * max_x * 0.35
    cy = h / 2 + np.clip(pan_y, -1, 1) * max_y * 0.35
    x0 = int(np.clip(cx - crop_w / 2, 0, max_x))
    y0 = int(np.clip(cy - crop_h / 2, 0, max_y))
    crop = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
    return cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA)


def warm_grade(frame: np.ndarray) -> np.ndarray:
    """Étalonnage T2 original, volontairement modéré et face-safe."""
    f = frame.astype(np.float32) / 255.0
    # Contraste doux.
    f = (f - 0.5) * 1.07 + 0.5
    # Chaleur : BGR.
    f[..., 0] *= 0.94
    f[..., 1] *= 1.01
    f[..., 2] *= 1.055
    # Saturation légère.
    gray = cv2.cvtColor(np.clip(f, 0, 1), cv2.COLOR_BGR2GRAY)[..., None]
    f = gray + (f - gray) * 1.08
    return np.clip(f * 255.0, 0, 255).astype(np.uint8)
