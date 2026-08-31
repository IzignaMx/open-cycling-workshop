#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/api-client/openapi.json"
OUTPUT = ROOT / "packages/api-client/src/generated.ts"


def ts_type(schema: dict[str, object]) -> str:
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[-1]
    if "anyOf" in schema:
        values = [ts_type(item) for item in schema["anyOf"]]  # type: ignore[index]
        return " | ".join(dict.fromkeys(values))
    enum = schema.get("enum")
    if isinstance(enum, list):
        return " | ".join(json.dumps(value) for value in enum)
    kind = schema.get("type")
    if kind == "string":
        return "string"
    if kind in {"integer", "number"}:
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        item_schema = schema.get("items")
        item_type = ts_type(item_schema) if isinstance(item_schema, dict) else "unknown"
        return f"Array<{item_type}>"
    if kind == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"Record<string, {ts_type(additional)}>"
        return "Record<string, unknown>"
    return "unknown"


def render(openapi: dict[str, object]) -> str:
    components = openapi.get("components")
    if not isinstance(components, dict):
        raise ValueError("OpenAPI components missing")
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        raise ValueError("OpenAPI component schemas missing")

    lines = [
        "// Generated from packages/api-client/openapi.json. Do not edit by hand.",
        "",
    ]
    for name in sorted(schemas):
        schema = schemas[name]
        if not isinstance(schema, dict):
            continue
        if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
            lines.append(f"export type {name} = {ts_type(schema)}")
            lines.append("")
            continue
        required = set(schema.get("required", []))
        lines.append(f"export interface {name} {{")
        for field, field_schema in schema["properties"].items():
            field_type = "unknown" if not isinstance(field_schema, dict) else ts_type(field_schema)
            optional = "" if field in required else "?"
            lines.append(f"  {field}{optional}: {field_type}")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    content = render(json.loads(OPENAPI.read_text()))
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text() != content:
            print("TypeScript API client drift detected: regenerate generated.ts")
            return 1
        print("TypeScript API types: OK")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
