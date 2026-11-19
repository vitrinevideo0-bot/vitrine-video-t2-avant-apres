#!/usr/bin/env python3
"""Build the one T2 v0.5 voice+music validation MP4 on GitHub Actions.

The audio architecture intentionally mirrors the locked public T1 reference:
one 30 s voice stem, deterministic clip-span ducking, two-pass EBU R128
mastering, objective intelligibility/QC measurements, and video bitstream copy.
No production render is permitted outside GitHub Actions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config/T2_complete_voice_mix_v0_5_0.json"
SCHEMA = ROOT / "schemas/T2_complete_voice_mix.schema.json"
SR = 48_000
TOTAL_S = 30.0
N = int(SR * TOTAL_S)


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, **kwargs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "T2-GitHub-Actions-Complete-Mix/0.5 (+https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres)"
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            target.write(block)
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
    if destination.stat().st_size < 100_000:
        raise RuntimeError(f"Téléchargement anormalement court: {url}")
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "published_as_standalone_asset": False,
    }


def probe(path: Path) -> dict[str, Any]:
    completed = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def stream_hash(path: Path, stream: str) -> str:
    completed = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            stream,
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if not value.startswith("SHA256="):
        raise RuntimeError(f"Hash de flux inattendu pour {path}: {value}")
    return value.split("=", 1)[1].lower()


def only_streams(metadata: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [item for item in metadata.get("streams", []) if item.get("codec_type") == kind]


def decode_audio(path: Path, channels: int) -> np.ndarray:
    raw = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-ar",
            str(SR),
            "-ac",
            str(channels),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
    ).stdout
    data = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return data.reshape(-1, channels) if channels > 1 else data


def write_float_wav(path: Path, data: np.ndarray, codec: str = "pcm_s24le") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    channels = data.shape[1] if data.ndim == 2 else 1
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "f32le",
            "-ar",
            str(SR),
            "-ac",
            str(channels),
            "-i",
            "-",
            "-map_metadata",
            "-1",
            "-c:a",
            codec,
            str(path),
        ],
        stdin=subprocess.PIPE,
    )
    process.communicate(np.asarray(data, dtype="<f4").tobytes())
    if process.returncode:
        raise RuntimeError(f"ffmpeg a échoué pendant l’écriture de {path}")


def loudness_stats(path: Path, target_i: float, target_tp: float) -> dict[str, float | str]:
    audio_filter = f"loudnorm=I={target_i}:TP={target_tp}:LRA=7:print_format=json"
    completed = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            audio_filter,
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    blocks = re.findall(r'\{\s*"input_i".*?\}', completed.stderr, re.S)
    if not blocks:
        raise RuntimeError(f"loudnorm n’a renvoyé aucun JSON pour {path}")
    return json.loads(blocks[-1])


def master_audio(source: Path, target: Path, target_i: float, target_tp: float) -> tuple[dict, dict]:
    """Canonical T1-style two-pass EBU R128 mastering."""
    before = loudness_stats(source, target_i, target_tp)
    audio_filter = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA=7:"
        f"measured_I={before['input_i']}:measured_LRA={before['input_lra']}:"
        f"measured_TP={before['input_tp']}:measured_thresh={before['input_thresh']}:"
        f"offset={before['target_offset']}:linear=false:print_format=summary"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-af",
            audio_filter,
            "-t",
            str(TOTAL_S),
            "-ar",
            str(SR),
            "-ac",
            "2",
            "-map_metadata",
            "-1",
            "-c:a",
            "pcm_s24le",
            str(target),
        ]
    )
    return before, loudness_stats(target, target_i, target_tp)


def normalize_voice(source: Path, target: Path, target_i: float, target_tp: float) -> dict[str, float]:
    """Canonical T1 voice normalization without retiming the source."""
    before = loudness_stats(source, target_i, target_tp)
    gain_db = target_i - float(before["input_i"])
    limit = 10 ** ((target_tp - 0.1) / 20.0)
    audio_filter = (
        f"afade=t=in:st=0:d=0.006,volume={gain_db:.6f}dB,"
        f"alimiter=limit={limit:.9f}:attack=5:release=50:level=false:latency=true"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-af",
            audio_filter,
            "-ar",
            str(SR),
            "-ac",
            "1",
            "-map_metadata",
            "-1",
            "-c:a",
            "pcm_s16le",
            str(target),
        ]
    )
    after = loudness_stats(target, target_i, target_tp)
    return {
        "applied_gain_db": round(gain_db, 3),
        "integrated_lufs": float(after["input_i"]),
        "true_peak_dbtp": float(after["input_tp"]),
        "loudness_range_lu": float(after["input_lra"]),
    }


def prepare_music_program(
    source: Path, faded: Path, mastered: Path, selection: dict[str, Any]
) -> tuple[dict, dict]:
    duration = float(selection["program_duration_s"])
    fade_out_start = duration - float(selection["fade_out_s"])
    audio_filter = (
        f"afade=t=in:st=0:d={float(selection['fade_in_s'])},"
        f"afade=t=out:st={fade_out_start}:d={float(selection['fade_out_s'])}"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            str(float(selection["source_start_s"])),
            "-i",
            str(source),
            "-t",
            str(duration),
            "-map",
            "0:a:0",
            "-af",
            audio_filter,
            "-ar",
            str(SR),
            "-ac",
            "2",
            "-map_metadata",
            "-1",
            "-c:a",
            "pcm_s24le",
            str(faded),
        ]
    )
    return master_audio(
        faded,
        mastered,
        float(selection["program_target_lufs"]),
        float(selection["program_true_peak_dbtp_max"]),
    )


def duck_envelope(spans: list[tuple[float, float]], attack_s: float, release_s: float) -> np.ndarray:
    """Return 0=open and 1=fully ducked; ramps are linear in dB, as in T1."""
    envelope = np.zeros(N, dtype=np.float64)
    for start, end in spans:
        attack_start = max(0, int(round((start - attack_s) * SR)))
        full_start = int(round(start * SR))
        full_end = min(N, int(round(end * SR)))
        release_end = min(N, int(round((end + release_s) * SR)))
        if full_start > attack_start:
            envelope[attack_start:full_start] = np.maximum(
                envelope[attack_start:full_start],
                np.linspace(0.0, 1.0, full_start - attack_start, endpoint=False),
            )
        envelope[full_start:full_end] = 1.0
        if release_end > full_end:
            envelope[full_end:release_end] = np.maximum(
                envelope[full_end:release_end],
                np.linspace(1.0, 0.0, release_end - full_end, endpoint=False),
            )
    return envelope


def sample_qc(audio: np.ndarray) -> dict[str, Any]:
    peak = float(np.max(np.abs(audio)))
    dc_values = [float(np.mean(audio))] if audio.ndim == 1 else [float(x) for x in np.mean(audio, axis=0)]
    return {
        "sample_peak_dbfs": round(float(20 * np.log10(max(peak, 1e-12))), 3),
        "clipped_sample_count": int(np.count_nonzero(np.abs(audio) >= 0.999999)),
        "nan_count": int(np.isnan(audio).sum()),
        "inf_count": int(np.isinf(audio).sum()),
        "dc_offset_max_abs": round(max(abs(value) for value in dc_values), 7),
    }


def frame_speech_metrics(
    voice: np.ndarray,
    music: np.ndarray,
    spans: list[tuple[float, float]],
    threshold_db: float = -38.0,
) -> dict[str, Any]:
    frame = int(0.020 * SR)
    values: list[float] = []
    voice_powers: list[float] = []
    music_powers: list[float] = []
    scenes: list[dict[str, Any]] = []
    for scene, (start, end) in enumerate(spans, 1):
        scene_values: list[float] = []
        first = int(start * SR) // frame
        last = min(len(voice) // frame, int(np.ceil(end * SR / frame)))
        for index in range(first, last):
            a, b = index * frame, (index + 1) * frame
            voice_power = float(np.mean(voice[a:b] ** 2))
            voice_db = 10 * np.log10(max(voice_power, 1e-20))
            if voice_db <= threshold_db:
                continue
            music_power = float(np.mean(music[a:b] ** 2))
            ratio = 10 * np.log10(max(voice_power, 1e-20) / max(music_power, 1e-20))
            values.append(ratio)
            scene_values.append(ratio)
            voice_powers.append(voice_power)
            music_powers.append(music_power)
        if not scene_values:
            raise RuntimeError(f"Aucune parole active détectée dans la scène {scene}")
        scenes.append(
            {
                "scene": scene,
                "active_speech_s": round(len(scene_values) * frame / SR, 3),
                "median_speech_to_music_db": round(float(np.median(scene_values)), 2),
                "p10_speech_to_music_db": round(float(np.percentile(scene_values, 10)), 2),
            }
        )
    aggregate = 10 * np.log10(np.mean(voice_powers) / np.mean(music_powers))
    return {
        "method": "20 ms frames; voice RMS above -38 dBFS; pre-master stems",
        "active_speech_s": round(len(values) * frame / SR, 3),
        "aggregate_speech_to_music_db": round(float(aggregate), 2),
        "median_speech_to_music_db": round(float(np.median(values)), 2),
        "p10_speech_to_music_db": round(float(np.percentile(values, 10)), 2),
        "scenes": scenes,
    }


def write_automation_csv(path: Path, music_gain_db: np.ndarray, spans: list[tuple[float, float]]) -> None:
    step = int(0.010 * SR)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "music_gain_db", "voice_clip_active"])
        for sample in range(0, N + 1, step):
            index = min(sample, N - 1)
            time_s = sample / SR
            active = int(any(start <= time_s < end for start, end in spans))
            writer.writerow([f"{time_s:.3f}", f"{music_gain_db[index]:.4f}", active])


def draw_ducking_plot(
    path: Path, voice: np.ndarray, music_gain_db: np.ndarray, spans: list[tuple[float, float]]
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1600, 700
    image = Image.new("RGB", (width, height), "#f7f1e8")
    draw = ImageDraw.Draw(image, "RGBA")
    regular = ROOT / "assets/fonts/DejaVuSans.ttf"
    bold = ROOT / "assets/fonts/DejaVuSans-Bold.ttf"
    title_font = ImageFont.truetype(str(bold), 32)
    label_font = ImageFont.truetype(str(bold), 18)
    small_font = ImageFont.truetype(str(regular), 16)
    left, right = 100, 1545
    top_box = (left, 90, right, 330)
    bottom_box = (left, 390, right, 625)
    draw.rounded_rectangle(top_box, 18, fill="#fffaf4", outline="#ded2c5", width=2)
    draw.rounded_rectangle(bottom_box, 18, fill="#fffaf4", outline="#ded2c5", width=2)
    draw.text((left, 28), "T2 — stem voix 30 s et ducking musique B", fill="#201d19", font=title_font)

    def x_at(time_s: float) -> int:
        return int(round(left + time_s / TOTAL_S * (right - left)))

    for marker in [0, 6, 14, 21, 30]:
        x = x_at(marker)
        draw.line((x, top_box[1], x, top_box[3]), fill="#9b9187", width=1)
        draw.line((x, bottom_box[1], x, bottom_box[3]), fill="#9b9187", width=1)
        draw.text((x - 10, 638), f"{marker}", fill="#6e665e", font=small_font)

    center = (top_box[1] + top_box[3]) // 2
    peak = max(float(np.max(np.abs(voice))), 1e-9)
    samples_per_pixel = max(1, len(voice) // (right - left))
    for column in range(right - left):
        a = column * samples_per_pixel
        b = min(len(voice), a + samples_per_pixel)
        segment = voice[a:b]
        low = int(center - float(np.max(segment)) / peak * 96)
        high = int(center - float(np.min(segment)) / peak * 96)
        draw.line((left + column, low, left + column, high), fill="#a73337", width=1)
    draw.line((left, center, right, center), fill="#d6b2ae", width=1)
    draw.text((22, center - 12), "Voix", fill="#9b2d30", font=label_font)

    for start, end in spans:
        draw.rectangle((x_at(start), bottom_box[1], x_at(end), bottom_box[3]), fill="#f0a33b28")
    gain_top, gain_bottom = -2.3, -10.7

    def y_at(gain_db: float) -> int:
        return int(
            round(
                bottom_box[1]
                + (gain_top - gain_db) / (gain_top - gain_bottom) * (bottom_box[3] - bottom_box[1])
            )
        )

    for db in range(-10, -2):
        y = y_at(float(db))
        draw.line((left, y, right, y), fill="#ded2c5", width=1)
        draw.text((55, y - 10), str(db), fill="#6e665e", font=small_font)
    points = []
    for column in range(right - left + 1):
        index = min(N - 1, int(column / (right - left) * (N - 1)))
        points.append((left + column, y_at(float(music_gain_db[index]))))
    draw.line(points, fill="#16796f", width=4, joint="curve")
    draw.text((15, 485), "Gain", fill="#16796f", font=label_font)
    draw.text((10, 510), "musique", fill="#16796f", font=label_font)
    draw.text((x_at(0.35), y_at(-3) + 10), "hors voix −3 dB", fill="#16796f", font=small_font)
    draw.text((x_at(1.35), y_at(-10) - 30), "sous voix −10 dB", fill="#9b2d30", font=small_font)
    draw.text((right - 20, 638), "s", fill="#6e665e", font=small_font)
    image.save(path, optimize=True)


def write_human_report(path: Path, report: dict[str, Any]) -> None:
    voice = report["voice"]
    final = report["final_mp4"]
    speech = report["intelligibility_proxy"]
    mix = report["ducking"]
    lines = [
        "# Rapport des niveaux — T2 complet voix + musique B",
        "",
        f"**Contrôle objectif : {report['status']}**",
        "",
        "## Livrable",
        "",
        f"- Fichier : `{final['file']}`",
        f"- Durée conteneur : {final['duration_s']:.3f} s",
        f"- Image : {final['width']} × {final['height']}, {final['fps']}, {final['frames']} images",
        f"- Audio : {final['audio_codec'].upper()}, {final['sample_rate_hz']} Hz, {final['channels']} canaux",
        f"- Débit AAC demandé : {final['requested_audio_bitrate_bps']} b/s",
        f"- Débit AAC observé : {final['observed_audio_bitrate_bps']} b/s",
        "",
        "## Équilibre voix / musique",
        "",
        f"- Musique hors parole : {mix['maximum_music_gain_db']:.1f} dB",
        f"- Musique pendant la parole : {mix['minimum_music_gain_db']:.1f} dB",
        f"- Profondeur du ducking : {mix['duck_depth_db']:.1f} dB",
        f"- Attaque / relâchement : {mix['duck_attack_ms']} ms / {mix['duck_release_ms']} ms",
        f"- Rapport parole/musique actif agrégé : **{speech['aggregate_speech_to_music_db']:.2f} dB**",
        "",
        "| Scène | Départ | Fin | Parole active | Médiane parole/musique | P10 parole/musique |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for clip, scene in zip(voice["clips"], speech["scenes"]):
        lines.append(
            f"| S{clip['scene']} | {clip['start_s']:.3f} s | {clip['end_s']:.3f} s | "
            f"{scene['active_speech_s']:.3f} s | {scene['median_speech_to_music_db']:.2f} dB | "
            f"{scene['p10_speech_to_music_db']:.2f} dB |"
        )
    lines.extend(
        [
            "",
            "## Master final",
            "",
            f"- Cible : −16 LUFS ; mesure AAC : **{final['integrated_lufs']:.2f} LUFS**",
            f"- Plafond master WAV : −2 dBTP ; mesure AAC : **{final['true_peak_dbtp']:.2f} dBTP**",
            f"- Échantillons écrêtés : {final['clipped_sample_count']}",
            f"- NaN / Inf : {final['nan_count']} / {final['inf_count']}",
            "",
            "## Intégrité et portée",
            "",
            "- Le flux vidéo est identique bit à bit au montage v0.3 validé.",
            "- Les quatre textes sont les exemples exacts des scènes S1 à S4.",
            "- Les voix restent à vitesse 1×, réunies dans un stem de 30 s, sans sous-titres.",
            "- Le morceau B a été choisi pour cet exemplaire unique uniquement ; il n’est pas défini comme choix par défaut du gabarit.",
            "- La page Pixabay du morceau B affiche un statut Content ID enregistré.",
            "- Aucun MP3 musical, WAV voix ou stem audio autonome n’est publié dans la Release.",
            "",
            "L’approbation finale reste une écoute humaine du MP4.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def validate_source_config(config: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(config)
    if config["duration_s"] != TOTAL_S or config["sample_rate_hz"] != SR:
        raise ValueError("La durée ou la fréquence du contrat T2 ne correspond pas au moteur.")
    if config["music_selection"]["candidate_id"] != "B":
        raise ValueError("Cet exemplaire doit utiliser le choix utilisateur B.")
    if config["music_selection"]["template_default_selection"] is not False:
        raise ValueError("Le morceau B ne doit pas devenir un défaut du gabarit.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Rendu de production interdit hors GitHub Actions.")

    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_source_config(config)
    publication = config["publication"]
    mix = config["mix_contract"]
    gates = config["quality_gates"]
    voice_config = config["voice"]
    selection = config["music_selection"]

    output_mp4 = output_dir / publication["output_file"]
    report_path = output_dir / publication["validation_report"]
    human_report_path = output_dir / publication["human_report"]
    automation_path = output_dir / publication["automation_csv"]
    plot_path = output_dir / publication["timeline_plot"]

    with tempfile.TemporaryDirectory(prefix="t2-complete-voice-mix-") as temporary_name:
        temporary = Path(temporary_name)
        visual = temporary / config["visual_source"]["asset_name"]
        music_source = temporary / "pixabay_candidate_B_source.mp3"
        visual_download = download(config["visual_source"]["url"], visual)
        music_download = download(selection["source_audio_url"], music_source)

        if sha256(visual) != config["visual_source"]["sha256"]:
            raise RuntimeError("Le SHA-256 de la base visuelle v0.3 ne correspond pas au verrou.")
        visual_probe = probe(visual)
        visual_video = only_streams(visual_probe, "video")
        if len(visual_video) != 1 or only_streams(visual_probe, "audio"):
            raise RuntimeError("La base v0.3 doit contenir une vidéo et aucun audio.")
        visual_hash = stream_hash(visual, "0:v:0")
        if visual_hash != config["visual_source"]["video_stream_sha256"]:
            raise RuntimeError("Le flux vidéo v0.3 ne correspond pas au verrou.")

        music_probe = probe(music_source)
        source_audio_streams = only_streams(music_probe, "audio")
        if len(source_audio_streams) != 1:
            raise RuntimeError("Une unique source musicale est attendue.")
        source_duration = float(music_probe["format"]["duration"])
        required_music_duration = float(selection["source_start_s"]) + float(selection["program_duration_s"])
        if source_duration + 0.05 < required_music_duration:
            raise RuntimeError(f"La source musicale est trop courte: {source_duration:.3f} s")

        faded_music = temporary / "music_B_faded_30s.wav"
        music_program_file = temporary / "music_B_program_master_30s.wav"
        music_before, music_after = prepare_music_program(
            music_source, faded_music, music_program_file, selection
        )
        music_program = decode_audio(music_program_file, 2)
        if len(music_program) < N:
            music_program = np.pad(music_program, ((0, N - len(music_program)), (0, 0)))
        music_program = music_program[:N]

        voice = np.zeros(N, dtype=np.float64)
        voice_entries: list[dict[str, Any]] = []
        clips: list[np.ndarray] = []
        for item in voice_config["clips"]:
            source = ROOT / item["source"]
            if sha256(source) != item["source_sha256"]:
                raise RuntimeError(f"La prise voix S{item['scene']} ne correspond pas au contrat.")
            raw = decode_audio(source, 1)
            raw_duration = len(raw) / SR
            if abs(raw_duration - float(item["source_duration_s"])) > 0.002:
                raise RuntimeError(f"Durée source voix S{item['scene']} inattendue: {raw_duration:.6f}")
            processed = temporary / f"voice_scene{item['scene']}_norm.wav"
            normalization = normalize_voice(
                source,
                processed,
                float(voice_config["normalization_target_lufs"]),
                float(voice_config["normalization_true_peak_dbtp_max"]),
            )
            clip = decode_audio(processed, 1)
            start_s = float(item["start_s"])
            end_s = start_s + len(clip) / SR
            scene_start, scene_end = [float(value) for value in item["scene_window_s"]]
            if start_s < scene_start or end_s > scene_end + 0.001:
                raise RuntimeError(
                    f"La voix S{item['scene']} sort de sa scène: {start_s:.3f}–{end_s:.3f} / {scene_start:.3f}–{scene_end:.3f}"
                )
            start_sample = int(round(start_s * SR))
            count = min(len(clip), N - start_sample)
            voice[start_sample : start_sample + count] += clip[:count]
            clips.append(clip)
            voice_entries.append(
                {
                    **item,
                    "source_decoded_duration_s": round(raw_duration, 6),
                    "start_sample_48khz": start_sample,
                    "end_s": round(end_s, 6),
                    "processed_duration_s": round(len(clip) / SR, 6),
                    "processed_samples_48khz": len(clip),
                    "processed_sha256": sha256(processed),
                    "normalization": normalization,
                    "source_speed": 1.0,
                    "audio_time_map": "identity",
                }
            )

        voice_stem_file = temporary / "t2_voice_stem_30s.wav"
        write_float_wav(voice_stem_file, voice, "pcm_s24le")
        stem_stats = loudness_stats(voice_stem_file, -20.0, -3.0)
        stem_qc = sample_qc(voice)
        spans = [(float(item["start_s"]), float(item["end_s"])) for item in voice_entries]

        attack_s = float(mix["duck_attack_ms"]) / 1000.0
        release_s = float(mix["duck_release_ms"]) / 1000.0
        envelope = duck_envelope(spans, attack_s, release_s)
        open_db = float(mix["music_open_gain_db"])
        under_db = float(mix["music_under_voice_gain_db"])
        music_gain_db = open_db + (under_db - open_db) * envelope
        music_gain = 10 ** (music_gain_db / 20.0)
        music_stem = music_program * music_gain[:, None]
        voice_stereo = np.column_stack((voice, voice)) * 10 ** (float(mix["voice_gain_db"]) / 20.0)
        premix = music_stem + voice_stereo

        write_automation_csv(automation_path, music_gain_db, spans)
        draw_ducking_plot(plot_path, voice, music_gain_db, spans)
        intelligibility = frame_speech_metrics(voice, music_stem, spans)

        raw_mix = temporary / "t2_voice_music_premix.wav"
        master_wav = temporary / "t2_voice_music_master.wav"
        write_float_wav(raw_mix, premix, "pcm_s24le")
        master_before, master_after = master_audio(
            raw_mix,
            master_wav,
            float(mix["master_target_lufs"]),
            float(mix["master_true_peak_dbtp_max"]),
        )
        master_audio_data = decode_audio(master_wav, 2)
        master_qc = sample_qc(master_audio_data)
        master_stats = loudness_stats(master_wav, -16.0, -2.0)

        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(visual),
                "-i",
                str(master_wav),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                str(int(gates["required_audio_bitrate_bps"])),
                "-ar",
                str(SR),
                "-ac",
                "2",
                "-t",
                str(TOTAL_S),
                "-map_metadata",
                "-1",
                "-metadata",
                "title=T2 complet voix francaise + musique B",
                "-metadata",
                "artist=Vitrine Video",
                "-metadata",
                "comment=Exemplaire unique a valider; musique B non definie comme choix par defaut",
                "-movflags",
                "+faststart",
                str(output_mp4),
            ]
        )

        final_probe = probe(output_mp4)
        final_video_streams = only_streams(final_probe, "video")
        final_audio_streams = only_streams(final_probe, "audio")
        final_subtitles = only_streams(final_probe, "subtitle")
        if len(final_video_streams) != 1 or len(final_audio_streams) != 1 or final_subtitles:
            raise RuntimeError("Le MP4 final doit contenir exactement un flux vidéo et un flux audio.")
        video_stream = final_video_streams[0]
        audio_stream = final_audio_streams[0]
        final_audio_data = decode_audio(output_mp4, 2)
        final_stats = loudness_stats(output_mp4, -16.0, -1.0)
        final_qc = sample_qc(final_audio_data)
        final_video_hash = stream_hash(output_mp4, "0:v:0")
        duration = float(final_probe["format"]["duration"])
        observed_audio_bitrate = int(audio_stream.get("bit_rate") or 0)
        requested_audio_bitrate = int(gates["required_audio_bitrate_bps"])

        final_summary = {
            "file": output_mp4.name,
            "sha256": sha256(output_mp4),
            "bytes": output_mp4.stat().st_size,
            "duration_s": duration,
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": video_stream.get("r_frame_rate"),
            "frames": int(video_stream.get("nb_frames", 0)),
            "video_codec": video_stream.get("codec_name"),
            "video_stream_sha256": final_video_hash,
            "visual_stream_identical_to_v0_3": final_video_hash == visual_hash,
            "audio_codec": audio_stream.get("codec_name"),
            "sample_rate_hz": int(audio_stream.get("sample_rate", 0)),
            "channels": int(audio_stream.get("channels", 0)),
            "requested_audio_bitrate_bps": requested_audio_bitrate,
            "observed_audio_bitrate_bps": observed_audio_bitrate,
            "decoded_audio_samples_per_channel": len(final_audio_data),
            "decoded_audio_duration_s": round(len(final_audio_data) / SR, 6),
            "integrated_lufs": float(final_stats["input_i"]),
            "true_peak_dbtp": float(final_stats["input_tp"]),
            **final_qc,
        }

        current_mp4s = list(output_dir.glob("*.mp4"))
        autonomous_audio = [
            path.name
            for suffix in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.flac", "*.ogg", "*.opus")
            for path in output_dir.glob(suffix)
        ]
        checks = {
            "exactly_one_output_mp4": len(current_mp4s) == int(gates["exact_output_video_count"]),
            "no_standalone_audio_in_output": not autonomous_audio,
            "duration_30s": abs(duration - TOTAL_S) <= float(gates["duration_tolerance_s"]),
            "video_dimensions": (
                final_summary["width"] == int(gates["required_width"])
                and final_summary["height"] == int(gates["required_height"])
            ),
            "video_fps": final_summary["fps"] == gates["required_video_fps"],
            "video_frames": final_summary["frames"] == int(gates["required_video_frames"]),
            "visual_stream_bit_identical": final_summary["visual_stream_identical_to_v0_3"],
            "audio_codec": final_summary["audio_codec"] == gates["required_audio_codec"],
            "audio_sample_rate": final_summary["sample_rate_hz"] == int(gates["required_audio_sample_rate_hz"]),
            "audio_channels": final_summary["channels"] == int(gates["required_audio_channels"]),
            "audio_bitrate_near_target": (
                observed_audio_bitrate > 0
                and abs(observed_audio_bitrate - requested_audio_bitrate) / requested_audio_bitrate <= 0.12
            ),
            "integrated_loudness": (
                float(gates["integrated_lufs_min"])
                <= final_summary["integrated_lufs"]
                <= float(gates["integrated_lufs_max"])
            ),
            "wav_true_peak": float(master_stats["input_tp"]) <= float(gates["wav_true_peak_dbtp_max"]),
            "aac_true_peak": final_summary["true_peak_dbtp"] <= float(gates["aac_true_peak_dbtp_max"]),
            "speech_to_music": (
                intelligibility["aggregate_speech_to_music_db"]
                >= float(gates["minimum_active_speech_to_music_db"])
            ),
            "no_clipped_samples": (
                master_qc["clipped_sample_count"] <= int(gates["clipped_sample_count_max"])
                and final_qc["clipped_sample_count"] <= int(gates["clipped_sample_count_max"])
            ),
            "no_non_finite_samples": (
                master_qc["nan_count"] == master_qc["inf_count"] == 0
                and final_qc["nan_count"] == final_qc["inf_count"] == 0
            ),
            "voice_stem_exact_30s": len(voice) == N,
            "four_voice_clips_in_scene_windows": len(voice_entries) == 4,
            "music_candidate_B_only": selection["candidate_id"] == "B",
            "music_not_template_default": selection["template_default_selection"] is False,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        report = {
            "schema_version": "1.0.0",
            "status": status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_on_github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "commit": os.environ.get("GITHUB_SHA"),
            "configuration": str(config_path.relative_to(ROOT)),
            "t1_audio_reference": config["reference_t1"],
            "visual_source": {
                **config["visual_source"],
                "download": visual_download,
                "observed_video_stream_sha256": visual_hash,
            },
            "music": {
                **selection,
                "download": music_download,
                "source_duration_s": source_duration,
                "source_codec": source_audio_streams[0].get("codec_name"),
                "program_pre_master": {
                    "integrated_lufs": float(music_before["input_i"]),
                    "true_peak_dbtp": float(music_before["input_tp"]),
                },
                "program_master": {
                    "sha256": sha256(music_program_file),
                    "bytes": music_program_file.stat().st_size,
                    "decoded_samples_per_channel": len(music_program),
                    "duration_s": len(music_program) / SR,
                    "integrated_lufs": float(music_after["input_i"]),
                    "true_peak_dbtp": float(music_after["input_tp"]),
                    "ephemeral_not_published": True,
                },
            },
            "voice": {
                "provider": voice_config["provider"],
                "voice_id": voice_config["voice_id"],
                "language": voice_config["language"],
                "identity": voice_config["identity"],
                "same_identity_for_all_scenes": voice_config["same_identity_for_all_scenes"],
                "source_speed": voice_config["source_speed"],
                "audio_time_map": voice_config["audio_time_map"],
                "automatic_subtitles": voice_config["automatic_subtitles"],
                "clips": voice_entries,
                "stem": {
                    "sha256": sha256(voice_stem_file),
                    "bytes": voice_stem_file.stat().st_size,
                    "decoded_samples": len(voice),
                    "duration_s": len(voice) / SR,
                    "integrated_lufs": float(stem_stats["input_i"]),
                    "true_peak_dbtp": float(stem_stats["input_tp"]),
                    "ephemeral_not_published": True,
                    **stem_qc,
                },
            },
            "ducking": {
                **mix,
                "minimum_music_gain_db": round(float(music_gain_db.min()), 4),
                "maximum_music_gain_db": round(float(music_gain_db.max()), 4),
                "duration_at_full_duck_s": round(
                    float(np.count_nonzero(music_gain_db <= under_db + 1e-6)) / SR, 3
                ),
                "duration_in_attack_or_release_s": round(
                    float(
                        np.count_nonzero(
                            (music_gain_db > under_db + 1e-6)
                            & (music_gain_db < open_db - 1e-6)
                        )
                    )
                    / SR,
                    3,
                ),
                "automation_csv": automation_path.name,
                "timeline_plot": plot_path.name,
            },
            "intelligibility_proxy": intelligibility,
            "master_wav": {
                "sha256": sha256(master_wav),
                "bytes": master_wav.stat().st_size,
                "decoded_samples_per_channel": len(master_audio_data),
                "duration_s": len(master_audio_data) / SR,
                "pre_master_integrated_lufs": float(master_before["input_i"]),
                "pre_master_true_peak_dbtp": float(master_before["input_tp"]),
                "integrated_lufs": float(master_stats["input_i"]),
                "true_peak_dbtp": float(master_stats["input_tp"]),
                "ephemeral_not_published": True,
                **master_qc,
            },
            "final_mp4": final_summary,
            "publication": {
                "exact_mp4_count": len(current_mp4s),
                "standalone_audio_files": autonomous_audio,
                "source_music_published": False,
                "voice_stem_published": False,
                "human_listening_required": True,
            },
            "quality_gates": gates,
            "checks": checks,
            "human_review": {
                "status": "PENDING",
                "required": True,
                "note": "QC objectif terminé; l’équilibre créatif et la prononciation doivent être approuvés en écoutant l’unique MP4.",
            },
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_human_report(human_report_path, report)

    print(
        json.dumps(
            {
                "status": report["status"],
                "mp4": report["final_mp4"]["file"],
                "sha256": report["final_mp4"]["sha256"],
                "lufs": report["final_mp4"]["integrated_lufs"],
                "true_peak_dbtp": report["final_mp4"]["true_peak_dbtp"],
                "speech_to_music_db": report["intelligibility_proxy"]["aggregate_speech_to_music_db"],
                "video_stream_sha256": report["final_mp4"]["video_stream_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if report["status"] != "PASS":
        failed = [name for name, passed in report["checks"].items() if not passed]
        raise SystemExit(f"Échec des contrôles T2: {failed}")


if __name__ == "__main__":
    main()
