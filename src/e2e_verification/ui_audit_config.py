from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_STATES = {"loading", "data", "empty", "error"}
SUPPORTED_ARTIFACTS = {"viewport", "full_page"}
SUPPORTED_FIXTURE_ACTIONS = {"delay", "fulfill", "abort", "passthrough"}


def load_ui_audit_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_ui_audit_config(data, base_dir=path.parent)
    if errors:
        raise ValueError("\n".join(errors))
    data["_audit_path"] = str(path.resolve())
    return data


def validate_ui_audit_config(config: dict[str, Any], base_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if config.get("draft_contract_version") not in {"ui-audit-v1", None}:
        errors.append("draft_contract_version must be ui-audit-v1")
    if not str(config.get("name", "")).strip():
        errors.append("name is required")
    if config.get("read_only") is not True:
        errors.append("read_only must be true")

    viewports = config.get("viewports", [])
    if not isinstance(viewports, list) or not viewports:
        errors.append("viewports must be a non-empty array")
    else:
        names: set[str] = set()
        for index, viewport in enumerate(viewports):
            if not isinstance(viewport, dict):
                errors.append(f"viewports[{index}] must be an object")
                continue
            name = str(viewport.get("name", ""))
            if not name or name in names:
                errors.append(f"viewports[{index}].name must be unique and non-empty")
            names.add(name)
            for dimension in ("width", "height"):
                value = viewport.get(dimension)
                if not isinstance(value, int) or value < 320:
                    errors.append(f"viewports[{index}].{dimension} must be an integer >= 320")

    artifacts = config.get("artifacts", [])
    if not isinstance(artifacts, list) or set(artifacts) - SUPPORTED_ARTIFACTS:
        errors.append(f"artifacts may contain only {sorted(SUPPORTED_ARTIFACTS)}")
    if not SUPPORTED_ARTIFACTS <= set(artifacts or []):
        errors.append("artifacts must include viewport and full_page")

    safety = config.get("safety", {})
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
    elif any(not isinstance(host, str) or not host.strip() or "/" in host for host in safety.get("allowed_external_hosts", [])):
        errors.append("safety.allowed_external_hosts must contain hostnames only")

    roles = config.get("roles", {})
    if not isinstance(roles, dict) or not roles:
        errors.append("roles must be a non-empty object")

    cases = config.get("cases", [])
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty array")
    else:
        seen: set[tuple[str, str]] = set()
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                errors.append(f"cases[{index}] must be an object")
                continue
            page = str(case.get("page", ""))
            role = str(case.get("role", ""))
            if not page or not role or not case.get("route") or not case.get("title"):
                errors.append(f"cases[{index}] requires page, role, route, and title")
            if role not in roles:
                errors.append(f"cases[{index}] references unknown role {role}")
            if (page, role) in seen:
                errors.append(f"duplicate case group: {page}/{role}")
            seen.add((page, role))
            states = case.get("states", [])
            if not isinstance(states, list) or not states or set(states) - SUPPORTED_STATES:
                errors.append(f"cases[{index}].states must use {sorted(SUPPORTED_STATES)}")
            navigation = case.get("navigation")
            if navigation is not None and (
                not isinstance(navigation, dict) or not navigation.get("source_route") or not navigation.get("menu")
            ):
                errors.append(f"cases[{index}].navigation requires source_route and menu")

    state_contract = config.get("state_contract", {})
    if not isinstance(state_contract, dict):
        errors.append("state_contract must be an object")
    else:
        for state in sorted({item for case in cases if isinstance(case, dict) for item in case.get("states", [])}):
            if state not in state_contract:
                errors.append(f"state_contract is missing {state}")

    if base_dir is not None:
        errors.extend(_validate_fixture_references(config, base_dir))
    return errors


def load_state_fixture(config: dict[str, Any], page: str, state: str) -> dict[str, Any] | None:
    contract = config.get("state_contract", {}).get(state, {})
    if contract.get("action") == "passthrough":
        return None
    pattern = contract.get("fixture_pattern")
    if not pattern:
        raise ValueError(f"state {state} has no fixture_pattern")
    path = _resolve_fixture_path(config, str(pattern).format(page=page))
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_state_fixture(payload)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    payload["_fixture_path"] = str(path)
    return payload


def validate_state_fixture(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    state = payload.get("state")
    if state not in SUPPORTED_STATES:
        errors.append("fixture state must be loading, data, empty, or error")
    intercepts = payload.get("intercepts", [])
    if not isinstance(intercepts, list) or not intercepts:
        errors.append("fixture intercepts must be a non-empty array")
        return errors
    for index, intercept in enumerate(intercepts):
        if not isinstance(intercept, dict):
            errors.append(f"intercepts[{index}] must be an object")
            continue
        if str(intercept.get("method", "GET")).upper() not in {"GET", "HEAD", "OPTIONS"}:
            errors.append(f"intercepts[{index}] uses a mutating method")
        if not intercept.get("url"):
            errors.append(f"intercepts[{index}].url is required")
        action = intercept.get("action")
        if action not in SUPPORTED_FIXTURE_ACTIONS:
            errors.append(f"intercepts[{index}].action is unsupported: {action}")
        if action == "fulfill" and "body" not in intercept:
            errors.append(f"intercepts[{index}] fulfill requires body")
    return errors


def _validate_fixture_references(config: dict[str, Any], base_dir: Path) -> list[str]:
    errors: list[str] = []
    pages = {str(case.get("page")) for case in config.get("cases", []) if isinstance(case, dict)}
    states = {str(state) for case in config.get("cases", []) if isinstance(case, dict) for state in case.get("states", [])}
    for state in states:
        contract = config.get("state_contract", {}).get(state, {})
        if contract.get("action") == "passthrough":
            continue
        pattern = contract.get("fixture_pattern")
        if not pattern:
            errors.append(f"state_contract.{state}.fixture_pattern is required")
            continue
        for page in pages:
            if state not in next((case.get("states", []) for case in config.get("cases", []) if case.get("page") == page), []):
                continue
            try:
                path = _resolve_fixture_path({"_audit_path": str(base_dir / "audit.json")}, str(pattern).format(page=page))
            except ValueError as error:
                errors.append(str(error))
                continue
            if not path.is_file():
                errors.append(f"fixture does not exist: {path}")
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                errors.append(f"cannot read fixture {path}: {error}")
                continue
            errors.extend(f"{path}: {item}" for item in validate_state_fixture(payload))
    return errors


def _resolve_fixture_path(config: dict[str, Any], value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    audit_path = Path(str(config.get("_audit_path", Path.cwd() / "audit.json"))).resolve()
    # Product fixtures can live beside or above the audit document, but never
    # escape the current project checkout through `..` or a symlink.
    project_root = _project_root(audit_path.parent)
    try:
        resolved.relative_to(project_root)
    except ValueError as error:
        raise ValueError(f"fixture escapes project root: {value}") from error
    return resolved


def _project_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / ".git").exists() or (path / "pyproject.toml").exists() or (path / "package.json").exists():
            return path
    return Path.cwd().resolve()
