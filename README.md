# e2e-verification

**Agent-guided verification. Deterministic execution. Evidence you can audit.**

`e2e-verification` is an open verification platform for applications with complex roles, routes, APIs, UI actions, downloads, and test-data lifecycles. Agents decide what to investigate; reusable skills define safe procedures; resumable workflows control sequence and approval; deterministic harnesses interact with the product and record evidence.

```text
Agent ──selects──▶ Skill ──uses──▶ Workflow ──runs──▶ Harness
  ▲                                                     │
  └──────── findings and recommended follow-up ◀────────┘
                            │
                            ▼
                 JSON · screenshots · HTML · XLSX
```

The platform is framework-neutral. Product knowledge lives in removable profiles and adapters—not in the core.

## Why this exists

Traditional E2E suites are good at repeating known test cases. They are less helpful when verification must answer broader questions:

- Does every role see and reach only its intended surface?
- Does a visible control actually bind to the expected route, DOM state, or API?
- Is a negative response understandable and recoverable in the browser?
- Is an export structurally valid without leaking its private rows into a report?
- Can a write fixture prove both persistence and cleanup?
- Can a stopped run resume without repeating completed mutations?

This project turns those questions into inspectable workflows and versioned evidence.

## The model at a glance

| Layer | Responsibility | Must not do |
|---|---|---|
| **Agent** | Plan, interpret, triage, choose justified follow-up | Silently broaden execution scope |
| **Skill** | Capture a reusable verification procedure | Embed one product's credentials or selectors |
| **Workflow** | Declare dependencies, conditions, risk, approval, retry, and resume | Execute arbitrary shell supplied by a profile |
| **Harness** | Perform deterministic API/browser work and emit evidence | Decide its own next task |
| **Profile** | Describe product roles, login, routes, probes, and fixtures | Change platform-core behavior |

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install chromium
```

Validate the synthetic example profile and inspect its read-only workflow without contacting a target:

```bash
.venv/bin/e2e-verify validate --config examples/project.example.json
.venv/bin/e2e-verify plan --workflow workflows/read-only.json
.venv/bin/e2e-verify run --workflow workflows/read-only.json --dry-run
```

To run it against your isolated test application, provide credentials through the environment and override target URLs when needed:

```bash
export E2E_ADMIN_ID='test-admin'
export E2E_ADMIN_PASSWORD='...'
export E2E_API_BASE='http://127.0.0.1:8080/api'

.venv/bin/e2e-verify run \
  --workflow workflows/read-only.json \
  --run-dir evidence/runs/first-run
```

Inspect the execution environment before contacting a target:

```bash
e2e-verify doctor --config examples/project.example.json --target-mode host --connect
```

Docker and non-Docker targets use explicit target modes. Ambiguous loopback
addresses inside containers are blocked instead of guessed. See
[Environment and target modes](docs/environments.md).

A blocked run keeps its completed evidence. Fix the missing prerequisite and resume with the **same** workflow:

```bash
.venv/bin/e2e-verify resume \
  --workflow workflows/read-only.json \
  --run-dir evidence/runs/first-run
```

Approval tokens are supplied only to a workflow that declares the corresponding gated step. For example, a step declaring `approval: fixture-write` can run only when the operator supplies `--approve fixture-write`.

Generate a standalone human-readable report:

```bash
.venv/bin/e2e-verify report --run-dir evidence/runs/first-run
```

For an optional tabular export, install the extra and select XLSX explicitly:

```bash
.venv/bin/pip install -e '.[xlsx]'
.venv/bin/e2e-verify report --run-dir evidence/runs/first-run --format xlsx
```

The run directory contains `run.json`, one `result.json` per executed step, redacted logs, and selected artifacts. HTML is the default human report; XLSX remains an optional profile exporter.

## Safety is part of the contract

Read-only execution is the default. Every other risk class requires an explicit named workflow approval.

| Risk | Typical actions | Default |
|---|---|---|
| `read-only` | Login, GET probes, route checks | Allowed by the selected workflow |
| `download` | CSV/XLSX export | Approval-gated |
| `write` | Create, update, import commit | Approval-gated; cleanup required |
| `destructive` | Delete, disable, irreversible transition | Approval-gated; cleanup required |
| `external-send` | Email, SMS, push, payment, webhook | Separate explicit approval |

A mutating step cannot report `PASS` unless cleanup is independently verified. Tokens, authentication headers, cookies, known sensitive fields, email addresses, phone numbers, and sensitive URL parameters are redacted before structured evidence is written. Screenshots and raw downloads remain marked unredacted until reviewed.

## Add another project

Copy the example and describe only the product-specific contract:

```bash
mkdir -p profiles/my-project
cp examples/project.example.json profiles/my-project/project.json
.venv/bin/e2e-verify validate --config profiles/my-project/project.json
```

A profile may define:

- login requests and browser selectors;
- environment-variable names for test accounts;
- roles, home paths, menus, allowed routes, and forbidden routes;
- API probes and expected statuses;
- browser actions and expected paths, DOM state, or network bindings;
- fixture lifecycle and cleanup rules through an optional adapter.

Use `${account.id}`, `${account.password}`, `${account.mode}`, `${role}`, and `${env:NAME}` substitutions. Never put a real password in the profile.

Framework-specific discovery—Spring controllers, Django URL configuration, Rails routes, generated OpenAPI, or a proprietary workbook—belongs in a profile adapter. Removing a profile must not require changes to `src/e2e_verification/`.

Adapters are executable code and are loaded only through an explicit CLI argument—not from an untrusted workflow document:

```bash
e2e-verify plan \
  --adapter profiles/my-project/adapter.py \
  --workflow profiles/my-project/workflow.yaml
