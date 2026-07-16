from __future__ import annotations

import argparse
import copy
import functools
from pathlib import Path
from typing import Any

from .evidence import Finding, FunctionalStatus, Risk, Status, UsabilityStatus, legacy_status
from .workflow import HarnessOutcome, HarnessRegistry, StepSpec


def default_registry(target_mode: str = "auto", host_alias: str = "host.docker.internal") -> HarnessRegistry:
    registry = HarnessRegistry()
    registry.register("config-validate", validate_config_harness)
    registry.register("api-probes", functools.partial(api_probes_harness, target_mode=target_mode, host_alias=host_alias))
    registry.register("browser-probes", functools.partial(browser_probes_harness, target_mode=target_mode, host_alias=host_alias))
    registry.register("ui-audit", functools.partial(ui_audit_harness, target_mode=target_mode, host_alias=host_alias))
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


def ui_audit_harness(
    step: StepSpec,
    step_dir: Path,
    target_mode: str = "auto",
    host_alias: str = "host.docker.internal",
) -> HarnessOutcome:
    if step.risk != Risk.READ_ONLY:
        raise ValueError("ui-audit accepts read-only workflow steps only")
    from .ui_audit_harness import load_and_run_ui_audit

    audit = step.args.get("audit")
    if not audit:
        raise ValueError(f"step {step.id}: args.audit is required")
    args = _legacy_args(step, step_dir, target_mode, host_alias)
    report = load_and_run_ui_audit(_config_path(step), Path(str(audit)).expanduser().resolve(), args, step_dir)
    _relativize_ui_report_artifacts(report, step.id)
    functional = FunctionalStatus(report.get("functional_status", "BLOCKED"))
    usability = UsabilityStatus(report.get("usability_status", "BLOCKED"))
    artifacts: list[dict[str, Any]] = []
    findings: list[Finding] = []
    for case in report.get("cases", []):
        case_id = str(case.get("case_id", "ui-audit"))
        viewport = case.get("viewport", {})
        for variant in ("viewport", "full_page", "focus"):
            path = case.get("artifacts", {}).get(variant)
            if not path:
                continue
            artifacts.append({
                "kind": "screenshot",
                "path": path,
                "description": f"{case_id} {variant}",
                "redacted": False,
                "case_id": case_id,
                "variant": variant,
                "role": str(case.get("role", "")),
                "state": str(case.get("state", "")),
                "page": str(case.get("page", "")),
                "shard": str(step.args.get("shard") or step.id),
                "viewport": dict(viewport) if isinstance(viewport, dict) else {},
            })
        findings.extend(_ui_case_findings(case))
    return HarnessOutcome(
        status=legacy_status(functional),
        functional_status=functional,
        usability_status=usability,
        summary={key: int(value) for key, value in report.get("summary", {}).items() if isinstance(value, int)},
        artifacts=artifacts,
        findings=findings,
        metadata={"ui_audit": report},
        recommended_next_steps=[
            "Review usability findings with their paired viewport and full-page evidence."
        ] if usability == UsabilityStatus.REVIEW else [],
    )


def _ui_case_findings(case: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    case_id = str(case.get("case_id", "ui-audit"))
    evidence = [str(value) for value in case.get("artifacts", {}).values() if value]
    for index, message in enumerate(case.get("errors", []), start=1):
        findings.append(Finding(
            id=f"{case_id}-functional-{index}", status=Status.FAIL,
            title="UI audit could not prove the configured state", message=str(message), severity="high",
            evidence=evidence, category="functional", case_id=case_id,
        ))
    measurements = case.get("measurements", {})
    scroll_reset = measurements.get("menu_scroll_reset", {})
    if scroll_reset.get("status") == "FAIL":
        findings.append(Finding(
            id=f"{case_id}-scroll-reset", status=Status.FAIL,
            title="Menu navigation did not reset document scroll position",
            message=(
                f"{scroll_reset.get('menu', 'configured menu')}: "
                f"scrollY {scroll_reset.get('before_scroll_y')} -> {scroll_reset.get('after_scroll_y')}"
            ),
            severity="high", evidence=evidence, category="navigation", case_id=case_id,
        ))
    usability_messages: list[tuple[str, str, str]] = []
    if measurements and not measurements.get("title_visible", False):
        usability_messages.append(("title-first-viewport", "Page title is not fully visible in the first viewport", "high"))
    if measurements.get("overflow_x"):
        usability_messages.append(("horizontal-overflow", "The document overflows horizontally", "high"))
    if measurements.get("clipped_candidates"):
        usability_messages.append(("clipped-content", f"Detected {measurements['clipped_candidates']} clipped content candidates", "medium"))
    if case.get("known_gap"):
        usability_messages.append(("known-gap", str(case["known_gap"]), "high"))
    accessibility = case.get("accessibility") or {}
    if accessibility.get("usability_status") in {"REVIEW", "BLOCKED"}:
        counts = accessibility.get("summary", {})
        usability_messages.append(("accessibility", f"Accessibility audit requires review: {counts}", "high"))
    for index, (category, message, severity) in enumerate(usability_messages, start=1):
        findings.append(Finding(
            id=f"{case_id}-usability-{index}", status=Status.REVIEW,
            title=message, severity=severity, evidence=evidence, category=category, case_id=case_id,
        ))
    return findings


def _relativize_ui_report_artifacts(report: dict[str, Any], step_id: str) -> None:
    for case in report.get("cases", []):
        artifacts = case.get("artifacts", {})
        for key, value in list(artifacts.items()):
            if not value:
                continue
            artifacts[key] = f"steps/{step_id}/screenshots/{Path(str(value)).name}"


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
