from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import expand, nested_get, role_context
from .http import HttpClient
from .environment import endpoint_checks, resolve_endpoint


def login_api(client: HttpClient, config: dict[str, Any], role: dict[str, Any]) -> dict[str, Any]:
    login = config.get("api_login")
    if not login:
        return {"result": "SKIP", "reason": "api_login is not configured"}
    context = role_context(role)
    if not context["account"]["id"] or not context["account"]["password"]:
        return {"result": "BLOCKED", "reason": "account id/password environment variables are missing"}
    result = client.request(login.get("method", "POST"), login["path"], expand(login.get("body", {}), context))
    expected = login.get("expected_status", [200])
    token = nested_get(result.body, login.get("token_path", "data.accessToken"))
    if token:
        client.token = str(token)
    passed = result.status in expected and (not login.get("token_path") or bool(token))
    return {
        "result": "PASS" if passed else "FAIL",
        "status": result.status,
        "elapsedMs": result.elapsed_ms,
        "requestId": result.headers.get("X-Request-Id", ""),
        "reason": result.error or ("" if passed else "login response did not match contract"),
    }


def run_api(config: dict[str, Any], options: Any, _out_dir: Path) -> dict[str, Any]:
    defaults = config.get("defaults", {})
    import os
    resolution = resolve_endpoint(
        "api",
        options.api_base,
        config,
        getattr(options, "target_mode", None) or os.environ.get("E2E_TARGET_MODE", "auto"),
        getattr(options, "host_alias", None) or os.environ.get("E2E_HOST_ALIAS", "host.docker.internal"),
    )
    api_base = resolution.url
    preflight = (
        endpoint_checks(resolution, connect=bool(getattr(options, "preflight_connect", False)))
        if bool(getattr(options, "preflight", False))
        else [
            {"status": "BLOCKED", "check": "endpoint:api", "detail": detail}
            for detail in resolution.blockers
        ]
    )
    environment_blocked = any(check["status"] == "BLOCKED" for check in preflight)
    if environment_blocked:
        rows = [
            {"id": probe.get("id", "environment"), "role": probe.get("role", ""), "result": "BLOCKED_ENVIRONMENT"}
            for probe in config.get("api_probes", [])
        ] or [{"id": "environment", "role": "", "result": "BLOCKED_ENVIRONMENT"}]
        return {
            "apiBase": api_base,
            "endpoint": resolution.__dict__,
            "preflight": preflight,
            "logins": {},
            "rows": rows,
            "summary": summarize_rows(rows),
        }
    timeout = int(defaults.get("request_timeout_seconds", 30))
    role_map = {role["name"]: role for role in config.get("roles", [])}
    clients: dict[str, HttpClient] = {}
    logins: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for probe in config.get("api_probes", []):
        role_name = probe["role"]
        role = role_map[role_name]
        client = clients.setdefault(role_name, HttpClient(api_base, timeout))
        if role_name not in logins:
            logins[role_name] = login_api(client, config, role)
        if logins[role_name]["result"] != "PASS" and config.get("api_login"):
            rows.append({"id": probe["id"], "role": role_name, "result": "BLOCKED_LOGIN"})
            continue
        context = role_context(role)
        path = expand(probe["path"], context)
        body = expand(probe.get("body"), context)
        result = client.request(probe.get("method", "GET"), path, body)
        expected = probe.get("expected_status", [200])
        passed = result.status in expected
        rows.append({
            "id": probe["id"], "role": role_name, "method": probe.get("method", "GET"),
            "path": path, "status": result.status, "expectedStatus": expected,
            "elapsedMs": result.elapsed_ms, "requestId": result.headers.get("X-Request-Id", ""),
            "result": "PASS" if passed else "FAIL", "error": result.error,
        })
    return {
        "apiBase": api_base,
        "endpoint": resolution.__dict__,
        "preflight": preflight,
        "logins": logins,
        "rows": rows,
        "summary": summarize_rows(rows),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "passed": sum(1 for row in rows if row.get("result") == "PASS"),
        "failed": sum(1 for row in rows if row.get("result") == "FAIL"),
        "blocked": sum(1 for row in rows if str(row.get("result", "")).startswith("BLOCKED")),
    }
