# Architecture

`e2e-verification` separates adaptive verification decisions from deterministic execution.

```text
Agent ──chooses──▶ Skill ──runs──▶ Workflow ──invokes──▶ Harness
  ▲                                                       │
  └──────────── findings and recommended next steps ◀─────┘
                              │
                              ▼
                    evidence artifacts and reports
```

## Components

### Agents

Agents plan verification, interpret findings, select follow-up work, and stop when a safety boundary or approval gate is reached. They do not hide product mutations inside reasoning.

### Skills

Skills contain concise, reusable operating procedures. A skill tells an agent which workflow to use, which references to load, how to interpret results, and when to request approval.

### Workflows

Workflows are declarative execution graphs. They define step dependencies, conditions, timeouts, retries, approval gates, and resume behavior. A workflow must remain inspectable before it is run.

### Harnesses

Harnesses are deterministic commands. They interact with APIs and browsers, enforce configured safety limits, and emit evidence that conforms to a shared contract. Harnesses never decide to broaden their own scope.

### Profiles

Profiles adapt the platform to a product. They contain selectors, roles, routes, endpoint expectations, fixture lifecycle rules, and optional report exporters. Product-specific knowledge must not leak into the platform core.

## Control flow

1. Discover the target and validate its profile.
2. Materialize a workflow plan without executing it.
3. Run read-only steps and persist one result document per step.
4. Stop at approval gates for write, destructive, notification, payment, or external-send behavior.
5. Resume approved steps from the existing run directory.
6. Verify cleanup before marking a mutating step complete.
7. Aggregate findings and artifacts into machine-readable JSON and a human-readable report.
8. Let an agent select only the follow-up steps justified by the recorded findings.

The adaptive loop is optional but intentional: a provider-neutral model plan
selects an agent capability slot, and an agent task packet combines that stage
with skills and redacted evidence. A model response can recommend a bounded
follow-up workflow; it never bypasses workflow validation or approval gates.
See [Model orchestration and the adaptive loop](model-orchestration.md).

## Design rules

- Read-only is the default.
- Execution scope is explicit and reviewable.
- Every assessed result is backed by an observable contract.
- `PASS`, `FAIL`, `REVIEW`, `BLOCKED`, and `SKIP` have stable meanings.
- Evidence is redacted before it is written.
- A mutating step without verified cleanup cannot pass.
- Resume reuses completed step results rather than silently rerunning mutations.
- Legacy commands remain wrappers until parity tests authorize their removal.
