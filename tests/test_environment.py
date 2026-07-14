from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from e2e_verification.environment import (
    RuntimeEnvironment,
    credential_checks,
    diagnose,
    endpoint_checks,
    resolve_endpoint,
)


def runtime(in_container: bool) -> RuntimeEnvironment:
    return RuntimeEnvironment("Linux", "x86_64", "3.12", in_container, True, False, True, True)


class EnvironmentTest(unittest.TestCase):
    def test_unstamped_host_runtime_reports_unknown_source_revision(self) -> None:
        self.assertEqual("unknown", runtime(False).source_revision)

    def test_cli_endpoint_wins(self) -> None:
        config = {"defaults": {"api_base": "http://config:8080"}}
        with patch.dict(os.environ, {"E2E_API_BASE": "http://env:8080"}):
            result = resolve_endpoint("api", "http://cli:8080", config, "same-network", runtime=runtime(True))
        self.assertEqual("http://cli:8080", result.url)
        self.assertEqual("cli", result.source)

    def test_environment_endpoint_wins_over_config(self) -> None:
        config = {"defaults": {"api_base": "http://config:8080"}}
        with patch.dict(os.environ, {"E2E_API_BASE": "http://env:8080"}):
            result = resolve_endpoint("api", None, config, "same-network", runtime=runtime(True))
        self.assertEqual("http://env:8080", result.url)

    def test_auto_blocks_ambiguous_container_loopback(self) -> None:
        result = resolve_endpoint("api", "http://127.0.0.1:8080", {}, "auto", runtime=runtime(True))
        self.assertTrue(result.blockers)

    def test_container_local_accepts_loopback_in_container(self) -> None:
        result = resolve_endpoint("api", "http://127.0.0.1:8080", {}, "container-local", runtime=runtime(True))
        self.assertEqual([], result.blockers)

    def test_container_local_is_rejected_on_host(self) -> None:
        result = resolve_endpoint("api", "http://127.0.0.1:8080", {}, "container-local", runtime=runtime(False))
        self.assertTrue(result.blockers)

    def test_same_network_requires_service_hostname(self) -> None:
        result = resolve_endpoint("api", "http://localhost:8080", {}, "same-network", runtime=runtime(True))
        self.assertTrue(result.blockers)

    def test_same_network_requires_container_runtime(self) -> None:
        result = resolve_endpoint("api", "http://service:8080", {}, "same-network", runtime=runtime(False))
        self.assertTrue(result.blockers)

    def test_host_mode_is_rejected_inside_container(self) -> None:
        result = resolve_endpoint("api", "http://host.example:8080", {}, "host", runtime=runtime(True))
        self.assertTrue(result.blockers)

    def test_embedded_url_credentials_are_rejected(self) -> None:
        result = resolve_endpoint("api", "https://user:secret@example.test/api", {}, "external", runtime=runtime(False))
        self.assertTrue(result.blockers)

    def test_host_from_container_rewrites_only_when_explicit(self) -> None:
        result = resolve_endpoint(
            "api",
            "http://localhost:8080/api",
            {},
            "host-from-container",
            "gateway.internal",
            runtime(True),
        )
        self.assertEqual("http://gateway.internal:8080/api", result.url)
        self.assertTrue(result.warnings)

    def test_external_http_warns(self) -> None:
        result = resolve_endpoint("web", "http://example.test", {}, "external", runtime=runtime(False))
        self.assertEqual([], result.blockers)
        self.assertTrue(result.warnings)

    def test_missing_endpoint_blocks(self) -> None:
        result = resolve_endpoint("api", None, {}, "host", runtime=runtime(False))
        self.assertTrue(result.blockers)

    def test_missing_credentials_are_reported_without_values(self) -> None:
        config = {
            "api_login": {"path": "/login"},
            "roles": [{"name": "ADMIN", "account": {"id_env": "TEST_ID", "password_env": "TEST_PASSWORD"}}],
        }
        with patch.dict(os.environ, {}, clear=True):
            checks = credential_checks(config)
        self.assertEqual(["BLOCKED", "BLOCKED"], [check["status"] for check in checks])
        self.assertNotIn("secret", str(checks))

    def test_endpoint_check_does_not_connect_by_default(self) -> None:
        endpoint = resolve_endpoint("api", "http://localhost:1", {}, "host", runtime=runtime(False))
        checks = endpoint_checks(endpoint, connect=False)
        self.assertTrue(any(check["check"] == "dns:api" for check in checks))
        self.assertFalse(any(check["check"] == "tcp:api" for check in checks))

    def test_doctor_without_profile_is_non_blocking(self) -> None:
        with patch("e2e_verification.environment.detect_runtime", return_value=runtime(False)):
            result = diagnose(None, None, None, "auto", "host.docker.internal", False)
        self.assertEqual(0, result["summary"]["blocked"])


if __name__ == "__main__":
    unittest.main()
