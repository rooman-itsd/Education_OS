"""Pure functions: row validation and the depositories' upload files. Nothing here touches the database or the
network, so the files are tested byte for byte against golden files (tests/fixtures/golden).

Upload file format, template version 1 (NAD_AWARDS_CSV_TEMPLATE_VERSION, NAD_CREDITS_CSV_TEMPLATE_VERSION). The
columns follow the examples in NAD guidance listed in docs/prd.md; the depositories' own templates sit behind each
institution's login, so the column set is fixed here until the first institution downloads them (PRD open
question 1) and then changes by bumping the version, never silently.

- UTF-8 without a byte-order mark, comma separated, fields quoted only when they must be, CRLF line ends, one header
  row, one row per learner (awards) or per learner and course (credits).
- Dates DD/MM/YYYY. Marks, credits and grade points as plain decimals without trailing zeros; CGPA and percentage
  with two decimals. Text is collapsed to single spaces; a value that a spreadsheet would read as a formula
  (starts with = + - @) is prefixed with an apostrophe.
- Awards carry up to 12 subjects as repeated column groups; a record with more is refused (`too_many_courses`).
- MARKS REC STATUS is N for a new record and M for a correction.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError

from ..application.schemas import AwardRecord, CreditRecord

MAX_SUBJECTS = 12
MAX_ERRORS = 1000
NEEDS_COURSES = ("marksheet", "grade_card", "consolidated_marksheet")
MIN_DOB = date(1900, 1, 1)

AWARD_HEAD = [
    "NAD INSTITUTION ID", "INSTITUTION NAME", "REGISTRATION NO", "CANDIDATE NAME", "MOTHER NAME", "FATHER NAME",
    "GENDER", "DATE OF BIRTH", "ABC ID", "COURSE NAME", "PROGRAMME CODE", "PROGRAMME LEVEL", "MODE OF STUDY",
    "SESSION", "TERM", "EXAM MONTH", "EXAM YEAR", "RESULT", "DIVISION", "CGPA", "PERCENTAGE", "TOTAL CREDITS",
    "CERTIFICATE NO", "DATE OF ISSUE",
]  # fmt: skip
SUBJECT_FIELDS = ["CODE", "NAME", "MAX MARKS", "MARKS", "GRADE", "GRADE POINT", "CREDITS"]
AWARD_COLUMNS = {
    "1": AWARD_HEAD
    + [f"SUBJECT {n} {f}" for n in range(1, MAX_SUBJECTS + 1) for f in SUBJECT_FIELDS]
    + ["MARKS REC STATUS"]
}
CREDIT_COLUMNS = {
    "1": [
        "ABC INSTITUTION ID", "ABC ID", "STUDENT NAME", "DATE OF BIRTH", "PROGRAMME CODE", "SESSION", "TERM",
        "COURSE CODE", "COURSE TITLE", "CREDITS EARNED", "GRADE", "GRADE POINT", "COMPLETED ON",
    ]
}  # fmt: skip


@dataclass(frozen=True)
class RowError:
    row: int
    field: str
    code: str

    def to_dict(self) -> dict:
        return {"row": self.row, "field": self.field, "code": self.code}


# ---------------------------------------------------------------- identity


def apaar_hash(pepper: str, organisation_id: str, apaar_id: str) -> str:
    """A keyed hash so a correction can be matched to its award without keeping the id in clear."""
    return hmac.new(pepper.encode(), f"{organisation_id}|{apaar_id}".encode(), hashlib.sha256).hexdigest()


def payload_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- validation


class _Rows:
    """Collects row errors, bounded, so a huge broken batch cannot make a huge answer."""

    def __init__(self) -> None:
        self.errors: list[RowError] = []
        self.bad_rows: set[int] = set()
        self.count = 0  # every error, including those past the cap

    def add(self, row: int, field: str, code: str) -> None:
        self.count += 1
        self.bad_rows.add(row)
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(RowError(row, field, code))


def parse_record(model: type[BaseModel], raw: Any, row: int, out: _Rows):
    if not isinstance(raw, dict):
        out.add(row, "record", "invalid")
        return None
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        for err in e.errors()[:20]:
            # list positions are 1-based, like row numbers and the semantic checks below
            loc = ".".join(str(p + 1 if isinstance(p, int) else p) for p in err["loc"]) or "record"
            out.add(row, loc, "missing" if err["type"] == "missing" else "invalid")
        return None


def _in_range(value: float | None, low: float, high: float) -> bool:
    return value is None or low <= value <= high


def check_learner(learner, row: int, out: _Rows, today: date, *, prefix: str = "learner") -> None:
    if learner is None:
        out.add(row, prefix, "missing")
        return
    if not (learner.name or "").strip():
        out.add(row, f"{prefix}.name", "missing")
    if learner.date_of_birth is None:
        out.add(row, f"{prefix}.date_of_birth", "missing")
    elif not MIN_DOB <= learner.date_of_birth <= today:
        out.add(row, f"{prefix}.date_of_birth", "out_of_range")
    apaar = (learner.apaar_id or "").strip()
    if not apaar:
        out.add(row, f"{prefix}.apaar_id", "apaar_missing")  # refused unless the institution decides otherwise (Q4)
    elif not (len(apaar) == 12 and apaar.isascii() and apaar.isdigit()):
        out.add(row, f"{prefix}.apaar_id", "apaar_invalid")
    if not (learner.enrolment_number or "").strip():
        out.add(row, f"{prefix}.enrolment_number", "missing")


def _printable(value: str) -> bool:
    return bool(value.strip()) and not any(unicodedata.category(c).startswith("C") for c in value)


def validate_awards(records: list, *, award_kind: str, today: date) -> tuple[list[tuple[int, AwardRecord]], _Rows]:
    out = _Rows()
    good: list[tuple[int, AwardRecord]] = []
    seen: set[str] = set()
    for i, raw in enumerate(records, start=1):
        rec = parse_record(AwardRecord, raw, i, out)
        if rec is None:
            continue
        before = out.count
        check_learner(rec.learner, i, out, today)
        number = (rec.award_number or "").strip()
        if not number:
            out.add(i, "award_number", "missing")
        elif not _printable(number):
            out.add(i, "award_number", "invalid")
        elif number in seen:
            out.add(i, "award_number", "duplicate")
        seen.add(number)
        r = rec.result
        if r is None:
            out.add(i, "result", "missing")
        else:
            if not (r.result_status or "").strip():
                out.add(i, "result.result_status", "missing")
            if r.cgpa is None and r.percentage is None and not (r.division or "").strip():
                out.add(i, "result", "missing")
            if not _in_range(r.cgpa, 0, 10):
                out.add(i, "result.cgpa", "out_of_range")
            if not _in_range(r.percentage, 0, 100):
                out.add(i, "result.percentage", "out_of_range")
        if rec.issued_on is None:
            out.add(i, "issued_on", "missing")
        elif not date(1990, 1, 1) <= rec.issued_on <= today + timedelta(days=366):
            out.add(i, "issued_on", "out_of_range")
        if award_kind in NEEDS_COURSES and not rec.courses:
            out.add(i, "courses", "missing")
        if len(rec.courses) > MAX_SUBJECTS:
            out.add(i, "courses", "too_many_courses")
        for n, c in enumerate(rec.courses[:MAX_SUBJECTS], start=1):
            f = f"courses.{n}"
            if not (c.code or "").strip():
                out.add(i, f"{f}.code", "missing")
            if not (c.title or "").strip():
                out.add(i, f"{f}.title", "missing")
            if c.marks is None and not (c.grade or "").strip():
                out.add(i, f"{f}.marks", "missing")
            if not _in_range(c.credits, 0, 30):
                out.add(i, f"{f}.credits", "out_of_range")
            if not _in_range(c.grade_point, 0, 10):
                out.add(i, f"{f}.grade_point", "out_of_range")
            if c.max_marks is not None and not 0 < c.max_marks <= 1000:
                out.add(i, f"{f}.max_marks", "out_of_range")
            if c.marks is not None and not 0 <= c.marks <= (c.max_marks or 1000):
                out.add(i, f"{f}.marks", "out_of_range")
        if out.count == before:
            good.append((i, rec))
    return good, out


def validate_credits(records: list, *, today: date) -> tuple[list[tuple[int, CreditRecord]], _Rows]:
    out = _Rows()
    good: list[tuple[int, CreditRecord]] = []
    seen: set[tuple[str, str]] = set()
    for i, raw in enumerate(records, start=1):
        rec = parse_record(CreditRecord, raw, i, out)
        if rec is None:
            continue
        before = out.count
        check_learner(rec.learner, i, out, today)
        if not (rec.programme_code or "").strip():
            out.add(i, "programme_code", "missing")
        if not rec.courses:
            out.add(i, "courses", "missing")
        apaar = ((rec.learner.apaar_id if rec.learner else "") or "").strip()
        for n, c in enumerate(rec.courses, start=1):
            f = f"courses.{n}"
            code = (c.code or "").strip()
            if not code:
                out.add(i, f"{f}.code", "missing")
            elif apaar and (apaar, code) in seen:
                out.add(i, f"{f}.code", "duplicate")
            seen.add((apaar, code))
            if not (c.title or "").strip():
                out.add(i, f"{f}.title", "missing")
            if c.credits_earned is None:
                out.add(i, f"{f}.credits_earned", "missing")
            elif not 0 <= c.credits_earned <= 30:
                out.add(i, f"{f}.credits_earned", "out_of_range")
            if not _in_range(c.grade_point, 0, 10):
                out.add(i, f"{f}.grade_point", "out_of_range")
            if c.completed_on is None:
                out.add(i, f"{f}.completed_on", "missing")
            elif not date(1990, 1, 1) <= c.completed_on <= today:
                out.add(i, f"{f}.completed_on", "out_of_range")
        if out.count == before:
            good.append((i, rec))
    return good, out


# ---------------------------------------------------------------- files


def text(value: object) -> str:
    s = " ".join(unicodedata.normalize("NFC", str(value)).split()) if value is not None else ""
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def num(value: float | None) -> str:
    if value is None:
        return ""
    d = Decimal(str(value))
    return format(d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize(), "f")


def fixed2(value: float | None) -> str:
    return "" if value is None else format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def dmy(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def render(columns: list[str], rows: list[list[str]]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def award_row(
    rec: AwardRecord, *, programme, institution_id: str, institution_name: str, session: str, correction: bool
) -> list[str]:
    learner, result = rec.learner, rec.result
    issued = rec.issued_on
    row = [
        text(institution_id), text(institution_name), text(learner.enrolment_number), text(learner.name),
        text(learner.mother_name), text(learner.father_name), learner.gender or "", dmy(learner.date_of_birth),
        (learner.apaar_id or "").strip(), text(programme.name), text(programme.code), text(programme.level),
        text(programme.mode_of_study), session, text(rec.term), f"{issued.month:02d}", f"{issued.year:04d}",
        text(result.result_status).upper(), text(result.division), fixed2(result.cgpa), fixed2(result.percentage),
        num(sum(c.credits for c in rec.courses if c.credits is not None) if any(c.credits is not None for c in rec.courses) else None),
        text(rec.award_number), dmy(issued),
    ]  # fmt: skip
    for n in range(MAX_SUBJECTS):
        c = rec.courses[n] if n < len(rec.courses) else None
        row += (
            [
                text(c.code),
                text(c.title),
                num(c.max_marks),
                num(c.marks),
                text(c.grade),
                num(c.grade_point),
                num(c.credits),
            ]
            if c
            else [""] * len(SUBJECT_FIELDS)
        )
    row.append("M" if correction else "N")
    return row


def credit_rows(rec: CreditRecord, *, institution_id: str, session: str, term: str) -> list[list[str]]:
    learner = rec.learner
    return [
        [
            text(institution_id),
            (learner.apaar_id or "").strip(),
            text(learner.name),
            dmy(learner.date_of_birth),
            text(rec.programme_code),
            session,
            text(term),
            text(c.code),
            text(c.title),
            num(c.credits_earned),
            text(c.grade),
            num(c.grade_point),
            dmy(c.completed_on),
        ]  # fmt: skip
        for c in rec.courses
    ]
