#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".toml", ".json", ".yml", ".yaml", ".txt", ".ini", ".cfg"}
DENIED_SUFFIXES = {".xlsx", ".xls", ".har", ".trace", ".sqlite", ".db", ".pem", ".key"}
DENIED_PARTS = {"evidence", ".venv", "node_modules", "__pycache__"}
HISTORY_REVIEW_MARKERS = ("profiles/", "compat/", "evidence/")
FORBIDDEN = {
    "private key": re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY"),
    "GitHub token": re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Unix home path": re.compile(r"/home/[A-Za-z0-9._-]+/"),
    "Windows home path": re.compile(r"[A-Za-z]:\\Users\\[^\\]+\\"),
}


def candidate_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [ROOT / name for name in result.stdout.splitlines() if (ROOT / name).is_file()]


def historical_private_paths() -> list[str]:
    result = subprocess.run(
        ["git", "log", "HEAD", "--name-only", "--format="],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git log failed")
    current = {str(path.relative_to(ROOT)).replace("\\", "/") for path in candidate_paths()}
    return sorted({
        name
        for name in result.stdout.splitlines()
        if name and name not in current and name.lower().startswith(HISTORY_REVIEW_MARKERS)
    })


def main() -> int:
    release = subprocess.run([sys.executable, str(ROOT / "tools/release_check.py")], cwd=ROOT, check=False)
    if release.returncode:
        return release.returncode
    errors: list[str] = []
    paths = candidate_paths()
    for path in paths:
        relative = path.relative_to(ROOT)
        lowered_parts = {part.lower() for part in relative.parts}
        if lowered_parts & DENIED_PARTS:
            errors.append(f"local/generated path is tracked: {relative}")
        if path.suffix.lower() in DENIED_SUFFIXES:
            errors.append(f"sensitive/generated file type is tracked: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in FORBIDDEN.items():
            if pattern.search(content):
                errors.append(f"{label} candidate: {relative}")
    history_paths = historical_private_paths()
    if history_paths:
        errors.append(
            f"removed private/profile paths remain in Git history ({len(history_paths)}); "
            "publish from a clean orphan history or perform a reviewed history rewrite"
        )
    if errors:
        print("public repository gate failed")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print(f"public repository gate passed: {len(paths)} candidate files scanned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
