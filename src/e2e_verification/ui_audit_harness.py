from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .browser_harness import browser_login
from .config import load_config, safe_name
from .environment import endpoint_checks, resolve_endpoint
from .ui_audit_config import load_state_fixture, load_ui_audit_config


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SESSION_PROBE_TIMEOUT_MS = 5_000


def _operation_timeout_ms(project_config: dict[str, Any], options: Any) -> int:
    """Keep a workflow budget from becoming a single Playwright wait budget."""
    workflow_seconds = int(getattr(options, "timeout_seconds", 30))
    request_seconds = int(project_config.get("defaults", {}).get("request_timeout_seconds", 30))
    return max(1, min(workflow_seconds, request_seconds)) * 1000


def _browser_auth_request_path(project_config: dict[str, Any]) -> str:
    value = str(project_config.get("browser_login", {}).get("request_path", "")).strip()
    return value if value.startswith("/") else ""


def run_ui_audit(
    project_config: dict[str, Any],
    audit_config: dict[str, Any],
    options: Any,
    out_dir: Path,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Playwright is required for ui-audit") from error

    resolution = resolve_endpoint(
        "web",
        getattr(options, "web_base", None),
        project_config,
        getattr(options, "target_mode", None) or os.environ.get("E2E_TARGET_MODE", "auto"),
        getattr(options, "host_alias", None) or os.environ.get("E2E_HOST_ALIAS", "host.docker.internal"),
    )
    web_base = resolution.url.rstrip("/")
    preflight = endpoint_checks(resolution, connect=bool(getattr(options, "preflight_connect", False)))
    if any(item["status"] == "BLOCKED" for item in preflight):
        return {
            "webBase": web_base,
            "endpoint": resolution.__dict__,
            "preflight": preflight,
            "functional_status": "BLOCKED",
            "usability_status": "BLOCKED",
            "cases": [],
            "summary": {"total": 0, "passed": 0, "failed": 0, "blocked": 1, "review": 0},
        }

    roles = {item["name"]: item for item in project_config.get("roles", [])}
    requested_roles = {str(item["role"]) for item in audit_config.get("cases", [])}
    missing_roles = requested_roles - roles.keys()
    if missing_roles:
        raise ValueError(f"ui-audit references project roles that do not exist: {sorted(missing_roles)}")

    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "webBase": web_base,
        "endpoint": resolution.__dict__,
        "preflight": preflight,
        "logins": [],
        "cases": [],
    }
    defaults = project_config.get("defaults", {})
    timeout_ms = _operation_timeout_ms(project_config, options)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not bool(getattr(options, "headed", False)))
        storage_states: dict[str, dict[str, Any]] = {}
        for role_name in sorted(requested_roles):
            role = roles[role_name]
            login: dict[str, Any] = {"role": role_name, "result": "FAIL"}
            for attempt in range(1, 3):
                context = browser.new_context(viewport={"width": 1366, "height": 768})
                page = context.new_page()
                page.set_default_timeout(timeout_ms)
                page.set_default_navigation_timeout(timeout_ms)
                login = {"role": role_name, **browser_login(page, project_config, role, web_base), "attempts": attempt}
                if login["result"] == "PASS":
                    authenticated_selector = str(audit_config.get("roles", {}).get(role_name, {}).get("authenticated_selector", ""))
                    if authenticated_selector:
                        try:
                            page.locator(authenticated_selector).first.wait_for(state="visible")
                        except Exception as error:
                            login.update({"result": "FAIL", "reason": f"authenticated UI did not appear: {type(error).__name__}"})
                if login["result"] == "PASS":
                    storage_states[role_name] = context.storage_state()
                    context.close()
                    break
                context.close()
            result["logins"].append(login)

        for group in audit_config.get("cases", []):
            role_name = str(group["role"])
            if role_name not in storage_states:
                for state in group.get("states", []):
                    for viewport in audit_config.get("viewports", []):
                        result["cases"].append(_blocked_case(group, state, viewport, "role login did not pass"))
                continue
            for state in group.get("states", []):
                fixture = load_state_fixture(audit_config, str(group["page"]), str(state))
                for viewport in audit_config.get("viewports", []):
                    context = browser.new_context(
                        viewport={"width": int(viewport["width"]), "height": int(viewport["height"])},
                        storage_state=storage_states[role_name],
                        accept_downloads=False,
                    )
                    page = context.new_page()
                    page.set_default_timeout(timeout_ms)
                    page.set_default_navigation_timeout(timeout_ms)
                    case = _run_case(
                        page=page,
                        context=context,
                        group=group,
                        state=str(state),
                        viewport=viewport,
                        fixture=fixture,
                        audit_config=audit_config,
                        project_config=project_config,
                        web_base=web_base,
                        screenshot_dir=screenshot_dir,
                        settle_ms=int(defaults.get("settle_ms", 500)),
                    )
                    result["cases"].append(case)
                    if case.get("measurements", {}).get("login_recovered"):
                        # Reuse the refreshed cookie in later isolated contexts;
                        # otherwise every remaining matrix case starts stale and
                        # repeats the recovery probe and login.
                        storage_states[role_name] = context.storage_state()
                    context.close()
        browser.close()

    result["functional_status"] = _aggregate_axis(result["cases"], "functional_status", review=False)
    result["usability_status"] = _aggregate_axis(result["cases"], "usability_status", review=True)
    result["summary"] = _summarize_cases(result["cases"])
    return result


