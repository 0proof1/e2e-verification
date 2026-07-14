from __future__ import annotations

import argparse
import copy
import functools
from pathlib import Path
from typing import Any

from .evidence import FunctionalStatus, Risk, Status, UsabilityStatus
from .workflow import HarnessOutcome, HarnessRegistry, StepSpec


def default_registry(target_mode: str = "auto", host_alias: str = "host.docker.internal") -> HarnessRegistry:
    registry = HarnessRegistry()
    registry.register("config-validate", validate_config_harness)
    registry.register("api-probes", functools.partial(api_probes_harness, target_mode=target_mode, host_alias=host_alias))
    registry.register("browser-probes", functools.partial(browser_probes_harness, target_mode=target_mode, host_alias=host_alias))
    return registry


def validate_config_harness(step: StepSpec, _step_dir: Path) -> HarnessOutcome:
    from .config import load_config

    config = load_config(_config_path(step))
    return HarnessOutcome(
        status=Status.PASS,
        summary={"passed": 1, "failed": 0},
        metadata={"profile_name": config["name"]},
    )


def api_probes_harness(
    step: StepSpec,
    step_dir: Path,
    target_mode: str = "auto",
    host_alias: str = "host.docker.internal",
) -> HarnessOutcome:
    from .api_harness import run_api
    from .config import load_config

    config = load_config(_config_path(step))
    unsafe = [
        probe.get("id", "unknown")
        for probe in config.get("api_probes", [])
        if _api_probe_risk(probe) != Risk.READ_ONLY
    ]
    if unsafe:
        raise ValueError(f"api-probes accepts read-only probes only; use a dedicated gated harness for {unsafe}")
    config = copy.deepcopy(config)
    defaults = config.setdefault("defaults", {})
    defaults["request_timeout_seconds"] = min(int(defaults.get("request_timeout_seconds", 30)), step.timeout_seconds)
    args = _legacy_args(step, step_dir, target_mode, host_alias)
    report = run_api(config, args, step_dir)
    return _legacy_outcome(report)


def browser_probes_harness(
    step: StepSpec,
    step_dir: Path,
    target_mode: str = "auto",
    host_alias: str = "host.docker.internal",
) -> HarnessOutcome:
    from .browser_harness import run_browser
    from .config import load_config

    config = load_config(_config_path(step))
    unsafe = [
        probe.get("id", "unknown")
        for probe in config.get("browser_probes", [])
        if Risk(probe.get("risk", Risk.READ_ONLY)) != Risk.READ_ONLY
    ]
    if unsafe:
        raise ValueError(f"browser-probes accepts read-only probes only; use a dedicated gated harness for {unsafe}")
    args = _legacy_args(step, step_dir, target_mode, host_alias)
    report = run_browser(config, args, step_dir)
    artifacts: list[dict[str, Any]] = []
    for group in ("routes", "probes"):
        for row in report.get(group, []):
            screenshots = row.get("screenshots", {})
            if row.get("screenshot") and not screenshots:
                screenshots = {"viewport": row["screenshot"]}
            for capture_type, path in screenshots.items():
                artifacts.append({
                    "kind": "screenshot",
                    "path": path,
                    "description": f"{group} {capture_type} evidence",
                    "redacted": False,
                })
    for path in report.get("traces", []):
        artifacts.append({
            "kind": "trace",
            "path": path,
            "description": "Playwright failure trace",
            "redacted": False,
        })
    report_path = step_dir / "browser-report.json"
    if report_path.is_file():
        artifacts.append({
            "kind": "json",
            "path": str(report_path),
            "description": "Structured browser measurements and capture index",
            "redacted": True,
        })
    outcome = _legacy_outcome(report)
    outcome.artifacts = artifacts
    return outcome


def _config_path(step: StepSpec) -> Path:
    value = step.args.get("config")
    if not value:
        raise ValueError(f"step {step.id}: args.config is required")
    return Path(str(value)).expanduser().resolve()


def _legacy_args(step: StepSpec, step_dir: Path, target_mode: str, host_alias: str) -> argparse.Namespace:
    return argparse.Namespace(
        api_base=step.args.get("api_base"),
        web_base=step.args.get("web_base"),
        out_dir=step_dir,
        headed=bool(step.args.get("headed", False)),
        timeout_seconds=step.timeout_seconds,
        target_mode=step.args.get("target_mode", target_mode),
        host_alias=step.args.get("host_alias", host_alias),
        preflight=bool(step.args.get("preflight", True)),
        preflight_connect=bool(step.args.get("preflight_connect", True)),
        trace_on_failure=bool(step.args.get("trace_on_failure", False)),
    )


def _legacy_outcome(report: dict[str, Any]) -> HarnessOutcome:
    summary = report.get("summary", {})
    failed = int(summary.get("failed", 0))
    server_errors = int(summary.get("serverErrors", 0))
    blocked = int(summary.get("blocked", 0))
    review = int(summary.get("review", 0))
    usability_assessed = int(summary.get("usabilityAssessed", 0))
    if failed or server_errors:
        status = Status.FAIL
    elif blocked:
        status = Status.BLOCKED
    elif review:
        status = Status.REVIEW
    else:
        status = Status.PASS
    functional_status = (
        FunctionalStatus.FAIL
        if failed or server_errors
        else FunctionalStatus.BLOCKED
        if blocked
        else FunctionalStatus.PASS
    )
    usability_status = (
        UsabilityStatus.REVIEW
        if review
        else UsabilityStatus.PASS
        if usability_assessed
        else UsabilityStatus.NOT_RUN
    )
    counts = {
        key: int(value)
        for key, value in summary.items()
        if isinstance(value, int) and value >= 0
    }
    return HarnessOutcome(
        status=status,
        functional_status=functional_status,
        usability_status=usability_status,
        summary=counts,
        metadata={"legacy_report": report},
    )


def _api_probe_risk(probe: dict[str, Any]) -> Risk:
    if probe.get("risk"):
        return Risk(probe["risk"])
    return Risk.READ_ONLY if probe.get("method", "GET").upper() in {"GET", "HEAD", "OPTIONS"} else Risk.WRITE
