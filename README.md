# e2e-verification

<p align="center"><strong>Agent-guided verification. Deterministic execution. Evidence you can audit.</strong></p>

<p align="center">
  <strong>English</strong> · <a href="README.ko.md">한국어</a>
</p>

<p align="center"><code>Python 3.11+</code> · <code>API</code> · <code>Playwright</code> · <code>Docker</code> · <code>Apache-2.0</code></p>

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

### AI is the adaptive control plane

Without a model, the safety gates, redaction, deterministic harnesses, resume,
and reports remain useful. The differentiating loop is AI-guided: an agent uses
recorded evidence to choose a bounded follow-up workflow, interpret usability,
triage failures, or escalate an ambiguous decision. Models never replace the
harness for screenshots, DOM measurements, retries, or assertions.

Model work plans use capability slots instead of hard-coded vendor generations.
Bind any Codex, Claude, or custom models at runtime:

```bash
e2e-verify model-plan \
  --model-plan examples/model-plan.example.json \
  --provider codex

e2e-verify plan \
  --workflow workflows/pilot-visual.json \
  --model-plan examples/model-plan.example.json \
  --provider codex
```

After a run, `agent-task` produces a redacted, evidence-backed task packet for
an external model orchestrator. Generating a packet does not invoke a model or
authorize a mutation. See [Model orchestration](docs/model-orchestration.md).

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[browser]'
.venv/bin/playwright install chromium
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` and commands from
`.venv\Scripts`. Linux CI or container images can install browser system
packages with `python -m playwright install --with-deps chromium`.

### Choose the installation that matches your environment

| Environment | Recommended path | What is additionally required |
|---|---|---|
| API-only host | `.venv/bin/pip install -e .` | Base PyYAML dependency only |
| Browser host | `.venv/bin/pip install -e '.[browser]'` | Matching Playwright Chromium bundle |
| Development or CI | `tools/install_checkout.py --extras dev` | Git checkout and test dependencies |
| Docker or Compose | Included `Dockerfile` and `compose.yaml` | Docker Engine with Compose |
| Air-gapped host | Preloaded wheelhouse and browser bundle | Dependencies, build backend, and platform-matching binaries |

The package and unit-test matrix targets Python 3.11-3.13 on Linux and Python
3.12 on macOS and Windows. Full API, Chromium, and Docker integration is
currently exercised on Linux. ARM64, Alpine/musl, WSL, private-CA, and proxy
environments should run `e2e-verify doctor` and a synthetic smoke test before
being treated as validated deployment targets.

### Reinstall a checkout reproducibly

For repeated development installs, let the checkout installer resolve only the
selected dependency groups and then force-reinstall the project once:

```bash
.venv/bin/python tools/install_checkout.py --extras dev
```

CI and release jobs should also reject local modifications. `GITHUB_SHA` is
verified automatically when present; `--expected-sha` can provide it
explicitly.

```bash
.venv/bin/python tools/install_checkout.py --extras dev --require-clean
```

The installer verifies the source revision, import path, installed console
entry point, and current `model-plan` and `agent-task` commands. This prevents
pip's same-version satisfaction check from leaving an older CLI active. See
[Installation and environments](wiki/Installation-and-Environments.md).

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

### Run the synthetic visual pilot

The repository-owned pilot collects paired 1366x768 viewport/full-page
screenshots, scroll and title visibility measurements, overflow/clipping data,
and a failure trace after one retry:

```bash
docker compose build
docker compose run --rm verifier run \
  --workflow workflows/pilot-visual.json \
  --run-dir /evidence/runs/pilot-001
docker compose run --rm verifier report \
  --run-dir /evidence/runs/pilot-001