def _run_case(
    *,
    page: Any,
    context: Any,
    group: dict[str, Any],
    state: str,
    viewport: dict[str, Any],
    fixture: dict[str, Any] | None,
    audit_config: dict[str, Any],
    project_config: dict[str, Any],
    web_base: str,
    screenshot_dir: Path,
    settle_ms: int,
) -> dict[str, Any]:
    case_id = _case_id(group, state, viewport)
    unsafe_requests: list[dict[str, str]] = []
    blocked_external: list[str] = []
    origin = urlparse(web_base)
    auth_request_path = _browser_auth_request_path(project_config)

    def safety_handler(route: Any, request: Any) -> None:
        method = request.method.upper()
        parsed = urlparse(request.url)
        same_origin = parsed.scheme == origin.scheme and parsed.netloc == origin.netloc
        allowed_external_hosts = set(audit_config.get("safety", {}).get("allowed_external_hosts", []))
        is_browser_auth = bool(auth_request_path) and same_origin and method == "POST" and parsed.path == auth_request_path
        if is_browser_auth:
            route.continue_()
        elif method not in SAFE_METHODS:
            unsafe_requests.append({"method": method, "url": _safe_url(request.url)})
            route.abort("blockedbyclient")
        elif audit_config.get("safety", {}).get("block_external_hosts", True) and not same_origin and parsed.hostname not in allowed_external_hosts:
            blocked_external.append(_safe_url(request.url))
            route.abort("blockedbyclient")
        else:
            route.continue_()

    context.route("**/*", safety_handler)
    if fixture:
        delay_patterns = [
            str(intercept["url"]).replace("**", "")
            for intercept in fixture.get("intercepts", [])
            if intercept.get("action") == "delay"
        ]
        if delay_patterns:
            encoded_patterns = json.dumps(delay_patterns, ensure_ascii=False)
            page.add_init_script(
                f"""(() => {{
                  const patterns = {encoded_patterns};
                  const originalFetch = globalThis.fetch.bind(globalThis);
                  globalThis.fetch = (input, init) => {{
                    const url = typeof input === 'string' ? input : input.url;
                    if (patterns.some(pattern => url.includes(pattern))) return new Promise(() => {{}});
                    return originalFetch(input, init);
                  }};
                }})()"""
            )
        for intercept in fixture.get("intercepts", []):
            if intercept.get("action") == "delay":
                continue
            page.route(str(intercept["url"]), _fixture_handler(intercept))

    functional = "PASS"
    usability = "PASS"
    errors: list[str] = []
    measurements: dict[str, Any] = {}
    artifacts: dict[str, str | None] = {"viewport": None, "full_page": None, "focus": None, "trace": None}
    accessibility: dict[str, Any] | None = None
    login_recovered = False
    viewport_path = screenshot_dir / f"{case_id}-viewport.png"
    full_path = screenshot_dir / f"{case_id}-full.png"
    try:
        page.goto(f"{web_base}/{str(group['route']).lstrip('/')}", wait_until="domcontentloaded")
        role_config = audit_config.get("roles", {}).get(str(group["role"]), {})
        authenticated_selector = str(role_config.get("authenticated_selector", ""))
        if authenticated_selector:
            try:
                page.locator(authenticated_selector).first.wait_for(
                    state="visible",
                    timeout=min(timeout_ms, SESSION_PROBE_TIMEOUT_MS),
                )
            except Exception:
                # A captured storage state can become stale during a long matrix.
                # Recover once in the isolated case context instead of converting
                # an environmental session expiry into a product failure.
                context.clear_cookies()
                project_role = next(
                    role for role in project_config.get("roles", [])
                    if role.get("name") == group["role"]
                )
                recovery = browser_login(page, project_config, project_role, web_base)
                if recovery.get("result") != "PASS":
                    raise RuntimeError(f"case login recovery failed: {recovery}")
                login_recovered = True
                page.goto(f"{web_base}/{str(group['route']).lstrip('/')}", wait_until="domcontentloaded")
                page.locator(authenticated_selector).first.wait_for(state="visible")

        title_locator = (
            page.locator(str(group["title_selector"])).first
            if group.get("title_selector")
            else page.get_by_role("heading", name=str(group["title"]), exact=False).first
        )
        title_locator.wait_for(state="visible")
        if state == "data" and group.get("data_selector"):
            page.locator(str(group["data_selector"])).first.wait_for(state="visible")
        proof = dict(audit_config.get("state_contract", {}).get(state, {}).get("proof", {}))
        if fixture:
            proof.update(fixture.get("proof", {}))
        _wait_for_proof(page, proof, state)
        page.wait_for_timeout(250 if state == "loading" else settle_ms)

        title_measure = _measure_title(page, title_locator)
        if title_measure.get("reason") == "title not found":
            functional = "FAIL"
            errors.append("configured page title was not found; target screen was not proven")
        layout_measure = page.evaluate(_LAYOUT_MEASURE_SCRIPT)
        measurements = {
            "login_recovered": login_recovered,
            "scroll_y": int(page.evaluate("window.scrollY")),
            "title_visible": bool(title_measure.get("visible")),
            "title_rect": title_measure.get("rect"),
            **layout_measure,
        }
        if not measurements["title_visible"] or measurements.get("overflow_x") or measurements.get("clipped_candidates"):
            usability = "REVIEW"
        if fixture and fixture.get("known_gap"):
            usability = "REVIEW"

        page.screenshot(path=str(viewport_path), full_page=False)
        page.screenshot(path=str(full_path), full_page=True)
        artifacts["viewport"] = str(viewport_path)
        artifacts["full_page"] = str(full_path)

        if state == "data" and str(viewport["name"]) == "office-laptop":
            try:
                from .accessibility import run_accessibility_audit

                accessibility = run_accessibility_audit(page)
                if accessibility.get("functional_status") == "FAIL":
                    functional = "FAIL"
                elif accessibility.get("functional_status") == "BLOCKED" and functional == "PASS":
                    functional = "BLOCKED"
                if accessibility.get("usability_status") == "REVIEW":
                    usability = "REVIEW"
                elif accessibility.get("usability_status") == "BLOCKED":
                    usability = "BLOCKED"
                focus_path = screenshot_dir / f"{case_id}-focus.png"
                page.screenshot(path=str(focus_path), full_page=False)
                artifacts["focus"] = str(focus_path)
            except (ImportError, FileNotFoundError) as error:
                accessibility = {"functional_status": "BLOCKED", "usability_status": "BLOCKED", "error": str(error)}
                usability = "BLOCKED"
        if state == "data":
            measurements["menu_scroll_reset"] = _measure_menu_scroll_reset(
                page, web_base, group.get("navigation"), group["route"], settle_ms
            )
            if measurements["menu_scroll_reset"].get("status") == "FAIL":
                functional = "FAIL"
    except Exception as error:
        functional = "FAIL"
        errors.append(f"{type(error).__name__}: {str(error)[:1000]}")
    finally:
        # A failed target/proof wait is itself valuable evidence. Best-effort
        # screenshots ensure functional failures never disappear from reports.
        if not artifacts["viewport"]:
            try:
                page.screenshot(path=str(viewport_path), full_page=False)
                artifacts["viewport"] = str(viewport_path)
            except Exception as screenshot_error:
                errors.append(f"viewport screenshot failed: {type(screenshot_error).__name__}: {screenshot_error}")
        if not artifacts["full_page"]:
            try:
                page.screenshot(path=str(full_path), full_page=True)
                artifacts["full_page"] = str(full_path)
            except Exception as screenshot_error:
                errors.append(f"full-page screenshot failed: {type(screenshot_error).__name__}: {screenshot_error}")

    if unsafe_requests:
        functional = "FAIL"
        errors.append("read-only guard blocked a mutating request")
    if blocked_external and usability == "PASS":
        usability = "REVIEW"
    if not artifacts["viewport"] or not artifacts["full_page"]:
        if functional == "PASS":
            functional = "BLOCKED"

    return {
        "case_id": case_id,
        "page": group["page"],
        "role": group["role"],
        "route": group["route"],
        "state": state,
        "viewport": {"name": viewport["name"], "width": viewport["width"], "height": viewport["height"]},
        "functional_status": functional,
        "usability_status": usability,
        "measurements": measurements,
        "artifacts": artifacts,
        "accessibility": accessibility,
        "known_gap": fixture.get("known_gap") if fixture else None,
        "unsafe_requests": unsafe_requests,
        "blocked_external_requests": sorted(set(blocked_external))[:50],
        "errors": errors,
    }


