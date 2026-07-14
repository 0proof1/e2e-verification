from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_checkout", ROOT / "tools" / "install_checkout.py")
assert SPEC and SPEC.loader
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


class InstallCheckoutTest(unittest.TestCase):
    def test_revision_matching_accepts_full_and_short_sha_only(self) -> None:
        full = "a" * 40
        self.assertTrue(INSTALL.revision_matches(full, "a" * 12))
        self.assertTrue(INSTALL.revision_matches("a" * 12, full))
        self.assertFalse(INSTALL.revision_matches(full, "b" * 12))

    def test_dependencies_are_resolved_separately_from_forced_reinstall(self) -> None:
        requirements = INSTALL.dependency_requirements("dev, xlsx")
        self.assertIn("PyYAML>=6.0", requirements)
        self.assertIn("jsonschema>=4.18", requirements)
        self.assertIn("playwright>=1.49", requirements)
        self.assertIn("openpyxl>=3.1", requirements)
        commands = INSTALL.install_commands("dev")
        self.assertIn("PyYAML>=6.0", commands[0])
        self.assertNotIn(".", commands[0])
        self.assertEqual(["--force-reinstall", "--no-deps", "-e", "."], commands[1][-4:])
        with self.assertRaisesRegex(ValueError, "extra names"):
            INSTALL.requested_extras("dev;unsafe")
        with self.assertRaisesRegex(ValueError, "unknown extras"):
            INSTALL.dependency_requirements("unknown")

    def test_project_version_matches_package_version(self) -> None:
        import e2e_verification

        self.assertEqual(e2e_verification.__version__, INSTALL.project_version(ROOT))

    def test_cli_check_rejects_a_same_version_stale_entry_point(self) -> None:
        imported = json.dumps({"version": INSTALL.project_version(ROOT), "module": str(ROOT / "src" / "e2e_verification" / "__init__.py")})
        with (
            patch.object(INSTALL.shutil, "which", return_value="/venv/bin/e2e-verify"),
            patch.object(
                INSTALL.subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, imported, ""),
                    subprocess.CompletedProcess([], 0, "model-plan", ""),
                ],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "stale; missing commands: agent-task"):
                INSTALL.verify_install(INSTALL.project_version(ROOT))

    def test_check_only_enforces_expected_sha_without_installing(self) -> None:
        revision = INSTALL.git_revision(ROOT)
        accepted = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "install_checkout.py"), "--check-only", "--expected-sha", revision],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertFalse(json.loads(accepted.stdout)["forcedReinstall"])
        rejected = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "install_checkout.py"), "--check-only", "--expected-sha", "0" * 40],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(2, rejected.returncode)
        self.assertIn("does not match expected SHA", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
