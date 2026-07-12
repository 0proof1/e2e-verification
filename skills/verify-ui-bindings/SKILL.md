---
name: verify-ui-bindings
description: Verify that visible UI controls produce their configured route, DOM, or network effects. Use for button and form binding audits, inert-control detection, tab and filter behavior, frontend-to-API contract checks, or UI action coverage analysis.
---

# Verify UI bindings

1. Inventory controls without clicking them and assign a risk class to each candidate.
2. Probe only controls explicitly declared safe by the profile and workflow.
3. Observe route changes, DOM changes, downloads, and network responses from the action boundary.
4. Mark client-state-only behavior as `PASS` only when the profile defines that observable contract; otherwise use `REVIEW`.
5. Mark an expected binding mismatch as `FAIL` and include the control selector, expected effect, and observed effect.
6. Store redacted network metadata and minimal screenshots. Never store request bodies containing credentials or PII.
7. Send export and write candidates to their dedicated approval-aware skills.

Never auto-click controls solely because they are visible or enabled.