```

Use a new run directory for each pilot. CI supplies `SOURCE_SHA` while building
the verifier image so `doctor` can report the exact source revision.

### Collect UI audit evidence

Evidence contract `2.0` records functional and usability verdicts independently.
A usability `REVIEW` never changes a functional `PASS`, while a functional
failure remains visible even when screenshots were collected successfully. The
HTML report renders screenshot thumbnails with original-file links and filters
for role, state, and viewport; missing or unsafe artifact paths are reported as
warnings instead of being embedded.

For repeatable UI evidence, add a read-only `ui-audit` workflow step with an
`args.audit` file that conforms to `schemas/ui-audit-v1.schema.json`. The audit
can collect paired first-viewport/full-page screenshots across roles, loading,
data, empty, and error states; measure first-view title visibility, overflow,
clipping, and menu scroll reset; and run the bundled, pinned axe-core plus Tab
and focus-indicator checks for data cases. Product selectors and synthetic API
fixtures stay in the consuming project rather than this platform repository.
The `data` contract may either use `{"action": "passthrough"}` for seeded test
environments or a read-only `fixture_pattern` when the audit must prove a
deterministic non-empty state.

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
- `evidence-collector` runs bounded pilot/full collection and preserves paired evidence.
- `ux-reviewer` builds collectors and reviews usability independently from functionality.

These definitions are intentionally thin. Product behavior stays in profiles; reliable execution stays in harness code.

Source distributions and wheels include schemas, agents, skills, the synthetic profile, and the example workflow under `share/e2e-verification/`. Locate the checkout or installed asset root with:

```bash
e2e-verify assets
```

## Status semantics

Evidence contract 1.1 keeps the two questions independent:

| Field | Values | Question |
|---|---|---|
| `functionalStatus` | `PASS`, `FAIL`, `BLOCKED` | Did the observable product contract work? |
| `usabilityStatus` | `PASS`, `REVIEW`, `NOT_RUN` | Is the UX acceptable or does it need judgment? |

The aggregate workflow status remains:

| Status | Meaning |
|---|---|
| `PASS` | The configured observable contract was proven |
| `FAIL` | The observed behavior contradicted the contract |
| `REVIEW` | Evidence exists, but a human or product-policy decision remains |
| `BLOCKED` | A prerequisite, fixture, credential, environment, or approval is missing |
| `SKIP` | A declared workflow condition did not select the step |

Missing evidence is never converted into success. CLI exit codes are `0` for completed/reviewed work, `2` for failure or invalid invocation, and `3` for a safely blocked workflow.

Evidence contract 1.0 run directories remain reviewable but cannot resume
under 0.2. Start a new 1.1 run directory instead of mixing contracts; see
[0.2 migration guidance](docs/migration-0.2.md).

## Repository map

```text
agents/                    portable verification roles
skills/                    reusable procedures and UI metadata
workflows/                 declarative execution graphs
schemas/                   workflow, agent, run, and step contracts
wiki/                      GitHub Wiki source and operator guidance
src/e2e_verification/
  config.py                profile validation and substitution
  model_plan.py            provider-neutral model routing and escalation
  agent_task.py            redacted evidence handoffs for external model runtimes
  api_harness.py           deterministic API probes
  browser_harness.py       deterministic browser probes
  workflow.py              planning, gates, retries, and resume
  evidence.py              status and evidence models
  redaction.py             persistence-time redaction
  reporting.py             human-readable reports
profiles/<project>/        removable product adapters and references
tests/                     contract and execution tests
```

The repository contains only product-neutral platform code and synthetic examples. Python wheel and source-release boundaries are defined by `pyproject.toml`, `MANIFEST.in`, and `PUBLICATION_ALLOWLIST.txt`. Source archives include the reviewed Wiki source; wheels include runtime schemas, agents, skills, workflows, and examples. The stricter `tools/public_repo_gate.py` scans the complete tracked source candidate before repository publication.

## Maturity and validation limits

Version 0.2 is Alpha and currently **synthetic-verified**, not externally
validated. The repository demonstrates its contracts against repository-owned
targets on Linux, but it does not yet provide a public production-project case
study, independent security audit, PyPI release, multi-browser result, or broad
maintainer/community adoption. Provider-neutral model routing and task packets
are implemented; vendor model invocation and autonomous production exploration
remain external responsibilities.

The separate `feat/ui-ux-evidence-v2` feature line is under contract and
supply-chain review; multi-state UI audit and bundled axe-core execution are
not advertised as `main` features yet. See the
[UI Audit v2 integration note](docs/ui-audit-v2-integration.md).

Treat new product profiles, adapters, platforms, proxies, and private-CA
environments as unvalidated until they pass `doctor` and a synthetic smoke run.
See [Readiness and validation claims](docs/readiness.md) and the
[Roadmap](ROADMAP.md).

## Direct commands

Config-driven commands are available for direct verification:

```bash
e2e-verify api --config profiles/my-project/project.json
e2e-verify browser --config profiles/my-project/project.json
e2e-verify all --config profiles/my-project/project.json
```

These commands use the same product-neutral configuration and evidence contracts as workflow harnesses.

## Development

```bash
.venv/bin/python tools/install_checkout.py --extras dev
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
python3 tools/release_check.py
```

The checkout installer verifies `GITHUB_SHA` when present and force-reinstalls
the project itself with `--no-deps`, so pip's same-version satisfaction check
cannot leave an older CLI active. It then imports the package
from this checkout and invokes the installed console entry point, requiring the
current `model-plan` and `agent-task` commands to appear.

Release artifacts must also pass:

```bash
python3 tools/check_artifact.py dist/*
python3 tools/generate_sbom.py dist/sbom.cdx.json
```

Architecture and policy details:

- [Wiki home](wiki/Home.md)
- [Wiki installation and environments](wiki/Installation-and-Environments.md)
- [Wiki migration 0.2](wiki/Migration-0.2.md)
- [UI Audit v2 integration note](docs/ui-audit-v2-integration.md)
- [Architecture](docs/architecture.md)
- [Model orchestration](docs/model-orchestration.md)
- [0.2 migration guidance](docs/migration-0.2.md)
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
