#!/usr/bin/env python3
"""Black-box contract test for a local Wrangler T2 control plane."""
from __future__ import annotations

import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
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
    expected: int | tuple[int, ...] = 200,
) -> tuple[bytes, dict[str, str], int]:
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
    allowed = (expected,) if isinstance(expected, int) else expected
    if status not in allowed:
        raise AssertionError(f"{method} {path}: HTTP {status}, attendu {allowed}: {payload.decode(errors='replace')}")
    return payload, response_headers, status


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
    assert as_json(call(args.base, "/v1/contracts/music-pool")[0]) == json.loads((ROOT / "config/T2_music_pool_v1_0_0.json").read_text())
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
    assert job["audio_plan"]["music"]["selected_candidate_id"] in {"A", "B", "C", "D"}
    assert job["audio_plan"]["music"]["requested_candidate_id"] == "auto"
    assert job["audio_plan"]["music"]["last_successful_music_id"] is None
    assert job["audio_plan"]["music"]["state_update_policy"] == "after_success_only"
    assert job["audio_plan"]["music"]["owner_approved"] is True
    assert job["runtime_contract"] == "config/T2_runtime_contract_v1_0_0.json"
    for slot in ("S1", "S2", "S3", "S4"):
        assert call(args.base, f"/v1/jobs/{job_id}/captures/{slot}", headers=auth)[0] == media

    invalid_callback = json.dumps({"status": "COMPLETED", "result": {"job_id": "wrong"}}).encode()
    invalid = as_json(call(args.base, f"/v1/jobs/{job_id}/events", method="POST", body=invalid_callback, headers={**auth, "content-type": "application/json"}, expected=422)[0])
    assert invalid["code"] == "T2_INVALID_CALLBACK_PAYLOAD"

    result = json.loads((ROOT / "fixtures/t2-avant-apres/render_result.valid.json").read_text())
    result["job_id"] = job_id
    result["idempotency_key"] = nonce
    result["control_plane"] = "cloudflare_worker"
    result["inputs"]["capture_sha256"] = {slot: media_sha for slot in ("S1", "S2", "S3", "S4")}
    result["inputs"]["music_source_sha256"] = job["audio_plan"]["music"]["source_sha256"]
    result["output"]["uri"] = job["output"]["uri"]
    Draft202012Validator(json.loads((ROOT / "schemas/render_result.schema.json").read_text())).validate(result)

    wrong_music = json.loads(json.dumps(result))
    wrong_music["inputs"]["music_source_sha256"] = "0" * 64
    mismatch = as_json(call(
        args.base,
        f"/v1/jobs/{job_id}/events",
        method="POST",
        body=json.dumps({"status": "COMPLETED", "result": wrong_music}).encode(),
        headers={**auth, "content-type": "application/json"},
        expected=422,
    )[0])
    assert mismatch["code"] == "T2_INVALID_CALLBACK_PAYLOAD"

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
    music_state = as_json(call(args.base, "/v1/music-state", headers=auth)[0])
    assert music_state["last_successful_music_id"] == job["audio_plan"]["music"]["selected_candidate_id"]
    assert music_state["last_successful_render_job_id"] == job_id
    assert music_state["successful_render_count"] == 1

    def prepare_explicit(music_id: str, *, expected_dispatch: int = 202) -> tuple[str, str, dict[str, Any] | None, dict[str, Any]]:
        idem = f"integration-{music_id.lower()}-{time.time_ns()}"
        body = json.dumps(
            {"merchant_payload": merchant_payload, "voice_mode": "captured_or_registered_fallback", "music_id": music_id},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {**client_auth, "content-type": "application/json", "idempotency-key": idem}
        created_job = as_json(call(args.base, "/v1/jobs", method="POST", body=body, headers=headers, expected=201)[0])
        prepared_id = created_job["job_id"]
        for slot, duration, frames in (("S1", 6000, 180), ("S2", 8000, 240), ("S3", 7000, 210), ("S4", 9000, 270)):
            upload_headers = {
                **client_auth,
                "content-type": "video/mp4",
                "content-length": str(len(media)),
                "x-content-sha256": media_sha,
                "x-video-width": "1080",
                "x-video-height": "1920",
                "x-video-fps": "30",
                "x-video-frames": str(frames),
                "x-video-duration-ms": str(duration),
                "x-video-codec": "h264",
                "x-has-audio": "true",
                "x-audio-codec": "aac",
            }
            call(args.base, f"/v1/jobs/{prepared_id}/captures/{slot}", method="PUT", body=media, headers=upload_headers, expected=201)
        dispatch_payload = as_json(call(
            args.base,
            f"/v1/jobs/{prepared_id}/dispatch",
            method="POST",
            headers=client_auth,
            expected=expected_dispatch,
        )[0])
        if expected_dispatch != 202:
            return prepared_id, idem, None, dispatch_payload
        prepared_job = as_json(call(args.base, f"/v1/jobs/{prepared_id}/payload", headers=auth)[0])["job"]
        return prepared_id, idem, prepared_job, dispatch_payload

    selected_id = job["audio_plan"]["music"]["selected_candidate_id"]
    _, _, _, repeat_error = prepare_explicit(selected_id, expected_dispatch=400)
    assert repeat_error["code"] == "T2_INVALID_REQUEST"
    assert as_json(call(args.base, "/v1/music-state", headers=auth)[0]) == music_state

    alternative_id = next(candidate for candidate in ("A", "B", "C", "D") if candidate != selected_id)
    failed_id, _, failed_job, _ = prepare_explicit(alternative_id)
    assert failed_job is not None and failed_job["audio_plan"]["music"]["selected_candidate_id"] == alternative_id
    render_error = json.loads((ROOT / "fixtures/t2-avant-apres/render_error.unsupported_media.json").read_text())
    render_error["job_id"] = failed_id
    failed_callback = as_json(call(
        args.base,
        f"/v1/jobs/{failed_id}/events",
        method="POST",
        body=json.dumps({"status": "FAILED", "error": render_error}).encode(),
        headers={**auth, "content-type": "application/json"},
    )[0])
    assert failed_callback["status"] == "FAILED"
    assert as_json(call(args.base, "/v1/music-state", headers=auth)[0]) == music_state

    concurrent_jobs = [prepare_explicit(alternative_id), prepare_explicit(alternative_id)]

    def result_for(prepared_id: str, idem: str, prepared_job: dict[str, Any]) -> dict[str, Any]:
        prepared_result = json.loads((ROOT / "fixtures/t2-avant-apres/render_result.valid.json").read_text())
        prepared_result["job_id"] = prepared_id
        prepared_result["idempotency_key"] = idem
        prepared_result["control_plane"] = "cloudflare_worker"
        prepared_result["inputs"]["capture_sha256"] = {slot: media_sha for slot in ("S1", "S2", "S3", "S4")}
        prepared_result["inputs"]["music_source_sha256"] = prepared_job["audio_plan"]["music"]["source_sha256"]
        prepared_result["output"]["uri"] = prepared_job["output"]["uri"]
        return prepared_result

    def complete_concurrently(prepared: tuple[str, str, dict[str, Any] | None, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        prepared_id, idem, prepared_job, _ = prepared
        assert prepared_job is not None
        event = {
            "status": "COMPLETED",
            "github_run_id": prepared_id,
            "github_run_url": f"https://github.com/example/actions/runs/{prepared_id}",
            "result": result_for(prepared_id, idem, prepared_job),
        }
        payload, _, status = call(
            args.base,
            f"/v1/jobs/{prepared_id}/events",
            method="POST",
            body=json.dumps(event).encode(),
            headers={**auth, "content-type": "application/json"},
            expected=(200, 409),
        )
        return status, as_json(payload)

    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent_results = list(executor.map(complete_concurrently, concurrent_jobs))
    assert sorted(status for status, _ in concurrent_results) == [200, 409], concurrent_results
    conflict = next(payload for status, payload in concurrent_results if status == 409)
    assert conflict["code"] == "T2_MUSIC_STATE_CONFLICT"
    final_music_state = as_json(call(args.base, "/v1/music-state", headers=auth)[0])
    assert final_music_state["last_successful_music_id"] == alternative_id
    assert final_music_state["successful_render_count"] == 2
    print("T2_CLOUDFLARE_CONTROL_PLANE_INTEGRATION_OK", job_id)


if __name__ == "__main__":
    main()
