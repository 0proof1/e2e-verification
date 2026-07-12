---
name: verify-error-ux
description: Measure API and browser behavior on configured negative paths and verify user recovery. Use for validation errors, unauthenticated and forbidden behavior, not-found handling, timeout presentation, retry and recovery checks, or quantitative error UX review.
---

# Verify error UX

1. Use only synthetic invalid input and configured negative cases.
2. Confirm the expected API status and safe error payload before assessing the UI.
3. Assess message clarity, field association, actionability, state preservation, and recovery according to the profile rubric.
4. Separate a confirmed contract failure from subjective UX review.
5. Verify that the user can retry, correct input, navigate away, or reauthenticate as configured.
6. Fail the step on unexpected server errors even when an error message is displayed.
7. Redact entered values, payload samples, URLs, screenshots, and logs before persistence.

Do not trigger account lockout, rate-limit exhaustion, or destructive failure modes unless separately isolated and approved.

