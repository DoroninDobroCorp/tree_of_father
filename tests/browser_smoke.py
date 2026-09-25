#!/usr/bin/env python3
"""Browser smoke test for Своя мастерская · Skill RPG.

Runs end-to-end browser check with Playwright if installed.
Falls back to deep HTML/DOM structure inspection if Playwright is not available.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
import time
from http.server import ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server
from server import Config, WorkshopServer, WorkshopRequestHandler


def static_dom_smoke_check(html_path: pathlib.Path) -> bool:
    print("Running static DOM & contract smoke checks...")
    content = html_path.read_text(encoding="utf-8")

    # 1. Essential markup presence
    assert "<!doctype html>" in content.lower(), "Missing doctype"
    assert "<title>Своя мастерская · Skill RPG</title>" in content, "Missing or incorrect title"
    assert '<div id="app"></div>' in content, "Missing #app mount point"
    assert '<div id="modal-root"></div>' in content, "Missing #modal-root"
    assert '<div id="toast-root"></div>' in content, "Missing #toast-root"

    # 2. Seed data script tag
    seed_marker = '<script id="seed-data" type="application/json">'
    assert seed_marker in content, "Missing #seed-data script tag"
    seed_start = content.find(seed_marker) + len(seed_marker)
    seed_end = content.find("</script>", seed_start)
    seed_raw = content[seed_start:seed_end]
    seed_data = json.loads(seed_raw)
    assert seed_data.get("schemaVersion") == 3, "Invalid schemaVersion in seed"
    assert len(seed_data.get("skills", [])) > 50, "Insufficient skills in seed"
    print(f"  ✓ Seed data verified ({len(seed_data['skills'])} skills, {len(seed_data['projects'])} projects)")

    # 3. Proposal schema script tag
    schema_marker = '<script id="proposal-schema" type="application/json">'
    assert schema_marker in content, "Missing #proposal-schema script tag"
    schema_start = content.find(schema_marker) + len(schema_marker)
    schema_end = content.find("</script>", schema_start)
    schema_raw = content[schema_start:schema_end]
    schema_data = json.loads(schema_raw)
    assert "$defs" in schema_data, "Schema missing $defs"
    print("  ✓ Proposal schema verified")

    # 4. App JavaScript integrity
    script_marker = "<script>(()=>{"
    assert script_marker in content, "Missing app script bundle"
    assert "Core.validateState(D,SCHEMA)" in content, "Missing state validation startup call"
    assert "window.Workshop=" in content, "Missing window.Workshop test interface"
    print("  ✓ App JS startup entry verified")

    print("Static smoke check PASSED!\n")
    return True


def run_playwright_test(base_url: str):
    from playwright.sync_api import sync_playwright

    chromium_path = os.environ.get("CHROMIUM_PATH")
    launch_kwargs = {"headless": True}
    if chromium_path:
        launch_kwargs["executable_path"] = chromium_path

    print(f"Running Playwright smoke test against {base_url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(base_url)
        page.wait_for_selector("#app")

        # Check title
        title = page.title()
        assert "Своя мастерская" in title, f"Unexpected title: {title}"
        print(f"  ✓ Page loaded: title = '{title}'")

        # Check that window.Workshop is exposed
        workshop_exists = page.evaluate("typeof window.Workshop === 'object'")
        assert workshop_exists, "window.Workshop not exposed"
        print("  ✓ window.Workshop interface available")

        # Verify state is valid
        is_valid = page.evaluate("window.Workshop.validate()")
        assert is_valid is True, "window.Workshop.validate() failed"
        print("  ✓ In-browser Core.validateState(D, SCHEMA) passed")

        # Click Mentor navigation
        page.click('[data-action="nav"][data-id="mentor"]')
        page.wait_for_selector('#ai-scope')
        print("  ✓ Navigated to 'ИИ-наставник' page successfully")

        # Click health check button
        page.click('[data-action="health"]')
        time.sleep(0.5)

        assert len(errors) == 0, f"Encountered page errors: {errors}"
        browser.close()

    print("Playwright smoke test PASSED!\n")


def main():
    index_path = ROOT / "index.html"
    if not index_path.is_file():
        print("Error: index.html not found", file=sys.stderr)
        sys.exit(1)

    static_dom_smoke_check(index_path)

    # Check if playwright is available
    try:
        import playwright
        has_playwright = True
    except ImportError:
        has_playwright = False

    if not has_playwright:
        print("Note: playwright is not installed. To run full browser E2E test:")
        print("  pip install playwright && playwright install chromium")
        print("  python3 tests/browser_smoke.py")
        sys.exit(0)

    # Start ephemeral background server
    config = Config(cli_port=0, cli_host="127.0.0.1")
    workshop_app = WorkshopServer(config)

    class SmokeHandler(WorkshopRequestHandler):
        server_app = workshop_app

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), SmokeHandler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        run_playwright_test(base_url)
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
