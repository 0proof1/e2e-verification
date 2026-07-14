from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from e2e_verification.evidence import Cleanup, Finding, FunctionalStatus, Risk, Status, UsabilityStatus
from e2e_verification.workflow import (
    HarnessOutcome,
    HarnessRegistry,
    StepSpec,
    WorkflowRunner,
    WorkflowSpec,
    ordered_steps,
    validate_workflow,
)


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[str] = []
        self.registry = HarnessRegistry()

        def passing(step: StepSpec, _out: Path) -> HarnessOutcome:
            self.calls.append(step.id)
            cleanup = Cleanup(required=step.risk != Risk.READ_ONLY, status=Status.PASS)
            return HarnessOutcome(status=Status.PASS, summary={"passed": 1}, cleanup=cleanup)

        self.registry.register("pass", passing)

    def test_dependency_order_is_stable(self) -> None:
        spec = WorkflowSpec("test", [
            StepSpec("browser", "pass", needs=["api"]),
            StepSpec("api", "pass"),
        ])
        self.assertEqual(["api", "browser"], [item.id for item in ordered_steps(spec)])

    def test_cycle_is_rejected(self) -> None:
        spec = WorkflowSpec("test", [
            StepSpec("a", "pass", needs=["b"]),
            StepSpec("b", "pass", needs=["a"]),
        ])
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_workflow(spec)

    def test_mutation_requires_named_approval(self) -> None:
        spec = WorkflowSpec("test", [StepSpec("write", "pass", risk=Risk.WRITE)])
        with self.assertRaisesRegex(ValueError, "approval gate"):
            validate_workflow(spec)

    def test_blocked_write_resumes_after_approval_without_rerunning_passed_step(self) -> None:
        spec = WorkflowSpec("test", [
            StepSpec("read", "pass"),
            StepSpec("write", "pass", needs=["read"], risk=Risk.WRITE, approval="safe-write"),
        ])
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            first = WorkflowRunner(self.registry).run(spec, run_dir)
            self.assertEqual("BLOCKED", first["status"])
            self.assertEqual(["read"], self.calls)
            second = WorkflowRunner(self.registry).run(spec, run_dir, approvals={"safe-write"}, resume=True)
        self.assertEqual("PASS", second["status"])
        self.assertEqual(["read", "write"], self.calls)

    def test_unknown_harness_is_rejected_before_execution(self) -> None:
        spec = WorkflowSpec("test", [StepSpec("read", "missing")])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unknown harness"):
                WorkflowRunner(self.registry).run(spec, Path(directory))

    def test_resume_rejects_changed_workflow_with_same_name(self) -> None:
        original = WorkflowSpec("test", [StepSpec("read", "pass")], profile="profile-a")
        changed = WorkflowSpec("test", [StepSpec("read", "pass"), StepSpec("extra", "pass")], profile="profile-a")
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            WorkflowRunner(self.registry).run(original, run_dir)
            with self.assertRaisesRegex(ValueError, "definition changed"):
                WorkflowRunner(self.registry).run(changed, run_dir, resume=True)

    def test_resume_rejects_an_older_evidence_contract(self) -> None:
        spec = WorkflowSpec("test", [StepSpec("read", "pass")])
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            WorkflowRunner(self.registry).run(spec, run_dir)
            state_path = run_dir / "run.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["contract_version"] = "1.0"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "evidence contract 1.0"):
                WorkflowRunner(self.registry).run(spec, run_dir, resume=True)

    def test_new_run_refuses_to_overwrite_existing_state(self) -> None:
        spec = WorkflowSpec("test", [StepSpec("read", "pass")])
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            WorkflowRunner(self.registry).run(spec, run_dir)
            with self.assertRaisesRegex(ValueError, "already exists"):
                WorkflowRunner(self.registry).run(spec, run_dir)

    def test_failure_condition_runs_only_after_failed_dependency(self) -> None:
        self.registry.register("fail", lambda _step, _out: HarnessOutcome(status=Status.FAIL))
        spec = WorkflowSpec("test", [
            StepSpec("probe", "fail"),
            StepSpec("triage", "pass", needs=["probe"], when="failure"),
            StepSpec("normal", "pass", needs=["probe"]),
        ])
        with tempfile.TemporaryDirectory() as directory:
            state = WorkflowRunner(self.registry).run(spec, Path(directory))
        self.assertEqual("PASS", state["steps"]["triage"]["status"])
        self.assertEqual("SKIP", state["steps"]["normal"]["status"])

    def test_unknown_condition_is_rejected(self) -> None:
        spec = WorkflowSpec("test", [StepSpec("read", "pass", when="sometimes")])
        with self.assertRaisesRegex(ValueError, "unsupported condition"):
            validate_workflow(spec)

    def test_mutating_retry_requires_explicit_idempotency(self) -> None:
        spec = WorkflowSpec("test", [
            StepSpec("write", "pass", risk=Risk.WRITE, approval="safe-write", retries=1),
        ])
        with self.assertRaisesRegex(ValueError, "idempotent"):
            validate_workflow(spec)

    def test_external_send_cannot_retry_automatically(self) -> None:
        spec = WorkflowSpec("test", [
            StepSpec("send", "pass", risk=Risk.EXTERNAL_SEND, approval="external-send", retries=1, idempotent=True),
        ])
        with self.assertRaisesRegex(ValueError, "cannot retry"):
            validate_workflow(spec)

    def test_missing_cleanup_is_persisted_as_failure(self) -> None:
        self.registry.register("unsafe-write", lambda _step, _out: HarnessOutcome(status=Status.PASS))
        spec = WorkflowSpec("test", [
            StepSpec("write", "unsafe-write", risk=Risk.WRITE, approval="safe-write"),
        ])
        with tempfile.TemporaryDirectory() as directory:
            state = WorkflowRunner(self.registry).run(spec, Path(directory), approvals={"safe-write"})
        self.assertEqual("FAIL", state["status"])
        self.assertEqual("FAIL", state["steps"]["write"]["cleanup"]["status"])
        self.assertIn("required cleanup", state["steps"]["write"]["cleanup"]["message"])

    def test_usability_review_and_findings_propagate_without_failing_run(self) -> None:
        self.registry.register("review", lambda _step, _out: HarnessOutcome(
            status=Status.REVIEW,
            functional_status=FunctionalStatus.PASS,
            usability_status=UsabilityStatus.REVIEW,
            findings=[Finding("UX-1", Status.REVIEW, "Ambiguous label")],
            recommended_next_steps=["Clarify the label"],
        ))
        with tempfile.TemporaryDirectory() as directory:
            state = WorkflowRunner(self.registry).run(
                WorkflowSpec("test", [StepSpec("ui", "review")]), Path(directory),
            )
        self.assertEqual("PASS", state["status"])
        self.assertEqual("REVIEW", state["steps"]["ui"]["usability_status"])
        self.assertEqual("UX-1", state["steps"]["ui"]["findings"][0]["id"])
        self.assertEqual(["Clarify the label"], state["steps"]["ui"]["recommended_next_steps"])

    def test_artifact_paths_are_run_relative_and_cannot_escape(self) -> None:
        def artifact(_step: StepSpec, out: Path) -> HarnessOutcome:
            image = out / "shot.png"; image.write_bytes(b"png")
            return HarnessOutcome(status=Status.PASS, artifacts=[{"kind": "screenshot", "path": str(image)}])
        self.registry.register("artifact", artifact)
        with tempfile.TemporaryDirectory() as directory:
            state = WorkflowRunner(self.registry).run(
                WorkflowSpec("test", [StepSpec("ui", "artifact")]), Path(directory),
            )
        self.assertEqual("steps/ui/shot.png", state["steps"]["ui"]["artifacts"][0]["path"])

        self.registry.register("escape", lambda _step, _out: HarnessOutcome(
            status=Status.PASS, artifacts=[{"kind": "screenshot", "path": "/tmp/outside.png"}],
        ))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "escapes run directory"):
                WorkflowRunner(self.registry).run(
                    WorkflowSpec("test", [StepSpec("ui", "escape")]), Path(directory),
                )


if __name__ == "__main__":
    unittest.main()
