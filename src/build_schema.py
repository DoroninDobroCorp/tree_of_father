#!/usr/bin/env python3
"""JSON Schema builder and validator for OpenAI Structured Outputs.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def validate_openai_strict_schema(schema, path=""):
    """Verify that schema conforms to OpenAI Structured Outputs requirements:
    1. additionalProperties must be explicitly False on all object schemas
    2. required must contain all keys from properties
    """
    if not isinstance(schema, dict):
        return

    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, (
            f"OpenAI strict requirement violated at {path}: additionalProperties must be False"
        )
        props = set(schema.get("properties", {}).keys())
        req = set(schema.get("required", []))
        diff = props - req
        assert not diff, (
            f"OpenAI strict requirement violated at {path}: properties {diff} missing from required"
        )
        for k, v in schema.get("properties", {}).items():
            validate_openai_strict_schema(v, f"{path}.{k}")

    if "$defs" in schema:
        for k, v in schema["$defs"].items():
            validate_openai_strict_schema(v, f"$defs.{k}")

    if "items" in schema:
        validate_openai_strict_schema(schema["items"], f"{path}[]")

    if "anyOf" in schema:
        for i, variant in enumerate(schema["anyOf"]):
            validate_openai_strict_schema(variant, f"{path}.anyOf[{i}]")


def build_schema():
    schema_file = SRC / "proposal.schema.json"
    if not schema_file.is_file():
        print(f"Error: {schema_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)

    print("Validating schema against OpenAI Structured Outputs rules...")
    validate_openai_strict_schema(schema)

    formatted = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    schema_file.write_text(formatted, encoding="utf-8")
    print(f"Schema validated and formatted successfully: {schema_file}")


if __name__ == "__main__":
    build_schema()
