from __future__ import annotations

import hashlib
from importlib import resources
from typing import Any, Iterable


DEFAULT_AXE_TAGS = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa")
DEFAULT_MAX_TABS = 100
_FUNCTIONAL_STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "SKIP"})
_USABILITY_STATUSES = frozenset({"PASS", "REVIEW", "BLOCKED", "SKIP"})


def load_axe_source() -> str:
    """Return the pinned axe-core source without making a network request."""
    asset = resources.files("e2e_verification").joinpath("assets", "axe.min.js")
    source = asset.read_text(encoding="utf-8")
    if "axe" not in source or "run" not in source:
        raise RuntimeError("bundled axe-core asset is invalid")
    return source


def axe_asset_sha256() -> str:
    return hashlib.sha256(load_axe_source().encode("utf-8")).hexdigest()


def run_axe_audit(page: Any, tags: Iterable[str] | None = None) -> dict[str, Any]:
    """Run local axe-core and return small, deterministic, JSON-safe evidence.

    A failure to load or execute the audit is evidence collection BLOCKED. It is
    deliberately not treated as a clean accessibility result.
    """
    selected_tags = _validate_tags(DEFAULT_AXE_TAGS if tags is None else tags)
    try:
        source = load_axe_source()
        page.add_script_tag(content=source)
        raw = page.evaluate(
            """async ({ tags }) => {
                if (!globalThis.axe || typeof globalThis.axe.run !== 'function') {
                  throw new Error('bundled axe-core did not initialize');
                }
                return await globalThis.axe.run(document, {
                  runOnly: { type: 'tag', values: tags },
                  resultTypes: ['violations', 'incomplete', 'passes', 'inapplicable']
                });
            }""",
            {"tags": selected_tags},
        )
    except Exception as error:  # Playwright exposes several runtime-specific errors.
        return _blocked_result("axe-execution-failed", error, tags=selected_tags)

    groups = {
        name: [_normalize_axe_rule(rule) for rule in raw.get(name, [])]
        for name in ("violations", "incomplete", "passes", "inapplicable")
    }
    return _with_statuses({
        "engine": {"name": "axe-core", "version": raw.get("testEngine", {}).get("version", "")},
        "asset_sha256": axe_asset_sha256(),
        "tags": selected_tags,
        **groups,
        "summary": {name: len(rows) for name, rows in groups.items()},
    }, "PASS", "REVIEW" if groups["violations"] or groups["incomplete"] else "PASS")


def audit_keyboard_navigation(page: Any, max_tabs: int = DEFAULT_MAX_TABS) -> dict[str, Any]:
    """Traverse keyboard focus with Tab only; never activate a control."""
    if isinstance(max_tabs, bool) or not isinstance(max_tabs, int) or max_tabs < 1:
        raise ValueError("max_tabs must be a positive integer")
    try:
        page.evaluate("document.activeElement && document.activeElement.blur(); document.body.focus();")
        steps: list[dict[str, Any]] = []
        first_key = ""
        cycle_complete = False
        for index in range(max_tabs):
            page.keyboard.press("Tab")
            step = page.evaluate(_FOCUS_SNAPSHOT_SCRIPT)
            step["index"] = index + 1
            steps.append(step)
            key = str(step.get("key", ""))
            if index == 0:
                first_key = key
            elif key and key == first_key:
                cycle_complete = True
                steps.pop()  # The repeated first target terminates the cycle.
                break
            if step.get("tag") in {"BODY", "HTML"}:
                break
    except Exception as error:
        return _blocked_result("keyboard-audit-failed", error, max_tabs=max_tabs)

    issues: list[dict[str, Any]] = []
    for step in steps:
        if int(step.get("tab_index", 0)) > 0:
            issues.append(_issue("positive-tabindex", step))
        if not step.get("visible", False):
            issues.append(_issue("focus-not-visible-in-viewport", step))
        if not step.get("focus_visible", False):
            issues.append(_issue("focus-visible-selector-missing", step))
        if not step.get("indicator_detected", False):
            issues.append(_issue("focus-indicator-not-detected", step))
    if steps and steps[-1].get("tag") in {"BODY", "HTML"}:
        issues.append(_issue("focus-escaped-to-document", steps[-1]))
    if len(steps) == max_tabs and not cycle_complete:
        issues.append({"id": "tab-limit-reached", "severity": "REVIEW", "step": max_tabs})

    return _with_statuses({
        "steps": steps,
        "cycle_complete": cycle_complete,
        "max_tabs": max_tabs,
        "issues": issues,
        "summary": {"tab_stops": len(steps), "issues": len(issues)},
    }, "PASS", "REVIEW" if issues else "PASS")


def audit_focus_visibility(page: Any, max_tabs: int = DEFAULT_MAX_TABS) -> dict[str, Any]:
    """Expose focus-specific evidence from the keyboard traversal."""
    keyboard = audit_keyboard_navigation(page, max_tabs=max_tabs)
    if keyboard["functional_status"] == "BLOCKED":
        return keyboard
    issues = [item for item in keyboard["issues"] if "focus" in item["id"]]
    return _with_statuses(
        {"steps": keyboard["steps"], "issues": issues},
        keyboard["functional_status"],
        "REVIEW" if issues else "PASS",
    )


