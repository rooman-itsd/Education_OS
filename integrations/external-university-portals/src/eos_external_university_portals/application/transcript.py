"""The normalised transcript of the inter-institution-records port, its schema, and the checks every format writer
relies on. Nothing here depends on a file format."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from . import schema

UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
DATE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
CREDIT_SYSTEMS = ["indian_credit", "ects", "other"]
STATUSES = ["passed", "failed", "in_progress"]
FORMATS = ["pdf", "csv", "elmo_xml", "edc_jsonld"]


def _s(maxlen: int, minlen: int = 1, **extra: Any) -> dict:
    return {"type": "string", "minLength": minlen, "maxLength": maxlen, **extra}


def _o(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TRANSCRIPT_SCHEMA = _o(
    {
        "learner": _o(
            {
                "person_id": _s(36, pattern=UUID),
                "name": _s(200),
                "given_names": _s(200),
                "family_name": _s(100),
                "date_of_birth": _s(10, pattern=DATE),
                "apaar_id": _s(40, pattern=r"^[A-Za-z0-9-]{1,40}$"),
                "partner_student_id": _s(60, pattern=r"^[A-Za-z0-9._/-]{1,60}$"),
                "email": _s(254, pattern=r"^[^@\s]{1,64}@[^@\s]{1,189}$"),
            },
            ["name", "date_of_birth"],
        ),
        "issuer": _o(
            {
                "institution_name": _s(200),
                "institution_code": _s(60),
                "country": _s(2, pattern=r"^[A-Z]{2}$"),
                "url": _s(300, pattern=r"^https?://[^\s]{1,290}$"),
            },
            ["institution_name", "institution_code", "country"],
        ),
        "programme": _o(
            {
                "code": _s(60),
                "name": _s(200),
                "level": _s(60),
                "eqf_level": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            ["code", "name", "level"],
        ),
        "entries": {
            "type": "array",
            "minItems": 1,
            "maxItems": 500,
            "items": _o(
                {
                    "course_code": _s(60),
                    "title": _s(300),
                    "credits": {"type": "number", "minimum": 0, "maximum": 1000},
                    "credit_system": {"type": "string", "enum": CREDIT_SYSTEMS},
                    "grade": _s(30),
                    "grade_scheme": _s(60),
                    "grade_point": {"type": "number", "minimum": 0, "maximum": 100},
                    "term": _s(60),
                    "started_on": _s(10, pattern=DATE),
                    "completed_on": _s(10, pattern=DATE),
                    "status": {"type": "string", "enum": STATUSES},
                },
                ["course_code", "title", "credits", "credit_system", "status"],
            ),
        },
        "totals": _o(
            {
                "credits_earned": {"type": "number", "minimum": 0, "maximum": 100_000},
                "cgpa": {"type": "number", "minimum": 0, "maximum": 100},
            },
            [],
        ),
        "issued_on": _s(10, pattern=DATE),
    },
    ["learner", "issuer", "programme", "entries", "issued_on"],
)


def _valid_date(text: Any) -> bool:
    try:
        return isinstance(text, str) and bool(re.fullmatch(DATE, text)) and bool(date.fromisoformat(text))
    except ValueError:
        return False


def validate(transcript: Any) -> list[dict]:
    """Issues as {path, code}; empty when the transcript can be written in any format."""
    issues: list[dict] = []
    schema.check(TRANSCRIPT_SCHEMA, transcript, "", issues)
    if issues:
        return issues
    paths = [("learner.date_of_birth", transcript["learner"]["date_of_birth"]), ("issued_on", transcript["issued_on"])]
    for i, e in enumerate(transcript["entries"]):
        paths += [(f"entries[{i}].{k}", e[k]) for k in ("started_on", "completed_on") if k in e]
    for path, value in paths:
        if not _valid_date(value):
            issues.append({"path": path, "code": "date"})
    if not issues:
        for i, e in enumerate(transcript["entries"]):
            if "started_on" in e and "completed_on" in e and e["completed_on"] < e["started_on"]:
                issues.append({"path": f"entries[{i}].completed_on", "code": "before_start"})
        if transcript["learner"]["date_of_birth"] > transcript["issued_on"]:
            issues.append({"path": "learner.date_of_birth", "code": "after_issue"})
        systems = {e["credit_system"] for e in transcript["entries"]}
        earned = transcript.get("totals", {}).get("credits_earned")
        if earned is not None and len(systems) == 1:
            total = sum(e["credits"] for e in transcript["entries"] if e["status"] == "passed")
            if abs(total - earned) > 0.01:
                issues.append({"path": "totals.credits_earned", "code": "total_mismatch"})
    return issues


def split_name(learner: dict) -> tuple[str, str]:
    """(given names, family name). Explicit fields win; otherwise the last word of `name` is the family name."""
    if learner.get("given_names") and learner.get("family_name"):
        return learner["given_names"], learner["family_name"]
    parts = learner["name"].split()
    if len(parts) <= 1:
        return learner["name"], learner["name"]
    return " ".join(parts[:-1]), parts[-1]


def num(value: float) -> str:
    """A number without a trailing .0 and without exponent notation."""
    from decimal import Decimal

    return format(Decimal(repr(float(value))).normalize(), "f") if not float(value).is_integer() else str(int(value))