```

## Reusable skills and agents

The repository ships eight validated skills under `skills/`:

`discover-project` · `verify-rbac-api` · `verify-browser-routes` · `verify-ui-bindings` · `verify-error-ux` · `verify-exports` · `verify-safe-writes` · `closeout-evidence`

Portable role definitions under `agents/` compose those skills:

- `verification-lead` plans and coordinates the smallest safe workflow.
- `failure-triage` classifies failures and proposes a minimal reproduction.
- `evidence-reviewer` audits completeness, redaction, cleanup, and publication readiness.

These definitions are intentionally thin. Product behavior stays in profiles; reliable execution stays in harness code.

Source distributions and wheels include schemas, agents, skills, the synthetic profile, and the example workflow under `share/e2e-verification/`. Locate the checkout or installed asset root with:

```bash
e2e-verify assets
```

## Status semantics

| Status | Meaning |
|---|---|
| `PASS` | The configured observable contract was proven |
| `FAIL` | The observed behavior contradicted the contract |
| `REVIEW` | Evidence exists, but a human or product-policy decision remains |
| `BLOCKED` | A prerequisite, fixture, credential, environment, or approval is missing |
| `SKIP` | A declared workflow condition did not select the step |

Missing evidence is never converted into success. CLI exit codes are `0` for completed/reviewed work, `2` for failure or invalid invocation, and `3` for a safely blocked workflow.

## Repository map

```text
agents/                    portable verification roles
skills/                    reusable procedures and UI metadata
workflows/                 declarative execution graphs
schemas/                   workflow, agent, run, and step contracts
src/e2e_verification/
  config.py                profile validation and substitution
  api_harness.py           deterministic API probes
  browser_harness.py       deterministic browser probes
  workflow.py              planning, gates, retries, and resume
  evidence.py              status and evidence models
  redaction.py             persistence-time redaction
  reporting.py             human-readable reports
profiles/<project>/        removable product adapters and references
tests/                     contract and execution tests
```

The repository contains only product-neutral platform code and synthetic examples. Python wheel and source-release boundaries are defined by `pyproject.toml`, `MANIFEST.in`, and `PUBLICATION_ALLOWLIST.txt`. The stricter `tools/public_repo_gate.py` scans the complete tracked source candidate before repository publication.

## Legacy commands

Config-driven commands are available for direct verification:

```bash
e2e-verify api --config profiles/my-project/project.json
e2e-verify browser --config profiles/my-project/project.json
e2e-verify all --config profiles/my-project/project.json
```

These commands use the same product-neutral configuration and evidence contracts as workflow harnesses.

## Development

```bash
.venv/bin/pip install -e '.[dev]'
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
python3 tools/release_check.py
```

Release artifacts must also pass:

```bash
python3 tools/check_artifact.py dist/*
python3 tools/generate_sbom.py dist/sbom.cdx.json
```

Architecture and policy details:

- [Architecture](docs/architecture.md)
- [Open-source boundary](docs/open-source-boundary.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Publication policy](PUBLICATION_POLICY.md)
- [Release process](docs/release.md)
- [Dependency policy](docs/dependency-policy.md)
- [Security audit record](docs/security-audit.md)
- [Open-source readiness](docs/readiness.md)
- [Roadmap](ROADMAP.md)
- [Environment and target modes](docs/environments.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
