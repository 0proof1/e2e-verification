from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
class PublicationTest(unittest.TestCase):
    def test_community_health_files_exist(self) -> None:
        required = [
            "README.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "SECURITY.md",
            "SUPPORT.md",
            "GOVERNANCE.md",
        ]
        self.assertEqual([name for name in required if not (ROOT / name).is_file()], [])

    def test_manifest_excludes_generated_evidence(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("prune evidence", manifest)
        self.assertIn("global-exclude", manifest)

    def test_allowlist_contains_only_public_roots(self) -> None:
        allowlist = (ROOT / "PUBLICATION_ALLOWLIST.txt").read_text(encoding="utf-8")
        self.assertNotIn("compat/", allowlist)
        self.assertIn("examples/", allowlist)

    def test_obsolete_local_workspaces_are_absent(self) -> None:
        self.assertFalse((ROOT / "compat").exists())
        self.assertFalse((ROOT / "package.json").exists())
        self.assertFalse((ROOT / "package-lock.json").exists())

    def test_public_tree_has_no_generated_evidence_types(self) -> None:
        suffixes = {".xlsx", ".xls", ".har", ".trace", ".sqlite", ".db"}
        public_roots = ["src", "schemas", "agents", "skills", "workflows", "examples", "docs", "tests"]
        offenders = [
            str(path.relative_to(ROOT))
            for root in public_roots
            for path in (ROOT / root).rglob("*")
            if path.is_file() and path.suffix.lower() in suffixes
        ]
        self.assertEqual(offenders, [])

    def test_docker_context_excludes_evidence(self) -> None:
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("evidence", ignored)

    def test_public_tree_has_no_absolute_user_home(self) -> None:
        pattern = re.compile(r"/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[^\\]+\\")
        offenders = []
        for root in ("src", "schemas", "agents", "skills", "workflows", "examples", "docs", "tests"):
            for path in (ROOT / root).rglob("*"):
                if path.is_file() and path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml"}:
                    if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
                        offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_release_check_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/release_check.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_public_repo_gate_reports_tree_or_history_status(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/public_repo_gate.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn(result.returncode, {0, 1}, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"public repository gate (passed|failed)")
        if result.returncode:
            self.assertIn("Git history", result.stdout)


if __name__ == "__main__":
    unittest.main()
