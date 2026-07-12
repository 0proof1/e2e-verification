from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api_harness import run_api
from .browser_harness import run_browser
from .config import load_config, safe_name, validate_config


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def direct_execution_risks(config: dict[str, Any], command: str) -> set[str]:
    risks: set[str] = set()
    if command in {"api", "all"}:
        for probe in config.get("api_probes", []):
            method = probe.get("method", "GET").upper()
            risks.add(probe.get("risk") or ("read-only" if method in {"GET", "HEAD", "OPTIONS"} else "write"))
    if command in {"browser", "all"}:
        risks.update(probe.get("risk", "read-only") for probe in config.get("browser_probes", []))
    return risks


def prepare_out_dir(config: dict[str, Any], args: argparse.Namespace) -> Path:
    if args.out_dir:
        out_dir = args.out_dir
    else:
        base = Path(
            os.environ.get(
                "E2E_EVIDENCE_DIR",
                config.get("defaults", {}).get("evidence_dir", str(Path(tempfile.gettempdir()) / "e2e-verification")),
            )
        )
        out_dir = base / safe_name(config["name"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence-first, config-driven E2E verification")
    parser.add_argument(
        "command",
        choices=["assets", "doctor", "validate", "api", "browser", "all", "plan", "run", "resume", "report"],
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--api-base")
    parser.add_argument("--web-base")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--workflow", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--approve", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=["html", "xlsx"], default="html")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--adapter", type=Path, action="append", default=[])
    parser.add_argument(
        "--target-mode",
        choices=["auto", "host", "docker-published", "same-network", "host-from-container", "external", "container-local"],
        default=os.environ.get("E2E_TARGET_MODE", "auto"),
    )
    parser.add_argument("--host-alias", default=os.environ.get("E2E_HOST_ALIAS", "host.docker.internal"))
    parser.add_argument("--connect", action="store_true", help="doctor: include TCP reachability checks")
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")
    if args.command == "assets":
        from .assets import asset_root
        try:
            root = asset_root()
        except FileNotFoundError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps({"assetRoot": str(root)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "doctor":
        from .environment import diagnose, print_diagnosis

        config: dict[str, Any] | None = None
        if args.config:
            try:
                config = load_config(args.config)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                print(str(error), file=sys.stderr)
                return 2
        diagnosis = diagnose(
            config,
            args.api_base,
            args.web_base,
            args.target_mode,
            args.host_alias,
            connect=args.connect,
            require_credentials=bool(config),
            evidence_dir=args.out_dir,
        )
        print_diagnosis(diagnosis)
        return 3 if diagnosis["summary"]["blocked"] else 0
    if args.command in {"plan", "run", "resume", "report"}:
        return run_platform_command(args, parser)
    if not args.config:
        parser.error("--config is required for validate, api, browser, and all")
    try:
        config = load_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.command == "validate":
        print(json.dumps({"valid": True, "name": config["name"], "config": config["_config_path"]}, ensure_ascii=False, indent=2))
        return 0
    from .environment import diagnose

    kinds = {"api"} if args.command == "api" else {"web"} if args.command == "browser" else {"api", "web"}
    diagnosis = diagnose(
        config,
        args.api_base,
        args.web_base,
        args.target_mode,
        args.host_alias,
        connect=True,
        kinds=kinds,
        evidence_dir=args.out_dir,
    )
    unsafe_risks = sorted(direct_execution_risks(config, args.command) - {"read-only"})
    if unsafe_risks:
        diagnosis["checks"].append(
            {
                "status": "BLOCKED",
                "check": "legacy-risk-boundary",
                "detail": (
                    f"legacy direct execution refuses risks {unsafe_risks}; use a workflow with named approval and cleanup"
                ),
            }
        )
        diagnosis["summary"]["blocked"] += 1
    if diagnosis["summary"]["blocked"]:
        print(json.dumps(diagnosis, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    for endpoint in diagnosis["endpoints"]:
        if endpoint["kind"] == "api":
            args.api_base = endpoint["url"]
        elif endpoint["kind"] == "web":
            args.web_base = endpoint["url"]
    out_dir = prepare_out_dir(config, args)
    from .redaction import redact

    (out_dir / "preflight.json").write_text(
        json.dumps(redact(diagnosis), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report: dict[str, Any] = {
        "name": config["name"],
        "startedAt": utc_now(),
        "config": config["_config_path"],
        "outDir": str(out_dir),
        "preflight": diagnosis,
    }
    if args.command in {"api", "all"}:
        report["api"] = run_api(config, args, out_dir)
    if args.command in {"browser", "all"}:
        report["browser"] = run_browser(config, args, out_dir)
    report["finishedAt"] = utc_now()
    report["failed"] = sum(report.get(section, {}).get("summary", {}).get("failed", 0) for section in ("api", "browser"))
    report["serverErrors"] = sum(report.get(section, {}).get("summary", {}).get("serverErrors", 0) for section in ("api", "browser"))
    path = out_dir / "summary.json"
    path.write_text(json.dumps(redact(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summaryPath": str(path), "failed": report["failed"], "serverErrors": report["serverErrors"]}, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 and report["serverErrors"] == 0 else 2


def run_platform_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from .harnesses import default_registry
    from .adapters import load_adapter
    from .reporting import write_html_report, write_xlsx_report
    from .workflow import WorkflowRunner, load_workflow, ordered_steps, validate_workflow

    if args.command == "report":
        if not args.run_dir:
            parser.error("report requires --run-dir")
        try:
            writer = write_xlsx_report if args.format == "xlsx" else write_html_report
            output = writer(args.run_dir / "run.json", args.output)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps({"reportPath": str(output)}, ensure_ascii=False, indent=2))
        return 0
    if not args.workflow:
        parser.error(f"{args.command} requires --workflow")
    try:
        spec = load_workflow(args.workflow)
        registry = default_registry(args.target_mode, args.host_alias)
        for adapter in args.adapter:
            load_adapter(adapter, registry)
        validate_workflow(spec, registry)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    plan = [{
        "id": step.id,
        "harness": step.harness,
        "needs": step.needs,
        "when": step.when,
        "risk": step.risk,
        "approval": step.approval or None,
        "retries": step.retries,
        "idempotent": step.idempotent,
        "timeoutSeconds": step.timeout_seconds,
    } for step in ordered_steps(spec)]
    if args.command == "plan" or args.dry_run:
        from .workflow import workflow_digest
        print(json.dumps({
            "workflow": spec.name,
            "profile": spec.profile,
            "workflowDigest": workflow_digest(spec),
            "targetMode": args.target_mode,
            "hostAlias": args.host_alias,
            "steps": plan,
            "dryRun": bool(args.dry_run),
        }, ensure_ascii=False, indent=2))
        return 0
    if not args.run_dir:
        parser.error(f"{args.command} requires --run-dir")
    try:
        state = WorkflowRunner(registry).run(spec, args.run_dir, approvals=set(args.approve), resume=args.command == "resume")
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({"runPath": str(args.run_dir / "run.json"), "status": state["status"]}, ensure_ascii=False, indent=2))
    from .evidence import Status, exit_code
    return exit_code(Status(state["status"]))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["load_config", "main", "run_api", "run_browser", "validate_config"]
