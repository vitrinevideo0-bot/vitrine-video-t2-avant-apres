#!/usr/bin/env python3
"""Black-box contract test for a local Wrangler T2 control plane."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def call(
    base: str,
    path: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    expected: int = 200,
) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(base.rstrip("/") + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            payload = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as error:
        status = error.code
        payload = error.read()
        response_headers = dict(error.headers.items())
    if status != expected:
        raise AssertionError(f"{method} {path}: HTTP {status}, attendu {expected}: {payload.decode(errors='replace')}")
    return payload, response_headers


def as_json(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8787")
    parser.add_argument("--client-token", default="test-client")
    parser.add_argument("--callback-token", default="test-callback")
    args = parser.parse_args()

    health = as_json(call(args.base, "/health")[0])
    assert health == {"status": "ok", "service": "t2-avant-apres-control-plane", "render_plane": "github_actions"}
    assert as_json(call(args.base, "/v1/contracts/form")[0]) == json.loads((ROOT / "form/questions_T2.json").read_text())
    assert as_json(call(args.base, "/v1/contracts/capture-flow")[0]) == json.loads((ROOT / "config/T2_capture_flow_v1_0_0.json").read_text())
    index = call(args.base, "/")[0].decode("utf-8")
    assert "12 ÉCRANS" in index and "/app.js" in index

    nonce = f"integration-{time.time_ns()}"
    merchant_payload = {
        "nom": "Le Jardin de Kandi",
        "produit": "Poulet braisé à l’alloco",
        "prix": "2 500",
        "whatsapp": "01 00 00 00 00",
        "quartier": "Gansosso — Kandi",
        "accroche": "",
    }
    create_body = json.dumps(
        {"merchant_payload": merchant_payload, "voice_mode": "captured_or_registered_fallback"},
        ensure_ascii=False,
    ).encode("utf-8")
    client_auth = {"authorization": f"Bearer {args.client_token}"}
    create_headers = {**client_auth, "content-type": "application/json", "idempotency-key": nonce}
    created = as_json(call(args.base, "/v1/jobs", method="POST", body=create_body, headers=create_headers, expected=201)[0])
    job_id = created["job_id"]
    assert created["status"] == "UPLOADING"
    replay = as_json(call(args.base, "/v1/jobs", method="POST", body=create_body, headers=create_headers)[0])
    assert replay == {"job_id": job_id, "status": "UPLOADING", "idempotent_replay": True}

    unsupported_headers = {
        **client_auth,
        "content-type": "application/octet-stream",
        "content-length": "4",
        "x-content-sha256": hashlib.sha256(b"test").hexdigest(),
    }
    unsupported = as_json(call(args.base, f"/v1/jobs/{job_id}/captures/S1", method="PUT", body=b"test", headers=unsupported_headers, expected=415)[0])
    assert unsupported["code"] == "T2_UNSUPPORTED_MEDIA"

    media = f"t2-control-plane-{job_id}".encode("utf-8")
    media_sha = hashlib.sha256(media).hexdigest()
    for slot, duration, frames in (("S1", 6000, 180), ("S2", 8000, 240), ("S3", 7000, 210), ("S4", 9000, 270)):
        browser_webm = slot == "S1"
        headers = {
            **client_auth,
            "content-type": "video/webm" if browser_webm else "video/mp4",
            "content-length": str(len(media)),
            "x-content-sha256": media_sha,
            "x-video-width": "1080",
            "x-video-height": "1920",
            "x-video-fps": "30",
            "x-video-frames": str(frames),
            "x-video-duration-ms": str(duration),
            "x-video-codec": "vp8" if browser_webm else "h264",
            "x-has-audio": "true",
            "x-audio-codec": "opus" if browser_webm else "aac",
        }
        uploaded = as_json(call(args.base, f"/v1/jobs/{job_id}/captures/{slot}", method="PUT", body=media, headers=headers, expected=201)[0])
        assert uploaded["sha256"] == media_sha
    assert uploaded["status"] == "READY"

    dispatched = as_json(call(args.base, f"/v1/jobs/{job_id}/dispatch", method="POST", headers=client_auth, expected=202)[0])
    assert dispatched == {"job_id": job_id, "status": "QUEUED"}

    auth = {"authorization": f"Bearer {args.callback_token}"}
    job = as_json(call(args.base, f"/v1/jobs/{job_id}/payload", headers=auth)[0])["job"]
    Draft202012Validator(json.loads((ROOT / "schemas/render_job.schema.json").read_text())).validate(job)
    assert job["merchant_payload"] == merchant_payload
    assert job["provenance"]["control_plane"] == "cloudflare_worker"
    assert job["provenance"]["render_plane"] == "github_actions"
    assert job["audio_plan"]["voice"]["mode"] == "captured_or_registered_fallback"
    assert job["audio_plan"]["voice"]["fallback_policy"] == "registered_clips_when_capture_has_no_usable_speech"
    assert job["audio_plan"]["music"]["selected_candidate_id"] == "B"
    assert job["runtime_contract"] == "config/T2_runtime_contract_v0_6_0.json"
    for slot in ("S1", "S2", "S3", "S4"):
        assert call(args.base, f"/v1/jobs/{job_id}/captures/{slot}", headers=auth)[0] == media

    invalid_callback = json.dumps({"status": "COMPLETED", "result": {"job_id": "wrong"}}).encode()
    invalid = as_json(call(args.base, f"/v1/jobs/{job_id}/events", method="POST", body=invalid_callback, headers={**auth, "content-type": "application/json"}, expected=422)[0])
    assert invalid["code"] == "T2_INVALID_CALLBACK_PAYLOAD"

    result = json.loads((ROOT / "fixtures/t2-avant-apres/render_result.valid.json").read_text())
    result["job_id"] = job_id
    result["idempotency_key"] = nonce
    result["control_plane"] = "cloudflare_worker"
    Draft202012Validator(json.loads((ROOT / "schemas/render_result.schema.json").read_text())).validate(result)
    completed = as_json(call(
        args.base,
        f"/v1/jobs/{job_id}/events",
        method="POST",
        body=json.dumps({"status": "COMPLETED", "github_run_id": "123", "github_run_url": "https://github.com/example/actions/runs/123", "result": result}).encode(),
        headers={**auth, "content-type": "application/json"},
    )[0])
    assert completed == {"job_id": job_id, "status": "COMPLETED"}
    final = as_json(call(args.base, f"/v1/jobs/{job_id}")[0])
    assert final["status"] == "COMPLETED" and final["result"]["job_id"] == job_id
    print("T2_CLOUDFLARE_CONTROL_PLANE_INTEGRATION_OK", job_id)


if __name__ == "__main__":
    main()
