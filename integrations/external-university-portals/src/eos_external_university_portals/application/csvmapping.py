"""Checks on the free-form object settings of a partner connection (csv_mapping, grade_conversion, credit_conversion),
which the small schema checker treats as plain objects."""

from __future__ import annotations

from typing import Any

MAX_ENTRIES = 200


def mapping_issues(settings: dict, columns: list[str]) -> list[dict]:
    issues: list[dict] = []
    mapping = settings.get("csv_mapping")
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            if key not in columns:
                issues.append({"path": f"csv_mapping.{str(key)[:40]}", "code": "unknown_column"})
            elif not isinstance(value, str) or not 1 <= len(value) <= 60:
                issues.append({"path": f"csv_mapping.{key}", "code": "length"})
    for name in ("grade_conversion", "credit_conversion"):
        table = settings.get(name)
        if isinstance(table, dict):
            if len(table) > MAX_ENTRIES:
                issues.append({"path": name, "code": "items_count"})
            for key, value in table.items():
                if len(str(key)) > 60 or not _scalar(value):
                    issues.append({"path": f"{name}.{str(key)[:40]}", "code": "value"})
                    break
    return issues


def _scalar(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return len(value) <= 60
    return isinstance(value, int | float) and value == value and abs(value) < 1e9
