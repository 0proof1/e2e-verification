from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any


@dataclass
class HttpResult:
    status: int
    body: Any
    headers: dict[str, str]
    elapsed_ms: int
    error: str = ""


class HttpClient:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.token = ""

    def request(self, method: str, path: str, body: Any = None) -> HttpResult:
        url = path if path.startswith(("http://", "https://")) else f"{self.base_url}/{path.lstrip('/')}"
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, data=payload, headers=headers, method=method.upper())
        started = time.monotonic()
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(500_000)
                return HttpResult(response.status, parse_body(raw), dict(response.headers), elapsed(started))
        except urllib.error.HTTPError as error:
            return HttpResult(error.code, parse_body(error.read(500_000)), dict(error.headers), elapsed(started))
        except Exception as error:
            return HttpResult(0, {}, {}, elapsed(started), str(error)[:500])


def parse_body(raw: bytes) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {"sample": raw[:500].decode("utf-8", errors="replace")}


def elapsed(started: float) -> int:
    return int((time.monotonic() - started) * 1000)

