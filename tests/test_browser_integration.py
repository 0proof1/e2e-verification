from __future__ import annotations

import argparse
import functools
import http.server
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from e2e_verification.browser_harness import run_browser


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@unittest.skipUnless(os.environ.get("E2E_RUN_BROWSER_TESTS") == "1", "set E2E_RUN_BROWSER_TESTS=1 with Chromium installed")
class BrowserIntegrationTest(unittest.TestCase):
    def test_login_route_menu_control_and_response_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "login.html").write_text(
                """<form id="login"><input name="username"><input name="password" type="password"><button type="submit">Sign in</button></form><script>document.querySelector('#login').onsubmit=(e)=>{e.preventDefault();location.href='dashboard.html'}</script>""",
                encoding="utf-8",
            )
            (root / "dashboard.html").write_text(
                """<nav>Users</nav><button data-testid="refresh">Refresh</button><p id="done" hidden>Done</p><script>document.querySelector('button').onclick=()=>fetch('data:application/json,{}').then(()=>document.querySelector('#done').hidden=false)</script>""",
                encoding="utf-8",
            )
            handler = functools.partial(QuietHandler, directory=str(root))
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            config = {
                "defaults": {"web_base": base, "settle_ms": 10},
                "browser_login": {
                    "path": "/login.html", "id_selector": "[name=username]", "password_selector": "[name=password]",
                    "submit_selector": "button[type=submit]", "settle_ms": 50,
                },
                "roles": [{
                    "name": "ADMIN", "home_path": "/dashboard.html",
                    "account": {"id_env": "TEST_ADMIN_ID", "password_env": "TEST_ADMIN_PASSWORD"},
                    "menus": [{"label": "Users"}], "routes": [{"path": "/dashboard.html", "outcome": "ALLOW"}],
                }],
                "browser_probes": [{
                    "id": "UI-1", "role": "ADMIN", "route": "/dashboard.html", "selector": "button[data-testid=refresh]",
                    "action": "click", "risk": "read-only", "after_ms": 100,
                    "expect": {"visible_selector": "#done:not([hidden])"},
                }],
            }
            try:
                with patch.dict(os.environ, {"TEST_ADMIN_ID": "admin", "TEST_ADMIN_PASSWORD": "test-password"}, clear=False):
                    report = run_browser(
                        config,
                        argparse.Namespace(
                            web_base=None,
                            headed=False,
                            timeout_seconds=5,
                            target_mode="host",
                            host_alias="host.docker.internal",
                            preflight_connect=False,
                        ),
                        root / "out",
                    )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
        self.assertEqual(0, report["summary"]["failed"])
        self.assertEqual(0, report["summary"]["serverErrors"])
        self.assertEqual(1, len(report["probes"]))
        self.assertEqual("PASS", report["probes"][0]["result"])


if __name__ == "__main__":
    unittest.main()
