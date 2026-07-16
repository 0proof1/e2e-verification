from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from .api_harness import summarize_rows
from .config import expand, role_context, safe_name
from .http import elapsed
from .environment import endpoint_checks, resolve_endpoint
from .evidence import write_json_atomic
from .redaction import redact


def assert_scroll_top(page: Any) -> dict[str, Any]:
    scroll_y = float(page.evaluate("() => window.scrollY"))
    return {"passed": scroll_y == 0, "scrollY": scroll_y}


def assert_title_in_first_viewport(page: Any, selector: str, viewport_height: int) -> dict[str, Any]:
    locator = page.locator(selector).first
    box = locator.bounding_box() if locator.count() else None
    visible = bool(box) and locator.is_visible()
    passed = bool(visible and box and box["y"] < viewport_height and box["y"] + box["height"] > 0)
    return {"passed": passed, "selector": selector, "visible": visible, "boundingBox": box}


def detect_horizontal_overflow_and_clipping(page: Any) -> dict[str, Any]:
    measurement = page.evaluate(
        """() => {
          const root = document.documentElement;
          const clientWidth = root.clientWidth;
          const candidates = Array.from(document.querySelectorAll('body *'))
            .map((element) => {
              const rect = element.getBoundingClientRect();
              const style = getComputedStyle(element);
              return {element, rect, style};
            })
            .filter(({rect, style}) =>
              style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 &&
              (rect.left < -1 || rect.right > clientWidth + 1))
            .slice(0, 20)
            .map(({element, rect}) => ({
              tag: element.tagName.toLowerCase(),
              id: element.id || '',
              className: typeof element.className === 'string' ? element.className.slice(0, 120) : '',
              left: Math.round(rect.left * 100) / 100,
              right: Math.round(rect.right * 100) / 100,
              width: Math.round(rect.width * 100) / 100
            }));
          return {
            clientWidth,
            scrollWidth: root.scrollWidth,
            horizontalOverflow: root.scrollWidth > clientWidth + 1,
            clippingCandidates: candidates
          };
        }"""
    )
    measurement["overflowPassed"] = not measurement["horizontalOverflow"]
    measurement["clippingPassed"] = not measurement["clippingCandidates"]
    return measurement


def capture_viewport_and_full_page(
    page: Any,
    screenshot_dir: Path,
    stem: str,
    capture_types: list[str],
) -> dict[str, str]:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    if "viewport" in capture_types:
        path = screenshot_dir / f"{stem}-viewport.png"
        page.screenshot(path=str(path), full_page=False)
        paths["viewport"] = str(path)
    if "full-page" in capture_types:
        path = screenshot_dir / f"{stem}-full-page.png"
        page.screenshot(path=str(path), full_page=True)
        paths["fullPage"] = str(path)
    return paths


def finish_trace(context: Any, out_dir: Path, role_name: str, save: bool) -> str:
    if not save:
        context.tracing.stop()
        return ""
    trace_dir = out_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{safe_name(role_name)}.zip"
    context.tracing.stop(path=str(trace_path))
    return str(trace_path)


def attach_page_evidence(
    row: dict[str, Any],
    page: Any,
    visual: dict[str, Any],
    role_dir: Path,
    stem: str,
    capture_types: list[str],
) -> None:
    try:
        usability_status, measurements = assess_page(page, visual)
        screenshots = capture_viewport_and_full_page(page, role_dir, stem, capture_types)
        row["usabilityStatus"] = usability_status
        row["measurements"] = measurements
        row["screenshots"] = screenshots
        row["screenshot"] = screenshots.get("viewport", "")
    except Exception as error:
        row["usabilityStatus"] = "NOT_RUN"
        row["measurements"] = {}
        row["screenshots"] = {}
        row["screenshot"] = ""
        row["evidenceError"] = f"{type(error).__name__}: {error}"[:500]


