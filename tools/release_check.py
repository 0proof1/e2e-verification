#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "README.md",
    "README.ko.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "PUBLICATION_POLICY.md",
    "PUBLICATION_MANIFEST.md",
    "PUBLICATION_ALLOWLIST.txt",
    "PUBLICATION_BLOCKERS.md",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    "Dockerfile",
    ".dockerignore",
    "compose.yaml",
    "docs/environments.md",
    "docs/migration-0.2.md",
    "docs/model-orchestration.md",
    "tools/install_checkout.py",
    "wiki/Installation-and-Environments.md",
    "wiki/Migration-0.2.md",
}
PUBLIC_ROOTS = ("src", "schemas", "agents", "skills", "workflows", "examples", "docs", "wiki", "tests")
PUBLIC_FILES = (
    "README.md",
    "README.ko.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "PUBLICATION_POLICY.md",
    "PUBLICATION_MANIFEST.md",
    "pyproject.toml",
)
TEXT_SUFFIXES = {".md", ".py", ".toml", ".json", ".yml", ".yaml", ".txt"}
FORBIDDEN = {
    "private key": re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY"),
    "GitHub token": re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Unix home path": re.compile(r"/home/[A-Za-z0-9._-]+/"),
    "Windows home path": re.compile(r"[A-Za-z]:\\Users\\[^\\]+\\"),
}


def public_files() -> list[Path]:
    paths = [ROOT / name for name in PUBLIC_FILES]
    for name in PUBLIC_ROOTS:
        paths.extend(path for path in (ROOT / name).rglob("*") if path.is_file())
    return [path for path in paths if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES]


def main() -> int:
    errors: list[str] = []
    errors.extend(f"missing required file: {name}" for name in sorted(REQUIRED) if not (ROOT / name).is_file())

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata.get("project", {})
    if project.get("license") != "Apache-2.0" or "LICENSE" not in project.get("license-files", []):
        errors.append("pyproject.toml must declare Apache-2.0 and include LICENSE")

    for path in public_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        for label, pattern in FORBIDDEN.items():
            if pattern.search(text):
                errors.append(f"{label} candidate: {relative}")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8") if (ROOT / "MANIFEST.in").exists() else ""
    if "prune evidence" not in manifest:
        errors.append("MANIFEST.in must exclude generated evidence")

    if errors:
        print("release check failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"release check passed: {len(REQUIRED)} required files, {len(public_files())} public text files scanned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