def _fixture_handler(intercept: dict[str, Any]) -> Any:
    def handle(route: Any) -> None:
        action = intercept.get("action")
        if action == "delay":
            raise ValueError("delay fixtures must be installed with the init-script interceptor")
        if action == "fulfill":
            route.fulfill(
                status=int(intercept.get("status", 200)),
                content_type=str(intercept.get("content_type", "application/json")),
                body=json.dumps(intercept.get("body"), ensure_ascii=False),
            )
            return
        if action == "abort":
            route.abort("failed")
            return
        route.continue_()

    return handle


def _wait_for_proof(page: Any, proof: dict[str, Any], state: str) -> None:
    if proof.get("role"):
        locator = page.get_by_role(str(proof["role"]), name=proof.get("name"), exact=False).first
        if proof.get("text"):
            locator = locator.filter(has_text=str(proof["text"]))
        locator.wait_for(state="visible")
    elif proof.get("text"):
        page.get_by_text(str(proof["text"]), exact=False).first.wait_for(state="visible")
    elif state != "data":
        raise ValueError(f"state {state} has no observable proof")
    if proof.get("retry_text"):
        page.get_by_text(str(proof["retry_text"]), exact=False).first.wait_for(state="visible")


def _measure_title(page: Any, locator: Any) -> dict[str, Any]:
    if locator.count() < 1:
        return {"visible": False, "rect": None, "reason": "title not found"}
    return locator.evaluate(
        """element => {
          const rect = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          const centerX = Math.max(0, Math.min(innerWidth - 1, rect.left + rect.width / 2));
          const centerY = Math.max(0, Math.min(innerHeight - 1, rect.top + Math.min(rect.height / 2, 8)));
          const hit = document.elementFromPoint(centerX, centerY);
          const unobscured = !hit || hit === element || element.contains(hit) || hit.contains(element);
          const visible = rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.bottom <= innerHeight
            && style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity || 1) > 0 && unobscured;
          return {visible, unobscured, rect: {top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left, width: rect.width, height: rect.height}};
        }"""
    )


