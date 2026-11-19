"""Six transitions originales T2, abstraites des trois références validées."""
from __future__ import annotations

import cv2
import numpy as np


def smoothstep(x: float) -> float:
    x = float(np.clip(x, 0.0, 1.0))
    return x * x * (3.0 - 2.0 * x)


def _mix(a: np.ndarray, b: np.ndarray, alpha: np.ndarray | float) -> np.ndarray:
    af = a.astype(np.float32)
    bf = b.astype(np.float32)
    if isinstance(alpha, np.ndarray) and alpha.ndim == 2:
        alpha = alpha[..., None]
    return np.clip(af * (1.0 - alpha) + bf * alpha, 0, 255).astype(np.uint8)


def intro_oblique(frame: np.ndarray, progress: float) -> np.ndarray:
    """T01 — deux ouvertures obliques asymétriques depuis le noir."""
    p = smoothstep(progress)
    h, w = frame.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    diagonal = xx - 0.16 * (yy - h / 2)
    half = p * w * 0.68
    primary = np.abs(diagonal - w * 0.47) <= half
    p2 = smoothstep((progress - 0.13) / 0.87)
    secondary = np.abs((xx + 0.11 * yy) - w * 0.58) <= p2 * w * 0.58
    mask = np.maximum(primary.astype(np.float32), secondary.astype(np.float32))
    return _mix(np.zeros_like(frame), frame, mask)


def center_window_expand(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """T02 — une fenêtre centrale s'étend, sans mosaïque stable."""
    p = smoothstep(progress)
    h, w = outgoing.shape[:2]
    muted = cv2.GaussianBlur(outgoing, (0, 0), sigmaX=4.0)
    gray = cv2.cvtColor(muted, cv2.COLOR_BGR2GRAY)
    muted = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    muted = _mix(muted, outgoing, 0.32)
    rw = max(2, int(w * (0.12 + 0.88 * p)))
    rh = max(2, int(h * (0.18 + 0.82 * p)))
    x0, y0 = (w - rw) // 2, (h - rh) // 2
    mask = np.zeros((h, w), np.float32)
    cv2.rectangle(mask, (x0, y0), (x0 + rw, y0 + rh), 1.0, thickness=-1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=1.4)
    out = _mix(muted, incoming, mask)
    if p < 0.98:
        cv2.rectangle(out, (x0, y0), (x0 + rw, y0 + rh), (105, 180, 255), 3)
    return out


def warm_flash(frame: np.ndarray, progress: float) -> np.ndarray:
    """T03 — flash chaud de luminance, sans copie d'habillage."""
    h, w = frame.shape[:2]
    peak = 1.0 - abs(2.0 * np.clip(progress, 0.0, 1.0) - 1.0)
    peak = smoothstep(peak)
    yy, xx = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xx - w * 0.72) / w) ** 2 + ((yy - h * 0.38) / h) ** 2)
    radial = np.clip(1.15 - dist * 1.8, 0, 1)[..., None]
    warm = np.zeros_like(frame, dtype=np.float32)
    warm[..., 0] = 30
    warm[..., 1] = 130
    warm[..., 2] = 255
    alpha = radial * (0.62 * peak)
    return np.clip(frame.astype(np.float32) * (1.0 + 0.22 * peak) + warm * alpha, 0, 255).astype(np.uint8)


def oblique_shutters(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """T04 — trois formes obliques non équidistantes."""
    h, w = outgoing.shape[:2]
    mask = np.zeros((h, w), np.float32)
    delays = (0.0, 0.12, 0.23)
    bands = ((0, int(h * 0.31)), (int(h * 0.31), int(h * 0.69)), (int(h * 0.69), h))
    yy, xx = np.mgrid[0:h, 0:w]
    for (y0, y1), delay in zip(bands, delays):
        p = smoothstep((progress - delay) / (1.0 - delay))
        edge = -w * 0.2 + p * w * 1.45 - 0.20 * (yy - h / 2)
        band_mask = (yy >= y0) & (yy < y1) & (xx <= edge)
        mask[band_mask] = 1.0
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=1.2)
    return _mix(outgoing, incoming, mask)


def staggered_bands(frame: np.ndarray, progress: float) -> np.ndarray:
    """T05 — trois bandes se décalent puis se réalignent en 0,42 s."""
    h, w = frame.shape[:2]
    amount = smoothstep(1.0 - abs(2.0 * np.clip(progress, 0, 1) - 1.0))
    offsets = (-1, 1, -1)
    out = np.zeros_like(frame)
    edges = [0, int(h * 0.29), int(h * 0.67), h]
    for i in range(3):
        y0, y1 = edges[i], edges[i + 1]
        shift = int(offsets[i] * amount * w * (0.075 + 0.018 * i))
        band = np.roll(frame[y0:y1], shift, axis=1)
        out[y0:y1] = band
    gap = max(0, int(4 * amount))
    if gap:
        for y in edges[1:-1]:
            out[max(0, y-gap):min(h, y+gap)] = (12, 10, 9)
    return out


def diagonal_desaturated_to_color(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """T06 — balayage diagonal de l'ancien plan désaturé au nouveau plan couleur."""
    p = smoothstep(progress)
    h, w = outgoing.shape[:2]
    gray = cv2.cvtColor(outgoing, cv2.COLOR_BGR2GRAY)
    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    yy, xx = np.mgrid[0:h, 0:w]
    edge = -w * 0.22 + p * w * 1.44 + 0.21 * (yy - h / 2)
    mask = (xx <= edge).astype(np.float32)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=2.0)
    return _mix(base, incoming, mask)
