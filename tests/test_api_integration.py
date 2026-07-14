from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from e2e_verification.api_harness import run_api
from e2e_verification.environment import detect_runtime


class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        if self.path == "/auth/login" and payload == {"username": "admin", "password": "test-password"}:
            self.respond(200, {"data": {"accessToken": "synthetic-token"}})
        else:
            self.respond(401, {"error": "invalid"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/users" and self.headers.get("Authorization") == "Bearer synthetic-token":
            self.respond(200, {"data": []})
        else:
            self.respond(403, {"error": "forbidden"})

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Request-Id", "synthetic-request")
        self.end_headers()
        self.wfile.write(body)


@unittest.skipUnless(os.environ.get("E2E_RUN_NETWORK_TESTS") == "1", "set E2E_RUN_NETWORK_TESTS=1 where loopback sockets are allowed")
class ApiIntegrationTest(unittest.TestCase):
    def test_login_token_and_probe_contract(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = {
            "defaults": {"api_base": f"http://127.0.0.1:{server.server_port}", "request_timeout_seconds": 2},
            "api_login": {
                "path": "/auth/login",
                "body": {"username": "${account.id}", "password": "${account.password}"},
                "token_path": "data.accessToken",
            },
            "roles": [{"name": "ADMIN", "account": {"id_env": "TEST_ADMIN_ID", "password_env": "TEST_ADMIN_PASSWORD"}}],
            "api_probes": [{"id": "API-1", "role": "ADMIN", "method": "GET", "path": "/users", "expected_status": [200]}],
        }
        try:
            with patch.dict(os.environ, {"TEST_ADMIN_ID": "admin", "TEST_ADMIN_PASSWORD": "test-password"}, clear=False):
                with tempfile.TemporaryDirectory() as directory:
                    report = run_api(
                        config,
                        argparse.Namespace(
                            api_base=None,
                            target_mode="container-local" if detect_runtime().in_container else "host",
                            host_alias="host.docker.internal",
                            preflight_connect=False,
                        ),
                        Path(directory),
                    )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual({"total": 1, "passed": 1, "failed": 0, "blocked": 0}, report["summary"])
        self.assertEqual("synthetic-request", report["rows"][0]["requestId"])


if __name__ == "__main__":
    unittest.main()
