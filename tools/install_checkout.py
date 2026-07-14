#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CLI_COMMANDS = ("model-plan", "agent-task")


def git_revision(root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git revision is unavailable")
    return result.stdout.strip()


def is_dirty(root: Path = ROOT) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git status is unavailable")
    return bool(result.stdout.strip())


def revision_matches(actual: str, expected: str) -> bool:
    return bool(actual and expected) and (actual.startswith(expected) or expected.startswith(actual))


def requested_extras(extras: str) -> list[str]:
    values = [value.strip() for value in extras.split(",") if value.strip()]
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", value) for value in values):
        raise ValueError("extras must contain only package extra names")
    return values


def project_metadata(root: Path = ROOT) -> dict[str, object]:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def dependency_requirements(extras: str, root: Path = ROOT) -> list[str]:
    project = project_metadata(root)
    optional = project.get("optional-dependencies", {})
    assert isinstance(optional, dict)
    selected = requested_extras(extras)
    unknown = [name for name in selected if name not in optional]
    if unknown:
        raise ValueError(f"unknown extras: {', '.join(unknown)}")
    requirements = list(project.get("dependencies", []))
    for name in selected:
        requirements.extend(optional[name])
    return list(dict.fromkeys(str(requirement) for requirement in requirements))


def install_commands(extras: str) -> list[list[str]]:
    dependencies = dependency_requirements(extras)
    commands = []
    if dependencies:
        commands.append([sys.executable, "-m", "pip", "install", *dependencies])
    commands.append([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", "-e", "."])
    return commands


def project_version(root: Path = ROOT) -> str:
    return str(project_metadata(root)["version"])


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")


def verify_install(expected_version: str) -> dict[str, str]:
    code = (
        "import json, pathlib; "
        "import e2e_verification as p; "
        "print(json.dumps({'version': p.__version__, 'module': str(pathlib.Path(p.__file__).resolve())}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "installed package cannot be imported")
    payload = json.loads(result.stdout)
    if payload["version"] != expected_version:
        raise RuntimeError(f"installed version {payload['version']} does not match source {expected_version}")
    module = Path(payload["module"])
    if ROOT not in module.parents:
        raise RuntimeError(f"editable install does not resolve to this checkout: {module}")

    scripts = Path(sysconfig.get_path("scripts"))
    cli = shutil.which("e2e-verify", path=str(scripts))
    if not cli:
        raise RuntimeError(f"e2e-verify was not installed for this interpreter: {scripts}")
    help_result = subprocess.run(
        [cli, "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if help_result.returncode:
        raise RuntimeError(help_result.stderr.strip() or "installed e2e-verify cannot start")
    missing = [command for command in REQUIRED_CLI_COMMANDS if command not in help_result.stdout]
    if missing:
        raise RuntimeError(f"installed e2e-verify is stale; missing commands: {', '.join(missing)}")
    payload["cli"] = str(Path(cli).resolve())
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install this checkout reproducibly, forcing the project itself to reinstall even when its version is unchanged."
    )
    parser.add_argument("--extras", default="")
    parser.add_argument("--expected-sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    try:
        revision = git_revision()
        dirty = is_dirty()
        if args.expected_sha and not revision_matches(revision, args.expected_sha):
            raise RuntimeError(f"checkout SHA {revision} does not match expected SHA {args.expected_sha}")
        if args.require_clean and dirty:
            raise RuntimeError("checkout is dirty; refusing a reproducible install")
        if not args.check_only:
            for command in install_commands(args.extras):
                run(command)
            installed = verify_install(project_version())
        else:
            installed = {}
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    print(json.dumps({
        "sourceRevision": revision,
        "sourceDirty": dirty,
        "expectedRevision": args.expected_sha or None,
        "forcedReinstall": not args.check_only,
        **installed,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
