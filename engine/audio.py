"""Musique de démonstration originale, générée sans échantillon tiers."""
from __future__ import annotations

from pathlib import Path
import wave
import numpy as np


def _tone(length: int, sr: int, hz: float, decay: float = 8.0) -> np.ndarray:
    t = np.arange(length) / sr
    return np.sin(2 * np.pi * hz * t) * np.exp(-decay * t)


def generate_demo_music(path: Path, duration: float = 30.0, sr: int = 44100) -> None:
    rng = np.random.default_rng(20261118)
    n = int(duration * sr)
    mix = np.zeros(n, np.float64)
    beat = 0.5  # 120 BPM

    # Pad harmonique discret, progression de quatre mesures.
    notes = [55.0, 65.41, 73.42, 49.0]
    t = np.arange(n) / sr
    for bar_start in np.arange(0, duration, 2.0):
        hz = notes[int(bar_start / 2) % len(notes)]
        idx = (t >= bar_start) & (t < min(duration, bar_start + 2.0))
        local = t[idx] - bar_start
        env = np.minimum(local / 0.18, 1.0) * np.minimum((2.0 - local) / 0.25, 1.0)
        mix[idx] += 0.08 * env * (
            np.sin(2 * np.pi * hz * local)
            + 0.38 * np.sin(2 * np.pi * hz * 1.5 * local)
        )

    # Kick et basse.
    for i, start in enumerate(np.arange(0, duration, beat)):
        pos = int(start * sr)
        length = min(int(0.34 * sr), n - pos)
        if length <= 0:
            continue
        tt = np.arange(length) / sr
        phase = 2 * np.pi * (78 * tt - 31 * tt * tt)
        kick = np.sin(phase) * np.exp(-14 * tt)
        mix[pos : pos + length] += 0.52 * kick
        if i % 2 == 0:
            bass = _tone(length, sr, notes[(i // 4) % len(notes)], decay=4.4)
            mix[pos : pos + length] += 0.18 * bass

    # Claquement sur 2 et 4.
    for start in np.arange(beat, duration, 2 * beat):
        pos = int(start * sr)
        length = min(int(0.18 * sr), n - pos)
        noise = rng.normal(0, 1, length)
        env = np.exp(-28 * np.arange(length) / sr)
        clap = noise * env
        clap = clap - np.concatenate(([0.0], clap[:-1])) * 0.6
        mix[pos : pos + length] += 0.18 * clap

    # Hi-hats en croches, avec légère syncope.
    for i, start in enumerate(np.arange(0, duration, beat / 2)):
        pos = int(start * sr)
        length = min(int(0.055 * sr), n - pos)
        noise = rng.normal(0, 1, length)
        env = np.exp(-72 * np.arange(length) / sr)
        gain = 0.065 if i % 2 == 0 else 0.045
        mix[pos : pos + length] += gain * noise * env

    # Whooshes originaux aux six transitions.
    for center in (0.21, 6.0, 10.0, 14.0, 17.5, 21.0):
        start = max(0, int((center - 0.23) * sr))
        end = min(n, int((center + 0.23) * sr))
        length = end - start
        if length <= 0:
            continue
        x = np.linspace(-1, 1, length)
        env = (1 - np.abs(x)) ** 1.7
        noise = rng.normal(0, 1, length)
        smooth = np.convolve(noise, np.ones(17) / 17, mode="same")
        mix[start:end] += 0.12 * env * smooth

    # Fondu final et normalisation à environ -3 dBFS crête.
    fade = int(0.7 * sr)
    mix[-fade:] *= np.linspace(1, 0, fade)
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = np.clip(mix / peak * 0.70, -1, 1)
    stereo = np.column_stack((mix, mix))
    pcm = (stereo * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        wav.writeframes(pcm.tobytes())
