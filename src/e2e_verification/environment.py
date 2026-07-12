from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import socket
import tempfile
from functools import lru_cache
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


TARGET_MODES = {
    "auto",
    "host",
    "docker-published",
    "same-network",
    "host-from-container",
    "external",
    "container-local",
}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class RuntimeEnvironment:
    system: str
    machine: str
    python: str
    in_container: bool
    docker_cli: bool
    docker_socket: bool
    playwright: bool
    chromium: bool


@dataclass(frozen=True)
class ResolvedEndpoint:
    kind: str
    url: str
    source: str
    target_mode: str
    original_url: str
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def detect_runtime() -> RuntimeEnvironment:
    in_container = Path("/.dockerenv").exists() or bool(os.environ.get("container"))
    if not in_container:
        try:
            cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
            in_container = any(marker in cgroup for marker in ("docker", "containerd", "kubepods", "podman"))
        except OSError:
            pass
    playwright = importlib.util.find_spec("playwright") is not None
    chromium = False
    if playwright:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as runtime:
                chromium = Path(runtime.chromium.executable_path).is_file()
        except Exception:
            chromium = False
    return RuntimeEnvironment(
        system=platform.system() or os.name,
        machine=platform.machine(),
        python=platform.python_version(),
        in_container=in_container,
        docker_cli=shutil.which("docker") is not None,
        docker_socket=Path("/var/run/docker.sock").exists(),
        playwright=playwright,
        chromium=chromium,
    )


def resolve_endpoint(
    kind: str,
    cli_value: str | None,
    config: dict[str, Any],
    target_mode: str = "auto",
    host_alias: str = "host.docker.internal",
    runtime: RuntimeEnvironment | None = None,
) -> ResolvedEndpoint:
    if target_mode not in TARGET_MODES:
        raise ValueError(f"unsupported target mode: {target_mode}")
    runtime = runtime or detect_runtime()
    env_name = "E2E_API_BASE" if kind == "api" else "E2E_WEB_BASE"
    config_name = "api_base" if kind == "api" else "web_base"
    if cli_value:
        value, source = cli_value, "cli"
    elif os.environ.get(env_name):
        value, source = os.environ[env_name], f"env:{env_name}"
    else:
        value, source = str(config.get("defaults", {}).get(config_name, "")), f"config:defaults.{config_name}"
    original = value
    warnings: list[str] = []
    blockers: list[str] = []
    parsed = urlsplit(value) if value else None
    if not value:
        blockers.append(f"{kind} base URL is not configured")
    elif parsed is None or parsed.scheme not in {"http", "https"} or not parsed.hostname:
        blockers.append(f"{kind} base URL must be an absolute http(s) URL")
    else:
        loopback = parsed.hostname.lower() in LOOPBACK_HOSTS
        if parsed.username or parsed.password:
            blockers.append(f"{kind} base URL must not embed credentials")
        if target_mode == "host-from-container" and loopback:
            hostname = host_alias
            if ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"
            port = f":{parsed.port}" if parsed.port else ""
            value = urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, parsed.query, parsed.fragment))
            warnings.append(f"rewrote loopback host to explicit container host alias {host_alias}")
        elif runtime.in_container and loopback and target_mode == "auto":
            blockers.append(
                "loopback inside a container is ambiguous; select container-local, same-network, or host-from-container"
            )
        elif runtime.in_container and target_mode in {"host", "docker-published"}:
            blockers.append(f"{target_mode} is a host-side mode; select same-network or host-from-container")
        elif target_mode == "same-network" and loopback:
            blockers.append("same-network mode requires a Docker/Compose service hostname, not loopback")
        elif target_mode == "same-network" and not runtime.in_container:
            blockers.append("same-network mode requires the verifier to run inside a container network")
        elif target_mode == "external" and loopback:
            blockers.append("external mode cannot use a loopback hostname")
        elif target_mode == "container-local" and not runtime.in_container:
            blockers.append("container-local mode requires the verifier to run inside a container")
        elif target_mode == "container-local" and not loopback:
            blockers.append("container-local mode requires a loopback hostname")
        elif target_mode == "host-from-container" and not runtime.in_container:
            warnings.append("host-from-container was selected outside a detected container")
        if target_mode == "external" and parsed.scheme != "https":
            warnings.append("external target uses HTTP; HTTPS is recommended")
    return ResolvedEndpoint(kind, value, source, target_mode, original, warnings, blockers)


