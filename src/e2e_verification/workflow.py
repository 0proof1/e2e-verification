from __future__ import annotations

import json
import hashlib
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .evidence import (
    CONTRACT_VERSION,
    Cleanup,
    Finding,
    FunctionalStatus,
    Risk,
    Status,
    StepResult,
    UsabilityStatus,
    functional_from_legacy,
    legacy_status,
    now,
    write_json_atomic,
)
from .redaction import redact


@dataclass(slots=True)
class StepSpec:
    id: str
    harness: str
    needs: list[str] = field(default_factory=list)
    args: dict[str, Any] = field(default_factory=dict)
    risk: Risk = Risk.READ_ONLY
    approval: str = ""
    retries: int = 0
    timeout_seconds: int = 300
    when: str = "success"
    idempotent: bool = False


@dataclass(slots=True)
class WorkflowSpec:
    name: str
    steps: list[StepSpec]
    version: int = 1
    profile: str = ""


@dataclass(slots=True)
class HarnessOutcome:
    status: Status
    summary: dict[str, int] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    cleanup: Cleanup = field(default_factory=Cleanup)
    findings: list[Finding] = field(default_factory=list)
    recommended_next_steps: list[str] = field(default_factory=list)
    functional_status: FunctionalStatus | None = None
    usability_status: UsabilityStatus = UsabilityStatus.SKIP


Harness = Callable[[StepSpec, Path], HarnessOutcome]


class HarnessRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Harness] = {}

    def register(self, name: str, harness: Harness) -> None:
        if not name or name in self._items:
            raise ValueError(f"invalid or duplicate harness: {name}")
        self._items[name] = harness

    def get(self, name: str) -> Harness:
        try:
            return self._items[name]
        except KeyError as error:
            raise ValueError(f"unknown harness: {name}") from error

    def names(self) -> list[str]:
        return sorted(self._items)


def load_workflow(path: Path) -> WorkflowSpec:
    raw = _load_document(path)
    if raw.get("version") != 1:
        raise ValueError("workflow version must be 1")
    steps = [
        StepSpec(
            id=item.get("id", ""),
            harness=item.get("harness", ""),
            needs=list(item.get("needs", [])),
            args=dict(item.get("args", {})),
            risk=Risk(item.get("risk", Risk.READ_ONLY)),
            approval=item.get("approval", ""),
            retries=int(item.get("retries", 0)),
            timeout_seconds=int(item.get("timeout_seconds", 300)),
            when=item.get("when", "success"),
            idempotent=bool(item.get("idempotent", False)),
        )
        for item in raw.get("steps", [])
    ]
    spec = WorkflowSpec(name=raw.get("name", ""), steps=steps, version=1, profile=raw.get("profile", ""))
    validate_workflow(spec)
    return spec


def validate_workflow(spec: WorkflowSpec, registry: HarnessRegistry | None = None) -> None:
    if not spec.name.strip():
        raise ValueError("workflow name is required")
    ids = [step.id for step in spec.steps]
    if any(not item for item in ids):
        raise ValueError("every workflow step requires an id")
    if len(ids) != len(set(ids)):
        raise ValueError("workflow step ids must be unique")
    known = set(ids)
    for step in spec.steps:
        if not step.harness:
            raise ValueError(f"step {step.id}: harness is required")
        if registry:
            registry.get(step.harness)
        missing = set(step.needs) - known
        if missing:
            raise ValueError(f"step {step.id}: unknown dependencies {sorted(missing)}")
        if step.id in step.needs:
            raise ValueError(f"step {step.id}: cannot depend on itself")
        if step.risk != Risk.READ_ONLY and not step.approval:
            raise ValueError(f"step {step.id}: {step.risk} requires an approval gate")
        if step.retries < 0 or step.timeout_seconds < 1:
            raise ValueError(f"step {step.id}: invalid retry or timeout")
        if step.retries and step.risk != Risk.READ_ONLY and not step.idempotent:
            raise ValueError(f"step {step.id}: mutating retries require idempotent: true")
        if step.risk == Risk.EXTERNAL_SEND and step.retries:
            raise ValueError(f"step {step.id}: external-send steps cannot retry automatically")
        if step.when not in {"success", "failure", "always"}:
            raise ValueError(f"step {step.id}: unsupported condition {step.when}")
    ordered_steps(spec)


def ordered_steps(spec: WorkflowSpec) -> list[StepSpec]:
    by_id = {step.id: step for step in spec.steps}
    pending = list(spec.steps)
    completed: set[str] = set()
    ordered: list[StepSpec] = []
    while pending:
        ready = [step for step in pending if set(step.needs) <= completed]
        if not ready:
            raise ValueError("workflow contains a dependency cycle")
        for step in ready:
            ordered.append(step)
            completed.add(step.id)
            pending.remove(step)
    return ordered


