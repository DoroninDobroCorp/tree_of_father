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
    assert seed_data.get("schemaVersion") == 4, "Invalid schemaVersion in seed"
    assert len(seed_data.get("skills", [])) > 300, "Insufficient skills in seed"
    assert all(len(s["criteria"]) >= 2 for s in seed_data["skills"]), "Skill without mastery criteria"
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

    for marker in ('<script id="catalog-history" type="application/json">', '<script id="ai-rules" type="text/plain">'):
        assert marker in content, f"Missing {marker}"
    assert "<!--" not in content.split("<script>(()=>{", 1)[0].split("</noscript>", 1)[1], "Unreplaced build marker"
    print("  ✓ Catalog history and AI rules embedded")

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

        # Mastery: tick the first skill of a branch and see the counter move
        page.click('[data-action="nav"][data-id="map"]')
        page.click('.branch-card[data-id="wood"]')
        page.wait_for_selector(".mastery-summary")
        page.click(".skill-tick >> nth=0")
        mastered = page.evaluate("Object.values(window.Workshop.getState().mastery).filter(m => m.mastered).length")
        assert mastered == 1, f"Expected one mastered skill, got {mastered}"
        assert page.text_content(".mastery-count b") == "1", "Branch mastery counter did not update"
        print("  ✓ Mastery tick updates state and branch progress")

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
    config.access_key = ""
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
