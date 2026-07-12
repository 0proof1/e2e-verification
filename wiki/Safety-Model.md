# Safety Model

Read-only execution is the default. Other risk classes require an explicit,
named workflow approval.

| Risk class | Examples | Default treatment |
|---|---|---|
| `read-only` | Login, GET probes, route checks | Allowed by the selected workflow |
| `download` | CSV/XLSX export | Approval-gated |
| `write` | Create, update, import commit | Approval-gated; cleanup required |
| `destructive` | Delete, disable, irreversible transition | Approval-gated; cleanup required |
| `external-send` | Email, SMS, payment, webhook | Separate explicit approval |

## Mutation invariant

A mutating step cannot report `PASS` unless cleanup is independently verified.
Cleanup failure is a failed verification, even when the main assertion passed.

## Credentials and targets

- Use isolated test targets, never an assumed production endpoint.
- Supply credentials through environment variables or a secret manager.
- Review `e2e-verify plan` before execution.
- Use explicit host/container target modes.
- Grant only the named approvals required by the chosen workflow.

## Redaction boundary

Tokens, authentication headers, cookies, known sensitive fields, email
addresses, phone numbers, and sensitive URL parameters are redacted before
structured evidence is persisted.

This is defense in depth, not a publication guarantee. Screenshots, raw
downloads, arbitrary HTML, and product-specific binary files remain unredacted
until a human or specialized sanitizer reviews them.

Report vulnerabilities through GitHub's private security-advisory channel with
synthetic reproduction material.