def _measure_menu_scroll_reset(
    page: Any,
    web_base: str,
    navigation: dict[str, Any] | None,
    target_route: str,
    settle_ms: int,
) -> dict[str, Any]:
    if not navigation:
        return {"status": "SKIP", "reason": "no applicable sidebar navigation contract"}
    source_route = str(navigation.get("source_route", ""))
    menu = str(navigation.get("menu", ""))
    if not source_route or not menu:
        return {"status": "SKIP", "reason": "navigation contract lacks source_route or menu"}
    page.goto(f"{web_base}/{source_route.lstrip('/')}", wait_until="domcontentloaded")
    page.wait_for_timeout(settle_ms)
    maximum = int(page.evaluate("Math.max(0, document.documentElement.scrollHeight - innerHeight)"))
    if maximum < 1:
        return {"status": "SKIP", "reason": "source page is not scrollable", "source_route": source_route}
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(50)
    before = int(page.evaluate("window.scrollY"))
    if before < 1:
        return {"status": "SKIP", "reason": "could not establish pre-scroll", "source_route": source_route}
    _navigation_menu_button(page, menu).click()
    page.wait_for_function("expected => location.hash === expected", arg=str(target_route).removeprefix("/"))
    page.wait_for_timeout(settle_ms)
    after = int(page.evaluate("window.scrollY"))
    return {
        "status": "PASS" if after == 0 else "FAIL",
        "source_route": source_route,
        "target_route": target_route,
        "menu": menu,
        "before_scroll_y": before,
        "after_scroll_y": after,
    }


