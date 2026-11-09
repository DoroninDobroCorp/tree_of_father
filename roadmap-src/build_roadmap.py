#!/usr/bin/env python3
"""Собирает roadmap.html из roadmap-data.json и template.html (без внешних зависимостей)."""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


def main() -> int:
    data = json.loads((HERE / "roadmap-data.json").read_text(encoding="utf-8"))
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    if "__DATA__" not in tpl:
        print("В шаблоне нет маркера __DATA__", file=sys.stderr)
        return 1
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    out = tpl.replace("__DATA__", payload)
    target = ROOT / "roadmap.html"
    target.write_text(out, encoding="utf-8")
    print(f"roadmap.html: {len(out):,} байт, этапов: {len(data['stages'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
