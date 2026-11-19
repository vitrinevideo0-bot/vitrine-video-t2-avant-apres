#!/usr/bin/env python3
"""Tiny local repository_dispatch endpoint used only by CI integration tests."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        assert self.path == "/repos/vitrinevideo0-bot/vitrine-video-t2-avant-apres/dispatches"
        assert payload["event_type"] == "t2_render_job"
        assert set(payload["client_payload"]) == {"job_id", "api_base"}
        self.send_response(204)
        self.end_headers()

    def log_message(self, message: str, *args: object) -> None:
        print(message % args, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