def _navigation_menu_button(page: Any, menu: str) -> Any:
    """Scope menu lookup to semantic navigation to avoid same-name page actions."""
    return page.get_by_role("navigation").first.get_by_role("button", name=menu, exact=True).first


_LAYOUT_MEASURE_SCRIPT = """() => {
  const root = document.documentElement;
  const hidden = element => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || 1) === 0 || rect.width === 0 || rect.height === 0;
  };
  const candidates = [];
  const offscreen = [];
  const insideHorizontalScroller = element => {
    let parent = element.parentElement;
    while (parent && parent !== document.body) {
      const style = getComputedStyle(parent);
      if (['auto', 'scroll'].includes(style.overflowX) && parent.scrollWidth > parent.clientWidth + 1) return true;
      parent = parent.parentElement;
    }
    return false;
  };
  for (const element of document.querySelectorAll('body *')) {
    if (hidden(element) || element.closest('[aria-hidden="true"], [inert], .visually-hidden, .sr-only')) continue;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const clipsX = ['hidden', 'clip'].includes(style.overflowX) && element.scrollWidth > element.clientWidth + 1;
    const clipsY = ['hidden', 'clip'].includes(style.overflowY) && element.scrollHeight > element.clientHeight + 1;
    if ((clipsX || clipsY) && candidates.length < 50) candidates.push({
      tag: element.tagName.toLowerCase(), id: element.id || '', className: String(element.className || '').slice(0, 160),
      clipsX, clipsY, clientWidth: element.clientWidth, scrollWidth: element.scrollWidth,
      clientHeight: element.clientHeight, scrollHeight: element.scrollHeight
    });
    if ((rect.right > innerWidth + 1 || rect.left < -1) && !insideHorizontalScroller(element) && offscreen.length < 50) offscreen.push({
      tag: element.tagName.toLowerCase(), id: element.id || '', className: String(element.className || '').slice(0, 160),
      left: rect.left, right: rect.right
    });
  }
  return {
    document_scroll_width: root.scrollWidth,
    document_client_width: root.clientWidth,
    overflow_x: root.scrollWidth > root.clientWidth + 1,
    clipped_candidates: candidates.length,
    clipped_elements: candidates,
    offscreen_candidates: offscreen.length,
    offscreen_elements: offscreen
  };
}"""


def _case_id(group: dict[str, Any], state: str, viewport: dict[str, Any]) -> str:
    raw = f"UI-{group['page']}-{state}-{group['role']}-{viewport['name']}"
    return safe_name(raw).upper()


def _blocked_case(group: dict[str, Any], state: str, viewport: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "case_id": _case_id(group, state, viewport),
        "page": group["page"], "role": group["role"], "route": group["route"], "state": state,
        "viewport": viewport, "functional_status": "BLOCKED", "usability_status": "BLOCKED",
        "measurements": {}, "artifacts": {"viewport": None, "full_page": None, "focus": None, "trace": None},
        "accessibility": None, "known_gap": None, "unsafe_requests": [], "blocked_external_requests": [],
        "errors": [reason],
    }


def _aggregate_axis(cases: list[dict[str, Any]], key: str, review: bool) -> str:
    values = {item.get(key) for item in cases}
    if "FAIL" in values:
        return "FAIL"
    if "BLOCKED" in values:
        return "BLOCKED"
    if review and "REVIEW" in values:
        return "REVIEW"
    return "PASS" if values else "BLOCKED"


def _summarize_cases(cases: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(cases),
        "passed": sum(item.get("functional_status") == "PASS" for item in cases),
        "failed": sum(item.get("functional_status") == "FAIL" for item in cases),
        "blocked": sum(item.get("functional_status") == "BLOCKED" for item in cases),
        "review": sum(item.get("usability_status") == "REVIEW" for item in cases),
    }


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    return parsed._replace(query="", fragment="").geturl()


def load_and_run_ui_audit(project_path: Path, audit_path: Path, options: Any, out_dir: Path) -> dict[str, Any]:
    return run_ui_audit(load_config(project_path), load_ui_audit_config(audit_path), options, out_dir)
