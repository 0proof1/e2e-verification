# Security Audit Record

This is a maintainer-run verification record, not an independent security
audit. Passing it reduces known risk but does not prove that redaction,
approval, cleanup, or evidence code is defect-free.

## 2026-07-14 v0.2 Synthetic Pilot

- 88 unit and contract tests were discovered; 86 passed and 2
  environment-gated browser/network tests were skipped in the host Python
  environment
- The Docker Chromium pilot completed with functional `PASS` and usability
  `PASS` at 1366x768
- Docker-local API and Chromium integration tests passed, including failure
  trace persistence for a deliberately missing selector
- The verifier image reported its supplied source revision and exact direct
  Playwright/PyYAML versions; a source-revision-only rebuild reused the pinned
  browser dependency layer and force-reinstalled the package layer
- The 0.2.0 wheel passed the publication-boundary check and a fresh-environment
  CLI smoke test for `doctor`, `assets`, and `model-plan`
- A same-version 0.2.0 checkout reinstall replaced the existing distribution,
  resolved imports to the expected checkout SHA, and passed the installed CLI
  command-contract check
- Viewport/full-page pairs, structured DOM measurements, and an HTML artifact
  index were generated for the synthetic dashboard and action probe
- This run used only the repository-owned synthetic target; it is not a public
  production-project case study or an external audit

## 2026-07-12 Local Candidate

- `pip-audit 2.10.1` against installed runtime, dev, and XLSX dependencies:
  no known vulnerabilities found
- Release policy scan: passed
- Wheel and sdist publication-boundary scan: passed
- Public text scan for private keys, GitHub tokens, AWS keys, and absolute user
  home paths: 0 candidates
- Loopback API and Chromium synthetic integration tests: passed locally; they
  remain environment-gated in the default unit suite and run fully in CI
- Environment and publication unit suite: 71 tests passed, including explicit
  host/container target-mode contracts
- Docker same-network API/browser run: 0 failures, 0 server errors
- Host to Docker published-port API/browser run: 0 failures, 0 server errors
- Container to host-gateway API/browser run: 0 failures, 0 server errors
- Verifier image: non-root UID 10001 and writable named evidence volume

The local package itself is not yet published on PyPI and was therefore skipped
as a vulnerability-database subject. Repeat both audits for every release
candidate and after dependency changes.
