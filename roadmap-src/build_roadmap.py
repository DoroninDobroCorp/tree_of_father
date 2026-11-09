#!/usr/bin/env python3
"""Build the standalone roadmap with validated references and atomic publication."""
import argparse
import json
import os
from pathlib import Path
import tempfile
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def validate(data):
    assert data["schema"] == 2, "Expected minimal roadmap schema 2"
    stages = {s["id"]: s for s in data["stages"]}
    assert len(stages) == len(data["stages"]), "Duplicate stage id"
    sources = {s["id"] for s in data["sources"]}
    assert len(sources) == len(data["sources"]), "Duplicate source id"
    ids = set()
    for item in data["items"]:
        assert item["id"] not in ids, "Duplicate purchase"
        ids.add(item["id"])
        assert item["stage"] in stages, "Unknown purchase stage"
        assert set(item["sources"]) <= sources, "Unknown purchase source"
        assert len(item["cost"]) == 2 and 0 <= item["cost"][0] <= item["cost"][1], "Invalid estimate"
        if item.get("ars"):
            assert len(item["freightUsd"]) == 2 and item["ars"][0] <= item["ars"][1], "Invalid ARS quote"
    seen, pending = set(), set()
    def visit(sid):
        assert sid in stages, "Unknown dependency"
        assert sid not in pending, "Dependency cycle"
        if sid in seen:
            return
        pending.add(sid)
        s = stages[sid]
        assert s["lane"] in {"base", "cnc", "mill"}, "Unexpected active branch"
        for dep in s["deps"]:
            visit(dep)
        assert set(s["buys"]) <= ids, "Unknown stage purchase"
        pending.remove(sid)
        seen.add(sid)
    for sid in stages:
        visit(sid)
    for row in data["bom"]:
        assert row[5] in sources, "Unknown BOM source"
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "roadmap.html")
    args = parser.parse_args()
    data = validate(json.loads((HERE / "roadmap-data.json").read_text()))
    template = (HERE / "template.html").read_text()
    assert template.count("__DATA__") == 1, "Expected one data marker"
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    result = template.replace("__DATA__", payload)
    target = args.output
    fd, name = tempfile.mkstemp(prefix=".roadmap-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(result)
        os.chmod(name, 0o644)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print(f"{target}: {len(result):,} chars; {len(data['stages'])} stages; {len(data['items'])} purchase choices")

if __name__ == "__main__":
    main()
