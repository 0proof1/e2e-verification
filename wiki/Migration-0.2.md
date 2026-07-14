# Migration 0.2

Version 0.2 changes evidence semantics, optional dependencies, and model-aware
planning. Existing source profiles remain the product-specific boundary.

## Evidence contract 1.1

- `functionalStatus`: `PASS`, `FAIL`, or `BLOCKED`
- `usabilityStatus`: `PASS`, `REVIEW`, or `NOT_RUN`
- finding severity: `P0` through `P3`
- every finding requires at least one evidence link

Version 1.0 evidence remains readable, but 0.2 rejects resume into a 1.0 run
directory. Preserve the old directory for audit and start a new 1.1 run instead
of mixing contracts.

## Installation

Playwright moved from the base package to the `browser` extra. API-only users
need no change beyond reinstalling 0.2. Browser users should install
`.[browser]` and the matching Chromium bundle.

For a source checkout, use `tools/install_checkout.py` rather than relying on
pip to notice changes under an unchanged package version. See
[[Installation and Environments]].

## Optional model and visual planning

Existing workflows do not require a model plan. To use staged AI review, add a
provider-neutral model-plan file and bind concrete provider models at runtime.
Generating an `agent-task` packet does not call a model or authorize mutation.

Visual verification is also opt-in through profile configuration. The v0.2
pilot supports a 1366x768 viewport, scroll-top and first-viewport title checks,
overflow/clipping measurements, paired viewport/full-page screenshots, one
retry, and a failure trace.

Generated screenshots, traces, reports, and agent task packets remain evidence,
not source assets. Do not commit them without an explicit publication review.
