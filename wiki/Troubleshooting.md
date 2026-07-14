# Troubleshooting

## `doctor` blocks a target

Check the selected target mode, resolved base URLs, DNS, TLS trust, proxy
settings, and whether a loopback address is being interpreted inside a
container. The tool refuses ambiguous connectivity rather than guessing.

## A workflow is `BLOCKED`

Read the structured result for the missing credential, fixture, approval, or
environment prerequisite. Correct it, keep the same workflow, and resume the
same run directory so completed mutations are not repeated.

## A write assertion passed but the step failed

Cleanup is part of the assertion contract. Inspect cleanup evidence and restore
the isolated test fixture before retrying.

## Browser checks fail while API checks pass

Confirm Chromium is installed for the active environment, selectors belong to
the current profile, the role reaches the expected start path, and target mode
resolves the browser-visible URL correctly.

The base package intentionally omits Playwright. Install the `browser` extra
and its matching Chromium bundle; see [[Installation and Environments]].

## The CLI does not recognize a command present in the checkout

Pip may consider an already installed package with the same version satisfied.
Run `tools/install_checkout.py` from the intended checkout. It verifies the
expected Git revision, force-reinstalls the project with `--no-deps`, confirms
imports resolve to that checkout, and checks the installed `e2e-verify`
command contract. Use `--require-clean` in CI and release jobs.

If the installer cannot obtain a build backend or dependency, prepare a
wheelhouse or package cache first. An offline checkout alone is not a complete
installation source.

## A report omits XLSX

Install the optional dependency group with `pip install -e '.[xlsx]'`. HTML is
the default and does not require `openpyxl`.

## Can evidence be committed or attached to an issue?

Not by default. Structured redaction is limited to known fields. Manually review
screenshots, HTML, traces, downloads, URLs, and product-specific values against
the repository's publication policy before sharing.

## Exit codes

- `0`: completed or reviewed work
- `2`: failure or invalid invocation
- `3`: safely blocked workflow

Use the structured result status, not only the process exit code, when deciding
what happens next.
