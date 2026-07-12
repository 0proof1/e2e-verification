from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_html_report(run_path: Path, output_path: Path | None = None) -> Path:
    state = json.loads(run_path.read_text(encoding="utf-8"))
    output_path = output_path or run_path.with_name("report.html")
    rows = "\n".join(_step_row(step_id, value) for step_id, value in state.get("steps", {}).items())
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(state.get('workflow', 'Verification report')))}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ max-width: 960px; margin: 0 auto; padding: 3rem 1.25rem; line-height: 1.5; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 1rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 2rem; }}
    th, td {{ padding: .75rem; border-bottom: 1px solid #8886; text-align: left; vertical-align: top; }}
    code {{ font-size: .9em; }}
    .status {{ font-weight: 700; }}
  </style>
</head>
<body>
  <header><div><p>E2E verification</p><h1>{html.escape(str(state.get('workflow', 'Run')))}</h1></div><p class="status">{html.escape(str(state.get('status', 'UNKNOWN')))}</p></header>
  <p>Run <code>{html.escape(str(state.get('run_id', '')))}</code><br>Profile <code>{html.escape(str(state.get('profile', '')))}</code><br>Started <code>{html.escape(str(state.get('started_at', '')))}</code><br>Finished <code>{html.escape(str(state.get('finished_at', '')))}</code></p>
  <table><thead><tr><th>Step</th><th>Harness</th><th>Status</th><th>Summary</th></tr></thead><tbody>{rows}</tbody></table>
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


def _step_row(step_id: str, value: dict[str, Any]) -> str:
    summary = ", ".join(f"{key}: {item}" for key, item in value.get("summary", {}).items()) or "—"
    return "<tr>" + "".join(
        f"<td>{html.escape(str(item))}</td>"
        for item in (step_id, value.get("harness", ""), value.get("status", ""), summary)
    ) + "</tr>"
