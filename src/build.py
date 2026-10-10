#!/usr/bin/env python3
"""Build index.html for Своя мастерская · Skill RPG.

Checks the sources (OpenAI strict schema rules, seed consistency), records the
shipped catalog in src/catalog_history.json and inlines everything into
src/shell.html. Run: python3 src/build.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CATALOG = ("branches", "tools", "skills", "projects")


def check_strict_schema(schema, path="$"):
    """OpenAI Structured Outputs strict mode: closed objects, every property required."""
    if not isinstance(schema, dict):
        return
    if schema.get("type") == "object":
        if schema.get("additionalProperties") is not False:
            raise SystemExit(f"schema {path}: additionalProperties must be false")
        missing = set(schema.get("properties", {})) - set(schema.get("required", []))
        if missing:
            raise SystemExit(f"schema {path}: not required: {sorted(missing)}")
        for key, sub in schema.get("properties", {}).items():
            check_strict_schema(sub, f"{path}.{key}")
    for key, sub in schema.get("$defs", {}).items():
        check_strict_schema(sub, f"$defs.{key}")
    if "items" in schema:
        check_strict_schema(schema["items"], f"{path}[]")
    for i, sub in enumerate(schema.get("anyOf", [])):
        check_strict_schema(sub, f"{path}.anyOf[{i}]")


def check_seed(seed):
    ids = {k: [x["id"] for x in seed[k]] for k in CATALOG}
    for k, values in ids.items():
        dupes = {v for v in values if values.count(v) > 1}
        if dupes:
            raise SystemExit(f"seed {k}: duplicate ids {sorted(dupes)}")
    branches, tools, skills = set(ids["branches"]), set(ids["tools"]), set(ids["skills"])
    for s in seed["skills"]:
        if s["branchId"] not in branches:
            raise SystemExit(f"seed skill {s['id']}: unknown branch {s['branchId']}")
        for ref in s["prerequisites"]:
            if ref not in skills:
                raise SystemExit(f"seed skill {s['id']}: unknown prerequisite {ref}")
        for ref in s["toolIds"]:
            if ref not in tools:
                raise SystemExit(f"seed skill {s['id']}: unknown tool {ref}")
        if not 2 <= len(s.get("criteria", [])) <= 8:
            raise SystemExit(f"seed skill {s['id']}: needs 2-8 mastery criteria")
    for p in seed["projects"]:
        for ref in p["skillIds"]:
            if ref not in skills:
                raise SystemExit(f"seed project {p['id']}: unknown skill {ref}")
        for ref in p["toolIds"]:
            if ref not in tools:
                raise SystemExit(f"seed project {p['id']}: unknown tool {ref}")


def js_json(value):
    """JSON.stringify-compatible compact form."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def item_hash(item):
    """Mirror of Core.itemHash: FNV-1a over UTF-16 code units; archived and empty criteria excluded."""
    text = js_json({k: item[k] for k in sorted(item) if k != "archived" and not (k == "criteria" and not item[k])})
    h = 0x811C9DC5
    data = text.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    digits, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while True:
        h, r = divmod(h, 36)
        out = digits[r] + out
        if not h:
            return out


def record_history(seed):
    """Append-only list of every shipped version of each catalog item.

    The app uses it to tell untouched catalog items (safe to update) from ones the user edited.
    """
    path = SRC / "catalog_history.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    for k in CATALOG:
        for item in seed[k]:
            known = history.setdefault(f"{k}:{item['id']}", [])
            h = item_hash(item)
            if h not in known:
                known.append(h)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    return history


def inline_json(value):
    return js_json(value).replace("</", "<\\/")


def build():
    seed = json.loads((SRC / "seed.json").read_text(encoding="utf-8"))
    schema = json.loads((SRC / "proposal.schema.json").read_text(encoding="utf-8"))
    suggest_schemas = {
        mode: json.loads((SRC / f"{name}.schema.json").read_text(encoding="utf-8"))
        for mode, name in (("skills", "skills"), ("project", "project_suggestion"), ("skill", "skill_card"))
    }
    rules = (SRC / "ai_instructions.txt").read_text(encoding="utf-8").strip()
    check_strict_schema(schema)
    for sub in suggest_schemas.values():
        check_strict_schema(sub)
    check_seed(seed)
    if "</" in rules:
        raise SystemExit("ai_instructions.txt must not contain '</'")
    history = record_history(seed)

    html = (SRC / "shell.html").read_text(encoding="utf-8")
    parts = {
        "<!-- STYLE -->": (SRC / "style.css").read_text(encoding="utf-8").strip(),
        "<!-- SEED -->": inline_json(seed),
        "<!-- SCHEMA -->": inline_json(schema),
        "<!-- SUGGEST_SCHEMAS -->": inline_json(suggest_schemas),
        "<!-- HISTORY -->": inline_json(history),
        "<!-- AI_RULES -->": rules,
        "<!-- CORE -->": (SRC / "core.js").read_text(encoding="utf-8").strip(),
        "<!-- APP -->": (SRC / "app.js").read_text(encoding="utf-8").strip().replace("__WORKSHOP_LINKS__", inline_json(json.loads((SRC / "workshop-links.json").read_text(encoding="utf-8")))),
    }
    for marker, content in parts.items():
        if html.count(marker) != 1:
            raise SystemExit(f"shell.html: expected one {marker}")
        html = html.replace(marker, content)

    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"index.html: {out.stat().st_size} bytes, {len(seed['skills'])} skills, "
          f"{len(seed['projects'])} projects, {len(seed['tools'])} tools")


if __name__ == "__main__":
    build()