class WorkflowRunner:
    def __init__(self, registry: HarnessRegistry) -> None:
        self.registry = registry

    def run(
        self,
        spec: WorkflowSpec,
        run_dir: Path,
        approvals: set[str] | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        validate_workflow(spec, self.registry)
        approvals = approvals or set()
        run_dir.mkdir(parents=True, exist_ok=True)
        state_path = run_dir / "run.json"
        if state_path.exists() and not resume:
            raise ValueError(f"run state already exists; use resume or choose another directory: {state_path}")
        state = self._load_state(state_path, spec) if resume else self._new_state(spec, run_dir)
        results = state.setdefault("steps", {})

        for step in ordered_steps(spec):
            existing = results.get(step.id, {})
            if resume and existing.get("status") in {Status.PASS, Status.REVIEW, Status.SKIP}:
                continue
            dependency_statuses = [results.get(item, {}).get("status") for item in step.needs]
            if not self._condition_matches(step.when, dependency_statuses):
                result = self._skipped(step, f"condition not met: {step.when}")
            elif step.approval and step.approval not in approvals:
                result = self._blocked(step, f"approval required: {step.approval}")
            else:
                result = self._execute(step, run_dir / "steps" / step.id, run_dir)
            results[step.id] = result.to_dict()
            state["status"] = self._run_status(results)
            state["updated_at"] = now()
            self._write_state(state_path, state)

        state["status"] = self._run_status(results)
        state["finished_at"] = now()
        self._write_state(state_path, state)
        return state

    def _execute(self, step: StepSpec, step_dir: Path, run_dir: Path) -> StepResult:
        step_dir.mkdir(parents=True, exist_ok=True)
        started = now()
        outcome: HarnessOutcome | None = None
        error = ""
        attempts = 0
        for attempt in range(step.retries + 1):
            attempts = attempt + 1
            try:
                outcome = self.registry.get(step.harness)(step, step_dir)
                if outcome.status != Status.FAIL:
                    break
            except Exception as caught:  # harness boundary: persist failure instead of losing the run
                error = f"{type(caught).__name__}: {caught}"
                outcome = HarnessOutcome(
                    status=Status.FAIL,
                    functional_status=FunctionalStatus.FAIL,
                    metadata={"error": error},
                )
            if attempt < step.retries:
                time.sleep(min(0.1 * (attempt + 1), 1.0))
        assert outcome is not None
        from .evidence import Artifact
        functional_status = outcome.functional_status or functional_from_legacy(outcome.status)
        outcome.status = legacy_status(functional_status)
        if step.risk in {Risk.WRITE, Risk.DESTRUCTIVE, Risk.EXTERNAL_SEND}:
            if not outcome.cleanup.required:
                outcome.cleanup = Cleanup(required=True, status=Status.FAIL, message="harness did not provide required cleanup evidence")
            if outcome.cleanup.status != Status.PASS and outcome.status == Status.PASS:
                outcome.status = Status.FAIL
                functional_status = FunctionalStatus.FAIL
        result = StepResult(
            step_id=step.id,
            harness=step.harness,
            status=outcome.status,
            risk=step.risk,
            started_at=started,
            finished_at=now(),
            summary=outcome.summary,
            artifacts=[Artifact(**item) for item in outcome.artifacts],
            cleanup=outcome.cleanup,
            metadata={**outcome.metadata, "attempts": attempts},
            findings=outcome.findings,
            recommended_next_steps=outcome.recommended_next_steps,
            functional_status=functional_status,
            usability_status=outcome.usability_status,
        )
        result.artifacts = [Artifact(**self._relative_artifact(item, run_dir)) for item in outcome.artifacts]
        result.write(step_dir / "result.json")
        return result

    def _blocked(self, step: StepSpec, reason: str) -> StepResult:
        timestamp = now()
        return StepResult(
            step_id=step.id,
            harness=step.harness,
            status=Status.BLOCKED,
            risk=step.risk,
            started_at=timestamp,
            finished_at=timestamp,
            functional_status=FunctionalStatus.BLOCKED,
            usability_status=UsabilityStatus.BLOCKED,
            cleanup=Cleanup(required=step.risk in {Risk.WRITE, Risk.DESTRUCTIVE, Risk.EXTERNAL_SEND}),
            metadata={"reason": reason},
        )

    def _skipped(self, step: StepSpec, reason: str) -> StepResult:
        timestamp = now()
        return StepResult(
            step_id=step.id,
            harness=step.harness,
            status=Status.SKIP,
            risk=step.risk,
            started_at=timestamp,
            finished_at=timestamp,
            functional_status=FunctionalStatus.SKIP,
            usability_status=UsabilityStatus.SKIP,
            cleanup=Cleanup(required=False, status=Status.SKIP),
            metadata={"reason": reason},
        )

    @staticmethod
    def _condition_matches(condition: str, statuses: list[str | None]) -> bool:
        if not statuses:
            return condition in {"success", "always"}
        if condition == "always":
            return all(status is not None for status in statuses)
        if condition == "failure":
            return any(status == Status.FAIL for status in statuses)
        return all(status in {Status.PASS, Status.REVIEW, Status.SKIP} for status in statuses)

    @staticmethod
    def _new_state(spec: WorkflowSpec, run_dir: Path) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_dir.name,
            "workflow": spec.name,
            "workflow_digest": workflow_digest(spec),
            "profile": spec.profile,
            "status": Status.BLOCKED,
            "started_at": now(),
            "updated_at": now(),
            "steps": {},
        }

    @staticmethod
    def _load_state(path: Path, spec: WorkflowSpec) -> dict[str, Any]:
        if not path.is_file():
            raise ValueError(f"cannot resume; run state does not exist: {path}")
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("contract_version") != CONTRACT_VERSION:
            raise ValueError(
                f"cannot resume evidence contract {state.get('contract_version')}; expected {CONTRACT_VERSION}"
            )
        if state.get("workflow") != spec.name:
            raise ValueError("resume workflow does not match existing run")
        if state.get("workflow_digest") != workflow_digest(spec):
            raise ValueError("cannot resume because the workflow definition changed")
        if state.get("profile", "") != spec.profile:
            raise ValueError("cannot resume because the workflow profile changed")
        return state

    @staticmethod
    def _run_status(results: dict[str, dict[str, Any]]) -> Status:
        statuses = {
            legacy_status(item["functional_status"]).value
            if item.get("functional_status") else legacy_status(functional_from_legacy(item.get("status", Status.BLOCKED))).value
            for item in results.values()
        }
        if Status.FAIL in statuses:
            return Status.FAIL
        if Status.BLOCKED in statuses:
            return Status.BLOCKED
        return Status.PASS if statuses else Status.BLOCKED

    @staticmethod
    def _relative_artifact(item: dict[str, Any], run_dir: Path) -> dict[str, Any]:
        value = dict(item)
        raw = Path(str(value.get("path", "")))
        if not str(raw):
            raise ValueError("artifact path is required")
        root = run_dir.resolve()
        candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
        try:
            relative = candidate.relative_to(root)
        except ValueError as error:
            raise ValueError(f"artifact path escapes run directory: {raw}") from error
        value["path"] = relative.as_posix()
        return value

    @staticmethod
    def _write_state(path: Path, state: dict[str, Any]) -> None:
        write_json_atomic(path, redact(state))


