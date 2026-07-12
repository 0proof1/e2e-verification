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
    result: dict[str, Any] = {
        "webBase": web_base,
        "endpoint": resolution.__dict__,
        "preflight": preflight,
        "logins": [],
        "routes": [],
        "menus": [],
        "probes": [],
        "network": [],
    }
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not options.headed)
        for role_name, role in role_map.items():
            context = browser.new_context(viewport={"width": 1440, "height": 960})
            page = context.new_page()
            page.set_default_timeout(options.timeout_seconds * 1000)
            page.set_default_navigation_timeout(options.timeout_seconds * 1000)
            role_network: list[dict[str, Any]] = []
            page.on("response", lambda response, rows=role_network: rows.append({
                "method": response.request.method, "url": response.url, "status": response.status,
            }) if "/api/" in response.url else None)
            login_row = {"role": role_name, **browser_login(page, config, role, web_base)}
            result["logins"].append(login_row)
            if login_row["result"] != "PASS":
                context.close()
                continue
            for menu in role.get("menus", []):
                selector = menu.get("selector") or f"text={menu['label']}"
                result["menus"].append({"role": role_name, "label": menu["label"], "visible": page.locator(selector).first.is_visible()})
            for route in role.get("routes", []):
                page.goto(f"{web_base.rstrip('/')}/{route['path'].lstrip('/')}", wait_until="domcontentloaded")
                page.wait_for_timeout(int(defaults.get("settle_ms", 500)))
                observed = page.url.removeprefix(web_base.rstrip("/")) or "/"
                expected = route.get("expected_path", route["path"])
                outcome = route.get("outcome", "ALLOW")
                passed = observed.startswith(expected) if outcome in {"ALLOW", "REDIRECT"} else not observed.startswith(route["path"])
                shot = screenshot_dir / f"route-{safe_name(role_name)}-{safe_name(route['path'])}.png"
                page.screenshot(path=str(shot), full_page=False)
                result["routes"].append({"role": role_name, "path": route["path"], "observedPath": observed, "outcome": outcome, "result": "PASS" if passed else "FAIL", "screenshot": str(shot)})
            for probe in [item for item in config.get("browser_probes", []) if item["role"] == role_name]:
                page.goto(f"{web_base.rstrip('/')}/{probe['route'].lstrip('/')}", wait_until="domcontentloaded")
                page.wait_for_timeout(int(probe.get("settle_ms", defaults.get("settle_ms", 500))))
                before = len(role_network)
                started = time.monotonic()
                row = {"id": probe["id"], "role": role_name, "route": probe["route"], "action": probe.get("action", "click")}
                try:
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
                shot = screenshot_dir / f"probe-{safe_name(probe['id'])}.png"
                page.screenshot(path=str(shot), full_page=False)
                row["screenshot"] = str(shot)
                result["probes"].append(row)
            result["network"].extend({"role": role_name, **item} for item in role_network)
            context.close()
        browser.close()
    assessed = result["logins"] + result["routes"] + result["probes"]
    menu_rows = [{"result": "PASS" if row["visible"] else "FAIL"} for row in result["menus"]]
    result["summary"] = summarize_rows(assessed + menu_rows)
    result["summary"]["serverErrors"] = sum(1 for row in result["network"] if row["status"] >= 500)
    return result
