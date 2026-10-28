#!/usr/bin/env python3
"""Validate inert M0 descriptors. Never installs, authorizes or loads a module."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, cast

MAX_BYTES = 16_384
MAX_DEPTH = 8
ERROR_CODES = frozenset(
    {
        "E_INPUT_TYPE",
        "E_SIZE",
        "E_UTF8",
        "E_JSON",
        "E_DUPLICATE_KEY",
        "E_NUMBER",
        "E_DEPTH",
        "E_STRING",
        "E_SCHEMA",
        "E_SCHEMA_DEFINITION",
        "E_IO",
    }
)
SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "packages/plugin-sdk/manifest/descriptor-m0.schema.json"
)
KEYWORDS = frozenset(
    {
        "$schema",
        "title",
        "description",
        "type",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "minLength",
        "maxLength",
        "pattern",
        "maxItems",
        "items",
    }
)


class DescriptorError(ValueError):
    """Fixed code only: raw descriptors may contain mistakenly supplied secrets."""

    def __init__(self, code: str):
        self.code = code if code in ERROR_CODES else "E_SCHEMA_DEFINITION"
        super().__init__(self.code)


def check_schema_definition(schema: object) -> None:
    """Fail closed on our trusted M0 vocabulary; not a general JSON Schema engine."""
    if not isinstance(schema, dict) or set(schema) - KEYWORDS:
        raise DescriptorError("E_SCHEMA_DEFINITION")
    if schema.get("type") not in ("object", "array", "string", "integer"):
        raise DescriptorError("E_SCHEMA_DEFINITION")
    expected_type = {"object": dict, "array": list, "string": str, "integer": int}[schema["type"]]
    if "const" in schema and type(schema["const"]) is not expected_type:
        raise DescriptorError("E_SCHEMA_DEFINITION")
    if "enum" in schema and (
        not isinstance(schema["enum"], list)
        or not schema["enum"]
        or any(type(item) is not expected_type for item in schema["enum"])
    ):
        raise DescriptorError("E_SCHEMA_DEFINITION")
    common = {"$schema", "title", "description", "type", "const", "enum"}
    specific = {
        "object": {"properties", "required", "additionalProperties"},
        "array": {"maxItems", "items"},
        "string": {"minLength", "maxLength", "pattern"},
        "integer": set(),
    }
    if set(schema) - common - specific[schema["type"]]:
        raise DescriptorError("E_SCHEMA_DEFINITION")
    if schema["type"] == "object":
        properties, required = schema.get("properties"), schema.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise DescriptorError("E_SCHEMA_DEFINITION")
        if (
            set(required) != set(properties)
            or len(required) != len(set(required))
            or schema.get("additionalProperties") is not False
        ):
            raise DescriptorError("E_SCHEMA_DEFINITION")
        for child in properties.values():
            check_schema_definition(child)
    if schema["type"] == "array" and (
        type(schema.get("maxItems")) is not int
        or schema.get("maxItems") != 0
        or schema.get("items") is not False
    ):
        raise DescriptorError("E_SCHEMA_DEFINITION")
    for key in ("minLength", "maxLength"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise DescriptorError("E_SCHEMA_DEFINITION")
    if "pattern" in schema:
        if (
            not isinstance(schema["pattern"], str)
            or not schema["pattern"].startswith("^")
            or not schema["pattern"].endswith("$")
        ):
            raise DescriptorError("E_SCHEMA_DEFINITION")
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            raise DescriptorError("E_SCHEMA_DEFINITION") from exc
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise DescriptorError("E_SCHEMA_DEFINITION")


def _load_schema() -> dict[str, Any]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        check_schema_definition(schema)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise DescriptorError("E_SCHEMA_DEFINITION") from exc
    return cast(dict[str, Any], schema)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DescriptorError("E_DUPLICATE_KEY")
        result[key] = value
    return result


def _integer(value: str) -> int:
    if len(value.lstrip("-")) > 10:
        raise DescriptorError("E_NUMBER")
    return int(value)


def _reject_number(_value: str) -> None:
    raise DescriptorError("E_NUMBER")


def _envelope(value: object, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise DescriptorError("E_DEPTH")
    if isinstance(value, str):
        if not value.isprintable() and value != "":
            raise DescriptorError("E_STRING")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise DescriptorError("E_STRING") from exc
    elif isinstance(value, dict):
        for key, item in value.items():
            _envelope(key, depth + 1)
            _envelope(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _envelope(item, depth + 1)


def _validate(value: object, schema: dict[str, Any] | bool) -> None:
    if schema is False:
        raise DescriptorError("E_SCHEMA")
    if schema is True:
        raise DescriptorError("E_SCHEMA_DEFINITION")
    types = {"object": dict, "array": list, "string": str, "integer": int}
    if type(value) is not types[schema["type"]]:
        raise DescriptorError("E_SCHEMA")
    if "const" in schema and value != schema["const"]:
        raise DescriptorError("E_SCHEMA")
    if "enum" in schema and value not in schema["enum"]:
        raise DescriptorError("E_SCHEMA")
    if isinstance(value, dict):
        if set(value) != set(schema["required"]):
            raise DescriptorError("E_SCHEMA")
        for key, item in value.items():
            _validate(item, schema["properties"][key])
    elif isinstance(value, list):
        if len(value) > schema["maxItems"]:
            raise DescriptorError("E_SCHEMA")
        for item in value:
            _validate(item, schema["items"])
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get(
            "maxLength", MAX_BYTES
        ):
            raise DescriptorError("E_SCHEMA")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise DescriptorError("E_SCHEMA")


def validate_descriptor(raw: bytes) -> dict[str, object]:
    """Validate bytes against strict envelope + fixed M0 schema; no runtime effects."""
    if type(raw) is not bytes:
        raise DescriptorError("E_INPUT_TYPE")
    if len(raw) > MAX_BYTES:
        raise DescriptorError("E_SIZE")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DescriptorError("E_UTF8") from exc
    if text.startswith("\ufeff"):
        raise DescriptorError("E_UTF8")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except DescriptorError:
        raise
    except RecursionError as exc:
        raise DescriptorError("E_DEPTH") from exc
    except (ValueError, TypeError) as exc:
        raise DescriptorError("E_JSON") from exc
    _envelope(value)
    _validate(value, _load_schema())
    return cast(dict[str, object], value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("descriptor", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.descriptor.open("rb") as file:
            raw = file.read(MAX_BYTES + 1)
        validate_descriptor(raw)
    except OSError:
        print("E_IO", file=sys.stderr)
        return 1
    except DescriptorError as exc:
        print(exc.code, file=sys.stderr)
        return 1
    print("descriptor valid; runtime not evaluated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
