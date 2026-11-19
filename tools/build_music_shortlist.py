#!/usr/bin/env python3
"""Construit quatre auditions musique+image exclusivement sur un runner GitHub."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

EXPECTED_IDS = ["A", "B", "C", "D"]
LICENSE_URL = "https://pixabay.com/service/license-summary/"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def ffprobe(path: Path) -> dict[str, Any]:
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def video_stream_hash(path: Path) -> str:
    value = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ]
    )
    if not value.startswith("SHA256="):
        raise RuntimeError(f"Hash vidéo ffmpeg inattendu: {value}")
    return value.split("=", 1)[1].lower()


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("status") != "audition_only_no_selection":
        raise ValueError("La présélection doit rester une audition sans choix final.")
    if manifest.get("provider", {}).get("license_url") != LICENSE_URL:
        raise ValueError("La licence Pixabay canonique doit être verrouillée.")
    if manifest.get("provider", {}).get("standalone_redistribution_forbidden") is not True:
        raise ValueError("L'interdiction de redistribution autonome doit être explicite.")

    audition = manifest.get("audition_contract", {})
    if audition.get("final_selection") is not None:
        raise ValueError("Aucune musique finale ne doit être présélectionnée automatiquement.")
    if audition.get("publish_source_audio") is not False:
        raise ValueError("Les MP3 source ne doivent jamais être publiés.")
    if audition.get("publish_derivative_video_only") is not True:
        raise ValueError("Seules les auditions vidéo dérivées peuvent être publiées.")
    if audition.get("visual_stream_policy") != "bitstream_copy_from_approved_v0_3":
        raise ValueError("Le flux vidéo v0.3 doit être copié sans réencodage.")

    mix = manifest.get("future_mix_contract", {})
    if mix.get("preserve_captured_voice") is not True or mix.get("captured_voice_speed") != 1.0:
        raise ValueError("La future voix doit rester prioritaire et à vitesse 1×.")
    if mix.get("source_time_map") != "identity" or mix.get("audio_time_map") != "identity":
        raise ValueError("La continuité caméra/voix doit rester à l'identité.")
    if mix.get("music_ducking_when_speech_present") is not True:
        raise ValueError("Le ducking musique sous la parole doit être réservé.")
    if mix.get("active_in_current_auditions") is not False:
        raise ValueError("Le mix voix ne doit pas être activé dans ces auditions.")

    base = manifest.get("approved_visual_base", {})
    if base.get("sha256") != "67c447dae81241fc9ecc34ee9edfbf8c354a6ddf76e7fa465a62cdac59550ada":
        raise ValueError("La base visuelle doit rester le rendu v0.3 validé.")
    if base.get("audio_streams") != 0 or base.get("frames") != 900:
        raise ValueError("La base doit être la vidéo v0.3 silencieuse de 900 images.")

    candidates = manifest.get("candidates", [])
    if [item.get("id") for item in candidates] != EXPECTED_IDS:
        raise ValueError("La shortlist doit contenir exactement A, B, C et D dans cet ordre.")
    outputs: set[str] = set()
    for item in candidates:
        source_page = urlparse(item.get("source_page", ""))
        source_audio = urlparse(item.get("source_audio_url", ""))
        if source_page.scheme != "https" or source_page.netloc != "pixabay.com":
            raise ValueError(f"Page Pixabay invalide pour {item.get('id')}")
        if source_audio.scheme != "https" or source_audio.netloc != "cdn.pixabay.com":
            raise ValueError(f"Source CDN Pixabay invalide pour {item.get('id')}")
        if item.get("content_id_status") not in {"registered", "not_displayed_on_source_page"}:
            raise ValueError(f"Statut Content ID absent pour {item.get('id')}")
        duration = float(item.get("duration_seconds", 0))
        start = float(item.get("preview_start_seconds", -1))
        preview = float(item.get("preview_duration_seconds", 0))
        if start < 0 or preview != 30.0 or start + preview > duration + 0.01:
            raise ValueError(f"Fenêtre d'audition invalide pour {item.get('id')}")
        output = item.get("output_file", "")
        if not output.endswith("_AUDITION_30S.mp4") or output in outputs:
            raise ValueError(f"Nom de sortie invalide ou dupliqué pour {item.get('id')}")
        outputs.add(output)


def download(url: str, destination: Path) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "T2-GitHub-Actions-Music-Audition/0.4 (+https://github.com/vitrinevideo0-bot/vitrine-video-t2-avant-apres)"
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as target:
        content_type = response.headers.get("Content-Type", "")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
        final_url = response.geturl()
    if destination.stat().st_size < 100_000:
        raise RuntimeError(f"Téléchargement anormalement court: {url}")
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def only_streams(probe: dict[str, Any], codec_type: str) -> list[dict[str, Any]]:
    return [stream for stream in probe.get("streams", []) if stream.get("codec_type") == codec_type]


def validate_base(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest["approved_visual_base"]
    actual_sha = sha256_file(path)
    if actual_sha != expected["sha256"]:
        raise RuntimeError(f"SHA-256 base v0.3 invalide: {actual_sha}")
    probe = ffprobe(path)
    video = only_streams(probe, "video")
    audio = only_streams(probe, "audio")
    if len(video) != 1 or audio:
        raise RuntimeError("La base v0.3 doit contenir une vidéo et zéro audio.")
    stream = video[0]
    if int(stream["width"]) != expected["width"] or int(stream["height"]) != expected["height"]:
        raise RuntimeError("Dimensions de la base v0.3 invalides.")
    if stream.get("r_frame_rate") != "30/1" or int(stream.get("nb_frames", "0")) != expected["frames"]:
        raise RuntimeError("Cadence ou nombre d'images de la base v0.3 invalide.")
    return {
        "sha256": actual_sha,
        "bytes": path.stat().st_size,
        "video_stream_sha256": video_stream_hash(path),
        "probe": probe,
    }


def render_audition(
    base_video: Path,
    source_audio: Path,
    output: Path,
    candidate: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    duration = float(candidate["preview_duration_seconds"])
    fade_out_start = duration - float(contract["fade_out_seconds"])
    audio_filter = (
        f"loudnorm=I={float(contract['music_target_lufs'])}:LRA=7:TP={float(contract['true_peak_db'])},"
        f"afade=t=in:st=0:d={float(contract['fade_in_seconds'])},"
        f"afade=t=out:st={fade_out_start}:d={float(contract['fade_out_seconds'])}"
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(float(candidate["preview_start_seconds"])),
            "-i",
            str(source_audio),
            "-i",
            str(base_video),
            "-filter_complex",
            f"[0:a:0]{audio_filter}[music]",
            "-map",
            "1:v:0",
            "-map",
            "[music]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-t",
            str(duration),
            "-movflags",
            "+faststart",
            "-metadata",
            f"title=T2 audition {candidate['id']} - {candidate['title']}",
            "-metadata",
            f"artist={candidate['artist']}",
            "-metadata",
            "comment=Audition non finale - source Pixabay integree au montage T2 v0.3",
            str(output),
        ]
    )


def validate_audition(
    output: Path,
    base_stream_hash: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    probe = ffprobe(output)
    videos = only_streams(probe, "video")
    audios = only_streams(probe, "audio")
    if len(videos) != 1 or len(audios) != 1:
        raise RuntimeError(f"Flux invalides dans {output.name}")
    video = videos[0]
    audio = audios[0]
    if int(video["width"]) != 720 or int(video["height"]) != 1280:
        raise RuntimeError(f"Dimensions invalides dans {output.name}")
    if video.get("r_frame_rate") != "30/1" or int(video.get("nb_frames", "0")) != 900:
        raise RuntimeError(f"Cadence ou images invalides dans {output.name}")
    if audio.get("codec_name") != "aac" or int(audio.get("sample_rate", "0")) != 48000:
        raise RuntimeError(f"Audio AAC 48 kHz attendu dans {output.name}")
    duration = float(probe["format"]["duration"])
    if not 29.95 <= duration <= 30.05:
        raise RuntimeError(f"Durée invalide {duration:.3f}s dans {output.name}")
    stream_hash = video_stream_hash(output)
    if stream_hash != base_stream_hash:
        raise RuntimeError(f"Le flux vidéo v0.3 a changé dans {output.name}")
    return {
        "id": candidate["id"],
        "title": candidate["title"],
        "artist": candidate["artist"],
        "source_page": candidate["source_page"],
        "content_id_status": candidate["content_id_status"],
        "output_file": output.name,
        "output_sha256": sha256_file(output),
        "output_bytes": output.stat().st_size,
        "duration_seconds": duration,
        "video_stream_sha256": stream_hash,
        "audio_codec": audio["codec_name"],
        "audio_sample_rate": int(audio["sample_rate"]),
        "audio_channels": int(audio["channels"]),
        "video_width": int(video["width"]),
        "video_height": int(video["height"]),
        "video_frames": int(video["nb_frames"]),
        "video_fps": video["r_frame_rate"],
    }


def build_index(manifest: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# T2 — quatre auditions musicales Afrobeat",
        "",
        "Ces fichiers associent chaque musique au montage visuel v0.3 validé. Ils servent uniquement au choix; aucune musique n'est encore définitive.",
        "",
    ]
    for item in manifest["candidates"]:
        lines.extend(
            [
                f"## {item['id']} — {item['title']} · {item['artist']}",
                "",
                f"- Fichier: `{item['output_file']}`",
                f"- Couleur: {item['style_label']}",
                f"- Source officielle: {item['source_page']}",
                f"- Content ID: {item['content_id_status']}",
                f"- Pourquoi T2: {item['fit_for_t2']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Règle de choix",
            "",
            "Répondre A, B, C ou D. Le mix final ne démarre qu'après ce choix explicite.",
            "",
        ]
    )
    (output_dir / "T2_MUSIC_SHORTLIST_V0_4_0.md").write_text("\n".join(lines), encoding="utf-8")


def build(manifest_path: Path, output_dir: Path, proof_path: Path) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Production interdite hors GitHub Actions.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="t2-music-shortlist-") as temp_name:
        temp = Path(temp_name)
        base_path = temp / manifest["approved_visual_base"]["asset_name"]
        base_download = download(manifest["approved_visual_base"]["asset_url"], base_path)
        base_validation = validate_base(base_path, manifest)

        results = []
        source_evidence = []
        for candidate in manifest["candidates"]:
            source_path = temp / f"source_{candidate['id']}.mp3"
            source_download = download(candidate["source_audio_url"], source_path)
            source_probe = ffprobe(source_path)
            source_audios = only_streams(source_probe, "audio")
            if len(source_audios) != 1:
                raise RuntimeError(f"Une source audio unique est attendue pour {candidate['id']}")
            measured_duration = float(source_probe["format"]["duration"])
            required_duration = float(candidate["preview_start_seconds"]) + float(candidate["preview_duration_seconds"])
            if measured_duration + 0.05 < required_duration:
                raise RuntimeError(f"Source trop courte pour {candidate['id']}: {measured_duration}")
            if abs(measured_duration - float(candidate["duration_seconds"])) > 2.0:
                raise RuntimeError(f"Durée source incohérente avec la page pour {candidate['id']}: {measured_duration}")
            output_path = output_dir / candidate["output_file"]
            render_audition(base_path, source_path, output_path, candidate, manifest["audition_contract"])
            results.append(validate_audition(output_path, base_validation["video_stream_sha256"], candidate))
            source_evidence.append(
                {
                    "id": candidate["id"],
                    "official_page": candidate["source_page"],
                    "download": source_download,
                    "measured_duration_seconds": measured_duration,
                    "codec": source_audios[0].get("codec_name"),
                    "sample_rate": int(source_audios[0].get("sample_rate", 0)),
                    "published_as_standalone_asset": False,
                }
            )
            source_path.unlink()

    build_index(manifest, output_dir)
    manifest_sha = sha256_file(manifest_path)
    proof = {
        "proof_version": "1.0.0",
        "status": "valid",
        "purpose": "four_music_auditions_no_final_selection",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_on_github_actions": True,
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "license_url": LICENSE_URL,
        "source_audio_published": False,
        "approved_visual_base": {
            "download": base_download,
            **base_validation,
        },
        "source_evidence": source_evidence,
        "auditions": results,
        "final_selection": None,
        "future_voice_mix_active": False,
    }
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checksums = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file():
            checksums.append(f"{sha256_file(path)}  {path.name}")
    checksums.append(f"{sha256_file(proof_path)}  {proof_path.name}")
    checksums.append(f"{manifest_sha}  {manifest_path.name}")
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    build(args.manifest, args.output_dir, args.proof)
