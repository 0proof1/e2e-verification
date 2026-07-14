from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from .redaction import redact


CONTRACT_VERSION = "1.1"


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"
    SKIP = "SKIP"


class FunctionalStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class UsabilityStatus(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    NOT_RUN = "NOT_RUN"


class Risk(StrEnum):
    READ_ONLY = "read-only"
    DOWNLOAD = "download"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    EXTERNAL_SEND = "external-send"


@dataclass(slots=True)
class Artifact:
    kind: str
    path: str
    description: str = ""
    redacted: bool = True


@dataclass(slots=True)
class Finding:
    id: str
    status: Status
    title: str
    message: str = ""
    severity: str = "P3"
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Cleanup:
    required: bool = False
    status: Status = Status.SKIP
    message: str = ""


@dataclass(slots=True)
class StepResult:
    step_id: str
    harness: str
    status: Status
    started_at: str
    finished_at: str
    risk: Risk = Risk.READ_ONLY
    summary: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    cleanup: Cleanup = field(default_factory=Cleanup)
    recommended_next_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION
    functionalStatus: FunctionalStatus = FunctionalStatus.PASS
    usabilityStatus: UsabilityStatus = UsabilityStatus.NOT_RUN

    def validate(self) -> None:
        if not self.step_id.strip():
            raise ValueError("step_id is required")
        if not self.harness.strip():
            raise ValueError("harness is required")
        for finding in self.findings:
            if finding.severity not in {"P0", "P1", "P2", "P3"}:
                raise ValueError(f"finding {finding.id}: severity must be P0, P1, P2, or P3")
            if not finding.evidence:
                raise ValueError(f"finding {finding.id}: at least one evidence link is required")
        if self.risk in {Risk.WRITE, Risk.DESTRUCTIVE, Risk.EXTERNAL_SEND}:
            if not self.cleanup.required:
                raise ValueError(f"{self.risk} steps must require cleanup")
            if self.status == Status.PASS and self.cleanup.status != Status.PASS:
                raise ValueError("a mutating step cannot pass without verified cleanup")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return _enum_values(asdict(self))

    def write(self, path: Path) -> None:
        payload = redact(self.to_dict())
        write_json_atomic(path, payload)


@dataclass(slots=True)
class RunResult:
    run_id: str
    workflow: str
    workflow_digest: str
    profile: str
    status: Status
    started_at: str
    updated_at: str
    finished_at: str
    steps: dict[str, StepResult] = field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        if not self.run_id.strip():
            raise ValueError("run_id is required")
        for step in self.steps.values():
            step.validate()
        payload = _enum_values(asdict(self))
        payload["steps"] = {key: step.to_dict() for key, step in self.steps.items()}
        return payload

    def write(self, path: Path) -> None:
        write_json_atomic(path, redact(self.to_dict()))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def exit_code(status: Status) -> int:
    return 2 if status == Status.FAIL else 3 if status == Status.BLOCKED else 0


def _enum_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _enum_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_enum_values(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
