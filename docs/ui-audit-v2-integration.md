# UI Audit v2 Integration Note

This note records how to integrate the remote `feat/ui-ux-evidence-v2` feature
line without weakening the v0.2 contracts already on `main`. It is an
integration plan, not a claim that these features are currently available on
`main`.

## Inspected feature line

As inspected on 2026-07-14, the remote branch is three commits ahead of its
`814373b` base and ends at `475a3e2`:

- `5f61694 feat: add UI audit evidence v2`
- `6a5ccc7 fix: classify UI audit accessibility evidence`
- `475a3e2 feat: support deterministic data-state fixtures`

The feature line adds a read-only `ui-audit` workflow harness, loading/data/
empty/error state contracts, paired viewport/full-page artifacts, bundled
axe-core checks, keyboard/focus evidence, richer artifact metadata, and
filterable HTML reporting. Product selectors and response fixtures remain
outside the platform core.

At inspection time the remote branch existed, but neither the GitHub API nor
`gh pr view` returned an associated pull request. Use the branch ref and head
SHA until a PR number is confirmed.

## Contract conflicts to resolve

Do not merge the branch mechanically. It was built from the earlier 0.1 source
line and overlaps `evidence.py`, `workflow.py`, `harnesses.py`, `reporting.py`,
schemas, tests, packaging, and README content changed by v0.2.

| Area | Current `main` | Feature line | Integration rule |
|---|---|---|---|
| Evidence contract | 1.1 | 2.0 | Keep 1.1 for v0.2; evaluate 2.0 separately with explicit compatibility tests |
| Public status fields | `functionalStatus`, `usabilityStatus` | snake_case variants | Preserve the current camelCase serialized contract |
| Functional values | `PASS`, `FAIL`, `BLOCKED` | also `SKIP` | Keep the frozen v0.2 values; express non-execution outside the verdict |
| Usability values | `PASS`, `REVIEW`, `NOT_RUN` | `PASS`, `REVIEW`, `BLOCKED`, `SKIP` | Map unexecuted/blocked audit work to `NOT_RUN` plus reason metadata |
| Finding severity | P0-P3 with evidence required | free-form values such as high/medium | Convert every finding to P0-P3 and require artifact/measurement links |
| Playwright dependency | optional `browser` extra | base dependency | Retain the optional extra and API-only minimal install |
| Reporting | paired thumbnails and original links | filters, findings, path confinement | Combine behavior while retaining redaction and relative-path safety |

Artifact fields such as case, variant, role, state, and viewport can be added as
optional 1.1 metadata without breaking existing consumers. Any required-field
change belongs in a separately versioned contract.

## Supply-chain and CLI gates

Before bundling axe-core, record the exact upstream version, source URL,
license, and SHA-256 digest; include the asset in artifact and SBOM checks. Run
the accessibility module without network access and verify that report output
cannot escape the run directory.

The feature line registers `ui-audit` as a workflow harness; it does not add a
top-level `e2e-verify ui-audit` parser command. Decide the intended interface
explicitly. If a direct command is added, extend `tools/install_checkout.py`
and wheel smoke tests so a same-version stale CLI cannot omit it. Otherwise,
document only the workflow form and never present `ui-audit` as a CLI command.

## Merge checklist

1. Rebase the feature branch onto the pushed v0.2 `main`.
2. Port UI audit config, accessibility, and harness modules before modifying
   shared evidence/reporting code.
3. Adapt outputs to evidence 1.1, P0-P3 findings, required evidence links, and
   the current usability semantics.
4. Preserve optional Playwright installation, fixed-SHA checkout reinstall,
   Docker provenance, and publication boundaries.
5. Add synthetic, offline axe, path-traversal, role/state, retry/trace, wheel,
   and installed-CLI tests.
6. Run the bounded synthetic pilot and publish only redacted evidence indexes.
7. Update English, Korean, Wiki, and changelog contract descriptions together.

Only after these gates pass should `main` advertise deterministic multi-state
UI audit or bundled accessibility execution as an available feature.
