# Synthetic Example

`project.example.json` contains only synthetic identities and local target URLs.
It is suitable for validation, planning, and dry-run demonstrations without a
real application:

```bash
e2e-verify validate --config examples/project.example.json
e2e-verify plan --workflow workflows/read-only.json
e2e-verify run --workflow workflows/read-only.json --dry-run
```

Live API and browser execution should target an isolated synthetic application.
Never substitute production credentials or retain its screenshots and downloads
in the repository.
