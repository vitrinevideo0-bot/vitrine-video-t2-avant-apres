#!/usr/bin/env python3
"""Bridge Cloudflare's T2 control plane to the GitHub Actions render plane."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
RENDER_JOB_SCHEMA = ROOT / "schemas/render_job.schema.json"


def validate_api_base(api_base: str) -> str:
    normalized = api_base.rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("L'origine Cloudflare doit être une URL HTTPS sans identifiants.")
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("L'origine Cloudflare ne doit contenir ni chemin, ni requête, ni fragment.")
    expected = os.environ.get("CF_EXPECTED_API_BASE", "").rstrip("/")
    if expected and normalized != expected:
        raise ValueError("L'origine Cloudflare ne correspond pas à la variable GitHub approuvée.")
    return normalized


def request_json(url: str, token: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(4):
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "T2-GitHub-Actions-Cloudflare-Bridge/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            if attempt == 3:
                raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
        time.sleep(2**attempt)
    raise AssertionError("unreachable")


def download(url: str, token: str, destination: Path, expected_sha256: str) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/octet-stream",
            "User-Agent": "T2-GitHub-Actions-Cloudflare-Bridge/1.0",
        },
    )
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=180) as response, destination.open("wb") as target:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(block)
            target.write(block)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Capture Cloudflare corrompue: {actual} != {expected_sha256}")


def fetch_job(api_base: str, token: str, job_id: str, output: Path) -> dict[str, Any]:
    api_base = validate_api_base(api_base)
    payload = request_json(f"{api_base}/v1/jobs/{job_id}/payload", token)
    job = payload["job"]
    Draft202012Validator(
        json.loads(RENDER_JOB_SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(job)
    if job["job_id"] != job_id:
        raise ValueError("Le job renvoyé par Cloudflare ne correspond pas à la demande.")
    if job["provenance"]["control_plane"] != "cloudflare_worker":
        raise ValueError("Le RenderJob ne déclare pas Cloudflare comme plan de contrôle.")
    manifest_sources = []
    for scene in range(1, 5):
        slot = f"S{scene}"
        capture = job["captures"][slot]
        relative = Path(capture["uri"])
        if relative.is_absolute() or ".." in relative.parts or not str(relative).startswith("rushes/runtime/"):
            raise ValueError(f"URI de capture Cloudflare non sûre : {relative}")
        destination = ROOT / relative
        download(
            f"{api_base}/v1/jobs/{job_id}/captures/{slot}",
            token,
            destination,
            capture["sha256"],
        )
        manifest_sources.append(
            {
                "scene": scene,
                "local_file": str(relative),
                "sha256": capture["sha256"],
                "source_metadata": {
                    "width": capture["width"],
                    "height": capture["height"],
                    "fps": capture["fps"],
                    "frame_count": capture["frame_count"],
                    "video_codec": capture["video_codec"],
                    "audio_codec": capture["audio_codec"],
                    "has_audio": capture["has_audio"],
                },
                "edit": {
                    "start": capture["source_in_ms"] / 1000.0,
                    "duration": capture["duration_ms"] / 1000.0,
                },
            }
        )
    manifest_relative = Path(job["capture_manifest"])
    manifest_path = ROOT / manifest_relative
    if manifest_relative.is_absolute() or ".." in manifest_relative.parts or not str(manifest_relative).startswith("rushes/runtime/"):
        raise ValueError("Chemin de manifeste runtime non sûr.")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"runtime": True, "job_id": job_id, "sources": manifest_sources}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return job


def callback(api_base: str, token: str, job_id: str, event_file: Path) -> dict[str, Any]:
    payload = json.loads(event_file.read_text(encoding="utf-8"))
    api_base = validate_api_base(api_base)
    return request_json(
        f"{api_base}/v1/jobs/{job_id}/events",
        token,
        method="POST",
        payload=payload,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    get = sub.add_parser("fetch")
    get.add_argument("--api-base", required=True)
    get.add_argument("--token", required=True)
    get.add_argument("--job-id", required=True)
    get.add_argument("--output", type=Path, required=True)
    post = sub.add_parser("callback")
    post.add_argument("--api-base", required=True)
    post.add_argument("--token", required=True)
    post.add_argument("--job-id", required=True)
    post.add_argument("--event", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        job = fetch_job(args.api_base, args.token, args.job_id, args.output.resolve())
        print("CLOUDFLARE_JOB_MATERIALIZED", job["job_id"])
    else:
        response = callback(args.api_base, args.token, args.job_id, args.event.resolve())
        print("CLOUDFLARE_CALLBACK_OK", json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    main()
