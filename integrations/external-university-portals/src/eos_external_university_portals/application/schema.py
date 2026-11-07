"""A small JSON Schema subset checker (no JSON Schema library is on the approved stack). Issues are {path, code}: a path
names a field, never a value, so they are safe in a log line and in an error detail."""

from __future__ import annotations

import math
import re
from typing import Any

MAX_ISSUES = 200


def _type_ok(kind: str, value: Any) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    return False


def check(schema: dict, value: Any, path: str, issues: list[dict]) -> None:
    if len(issues) >= MAX_ISSUES:
        return
    kind = schema["type"]
    if not _type_ok(kind, value):
        issues.append({"path": path or "$", "code": "type"})
        return
    if kind in ("integer", "number"):
        if isinstance(value, float) and not math.isfinite(value):
            issues.append({"path": path, "code": "not_finite"})
            return
        if "minimum" in schema and value < schema["minimum"]:
            issues.append({"path": path, "code": "minimum"})
        if "maximum" in schema and value > schema["maximum"]:
            issues.append({"path": path, "code": "maximum"})
    elif kind == "string":
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10_000):
            issues.append({"path": path, "code": "length"})
        elif "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            issues.append({"path": path, "code": "pattern"})
        elif "enum" in schema and value not in schema["enum"]:
            issues.append({"path": path, "code": "enum"})
    elif kind == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 100_000):
            issues.append({"path": path, "code": "items_count"})
            return
        for i, item in enumerate(value):
            check(schema["items"], item, f"{path}[{i}]", issues)
    elif kind == "object":
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                issues.append({"path": f"{path}.{name}" if path else name, "code": "required"})
        for name, item in value.items():
            child = f"{path}.{name}" if path else str(name)
            if name not in props:
                if schema.get("additionalProperties") is False:
                    issues.append({"path": child, "code": "unknown_field"})
                continue
            check(props[name], item, child, issues)
