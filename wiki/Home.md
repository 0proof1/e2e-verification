# e2e-verification Wiki

`e2e-verification` is an agent-guided, evidence-first platform for verifying
applications with complex roles, routes, APIs, browser behavior, downloads, and
test-data lifecycles.

Agents decide what to investigate. Declarative workflows bound the sequence and
risk. Deterministic harnesses interact with the target and write evidence that
can be reviewed independently.

## Start here

- [[Getting Started]] — validate the synthetic profile and run a dry plan.
- [[Installation and Environments]] — choose minimal extras, verify checkout provenance, and prepare Docker or offline hosts.
- [[Architecture]] — understand agents, skills, workflows, harnesses, and profiles.
- [[Model Orchestration]] — route model capabilities and create evidence-backed AI tasks.
- [[Profiles and Workflows]] — adapt the platform to another application.
- [[Safety Model]] — approvals, mutation rules, cleanup, and trust boundaries.
- [[Evidence and Reporting]] — statuses, artifacts, redaction, and reports.
- [[Migration 0.2]] — adopt evidence contract 1.1 and the v0.2 installation model.
- [[Troubleshooting]] — diagnose blocked or failed runs.

## Intended use

Run against local or explicitly isolated test environments. Review the plan
before execution. Keep credentials outside profiles and workflows. Downloads,
writes, destructive actions, and external sends require named approval.

The project is currently alpha. Missing evidence never becomes a pass, and
structured redaction does not make screenshots or arbitrary downloads safe to
publish automatically.
