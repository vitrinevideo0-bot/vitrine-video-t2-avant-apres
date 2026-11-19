#!/usr/bin/env python3
"""Build an approved T2 voice+music validation MP4 on GitHub Actions.

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
SCHEMAS = {
    "restaurants_maquis_T2_complete_voice_mix_v0_5_0": ROOT / "schemas/T2_complete_voice_mix.schema.json",
    "restaurants_maquis_T2_complete_voice_mix_v0_7_0": ROOT / "schemas/T2_complete_voice_mix_v0_7_0.schema.json",
}
RENDER_JOB_SCHEMA = ROOT / "schemas/render_job.schema.json"
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


def reference_visual_integrity(
    *,
    observed_file_sha256: str,
    observed_video_stream_sha256: str,
    approved_file_sha256: str,
    approved_video_stream_sha256: str,
) -> dict[str, Any]:
    """Enforce the visual bitstream; retain the MP4 container hash as provenance.

    A rebuilt MP4 may have container-level differences while carrying the exact
    approved H.264 stream. The copied video stream is the visual invariant.
    """
    stream_matches = observed_video_stream_sha256 == approved_video_stream_sha256
    if not stream_matches:
        raise RuntimeError(
            "Le flux vidéo de référence v0.3 ne correspond pas au verrou: "
            f"{observed_video_stream_sha256}"
        )
    return {
        "approved_file_sha256": approved_file_sha256,
        "observed_file_sha256": observed_file_sha256,
        "container_file_sha256_matches": observed_file_sha256 == approved_file_sha256,
        "approved_video_stream_sha256": approved_video_stream_sha256,
        "observed_video_stream_sha256": observed_video_stream_sha256,
        "video_stream_sha256_matches": True,
        "enforced_invariant": "copied_h264_video_stream_sha256",
    }


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
    path: Path,
    voice: np.ndarray,
    music_gain_db: np.ndarray,
    spans: list[tuple[float, float]],
    music_label: str = "musique B",
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
    draw.text((left, 28), f"T2 — stem voix 30 s et ducking {music_label}", fill="#201d19", font=title_font)

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
    music = report["music"]
    candidate_id = music["candidate_id"]
    music_label = "Afrofire — DPStudioMusic" if candidate_id == "D" else "musique B historique"
    lines = [
        f"# Rapport des niveaux — T2 complet voix + {music_label}",
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
            "- Le flux vidéo final est identique bit à bit au visuel 900 images reconstruit depuis le même RenderJob.",
            "- Les quatre textes sont les exemples exacts des scènes S1 à S4.",
            "- Les voix restent à vitesse 1×, réunies dans un stem de 30 s, sans sous-titres.",
            f"- La musique {candidate_id} est une sélection explicite du catalogue ; elle n’est pas un défaut implicite du gabarit.",
            f"- Statut Content ID observé et verrouillé dans le contrat : `{music['content_id_status']}`.",
            "- Aucun MP3 musical, WAV voix ou stem audio autonome n’est publié dans la Release.",
            "",
            "L’approbation finale reste une écoute humaine du MP4.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def validate_source_config(config: dict[str, Any]) -> None:
    try:
        schema_path = SCHEMAS[config["id"]]
    except KeyError as error:
        raise ValueError(f"Contrat audio T2 inconnu : {config.get('id')}") from error
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(config)
    if config["duration_s"] != TOTAL_S or config["sample_rate_hz"] != SR:
        raise ValueError("La durée ou la fréquence du contrat T2 ne correspond pas au moteur.")
    candidate_id = config["music_selection"]["candidate_id"]
    if candidate_id not in {"B", "D"}:
        raise ValueError("Le mixeur de production accepte uniquement les contrats approuvés B ou D.")
    if config["music_selection"]["template_default_selection"] is not False:
        raise ValueError("La piste sélectionnée ne doit pas devenir un défaut du gabarit.")


def validate_unified_job(job: dict[str, Any], config: dict[str, Any], config_path: Path) -> None:
    Draft202012Validator(
        json.loads(RENDER_JOB_SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(job)
    if job["render_stage"] != "complete_voice_music_render":
        raise ValueError("Le mixeur unifié exige complete_voice_music_render.")
    if job["render_audio"] is not True or job["audio_mode"] != "voice_music_ducking":
        raise ValueError("Le RenderJob complet doit activer voix, musique et ducking.")
    plan = job["audio_plan"]
    if plan["config"] != str(config_path.relative_to(ROOT)):
        raise ValueError("Le RenderJob ne référence pas le contrat audio chargé.")
    if plan["config_sha256"] != sha256(config_path):
        raise ValueError("Le SHA-256 du contrat audio référencé par le RenderJob est invalide.")
    selection = config["music_selection"]
    music = plan["music"]
    expected_music = {
        "selected_candidate_id": selection["candidate_id"],
        "source_page": selection["source_page"],
        "source_audio_url": selection["source_audio_url"],
        "source_sha256": selection["source_sha256"],
        "content_id_status": selection["content_id_status"],
        "template_default_selection": selection["template_default_selection"],
        "source_audio_publish": selection["source_audio_publish"],
    }
    for key, expected in expected_music.items():
        if music[key] != expected:
            raise ValueError(f"Le plan musical du RenderJob diverge du contrat : {key}")
    if plan["voice"]["clips"] != config["voice"]["clips"]:
        raise ValueError("Les quatre voix du RenderJob divergent du contrat v0.5 verrouillé.")
    if plan["mix"] != config["mix_contract"]:
        raise ValueError("Le ducking/mastering du RenderJob diverge du contrat T1 recopié.")
    if plan["publication"]["output_file"] != config["publication"]["output_file"]:
        raise ValueError("Le nom de sortie du RenderJob diverge du contrat de publication.")
    if Path(job["output"]["uri"]).name != config["publication"]["output_file"]:
        raise ValueError("La sortie finale du RenderJob n'est pas l'unique MP4 attendu.")


def is_reference_exemplar(job: dict[str, Any] | None) -> bool:
    if job is None:
        return True
    reference = json.loads((ROOT / "demo/render_job_complete_demo.json").read_text(encoding="utf-8"))
    return (
        job["merchant_payload"] == reference["merchant_payload"]
        and all(
            job["captures"][slot]["sha256"] == reference["captures"][slot]["sha256"]
            for slot in ("S1", "S2", "S3", "S4")
        )
        and job["audio_plan"]["voice"]["mode"] == "registered_voice_clips"
    )


def extract_capture_audio(source: Path, target: Path, source_in_s: float, duration_s: float) -> None:
    """Extract accepted camera audio at identity speed; never retime words."""
    run(
        [
            "ffmpeg", "-y", "-v", "error", "-ss", f"{source_in_s:.6f}", "-i", str(source),
            "-t", f"{duration_s:.6f}", "-map", "0:a:0", "-vn", "-ar", str(SR), "-ac", "1",
            "-map_metadata", "-1", "-c:a", "pcm_s16le", str(target),
        ]
    )


def captured_audio_qc(clip: np.ndarray) -> dict[str, Any]:
    """Conservative speech usability gate used by captured-or-registered fallback."""
    frame = int(0.020 * SR)
    powers = np.array(
        [float(np.mean(clip[index : index + frame] ** 2)) for index in range(0, len(clip), frame)],
        dtype=np.float64,
    )
    levels = 10 * np.log10(np.maximum(powers, 1e-20))
    noise_floor = float(np.percentile(levels, 20)) if len(levels) else -200.0
    speech_level = float(np.percentile(levels, 90)) if len(levels) else -200.0
    active_threshold = max(-48.0, min(noise_floor + 9.0, speech_level - 3.0))
    active = levels > active_threshold
    active_s = float(np.count_nonzero(active) * frame / SR)
    peak_dbfs = float(20 * np.log10(max(float(np.max(np.abs(clip))) if len(clip) else 0.0, 1e-12)))
    usable = bool(len(clip) and active_s >= 0.35 and peak_dbfs >= -42.0)
    return {
        "usable": usable,
        "active_speech_s": round(active_s, 3),
        "peak_dbfs": round(peak_dbfs, 3),
        "noise_floor_dbfs": round(noise_floor, 3),
        "speech_level_dbfs": round(speech_level, 3),
        "active_threshold_dbfs": round(active_threshold, 3),
    }


def detected_voice_window(clip: np.ndarray, timeline_start_s: float, threshold_db: float = -38.0) -> tuple[float, float]:
    """Return one conservative speech window for ducking within a captured scene."""
    frame = int(0.020 * SR)
    active: list[int] = []
    for index in range(0, len(clip), frame):
        block = clip[index : index + frame]
        if len(block) == 0:
            continue
        power = float(np.mean(block ** 2))
        if 10 * np.log10(max(power, 1e-20)) > threshold_db:
            active.append(index)
    if not active:
        raise RuntimeError("Aucune parole active détectée dans la prise audio acceptée.")
    start = timeline_start_s + active[0] / SR
    end = timeline_start_s + min(len(clip), active[-1] + frame) / SR
    return (start, end)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--job", type=Path, help="Unified T2 RenderJob; required by the v0.6 orchestrator.")
    parser.add_argument("--visual-source", type=Path, help="Visual rebuilt from the same RenderJob on GitHub Actions.")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Rendu de production interdit hors GitHub Actions.")

    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_source_config(config)
    unified_job: dict[str, Any] | None = None
    unified_job_path: Path | None = None
    if args.job:
        unified_job_path = args.job.resolve()
        unified_job = json.loads(unified_job_path.read_text(encoding="utf-8"))
        validate_unified_job(unified_job, config, config_path)
    if args.visual_source and unified_job is None:
        raise ValueError("--visual-source exige --job afin de prouver la filiation du visuel.")
    publication = config["publication"]
    mix = config["mix_contract"]
    gates = config["quality_gates"]
    voice_config = config["voice"]
    selection = config["music_selection"]
    reference_exemplar = is_reference_exemplar(unified_job)

    output_mp4 = output_dir / publication["output_file"]
    report_path = output_dir / publication["validation_report"]
    human_report_path = output_dir / publication["human_report"]
    automation_path = output_dir / publication["automation_csv"]
    plot_path = output_dir / publication["timeline_plot"]

    with tempfile.TemporaryDirectory(prefix="t2-complete-voice-mix-") as temporary_name:
        temporary = Path(temporary_name)
        candidate_id = selection["candidate_id"]
        music_source = temporary / f"pixabay_candidate_{candidate_id}_source.mp3"
        if args.visual_source:
            visual = args.visual_source.resolve()
            if not visual.is_file():
                raise FileNotFoundError(f"Visuel unifié absent : {visual}")
            visual_download = {
                "mode": "rebuilt_from_same_render_job",
                "path": str(visual),
                "bytes": visual.stat().st_size,
                "sha256": sha256(visual),
                "published_as_standalone_asset": False,
            }
        else:
            visual = temporary / config["visual_source"]["asset_name"]
            visual_download = download(config["visual_source"]["url"], visual)
        music_download = download(selection["source_audio_url"], music_source)
        if music_download["sha256"] != selection["source_sha256"]:
            raise RuntimeError(
                f"Le SHA-256 de la source musicale {candidate_id} ne correspond pas au contrat chargé."
            )

        visual_probe = probe(visual)
        visual_video = only_streams(visual_probe, "video")
        if len(visual_video) != 1 or only_streams(visual_probe, "audio"):
            raise RuntimeError("Le visuel reconstruit doit contenir une vidéo et aucun audio.")
        visual_stream = visual_video[0]
        visual_file_hash = sha256(visual)
        visual_hash = stream_hash(visual, "0:v:0")
        visual_shape_ok = (
            int(visual_stream.get("width", 0)) == int(gates["required_width"])
            and int(visual_stream.get("height", 0)) == int(gates["required_height"])
            and visual_stream.get("r_frame_rate") == gates["required_video_fps"]
            and int(visual_stream.get("nb_frames", 0)) == int(gates["required_video_frames"])
        )
        if not visual_shape_ok:
            raise RuntimeError("Le visuel reconstruit ne respecte pas les 720×1280, 30 i/s et 900 images verrouillés.")
        visual_reference_integrity = None
        if reference_exemplar:
            visual_reference_integrity = reference_visual_integrity(
                observed_file_sha256=visual_file_hash,
                observed_video_stream_sha256=visual_hash,
                approved_file_sha256=config["visual_source"]["sha256"],
                approved_video_stream_sha256=config["visual_source"]["video_stream_sha256"],
            )

        music_probe = probe(music_source)
        source_audio_streams = only_streams(music_probe, "audio")
        if len(source_audio_streams) != 1:
            raise RuntimeError("Une unique source musicale est attendue.")
        source_duration = float(music_probe["format"]["duration"])
        required_music_duration = float(selection["source_start_s"]) + float(selection["program_duration_s"])
        if source_duration + 0.05 < required_music_duration:
            raise RuntimeError(f"La source musicale est trop courte: {source_duration:.3f} s")

        faded_music = temporary / f"music_{candidate_id}_faded_30s.wav"
        music_program_file = temporary / f"music_{candidate_id}_program_master_30s.wav"
        music_before, music_after = prepare_music_program(
            music_source, faded_music, music_program_file, selection
        )
        music_program = decode_audio(music_program_file, 2)
        if len(music_program) < N:
            music_program = np.pad(music_program, ((0, N - len(music_program)), (0, 0)))
        music_program = music_program[:N]

        voice = np.zeros(N, dtype=np.float64)
        voice_entries: list[dict[str, Any]] = []
        duck_spans: list[tuple[float, float]] = []
        voice_mode = (
            unified_job["audio_plan"]["voice"]["mode"]
            if unified_job is not None
            else "registered_voice_clips"
        )
        for item in voice_config["clips"]:
            scene = int(item["scene"])
            capture = unified_job["captures"][f"S{scene}"] if unified_job is not None else None
            capture_requested = voice_mode in {"captured_scene_audio", "captured_or_registered_fallback"}
            use_capture = capture_requested
            scene_start, scene_end = [float(value) for value in item["scene_window_s"]]
            capture_quality: dict[str, Any] | None = None
            fallback_reason: str | None = None
            extracted: Path | None = None
            if capture_requested:
                if capture is None or not capture["has_audio"]:
                    if voice_mode == "captured_scene_audio":
                        raise RuntimeError(f"La prise S{scene} ne contient aucun audio accepté.")
                    use_capture = False
                    fallback_reason = "capture_has_no_audio_stream"
                else:
                    source = ROOT / capture["uri"]
                    if sha256(source) != capture["sha256"]:
                        raise RuntimeError(f"La capture audio S{scene} ne correspond pas au RenderJob.")
                    extracted = temporary / f"captured_scene{scene}_identity.wav"
                    extract_capture_audio(
                        source,
                        extracted,
                        float(capture["source_in_ms"]) / 1000.0,
                        float(capture["duration_ms"]) / 1000.0,
                    )
                    captured_raw = decode_audio(extracted, 1)
                    capture_quality = captured_audio_qc(captured_raw)
                    if not capture_quality["usable"]:
                        if voice_mode == "captured_scene_audio":
                            raise RuntimeError(f"La prise S{scene} ne contient aucune parole exploitable.")
                        use_capture = False
                        fallback_reason = "capture_audio_failed_speech_usability_gate"
            if use_capture:
                assert capture is not None and extracted is not None
                normalization_source = extracted
                raw = decode_audio(extracted, 1)
                raw_duration = len(raw) / SR
                start_s = scene_start
                effective_item = {
                    **item,
                    "source": capture["uri"],
                    "source_sha256": capture["sha256"],
                    "source_duration_s": round(raw_duration, 6),
                    "text": "captured_scene_audio_no_transcript",
                }
                source_mode = "captured_scene_audio"
            else:
                source = ROOT / item["source"]
                if sha256(source) != item["source_sha256"]:
                    raise RuntimeError(f"La prise voix S{scene} ne correspond pas au contrat.")
                normalization_source = source
                raw = decode_audio(source, 1)
                raw_duration = len(raw) / SR
                if abs(raw_duration - float(item["source_duration_s"])) > 0.002:
                    raise RuntimeError(f"Durée source voix S{scene} inattendue: {raw_duration:.6f}")
                start_s = float(item["start_s"])
                effective_item = dict(item)
                source_mode = (
                    "registered_voice_fallback"
                    if capture_requested
                    else "registered_voice_clip"
                )

            processed = temporary / f"voice_scene{scene}_norm.wav"
            normalization = normalize_voice(
                normalization_source,
                processed,
                float(voice_config["normalization_target_lufs"]),
                float(voice_config["normalization_true_peak_dbtp_max"]),
            )
            clip = decode_audio(processed, 1)
            end_s = start_s + len(clip) / SR
            if start_s < scene_start or end_s > scene_end + 0.05:
                raise RuntimeError(
                    f"La voix S{scene} sort de sa scène: {start_s:.3f}–{end_s:.3f} / {scene_start:.3f}–{scene_end:.3f}"
                )
            start_sample = int(round(start_s * SR))
            count = min(len(clip), N - start_sample)
            voice[start_sample : start_sample + count] += clip[:count]
            duck_span = detected_voice_window(clip, start_s) if use_capture else (start_s, end_s)
            duck_spans.append(duck_span)
            voice_entries.append(
                {
                    **effective_item,
                    "source_mode": source_mode,
                    "capture_audio_qc": capture_quality,
                    "fallback_reason": fallback_reason,
                    "source_decoded_duration_s": round(raw_duration, 6),
                    "start_sample_48khz": start_sample,
                    "end_s": round(end_s, 6),
                    "duck_span_s": [round(duck_span[0], 6), round(duck_span[1], 6)],
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
        spans = duck_spans

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
        draw_ducking_plot(
            plot_path,
            voice,
            music_gain_db,
            spans,
            "Afrofire" if candidate_id == "D" else "musique B",
        )
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
                f"title=T2 complet voix francaise + musique {candidate_id}",
                "-metadata",
                "artist=Vitrine Video",
                "-metadata",
                f"comment=Musique {candidate_id} explicite; aucune selection implicite du gabarit",
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
            "visual_stream_identical_to_rebuilt_input": final_video_hash == visual_hash,
            "reference_v0_3_hash_match": (
                visual_hash == config["visual_source"]["video_stream_sha256"]
                if reference_exemplar
                else None
            ),
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
            "approved_music_contract": selection["candidate_id"] in {"B", "D"},
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
            "render_job": (
                {
                    "file": str(unified_job_path),
                    "job_id": unified_job["job_id"],
                    "idempotency_key": unified_job["idempotency_key"],
                    "sha256": sha256(unified_job_path),
                    "merchant_payload": unified_job["merchant_payload"],
                    "capture_sha256": {
                        slot: unified_job["captures"][slot]["sha256"]
                        for slot in ("S1", "S2", "S3", "S4")
                    },
                    "control_plane": unified_job["provenance"]["control_plane"],
                    "render_plane": unified_job["provenance"]["render_plane"],
                }
                if unified_job is not None and unified_job_path is not None
                else None
            ),
            "t1_audio_reference": config["reference_t1"],
            "visual_source": {
                **config["visual_source"],
                "mode": "reference_v0_3_exact" if reference_exemplar else "dynamic_rebuild_same_render_job",
                "reference_exemplar": reference_exemplar,
                "reference_video_stream_hash_enforced": reference_exemplar,
                "container_file_hash_provenance_only": True,
                "reference_integrity": visual_reference_integrity,
                "download": visual_download,
                "observed_file_sha256": visual_file_hash,
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
