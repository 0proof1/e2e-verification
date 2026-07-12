from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "api_key",
    "apikey",
    "private_key",
}
SENSITIVE_QUERY_KEYS = SENSITIVE_KEYS | {
    "email",
    "phone",
    "mobile",
    "name",
    "resident_number",
}

EMAIL = re.compile(r"(?<![\w.+-])([\w.+-]+)@([\w.-]+\.[A-Za-z]{2,})(?![\w.-])")
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
KOREAN_PHONE = re.compile(r"(?<!\d)(?:01[016789]|0[2-6][1-5]?)[- ]?\d{3,4}[- ]?\d{4}(?!\d)")


def redact(value: Any, key: str = "") -> Any:
    if _normalized(key) in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {item_key: redact(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(redact_url(value))
    return value


def redact_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        return value
    parsed = urlsplit(value)
    query = [
        (key, REDACTED if _normalized(key) in SENSITIVE_QUERY_KEYS else item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def redact_text(value: str) -> str:
    value = BEARER.sub(f"Bearer {REDACTED}", value)
    value = JWT.sub(REDACTED, value)
    value = EMAIL.sub(lambda match: f"{match.group(1)[:1]}***@{match.group(2)}", value)
    return KOREAN_PHONE.sub(REDACTED, value)


def _normalized(key: str) -> str:
    return key.lower().replace("-", "_").strip()

