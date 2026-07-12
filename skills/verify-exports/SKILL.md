---
name: verify-exports
description: Verify configured browser downloads and exported file structure while minimizing retained data. Use for CSV or XLSX export checks, download button binding, filename and worksheet validation, PII-header risk review, or server-versus-client export analysis.
---

# Verify exports

1. Treat downloads as a distinct `download` risk and require the workflow's named approval when configured.
2. Save files only inside the run artifact directory.
3. Verify download completion, filename, media type, nonzero size, archive integrity, worksheet names, headers, and row-count contracts as configured.
4. Inspect structure rather than copying cell values into reports.
5. Record the presence of PII-bearing headers as `REVIEW`; never persist their row values in summary evidence.
6. Distinguish API-backed downloads from client-generated files using observable network evidence.
7. Remove ephemeral raw downloads when the profile retention policy requires it.

Do not publish or attach a downloaded artifact until its provenance, license, and redaction status are verified.