def subprocess_harness(command: list[str], timeout_seconds: int = 300) -> Harness:
    """Wrap a fixed executable prefix; workflow data can only append declared argument values."""
    fixed = tuple(command)

    def run(step: StepSpec, step_dir: Path) -> HarnessOutcome:
        args = [*fixed]
        for key, value in step.args.items():
            option = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    args.append(option)
            elif isinstance(value, list):
                for item in value:
                    args.extend((option, str(item)))
            else:
                args.extend((option, str(value)))
        completed = subprocess.run(
            args,
            cwd=step_dir,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=min(step.timeout_seconds, timeout_seconds),
            check=False,
        )
        (step_dir / "stdout.log").write_text(str(redact(completed.stdout)), encoding="utf-8")
        (step_dir / "stderr.log").write_text(str(redact(completed.stderr)), encoding="utf-8")
        return HarnessOutcome(
            status=Status.PASS if completed.returncode == 0 else Status.FAIL,
            summary={"passed": int(completed.returncode == 0), "failed": int(completed.returncode != 0)},
            artifacts=[
                {"kind": "log", "path": str(step_dir / "stdout.log"), "description": "harness stdout", "redacted": True},
                {"kind": "log", "path": str(step_dir / "stderr.log"), "description": "harness stderr", "redacted": True},
            ],
            metadata={"exit_code": completed.returncode},
        )

    return run


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as error:
            raise RuntimeError("YAML workflows require PyYAML") from error
        value = yaml.safe_load(text)
        if not isinstance(value, dict):
            raise ValueError("workflow document must be an object")
        return value
    raise ValueError("workflow must use .json, .yaml, or .yml")


def workflow_digest(spec: WorkflowSpec) -> str:
    payload = {
        "version": spec.version,
        "name": spec.name,
        "profile": spec.profile,
        "steps": [asdict(step) for step in spec.steps],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
