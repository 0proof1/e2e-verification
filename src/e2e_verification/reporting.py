from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any


def write_html_report(run_path: Path, output_path: Path | None = None) -> Path:
    state = json.loads(run_path.read_text(encoding="utf-8"))
    output_path = output_path or run_path.with_name("report.html")
    rows = "\n".join(_step_row(step_id, value, output_path.parent) for step_id, value in state.get("steps", {}).items())
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(state.get('workflow', 'Verification report')))}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ max-width: 1200px; margin: 0 auto; padding: 3rem 1.25rem; line-height: 1.5; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 1rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 2rem; }}
    th, td {{ padding: .75rem; border-bottom: 1px solid #8886; text-align: left; vertical-align: top; }}
    code {{ font-size: .9em; }}
    .status {{ font-weight: 700; }}
    .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: .75rem; min-width: 360px; }}
    .artifact {{ display: block; padding: .5rem; border: 1px solid #8886; border-radius: .5rem; text-decoration: none; }}
    .artifact img {{ display: block; width: 100%; height: 110px; object-fit: cover; object-position: top; margin-bottom: .35rem; background: #8882; }}
    .artifact small {{ display: block; overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header><div><p>E2E verification</p><h1>{html.escape(str(state.get('workflow', 'Run')))}</h1></div><p class="status">{html.escape(str(state.get('status', 'UNKNOWN')))}</p></header>
  <p>Run <code>{html.escape(str(state.get('run_id', '')))}</code><br>Profile <code>{html.escape(str(state.get('profile', '')))}</code><br>Started <code>{html.escape(str(state.get('started_at', '')))}</code><br>Finished <code>{html.escape(str(state.get('finished_at', '')))}</code></p>
  <table><thead><tr><th>Step</th><th>Harness</th><th>Functional</th><th>Usability</th><th>Summary</th><th>Evidence (thumbnail → original)</th></tr></thead><tbody>{rows}</tbody></table>
</body>
</html>
"""
    output_path.write_text(document, encoding="utf-8")
    return output_path


def write_xlsx_report(run_path: Path, output_path: Path | None = None) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError as error:
        raise RuntimeError("XLSX reports require: pip install 'e2e-verification[xlsx]'") from error
    state = json.loads(run_path.read_text(encoding="utf-8"))
    output_path = output_path or run_path.with_name("report.xlsx")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Verification"
    sheet.append(["Workflow", state.get("workflow", "")])
    sheet.append(["Run ID", state.get("run_id", "")])
    sheet.append(["Profile", state.get("profile", "")])
    sheet.append(["Status", state.get("status", "")])
    sheet.append(["Started", state.get("started_at", "")])
    sheet.append(["Finished", state.get("finished_at", "")])
    sheet.append([])
    headers = ["Step", "Harness", "Risk", "Status", "Passed", "Failed", "Blocked", "Review"]
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[sheet.max_row]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill
    for step_id, value in state.get("steps", {}).items():
        summary = value.get("summary", {})
        sheet.append([
            step_id,
            value.get("harness", ""),
            value.get("risk", ""),
            value.get("status", ""),
            summary.get("passed", 0),
            summary.get("failed", 0),
            summary.get("blocked", 0),
            summary.get("review", 0),
        ])
    header_row = 8
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:H{sheet.max_row}"
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(max(len(str(cell.value or "")) for cell in column) + 2, 48)
    workbook.save(output_path)
    return output_path


def _step_row(step_id: str, value: dict[str, Any], report_dir: Path) -> str:
    summary = ", ".join(f"{key}: {item}" for key, item in value.get("summary", {}).items()) or "—"
    gallery = _artifact_gallery(value.get("artifacts", []), report_dir)
    return "<tr>" + "".join(
        f"<td>{html.escape(str(item))}</td>"
        for item in (
            step_id,
            value.get("harness", ""),
            value.get("functionalStatus", value.get("status", "")),
            value.get("usabilityStatus", "NOT_RUN"),
            summary,
        )
    ) + f"<td>{gallery}</td></tr>"


def _artifact_gallery(artifacts: list[dict[str, Any]], report_dir: Path) -> str:
    cards: list[str] = []
    for artifact in artifacts:
        raw_path = str(artifact.get("path", ""))
        if not raw_path:
            continue
        path = Path(raw_path)
        href = os.path.relpath(path, report_dir) if path.is_absolute() else raw_path
        escaped_href = html.escape(href, quote=True)
        description = html.escape(str(artifact.get("description") or artifact.get("kind") or "artifact"))
        if artifact.get("kind") == "screenshot":
            preview = f'<img src="{escaped_href}" alt="{description}" loading="lazy">'
        else:
            preview = ""
        cards.append(
            f'<a class="artifact" href="{escaped_href}">{preview}<small>{description}</small></a>'
        )
    return f'<div class="gallery">{"".join(cards)}</div>' if cards else "—"
