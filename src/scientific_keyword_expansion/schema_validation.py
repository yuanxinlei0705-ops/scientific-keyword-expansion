"""Small validator for the project's deliberately limited JSON Schema vocabulary."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def validate(value: Any, spec: dict[str, Any], schema: dict[str, Any], location: str = "$") -> None:
    if "$ref" in spec:
        return validate(value, schema["$defs"][spec["$ref"].split("/")[-1]], schema, location)
    kinds = spec.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    recognized = {"object": lambda v: type(v) is dict, "array": lambda v: type(v) is list,
                  "string": lambda v: type(v) is str, "integer": lambda v: type(v) is int,
                  "number": lambda v: type(v) in (int, float),
                  "null": lambda v: v is None, "boolean": lambda v: type(v) is bool}
    if kinds and not any(recognized[kind](value) for kind in kinds):
        raise ValueError(f"{location}: unexpected type")
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(f"{location}: invalid enum")
    if "const" in spec and value != spec["const"]:
        raise ValueError(f"{location}: invalid constant")
    if type(value) is dict:
        for key in spec.get("required", []):
            if key not in value:
                raise ValueError(f"{location}.{key}: missing")
        properties = spec.get("properties", {})
        if spec.get("additionalProperties") is False and value.keys() - properties.keys():
            raise ValueError(f"{location}: unknown properties")
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], schema, f"{location}.{key}")
    if type(value) is list and "items" in spec:
        for index, item in enumerate(value):
            validate(item, spec["items"], schema, f"{location}[{index}]")
    if type(value) is int:
        if value < spec.get("minimum", value) or value > spec.get("maximum", value):
            raise ValueError(f"{location}: out of range")
    if type(value) is str and len(value) < spec.get("minLength", 0):
        raise ValueError(f"{location}: too short")
    if type(value) is str and spec.get("format") in {"date", "date-time"}:
        try:
            if spec["format"] == "date":
                date.fromisoformat(value)
            else:
                datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{location}: invalid {spec['format']}") from error