def run_accessibility_audit(
    page: Any,
    *,
    tags: Iterable[str] | None = None,
    max_tabs: int = DEFAULT_MAX_TABS,
) -> dict[str, Any]:
    """Collect axe, keyboard, and focus evidence under the v2 dual statuses."""
    axe = run_axe_audit(page, tags=tags)
    keyboard = audit_keyboard_navigation(page, max_tabs=max_tabs)
    blocked = axe["functional_status"] == "BLOCKED" or keyboard["functional_status"] == "BLOCKED"
    if blocked:
        functional_status = usability_status = "BLOCKED"
    else:
        functional_status = "PASS"
        usability_status = "REVIEW" if (
            axe["usability_status"] == "REVIEW" or keyboard["usability_status"] == "REVIEW"
        ) else "PASS"

    keyboard_issues = keyboard.get("issues", [])
    focus_issues = [item for item in keyboard_issues if "focus" in item["id"]]
    other_keyboard_issues = [item for item in keyboard_issues if "focus" not in item["id"]]
    return _with_statuses({
        "axe": axe,
        "keyboard": {
            "order": keyboard.get("steps", []),
            "issues": other_keyboard_issues,
            "cycle_complete": keyboard.get("cycle_complete", False),
        },
        "focus": {"issues": focus_issues},
        "summary": {
            "axe_violations": len(axe.get("violations", [])),
            "axe_incomplete": len(axe.get("incomplete", [])),
            "tab_stops": len(keyboard.get("steps", [])),
            "keyboard_issues": len(other_keyboard_issues),
            "focus_issues": len(focus_issues),
        },
    }, functional_status, usability_status)


def _with_statuses(payload: dict[str, Any], functional: str, usability: str) -> dict[str, Any]:
    if functional not in _FUNCTIONAL_STATUSES or usability not in _USABILITY_STATUSES:
        raise ValueError("invalid accessibility status")
    return {**payload, "functional_status": functional, "usability_status": usability}


def _blocked_result(identifier: str, error: Exception, **metadata: Any) -> dict[str, Any]:
    return _with_statuses({
        **metadata,
        "issues": [{
            "id": identifier,
            "severity": "BLOCKED",
            "error_type": type(error).__name__,
            "message": str(error)[:500],
        }],
        "summary": {"issues": 1},
    }, "BLOCKED", "BLOCKED")


def _validate_tags(tags: Iterable[str]) -> list[str]:
    if isinstance(tags, (str, bytes)):
        raise ValueError("axe tags must be a non-empty collection of non-empty strings")
    result = list(tags)
    if not result or any(not isinstance(tag, str) or not tag.strip() for tag in result):
        raise ValueError("axe tags must be a non-empty collection of non-empty strings")
    return result


def _normalize_axe_rule(rule: dict[str, Any]) -> dict[str, Any]:
    # Do not retain node HTML: it can contain customer or financial data.
    return {
        "id": rule.get("id", ""),
        "impact": rule.get("impact"),
        "tags": list(rule.get("tags", [])),
        "description": rule.get("description", ""),
        "help": rule.get("help", ""),
        "help_url": rule.get("helpUrl", ""),
        "nodes": [
            {
                "impact": node.get("impact"),
                "target": list(node.get("target", [])),
                "failure_summary": node.get("failureSummary", ""),
            }
            for node in rule.get("nodes", [])
        ],
    }


def _issue(identifier: str, step: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": identifier,
        "severity": "REVIEW",
        "step": step.get("index"),
        "target": step.get("selector", ""),
    }


_FOCUS_SNAPSHOT_SCRIPT = """() => {
  const element = document.activeElement;
  if (!element) return { key: '', tag: '', visible: false, focus_visible: false, indicator_detected: false };
  const cssPath = node => {
    if (node.id) return `#${CSS.escape(node.id)}`;
    const parts = [];
    while (node && node.nodeType === Node.ELEMENT_NODE && node !== document.documentElement) {
      let part = node.tagName.toLowerCase();
      const siblings = node.parentElement ? [...node.parentElement.children].filter(x => x.tagName === node.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  const visual = style => ({
    outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth, outlineColor: style.outlineColor,
    boxShadow: style.boxShadow, borderColor: style.borderColor, borderWidth: style.borderWidth,
    backgroundColor: style.backgroundColor
  });
  const differs = (a, b) => Object.keys(a).some(key => a[key] !== b[key]);
  const rect = element.getBoundingClientRect();
  const focused = visual(getComputedStyle(element));
  const focusVisible = element.matches(':focus-visible');
  element.blur();
  const unfocused = visual(getComputedStyle(element));
  element.focus({ preventScroll: true });
  const selector = cssPath(element);
  const style = getComputedStyle(element);
  const visible = rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 &&
    rect.top < innerHeight && rect.left < innerWidth && style.visibility !== 'hidden' && style.display !== 'none';
  return {
    key: selector,
    selector,
    tag: element.tagName,
    role: element.getAttribute('role') || '',
    name: element.getAttribute('aria-label') || element.innerText || element.getAttribute('name') || '',
    tab_index: element.tabIndex,
    focus_visible: focusVisible,
    indicator_detected: focusVisible && differs(focused, unfocused),
    visible,
    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    focused_style: focused,
    unfocused_style: unfocused
  };
}"""