def credential_checks(config: dict[str, Any]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    needs_credentials = bool(config.get("api_login") or config.get("browser_login"))
    if not needs_credentials:
        return checks
    for role in config.get("roles", []):
        account = role.get("account", {})
        for field, suffix in (("id_env", "id"), ("password_env", "password")):
            name = account.get(field, "")
            if not name:
                checks.append({"status": "BLOCKED", "check": f"credential:{role.get('name')}:{suffix}", "detail": f"{field} is not configured"})
            elif not os.environ.get(name):
                checks.append({"status": "BLOCKED", "check": f"credential:{role.get('name')}:{suffix}", "detail": f"environment variable {name} is missing"})
            else:
                checks.append({"status": "PASS", "check": f"credential:{role.get('name')}:{suffix}", "detail": f"environment variable {name} is set"})
    return checks


def endpoint_checks(endpoint: ResolvedEndpoint, connect: bool = False, timeout: float = 2.0) -> list[dict[str, str]]:
    checks = [{"status": "BLOCKED", "check": f"endpoint:{endpoint.kind}", "detail": detail} for detail in endpoint.blockers]
    checks.extend({"status": "WARN", "check": f"endpoint:{endpoint.kind}", "detail": detail} for detail in endpoint.warnings)
    if endpoint.blockers or not endpoint.url:
        return checks
    parsed = urlsplit(endpoint.url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        checks.append({"status": "PASS", "check": f"dns:{endpoint.kind}", "detail": f"resolved {host}"})
    except OSError as error:
        checks.append({"status": "BLOCKED", "check": f"dns:{endpoint.kind}", "detail": str(error)})
        return checks
    if connect:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
            checks.append({"status": "PASS", "check": f"tcp:{endpoint.kind}", "detail": f"connected to {host}:{port}"})
        except OSError as error:
            checks.append({"status": "BLOCKED", "check": f"tcp:{endpoint.kind}", "detail": str(error)})
    return checks


def writable_check(path: Path) -> dict[str, str]:
    candidate = path.expanduser().resolve()
    parent = candidate if candidate.exists() and candidate.is_dir() else candidate.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    status = "PASS" if parent.is_dir() and os.access(parent, os.W_OK) else "BLOCKED"
    return {"status": status, "check": "evidence-directory", "detail": str(candidate)}


def diagnose(
    config: dict[str, Any] | None,
    api_base: str | None,
    web_base: str | None,
    target_mode: str,
    host_alias: str,
    connect: bool,
    require_credentials: bool = True,
    kinds: set[str] | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    runtime = detect_runtime()
    config = config or {"defaults": {}, "roles": []}
    selected_kinds = []
    if (kinds is None or "api" in kinds) and (
        api_base or config.get("defaults", {}).get("api_base") or config.get("api_probes")
    ):
        selected_kinds.append("api")
    if (kinds is None or "web" in kinds) and (
        web_base or config.get("defaults", {}).get("web_base") or config.get("browser_probes")
    ):
        selected_kinds.append("web")
    endpoints = [
        resolve_endpoint(kind, api_base if kind == "api" else web_base, config, target_mode, host_alias, runtime)
        for kind in selected_kinds
    ]
    checks: list[dict[str, str]] = []
    for endpoint in endpoints:
        checks.extend(endpoint_checks(endpoint, connect=connect))
    if require_credentials:
        checks.extend(credential_checks(config))
    evidence = evidence_dir or Path(
        os.environ.get(
            "E2E_EVIDENCE_DIR",
            config.get("defaults", {}).get("evidence_dir", str(Path(tempfile.gettempdir()) / "e2e-verification")),
        )
    )
    checks.append(writable_check(evidence))
    if "web" in selected_kinds and config.get("browser_probes"):
        checks.append({"status": "PASS" if runtime.playwright else "BLOCKED", "check": "playwright-package", "detail": "installed" if runtime.playwright else "not installed"})
        checks.append({"status": "PASS" if runtime.chromium else "BLOCKED", "check": "chromium", "detail": "available" if runtime.chromium else "not installed for Playwright"})
    summary = {status.lower(): sum(1 for check in checks if check["status"] == status) for status in ("PASS", "WARN", "BLOCKED")}
    return {
        "runtime": asdict(runtime),
        "targetMode": target_mode,
        "hostAlias": host_alias,
        "endpoints": [asdict(endpoint) for endpoint in endpoints],
        "checks": checks,
        "summary": summary,
    }


def print_diagnosis(diagnosis: dict[str, Any]) -> None:
    print(json.dumps(diagnosis, ensure_ascii=False, indent=2))
