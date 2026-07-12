from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


SUPPORTED_ACTIONS = {"click", "fill", "select", "check", "press"}
SUPPORTED_OUTCOMES = {"ALLOW", "REDIRECT", "FORBID_REDIRECT"}
SUPPORTED_RISKS = {"read-only", "download", "write", "destructive", "external-send"}


def nested_get(value: Any, dotted_path: str) -> Any:
    for part in dotted_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def expand(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key.startswith("env:"):
                return os.environ.get(key[4:], "")
            resolved = nested_get(context, key)
            return "" if resolved is None else str(resolved)
        return re.sub(r"\$\{([^}]+)}", replace, value)
    if isinstance(value, list):
        return [expand(item, context) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, context) for key, item in value.items()}
    return value


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_config(data)
    if errors:
        raise ValueError("\n".join(errors))
    data["_config_path"] = str(path.resolve())
    return data


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if config.get("version") != 1:
        errors.append("version must be 1")
    if not config.get("name"):
        errors.append("name is required")
    roles = config.get("roles", [])
    if not isinstance(roles, list):
        return [*errors, "roles must be an array"]
    role_names: set[str] = set()
    for index, role in enumerate(roles):
        if not isinstance(role, dict):
            errors.append(f"roles[{index}] must be an object")
            continue
        name = role.get("name")
        if not name:
            errors.append(f"roles[{index}].name is required")
        elif name in role_names:
            errors.append(f"duplicate role: {name}")
        else:
            role_names.add(name)
        account = role.get("account", {})
        if not isinstance(account, dict):
            errors.append(f"role {name}: account must be an object")
        elif account.get("password"):
            errors.append(f"role {name}: inline password is forbidden; use password_env")
        for route in role.get("routes", []):
            if not isinstance(route, dict):
                errors.append(f"role {name}: route must be an object")
            elif route.get("outcome", "ALLOW") not in SUPPORTED_OUTCOMES:
                errors.append(f"role {name}: unsupported route outcome {route.get('outcome')}")
    ids: set[str] = set()
    for section in ("api_probes", "browser_probes"):
        probes = config.get(section, [])
        if not isinstance(probes, list):
            errors.append(f"{section} must be an array")
            continue
        for index, probe in enumerate(probes):
            if not isinstance(probe, dict):
                errors.append(f"{section}[{index}] must be an object")
                continue
            probe_id = probe.get("id")
            if not probe_id:
                errors.append(f"{section}[{index}].id is required")
            elif probe_id in ids:
                errors.append(f"duplicate probe id: {probe_id}")
            else:
                ids.add(probe_id)
            if probe.get("role") not in role_names:
                errors.append(f"{probe_id or section}: unknown role {probe.get('role')}")
            if section == "browser_probes" and probe.get("action", "click") not in SUPPORTED_ACTIONS:
                errors.append(f"{probe_id}: unsupported browser action {probe.get('action')}")
            risk = probe.get("risk")
            if risk is not None and risk not in SUPPORTED_RISKS:
                errors.append(f"{probe_id}: unsupported risk {risk}")
    return errors


def role_context(role: dict[str, Any]) -> dict[str, Any]:
    account = role.get("account", {})
    return {
        "role": role.get("name"),
        "account": {
            "id": os.environ.get(account.get("id_env", ""), account.get("id", "")),
            "password": os.environ.get(account.get("password_env", ""), account.get("password", "")),
            "mode": account.get("mode", ""),
        },
    }


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "root"
