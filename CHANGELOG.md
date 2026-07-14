# Changelog

All notable changes are documented here. The project follows semantic
versioning after the first public-ready release.

## Unreleased

## 0.2.0 - 2026-07-14

### Added

- Added provider-neutral model work plans with Codex, Claude, and custom
  environment bindings, capability slots, staged responsibilities, usage
  ceilings, and evidence-based escalation rules.
- Added `model-plan` CLI materialization and optional model routing in workflow
  plan output.
- Added `agent-task` packets that combine a resolved model stage, portable
  agent, complete skill instructions, minimal redacted run evidence,
  guardrails, and a structured response contract for external AI
  orchestrators.
- Added `evidence-collector` and `ux-reviewer` portable agent roles.
- Added a bounded 1366x768 Chromium pilot with scroll-top, first-viewport title,
  horizontal overflow, clipping, viewport/full-page capture pairs, structured
  measurements, one automatic retry, and failure trace persistence.
- Added HTML screenshot thumbnails linked to original evidence artifacts.
- Added provider-neutral model-plan and agent-task contract tests, mechanical UX
  validation tests, and container-aware API/Chromium integration coverage.
- Added a cross-platform checkout installer that verifies the expected Git SHA,
  installs only the selected declared dependencies, force-reinstalls
  same-version source once with `--no-deps`, and verifies the imported package
  and actual CLI entry point resolve to the current command contract.

### Changed

- Bumped the package from 0.1.0 to 0.2.0 and the evidence contract from 1.0 to
  1.1.
- Split `functionalStatus` (`PASS`, `FAIL`, `BLOCKED`) from `usabilityStatus`
  (`PASS`, `REVIEW`, `NOT_RUN`).
- Restricted finding severity to P0-P3 and require at least one evidence link
  for every finding.
- Reject resume when an existing run uses an incompatible evidence contract
  instead of silently mixing 1.0 and 1.1 evidence.
- Updated browser and closeout skills for paired captures, independent status
  review, and evidence-linked findings.
- Replaced the self-scored readiness rating with explicit `Designed`,
  `Synthetic-verified`, `Project-verified`, and `Externally-verified` claim
  levels.
- Documented synthetic-only validation, onboarding cost, Chromium/platform
  limits, trust-core risk, lack of independent audit, and maintainer bus-factor
  risk without presenting them as solved.
- Raised the minimum setuptools build backend to 77.0.3 so the declared SPDX
  license expression is valid in every supported isolated build.
- Moved Playwright from the base dependency set to the `browser` extra, retained
  it in `dev`, pinned direct Docker dependencies, embedded the source revision
  in the verifier image, and made package smoke tests checksum and
  force-reinstall their exact wheel. Source-only Docker rebuilds reuse the
  pinned browser-dependency layer while still reinstalling and smoke-testing
  the CLI.

### Verification

- Discovered 88 host unit/contract tests: 86 passed and 2 environment-gated
  integration tests skipped.
- Passed both skipped API and Chromium integration tests separately in Docker,
  including a deliberately missing selector that persisted a Playwright trace.
- Verified the Docker image reports package 0.2.0, Playwright 1.61.0, PyYAML
  6.0.3, and its supplied source revision; changing only that revision reused
  the browser dependency layer and force-reinstalled the project layer.
- Built and publication-boundary checked the 0.2.0 wheel, then force-installed
  that exact wheel into a fresh environment and smoke-tested `doctor`, `assets`,
  and `model-plan` through the installed console entry point.
- Re-ran the checkout installer against a virtual environment that already had
  0.2.0 installed; it replaced the distribution once, resolved imports to the
  requested checkout SHA, and verified the current CLI commands.
- Completed the repository-owned synthetic pilot with aggregate `PASS`,
  functional `PASS`, usability `PASS`, two viewport/full-page pairs, four HTML
  thumbnails, and a structured browser report.
- Passed compilation, schema validation, `git diff --check`, and the local
  release check. These results are synthetic verification, not a production
  case study or independent audit.

See [0.2 migration guidance](docs/migration-0.2.md) for evidence-contract and
resume compatibility.

## 0.1.0 - 2026-07-13

- Introduced portable agent definitions and eight reusable verification skills.
- Added versioned workflow, run, step-evidence, and agent schemas.
- Added registered harness execution, dependency ordering, conditions, approval
  gates, retries, dry-run planning, and resume.
- Added persistence-time redaction and mandatory verified cleanup for passing
  mutations.
- Added JSON run state and standalone HTML reports while retaining optional
  profile-specific XLSX tooling.
- Added direct `validate`, `api`, `browser`, and `all` commands alongside
  workflows.
- Added complete English and Korean README editions with platform-specific
  installation guidance and language navigation.
- Added community health, publication policy, product-neutral source checks,
  local release gates, wheel/source boundary checks, and CycloneDX SBOM
  generation.
- Added environment doctor, explicit target modes, connection preflight, and
  Docker/Compose synthetic verification.
- Removed product-specific migration profiles, compatibility wrappers, and
  local workbook tooling from the public source candidate.
