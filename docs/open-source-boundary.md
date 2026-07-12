# Open-source boundary

The public distribution is a reusable verification platform, not an archive of one product's internal audit.

## Included

- Agent role definitions that contain no organization-specific identity or policy
- Reusable verification skills
- Deterministic API and browser harnesses
- Workflow schemas and safe example workflows
- Evidence schemas, redaction, reporting, and validation tools
- Synthetic example profiles and fixtures

## Profile-only

Product selectors, endpoint maps, role names, fixture lifecycle rules, and optional report mappings belong under `profiles/<name>/`. A profile must be removable without changing the platform core.

## Excluded from a public release

- Credentials, tokens, cookies, private keys, and environment dumps
- Personal information in JSON, screenshots, traces, downloads, or workbooks
- Customer names, production URLs, institution identifiers, and internal host paths
- Proprietary source extracts or documentation without confirmed redistribution rights
- Historical evidence that cannot be regenerated from a synthetic target
- Mutating probes that lack explicit opt-in and verified cleanup

## Reference profile policy

Committed profiles must use synthetic identities, targets, selectors, and fixtures. Organization-specific adapters belong in the operator's private workspace and are loaded only through an explicit CLI argument.
