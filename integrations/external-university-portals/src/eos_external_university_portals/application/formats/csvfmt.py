"""CSV transcripts: one row per entry, with the learner and programme repeated on each row so a row stands alone.

Column names are the port's own; a partner whose spreadsheet uses other headers has a `csv_mapping` setting
({our column: their header}) that renames them on the way out and back on the way in. Text a spreadsheet would run
as a formula is prefixed with an apostrophe on the way out and stripped on the way in.
"""

from __future__ import annotations

import csv
import io
import math
import re
from datetime import date
from typing import Any

from ..transcript import CREDIT_SYSTEMS, STATUSES, num

COLUMNS = [
    "partner_student_id", "learner_name", "date_of_birth", "programme_code", "programme_name", "course_code", "title",
    "credits", "credit_system", "grade", "grade_scheme", "grade_point", "term", "started_on", "completed_on", "status",
]  # fmt: skip
REQUIRED = ("course_code", "title", "credits", "status")
MAX_ROWS = 5000
BOM = "﻿"


class CsvError(ValueError):
    """The file is not a CSV transcript this reader can open. The message never quotes the file."""


def _safe(text: str) -> str:
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _unsafe(text: str) -> str:
    return text[1:] if text[:1] == "'" and text[1:2] in ("=", "+", "-", "@", "\t", "\r") else text


def write(transcript: dict, mapping: dict[str, str]) -> bytes:
    header = [mapping.get(c, c) for c in COLUMNS]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    lr, pr = transcript["learner"], transcript["programme"]
    for e in transcript["entries"]:
        row = {
            "partner_student_id": lr.get("partner_student_id", ""),
            "learner_name": lr["name"],
            "date_of_birth": lr["date_of_birth"],
            "programme_code": pr["code"],
            "programme_name": pr["name"],
            "course_code": e["course_code"],
            "title": e["title"],
            "credits": num(e["credits"]),
            "credit_system": e["credit_system"],
            "grade": e.get("grade", ""),
            "grade_scheme": e.get("grade_scheme", ""),
            "grade_point": num(e["grade_point"]) if "grade_point" in e else "",
            "term": e.get("term", ""),
            "started_on": e.get("started_on", ""),
            "completed_on": e.get("completed_on", ""),
            "status": e["status"],
        }
        w.writerow([_safe(str(row[c])) for c in COLUMNS])
    return (BOM + buf.getvalue()).encode("utf-8")


def _valid_date(text: str) -> bool:
    try:
        return bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text)) and bool(date.fromisoformat(text))
    except ValueError:
        return False


def read(content: bytes, mapping: dict[str, str]) -> tuple[dict, list[dict], str]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise CsvError("not UTF-8 text") from e
    if "\x00" in text:
        raise CsvError("not a text file")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as e:
        raise CsvError("empty file") from e
    index = {name.strip(): i for i, name in enumerate(header)}
    column = {c: index.get(mapping.get(c, c)) for c in COLUMNS}
    missing = [c for c in REQUIRED if column[c] is None]
    if missing:
        raise CsvError(f"missing column(s): {', '.join(missing)}")
    unmapped: list[dict] = []
    entries: list[dict] = []
    learner: dict[str, Any] = {}
    programme: dict[str, Any] = {}

    def cell(row: list[str], c: str) -> str:
        i = column[c]
        return _unsafe(row[i].strip()) if i is not None and i < len(row) else ""

    try:
        for n, row in enumerate(reader, start=2):
            if n - 1 > MAX_ROWS:
                unmapped.append({"position": f"row {n}", "reason": "too_many_rows"})
                break
            if not any(x.strip() for x in row):
                continue
            position = f"row {n}"
            if not learner:
                learner = {
                    k: v
                    for k, v in (
                        ("name", cell(row, "learner_name")),
                        ("partner_student_id", cell(row, "partner_student_id")),
                    )
                    if v
                }
                if _valid_date(d := cell(row, "date_of_birth")):
                    learner["date_of_birth"] = d
                programme = {
                    k: v for k, v in (("code", cell(row, "programme_code")), ("name", cell(row, "programme_name"))) if v
                }
            title, status = cell(row, "title"), cell(row, "status").lower().replace("-", "_")
            if not title:
                unmapped.append({"position": position, "reason": "missing_title"})
                continue
            if status not in STATUSES:
                unmapped.append({"position": position, "reason": "unknown_status"})
                continue
            try:
                credits = float(cell(row, "credits"))
            except ValueError:
                unmapped.append({"position": position, "reason": "bad_credit_value"})
                continue
            if not math.isfinite(credits) or not 0 <= credits <= 1000:
                unmapped.append({"position": position, "reason": "bad_credit_value"})
                continue
            system = cell(row, "credit_system").lower()
            entry: dict[str, Any] = {
                "course_code": cell(row, "course_code"),
                "title": title[:300],
                "credits": credits,
                "credit_system": system if system in CREDIT_SYSTEMS else "other",
                "status": status,
            }
            for key, limit in (("grade", 30), ("grade_scheme", 60), ("term", 60)):
                if v := cell(row, key):
                    entry[key] = v[:limit]
            if v := cell(row, "grade_point"):
                try:
                    gp = float(v)
                    if math.isfinite(gp) and 0 <= gp <= 100:
                        entry["grade_point"] = gp
                    else:
                        unmapped.append({"position": position, "reason": "bad_grade_point"})
                except ValueError:
                    unmapped.append({"position": position, "reason": "bad_grade_point"})
            for key in ("started_on", "completed_on"):
                if v := cell(row, key):
                    if _valid_date(v):
                        entry[key] = v
                    else:
                        unmapped.append({"position": position, "reason": "bad_date"})
            entries.append(entry)
    except csv.Error as e:
        raise CsvError("malformed CSV") from e
    return {"learner": learner, "issuer": {}, "programme": programme, "entries": entries}, unmapped, "unsigned"