def assess_page(page: Any, visual: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not visual:
        return "NOT_RUN", {}
    checks = set(visual.get("checks", []))
    measurements: dict[str, Any] = {}
    pass_values: list[bool] = []
    if "scroll-top" in checks:
        measurements["scrollTop"] = assert_scroll_top(page)
        pass_values.append(measurements["scrollTop"]["passed"])
    if "title-in-first-viewport" in checks:
        measurements["titleInFirstViewport"] = assert_title_in_first_viewport(
            page,
            visual["title_selector"],
            int(visual["viewport"]["height"]),
        )
        pass_values.append(measurements["titleInFirstViewport"]["passed"])
    if checks & {"horizontal-overflow", "clipping"}:
        overflow = detect_horizontal_overflow_and_clipping(page)
        measurements["layout"] = overflow
        if "horizontal-overflow" in checks:
            pass_values.append(overflow["overflowPassed"])
        if "clipping" in checks:
            pass_values.append(overflow["clippingPassed"])
    return ("PASS" if all(pass_values) else "REVIEW"), measurements


def browser_login(page: Any, config: dict[str, Any], role: dict[str, Any], web_base: str) -> dict[str, Any]:
    login = config.get("browser_login")
    if not login:
        return {"result": "SKIP", "reason": "browser_login is not configured"}
    context = role_context(role)
    if not context["account"]["id"] or not context["account"]["password"]:
        return {"result": "BLOCKED", "reason": "account id/password environment variables are missing"}
    page.goto(f"{web_base.rstrip('/')}/{login.get('path', '/').lstrip('/')}", wait_until="domcontentloaded")
    mode_selector = role.get("account", {}).get("mode_selector")
    if mode_selector:
        page.locator(mode_selector).click()
    page.locator(login["id_selector"]).fill(context["account"]["id"])
    page.locator(login["password_selector"]).fill(context["account"]["password"])
    page.locator(login["submit_selector"]).click()
    page.wait_for_timeout(int(login.get("settle_ms", 800)))
    expected = role.get("home_path", "/")
    observed = page.url.removeprefix(web_base.rstrip("/")) or "/"
    return {"result": "PASS" if observed.startswith(expected) else "FAIL", "expectedPath": expected, "observedPath": observed}


def run_browser(config: dict[str, Any], options: Any, out_dir: Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Playwright is required: pip install -e . && playwright install chromium") from error
    defaults = config.get("defaults", {})
    resolution = resolve_endpoint(
        "web",
        options.web_base,
        config,
        getattr(options, "target_mode", None) or os.environ.get("E2E_TARGET_MODE", "auto"),
        getattr(options, "host_alias", None) or os.environ.get("E2E_HOST_ALIAS", "host.docker.internal"),
    )
    web_base = resolution.url
    preflight = (
        endpoint_checks(resolution, connect=bool(getattr(options, "preflight_connect", False)))
        if bool(getattr(options, "preflight", False))
        else [
            {"status": "BLOCKED", "check": "endpoint:web", "detail": detail}
            for detail in resolution.blockers
        ]
    )
    environment_blocked = any(check["status"] == "BLOCKED" for check in preflight)
    if environment_blocked:
        rows = [
            {"id": probe.get("id", "environment"), "role": probe.get("role", ""), "result": "BLOCKED_ENVIRONMENT"}
            for probe in config.get("browser_probes", [])
        ] or [{"id": "environment", "role": "", "result": "BLOCKED_ENVIRONMENT"}]
        return {
            "webBase": web_base,
            "endpoint": resolution.__dict__,
            "preflight": preflight,
            "logins": [],
            "routes": [],
            "menus": [],
            "probes": rows,
            "network": [],
            "summary": summarize_rows(rows),
        }
    role_map = {role["name"]: role for role in config.get("roles", [])}
    visual = config.get("visual_verification", {})
    viewport = visual.get("viewport", {"width": 1440, "height": 960})
    capture_types = list(visual.get("capture", ["viewport"]))
    result: dict[str, Any] = {
        "webBase": web_base,
        "endpoint": resolution.__dict__,
        "preflight": preflight,
        "logins": [],
        "routes": [],
        "menus": [],
        "probes": [],
        "network": [],
        "traces": [],
    }
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not options.headed)
        for role_name, role in role_map.items():
            role_dir = screenshot_dir / safe_name(role_name)
            context = browser.new_context(viewport={"width": int(viewport["width"]), "height": int(viewport["height"])})
            trace_on_failure = bool(getattr(options, "trace_on_failure", False))
            if trace_on_failure:
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
            page = context.new_page()
            page.set_default_timeout(options.timeout_seconds * 1000)
            page.set_default_navigation_timeout(options.timeout_seconds * 1000)
            role_network: list[dict[str, Any]] = []
            page.on("response", lambda response, rows=role_network: rows.append({
                "method": response.request.method, "url": response.url, "status": response.status,
            }) if "/api/" in response.url else None)
            try:
                login_row = {"role": role_name, **browser_login(page, config, role, web_base)}
            except Exception as error:
                login_row = {"role": role_name, "result": "FAIL", "reason": f"{type(error).__name__}: {error}"[:500]}
            result["logins"].append(login_row)
            if login_row["result"] != "PASS":
                if trace_on_failure:
                    trace_path = finish_trace(context, out_dir, role_name, login_row["result"] == "FAIL")
                    if trace_path:
                        result["traces"].append(trace_path)
                context.close()
                continue
            menus = role.get("menus", [])
            if menus:
                first_menu = menus[0]
                first_selector = first_menu.get("selector") or f"text={first_menu['label']}"
                try:
                    page.locator(first_selector).first.wait_for(
                        state="visible",
                        timeout=min(options.timeout_seconds * 1000, 10_000),
                    )
                except Exception:
                    # Record every declared menu below. A missing shell remains
                    # a normal functional failure rather than aborting the role.
                    pass
            for menu in menus:
                selector = menu.get("selector") or f"text={menu['label']}"
                result["menus"].append({"role": role_name, "label": menu["label"], "visible": page.locator(selector).first.is_visible()})
            for route in role.get("routes", []):
                outcome = route.get("outcome", "ALLOW")
                row = {"role": role_name, "path": route["path"], "outcome": outcome}
                try:
                    page.goto(f"{web_base.rstrip('/')}/{route['path'].lstrip('/')}", wait_until="domcontentloaded")
                    page.wait_for_timeout(int(defaults.get("settle_ms", 500)))
                    observed = page.url.removeprefix(web_base.rstrip("/")) or "/"
                    expected = route.get("expected_path", route["path"])
                    passed = observed.startswith(expected) if outcome in {"ALLOW", "REDIRECT"} else not observed.startswith(route["path"])
                    row.update({
                        "observedPath": observed,
                        "result": "PASS" if passed else "FAIL",
                        "functionalStatus": "PASS" if passed else "FAIL",
                    })
                except Exception as error:
                    row.update({
                        "result": "FAIL",
                        "functionalStatus": "FAIL",
                        "error": f"{type(error).__name__}: {error}"[:500],
                    })
                attach_page_evidence(
                    row,
                    page,
                    visual,
                    role_dir,
                    f"route-{safe_name(route['path'])}",
                    capture_types,
                )
                result["routes"].append(row)
            for probe in [item for item in config.get("browser_probes", []) if item["role"] == role_name]:
                started = time.monotonic()
                row = {"id": probe["id"], "role": role_name, "route": probe["route"], "action": probe.get("action", "click")}
                try:
                    page.goto(f"{web_base.rstrip('/')}/{probe['route'].lstrip('/')}", wait_until="domcontentloaded")
                    page.wait_for_timeout(int(probe.get("settle_ms", defaults.get("settle_ms", 500))))
                    before = len(role_network)
                    locator = page.locator(probe["selector"]).first
                    action = probe.get("action", "click")
                    value = expand(probe.get("value", ""), role_context(role))
                    if action == "click": locator.click()
                    elif action == "fill": locator.fill(str(value))
                    elif action == "select": locator.select_option(str(value))
                    elif action == "check": locator.check()
                    elif action == "press": locator.press(str(value))
                    page.wait_for_timeout(int(probe.get("after_ms", 500)))
                    expectation = probe.get("expect", {})
                    checks: list[bool] = []
                    if expectation.get("path"):
                        observed = page.url.removeprefix(web_base.rstrip("/")) or "/"
                        checks.append(observed.startswith(expectation["path"]))
                        row["observedPath"] = observed
                    if expectation.get("visible_selector"):
                        checks.append(page.locator(expectation["visible_selector"]).first.is_visible())
                    if expectation.get("response_url_regex"):
                        checks.append(any(re.search(expectation["response_url_regex"], item["url"]) for item in role_network[before:]))
                    row["result"] = "PASS" if all(checks or [True]) else "FAIL"
                except Exception as error:
                    row.update({"result": "FAIL", "error": str(error)[:500]})
                row["elapsedMs"] = elapsed(started)
                row["functionalStatus"] = row["result"]
                attach_page_evidence(
                    row,
                    page,
                    visual,
                    role_dir,
                    f"probe-{safe_name(probe['id'])}",
                    capture_types,
                )
                result["probes"].append(row)
            result["network"].extend({"role": role_name, **item} for item in role_network)
            role_failed = any(
                row.get("role") == role_name and row.get("functionalStatus") == "FAIL"
                for group in ("routes", "probes")
                for row in result[group]
            )
            if trace_on_failure:
                trace_path = finish_trace(context, out_dir, role_name, role_failed)
                if trace_path:
                    result["traces"].append(str(trace_path))
            context.close()
        browser.close()
    assessed = result["logins"] + result["routes"] + result["probes"]
    menu_rows = [{"result": "PASS" if row["visible"] else "FAIL"} for row in result["menus"]]
    result["summary"] = summarize_rows(assessed + menu_rows)
    result["summary"]["serverErrors"] = sum(1 for row in result["network"] if row["status"] >= 500)
    usability_rows = [row for row in result["routes"] + result["probes"] if row.get("usabilityStatus") != "NOT_RUN"]
    result["summary"]["usabilityAssessed"] = len(usability_rows)
    result["summary"]["review"] = sum(1 for row in usability_rows if row.get("usabilityStatus") == "REVIEW")
    write_json_atomic(out_dir / "browser-report.json", redact(result))
    return result
