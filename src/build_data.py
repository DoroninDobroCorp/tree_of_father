#!/usr/bin/env python3
"""Data validator and formatter for initial seed profile.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def build_data():
    seed_file = SRC / "seed.json"
    schema_file = SRC / "proposal.schema.json"

    if not seed_file.is_file():
        print(f"Error: {seed_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Checking seed data consistency...")
    assert data.get("schemaVersion") == 3, "schemaVersion must be 3"
    assert isinstance(data.get("revision"), int), "revision must be integer"
    assert isinstance(data.get("branches"), list), "branches must be list"
    assert isinstance(data.get("skills"), list), "skills must be list"
    assert isinstance(data.get("projects"), list), "projects must be list"
    assert isinstance(data.get("tools"), list), "tools must be list"
    assert isinstance(data.get("events"), list), "events must be list"

    branch_ids = {b["id"] for b in data["branches"]}
    tool_ids = {t["id"] for t in data["tools"]}
    skill_ids = {s["id"] for s in data["skills"]}
    project_ids = {p["id"] for p in data["projects"]}

    assert len(branch_ids) == len(data["branches"]), "Duplicate branch IDs"
    assert len(tool_ids) == len(data["tools"]), "Duplicate tool IDs"
    assert len(skill_ids) == len(data["skills"]), "Duplicate skill IDs"
    assert len(project_ids) == len(data["projects"]), "Duplicate project IDs"

    for s in data["skills"]:
        assert s["branchId"] in branch_ids, f"Skill {s['id']} has invalid branchId {s['branchId']}"
        for p in s.get("prerequisites", []):
            assert p in skill_ids, f"Skill {s['id']} has invalid prerequisite {p}"
        for t in s.get("toolIds", []):
            assert t in tool_ids, f"Skill {s['id']} has invalid toolId {t}"

    for p in data["projects"]:
        for b in p.get("branchIds", []):
            assert b in branch_ids, f"Project {p['id']} has invalid branchId {b}"
        for s in p.get("skillIds", []):
            assert s in skill_ids, f"Project {p['id']} has invalid skillId {s}"
        for t in p.get("toolIds", []):
            assert t in tool_ids, f"Project {p['id']} has invalid toolId {t}"

    caps = {"practice": 80, "theory": 20, "attempt": 15, "historical": 40}
    for e in data["events"]:
        kind = e["kind"]
        assert kind in caps, f"Event {e['id']} has invalid kind {kind}"
        total_xp = sum(a["points"] for a in e.get("allocations", []))
        assert total_xp <= caps[kind], f"Event {e['id']} exceeds cap {caps[kind]}: {total_xp}"
        for a in e.get("allocations", []):
            assert a["skillId"] in skill_ids, f"Event {e['id']} references unknown skill {a['skillId']}"

    # Re-save with clean formatting
    formatted = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    seed_file.write_text(formatted, encoding="utf-8")
    (ROOT / "initial-profile.json").write_text(formatted, encoding="utf-8")

    print(f"Seed data validated successfully:")
    print(f"  Branches: {len(data['branches'])}")
    print(f"  Skills: {len(data['skills'])}")
    print(f"  Projects: {len(data['projects'])}")
    print(f"  Tools: {len(data['tools'])}")
    print(f"  Events: {len(data['events'])}")


if __name__ == "__main__":
    build_data()
