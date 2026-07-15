# Release Process

Releases are prepared locally before any repository visibility or remote release
changes.

1. Run the full unit suite and enabled network/browser integration suites.
2. Run `python3 tools/release_check.py`.
3. Move completed changes out of `Unreleased`, date the version entry, and
   document schema, status, resume, or CLI compatibility changes.
4. Build wheel and source archives from a clean checkout.
5. Run `python3 tools/check_artifact.py dist/*`.
6. Confirm evidence, agent task packets, downloads, browser state, databases,
   and other generated binary artifacts are absent from every archive.
7. Install the wheel in a fresh environment and execute validation, plan, and
   dry-run smoke tests.
8. Generate `dist/sbom.cdx.json`, record SHA-256 checksums for wheel and sdist,
   verify those checksums, and force-reinstall the exact wheel path for smoke
   tests even when the version is already present.
9. Review Git history, provenance, redistribution rights, and security findings.
10. Complete `PUBLICATION_BLOCKERS.md` and run `tools/public_repo_gate.py` before
   changing repository visibility.
11. Only then change visibility, tag, or publish artifacts.

Versions follow semantic versioning. Schema and status-contract changes require
explicit compatibility notes.
