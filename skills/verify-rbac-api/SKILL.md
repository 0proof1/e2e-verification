---
name: verify-rbac-api
description: Verify role-based API authentication, authorization, and response contracts with redacted evidence. Use for RBAC matrices, allowed and forbidden endpoint checks, cross-scope access probes, read API regressions, or API evidence collection against local and isolated test targets.
---

# Verify RBAC API contracts

1. Validate the profile and confirm the target is local or explicitly isolated for testing.
2. Inspect the materialized workflow plan before execution.
3. Run only configured methods, paths, roles, and expected statuses through the `api-probes` harness.
4. Treat missing credentials or fixtures as `BLOCKED`, policy ambiguity as `REVIEW`, mismatched contracts as `FAIL`, and observed matches as `PASS`.
5. Record request IDs and elapsed time when available. Never persist tokens, cookies, passwords, response PII, or unredacted query parameters.
6. Separate authentication failure from authorization failure and product error from harness error.
7. Recommend browser or triage follow-up only when the evidence justifies it.

Do not broaden a read matrix into export or write endpoints without a different risk-classified workflow step.

