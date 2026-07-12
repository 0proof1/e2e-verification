from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


LOGIN = b"""<!doctype html><form id=login><input name=username><input name=password type=password><button type=submit>Sign in</button></form><script>login.onsubmit=(e)=>{e.preventDefault();location.href='/dashboard'}</script>"""
DASHBOARD = b"""<!doctype html><nav>Users</nav><button data-testid=refresh>Refresh</button><p id=done hidden>Done</p><script>document.querySelector('button').onclick=()=>fetch('/api/users').then(()=>document.querySelector('#done').hidden=false)</script>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send(200, b"ok", "text/plain")
        elif self.path in {"/login", "/"}:
            self.send(200, LOGIN, "text/html; charset=utf-8")
        elif self.path == "/dashboard":
            self.send(200, DASHBOARD, "text/html; charset=utf-8")
        elif self.path == "/api/users":
            self.send(200, json.dumps({"data": [{"id": "synthetic-user"}]}).encode(), "application/json")
        else:
            self.send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/api/auth/login":
            body = json.dumps({"data": {"accessToken": "synthetic-token"}}).encode()
            self.send(200, body, "application/json")
        else:
            self.send(404, b"not found", "text/plain")


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
