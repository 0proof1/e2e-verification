---
name: verify-safe-writes
description: Run explicitly approved test-data mutations and prove their cleanup. Use for create-update-delete fixtures, import commits, state transitions, destructive confirmation checks, or any E2E action classified as write, destructive, notification, payment, or external-send.
---

# Verify safe writes

1. Require a named workflow approval token before starting the step.
2. Confirm the target is local or an explicitly isolated test environment.
3. Use a unique synthetic fixture prefix and record stable created identifiers.
4. Observe pre-state, perform only the configured mutation, and verify persisted post-state through an independent API or reload.
5. Run cleanup in a finalization path even when the assertion or browser action fails.
6. Verify cleanup independently. A mutating step cannot return `PASS` unless cleanup returns `PASS`.
7. Return `BLOCKED` when prerequisites or approval are missing, `FAIL` when mutation or cleanup violates the contract, and `REVIEW` when residual state cannot be conclusively classified.
8. Keep notification, payment, push, email, SMS, and external-send operations behind their own explicit opt-in.

Never reuse real customer records as fixtures and never silently weaken cleanup requirements.

