#!/usr/bin/env python3
"""Build tech.html — the workshop technology tree (Civilization-style order of learning).

Sources: tech-src/tech-tree.json (technologies, eras, discoveries), workshop-data.json (plan steps,
purchases, budget ranges), src/seed.json (tool names and starting
inventory; the page reads the live inventory from /api/tech). Run: python3 tech-src/build_tech.py
"""
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
STATUSES = {"done", "active"}
RISKS = {"low", "care", "pro"}


def fail(message):
    raise SystemExit("tech-tree: " + message)


def check(tree, plan, tools):
    eras = {e["id"] for e in tree["eras"]}
    families = set(tree["families"])
    steps = {t["id"] for t in plan["tasks"]}
    catalog = {i["id"] for i in plan["catalog"]}
    modules = {m["id"] for m in plan["modules"]}
    ids = [t["id"] for t in tree["techs"]]
    if len(ids) != len(set(ids)):
        fail("повтор id технологии")
    era_of = {t["id"]: t["era"] for t in tree["techs"]}
    used_steps, used_items = {}, {}
    for t in tree["techs"]:
        tid = t["id"]
        for key in ("title", "gives", "place"):
            if not isinstance(t.get(key), str) or not t[key].strip():
                fail(f"{tid}: нет поля {key}")
        if t["era"] not in eras or t["family"] not in families or t.get("risk") not in RISKS:
            fail(f"{tid}: неизвестная эпоха, семейство или риск")
        if t.get("start") not in (None, *STATUSES):
            fail(f"{tid}: некорректный start")
        for r in t["req"]:
            if r not in era_of:
                fail(f"{tid}: неизвестное требование {r}")
            if era_of[r] > t["era"]:
                fail(f"{tid}: требование {r} из более поздней эпохи")
        for tool in t.get("have", []):
            if tool not in tools:
                fail(f"{tid}: неизвестный инструмент {tool}")
        for item in t.get("buy", []):
            if item not in catalog:
                fail(f"{tid}: неизвестная покупка {item}")
            if item in used_items:
                fail(f"{tid}: покупка {item} уже учтена в {used_items[item]}")
            used_items[item] = tid
        if not set(t.get("optional", [])) <= set(t.get("buy", [])):
            fail(f"{tid}: «по желанию» вне списка покупок")
        for step in t.get("steps", []):
            if step not in steps:
                fail(f"{tid}: неизвестный шаг {step}")
            if step in used_steps:
                fail(f"{tid}: шаг {step} уже учтён в {used_steps[step]}")
            used_steps[step] = tid
        for m in t.get("modules", []):
            if m not in modules:
                fail(f"{tid}: неизвестное направление {m}")
        if not t.get("steps") and not t.get("hours") and t.get("start") != "done":
            fail(f"{tid}: нет ни шагов плана, ни своей оценки часов")
    graph = {t["id"]: t["req"] for t in tree["techs"]}
    marks = {}
    for tid in graph:
        todo = [(tid, False)]
        while todo:
            node, leaving = todo.pop()
            if leaving:
                marks[node] = 2
                continue
            if marks.get(node) == 1:
                fail("цикл в требованиях через " + node)
            if marks.get(node) == 2:
                continue
            marks[node] = 1
            todo.append((node, True))
            todo.extend((r, False) for r in graph[node])
    combo_ids = set()
    for c in tree["combos"]:
        if c["id"] in combo_ids or c["id"] in era_of:
            fail("повтор id открытия " + c["id"])
        combo_ids.add(c["id"])
        if len(c["needs"]) < 2 or any(n not in era_of for n in c["needs"]):
            fail(f"{c['id']}: открытие требует минимум две известные технологии")
    return steps - set(used_steps)


def step_hours(task):
    return round(task["plannedHours"] if task.get("plannedHours") is not None else task["hours"] * 1.25, 2)


def main():
    tree = json.loads((SRC / "tech-tree.json").read_text(encoding="utf-8"))
    plan = json.loads((ROOT / "workshop-data.json").read_text(encoding="utf-8"))
    seed = json.loads((ROOT / "src" / "seed.json").read_text(encoding="utf-8"))
    tools = {t["id"]: t["title"] for t in seed["tools"]}
    # Starting inventory only: live statuses come from /api/tech, so the build stays reproducible.
    inventory = seed.get("inventory", {}) or {}
    unassigned = check(tree, plan, tools)

    used_steps = {s for t in tree["techs"] for s in t.get("steps", [])}
    used_items = {i for t in tree["techs"] for i in t.get("buy", [])}
    used_tools = {x for t in tree["techs"] for x in t.get("have", [])}
    ranges = plan.get("budgetPlanning", {}).get("items", {})
    items = {}
    for item in plan["catalog"]:
        if item["id"] not in used_items:
            continue
        q = item.get("quote") or {}
        r = ranges.get(item["id"])
        items[item["id"]] = {
            "title": item["title"], "kind": item["kind"],
            "quote": {k: q.get(k) for k in ("amount", "currency", "tax", "quantity", "exampleOnly", "vendor", "url")} if q.get("amount") is not None else None,
            "range": [r["low"], r["high"]] if r else None,
        }
    data = {
        "tree": tree,
        "steps": {t["id"]: {"title": t["title"], "hours": step_hours(t), "module": t["module"]} for t in plan["tasks"] if t["id"] in used_steps},
        "items": items,
        "tools": {k: tools[k] for k in sorted(used_tools)},
        "inventory": {k: inventory.get(k, "") for k in sorted(used_tools)},
        "modules": {m["id"]: m["title"] for m in plan["modules"]},
        "estimates": {k: v for k, v in tree.get("estimates", {}).items() if k in used_items},
        "fx": plan["fx"]["rate"],
        "planHours": round(sum(step_hours(t) for t in plan["tasks"]), 1),
    }
    page = (SRC / "template.html").read_text(encoding="utf-8")
    for key, value in [("CSS", (SRC / "tech.css").read_text(encoding="utf-8")),
                       ("JS", (SRC / "tech.js").read_text(encoding="utf-8")),
                       ("DATA", json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"))]:
        page = page.replace("__" + key + "__", value)
    (ROOT / "tech.html").write_text(page, encoding="utf-8")
    print(f"Built tech.html: {len(page.encode())} bytes · {len(tree['techs'])} технологий · "
          f"{len(tree['combos'])} открытий · шагов плана в дереве {len(used_steps)} из {len(plan['tasks'])}")
    if unassigned:
        print("Шаги плана без технологии:", " ".join(sorted(unassigned)), file=sys.stderr)


if __name__ == "__main__":
    main()
