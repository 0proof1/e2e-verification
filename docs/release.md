# Release Process

Releases are prepared locally before any repository visibility or remote release
changes.

1. Run the full unit suite and enabled network/browser integration suites.
2. Run `python3 tools/release_check.py`.
3. Build wheel and source archives from a clean checkout.
4. Run `python3 tools/check_artifact.py dist/*`.
5. Confirm evidence, downloads, browser state, databases, and other generated
   binary artifacts are absent from every archive.
6. Install the wheel in a fresh environment and execute validation, plan, and
   dry-run smoke tests.
7. Generate `dist/sbom.cdx.json` and SHA-256 checksums.
8. Review Git history, provenance, redistribution rights, and security findings.
9. Complete `PUBLICATION_BLOCKERS.md` and run `tools/public_repo_gate.py` before
   changing repository visibility.
10. Only then change visibility, tag, or publish artifacts.

Versions follow semantic versioning. Schema and status-contract changes require
compatibility notes and migration guidance.
