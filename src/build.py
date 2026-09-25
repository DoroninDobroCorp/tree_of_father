#!/usr/bin/env python3
"""Build script for Своя мастерская · Skill RPG.

Combines modular sources in src/ into:
- index.html (root standalone game)
- maker_rpg.html (backup copy)
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def build():
    print("Building standalone HTML files from src/...")

    shell_path = SRC / "shell.html"
    style_path = SRC / "style.css"
    seed_path = SRC / "seed.json"
    schema_path = SRC / "proposal.schema.json"
    core_path = SRC / "core.js"
    app_path = SRC / "app.js"

    for p in (shell_path, style_path, seed_path, schema_path, core_path, app_path):
        if not p.is_file():
            print(f"Error: missing required source file: {p}", file=sys.stderr)
            sys.exit(1)

    shell = shell_path.read_text(encoding="utf-8")
    style = style_path.read_text(encoding="utf-8").strip()
    
    # Parse and minify JSON payloads for embedded scripts
    seed_obj = json.loads(seed_path.read_text(encoding="utf-8"))
    schema_obj = json.loads(schema_path.read_text(encoding="utf-8"))
    seed_min = json.dumps(seed_obj, ensure_ascii=False, separators=(",", ":"))
    schema_min = json.dumps(schema_obj, ensure_ascii=False, separators=(",", ":"))

    core = core_path.read_text(encoding="utf-8").strip()
    app = app_path.read_text(encoding="utf-8").strip()

    # Replace placeholders
    html = shell
    html = html.replace("<!-- STYLE -->", style)
    html = html.replace("<!-- SEED -->", seed_min)
    html = html.replace("<!-- SCHEMA -->", schema_min)
    html = html.replace("<!-- CORE -->", core)
    html = html.replace("<!-- APP -->", app)

    index_path = ROOT / "index.html"
    maker_rpg_path = ROOT / "maker_rpg.html"

    index_path.write_text(html, encoding="utf-8")
    maker_rpg_path.write_text(html, encoding="utf-8")

    # Also keep initial-profile.json in sync with seed.json
    initial_profile_path = ROOT / "initial-profile.json"
    initial_profile_path.write_text(
        json.dumps(seed_obj, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    print(f"Successfully generated:")
    print(f"  - {index_path} ({len(html)} chars, {os.path.getsize(index_path)} bytes)")
    print(f"  - {maker_rpg_path} ({len(html)} chars, {os.path.getsize(maker_rpg_path)} bytes)")
    print(f"  - {initial_profile_path}")


if __name__ == "__main__":
    build()
