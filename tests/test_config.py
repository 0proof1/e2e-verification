from __future__ import annotations

import unittest

from e2e_verification.config import validate_config


class ConfigTest(unittest.TestCase):
    def test_malformed_collections_return_errors_instead_of_crashing(self) -> None:
        errors = validate_config({"version": 1, "name": "bad", "roles": {}})
        self.assertIn("roles must be an array", errors)

    def test_inline_password_is_rejected(self) -> None:
        errors = validate_config({
            "version": 1,
            "name": "unsafe",
            "roles": [{"name": "ADMIN", "account": {"password": "secret"}}],
        })
        self.assertTrue(any("inline password is forbidden" in item for item in errors))

    def test_unknown_probe_risk_is_rejected(self) -> None:
        errors = validate_config({
            "version": 1,
            "name": "unsafe",
            "roles": [{"name": "ADMIN"}],
            "api_probes": [{"id": "API-1", "role": "ADMIN", "risk": "production"}],
        })
        self.assertTrue(any("unsupported risk" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
