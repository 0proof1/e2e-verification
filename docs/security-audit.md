# Security Audit Record

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
