from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from e2e_verification.evidence import (
    Cleanup, Finding, FunctionalStatus, Risk, RunResult, Status, StepResult, UsabilityStatus, exit_code,
)
from e2e_verification.redaction import REDACTED, redact


class EvidenceTest(unittest.TestCase):
    def test_findings_require_p0_to_p3_severity_and_evidence(self) -> None:
        result = StepResult(
            step_id="ux", harness="review", status=Status.REVIEW,
            started_at="2026-07-12T00:00:00+00:00", finished_at="2026-07-12T00:00:01+00:00",
            findings=[Finding(id="UX-1", status=Status.REVIEW, title="Ambiguous CTA", severity="P1")],
        )
        with self.assertRaisesRegex(ValueError, "evidence link"):
            result.to_dict()
    def test_read_only_result_serializes(self) -> None:
        result = StepResult(
            step_id="api-read",
            harness="api-matrix",
            status=Status.PASS,
            started_at="2026-07-12T00:00:00+00:00",
            finished_at="2026-07-12T00:00:01+00:00",
            summary={"passed": 1, "failed": 0},
        )
        self.assertEqual("PASS", result.to_dict()["status"])
        self.assertEqual("PASS", result.to_dict()["functional_status"])
        self.assertEqual("SKIP", result.to_dict()["usability_status"])

    def test_usability_review_does_not_change_legacy_functional_status(self) -> None:
        result = StepResult(
            step_id="ui", harness="audit", status=Status.REVIEW,
            functional_status=FunctionalStatus.PASS, usability_status=UsabilityStatus.REVIEW,
            started_at="2026-07-12T00:00:00+00:00", finished_at="2026-07-12T00:00:01+00:00",
        )
        payload = result.to_dict()
        self.assertEqual("PASS", payload["status"])
        self.assertEqual("PASS", payload["functional_status"])
        self.assertEqual("REVIEW", payload["usability_status"])
        self.assertEqual(0, exit_code(result.status))

    def test_mutating_pass_requires_cleanup(self) -> None:
        result = StepResult(
            step_id="write",
            harness="write-fixture",
            status=Status.PASS,
            risk=Risk.WRITE,
            started_at="2026-07-12T00:00:00+00:00",
            finished_at="2026-07-12T00:00:01+00:00",
        )
        with self.assertRaisesRegex(ValueError, "require cleanup"):
            result.validate()

    def test_mutating_pass_accepts_verified_cleanup(self) -> None:
        result = StepResult(
            step_id="write",
            harness="write-fixture",
            status=Status.PASS,
            risk=Risk.WRITE,
            started_at="2026-07-12T00:00:00+00:00",
            finished_at="2026-07-12T00:00:01+00:00",
            cleanup=Cleanup(required=True, status=Status.PASS),
        )
        result.validate()

    def test_write_redacts_before_persisting(self) -> None:
        result = StepResult(
            step_id="api-read",
            harness="api-matrix",
            status=Status.PASS,
            started_at="2026-07-12T00:00:00+00:00",
            finished_at="2026-07-12T00:00:01+00:00",
            metadata={"token": "secret-token", "email": "person@example.com"},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "step.json"
            result.write(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(REDACTED, payload["metadata"]["token"])
        self.assertEqual("p***@example.com", payload["metadata"]["email"])

    def test_run_model_matches_keyed_step_contract(self) -> None:
        step = StepResult(
            step_id="read", harness="api", status=Status.PASS,
            started_at="2026-07-12T00:00:00+00:00", finished_at="2026-07-12T00:00:01+00:00",
        )
        run = RunResult(
            run_id="run-1", workflow="read", workflow_digest="a" * 64, profile="example",
            status=Status.PASS, started_at=step.started_at, updated_at=step.finished_at,
            finished_at=step.finished_at, steps={"read": step},
        )
        self.assertEqual("read", run.to_dict()["steps"]["read"]["step_id"])

    def test_exit_codes_distinguish_failure_and_blocked(self) -> None:
        self.assertEqual(0, exit_code(Status.PASS))
        self.assertEqual(2, exit_code(Status.FAIL))
        self.assertEqual(3, exit_code(Status.BLOCKED))


class RedactionTest(unittest.TestCase):
    def test_sensitive_headers_and_query_values_are_removed(self) -> None:
        payload = redact({
            "Authorization": "Bearer abc.def.ghi",
            "url": "https://test.invalid/users?name=Jane&limit=5&token=abc",
            "phone": "010-1234-5678",
        })
        self.assertEqual(REDACTED, payload["Authorization"])
        self.assertEqual(
            "https://test.invalid/users?name=%5BREDACTED%5D&limit=5&token=%5BREDACTED%5D",
            payload["url"],
        )
        self.assertEqual(REDACTED, payload["phone"])


if __name__ == "__main__":
    unittest.main()
