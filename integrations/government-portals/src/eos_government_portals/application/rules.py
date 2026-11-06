"""Validation: the form's data_schema (a small JSON Schema subset, checked here because no JSON Schema library is on
the approved stack) and the authority's published rules (cross-totals, year ranges, evidence).

An issue is {path, code, severity}. Paths name a field, never a value, so an issue is safe in a log line and in an
operator view: a teacher's name or a student's detail never travels in one.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from .catalogue import AUTHORITIES, FormSpec

MAX_ISSUES = 500
ERROR, WARNING = "error", "warning"


def issue(path: str, code: str, severity: str = ERROR) -> dict:
    return {"path": path, "code": code, "severity": severity}


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
    return False


def check_schema(schema: dict, value: Any, path: str, issues: list[dict]) -> None:
    if len(issues) >= MAX_ISSUES:
        return
    kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
    kind = next((k for k in kinds if _type_ok(k, value)), None)
    if kind is None:
        issues.append(issue(path or "$", "type"))
        return
    if kind in ("integer", "number"):
        if isinstance(value, float) and not math.isfinite(value):
            issues.append(issue(path, "not_finite"))
            return
        if "minimum" in schema and value < schema["minimum"]:
            issues.append(issue(path, "minimum"))
        if "maximum" in schema and value > schema["maximum"]:
            issues.append(issue(path, "maximum"))
    elif kind == "string":
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10_000):
            issues.append(issue(path, "length"))
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            issues.append(issue(path, "pattern"))
        if "enum" in schema and value not in schema["enum"]:
            issues.append(issue(path, "enum"))
    elif kind == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 100_000):
            issues.append(issue(path, "items_count"))
            return
        for i, item in enumerate(value):
            check_schema(schema["items"], item, f"{path}[{i}]", issues)
    elif kind == "object":
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                issues.append(issue(f"{path}.{name}" if path else name, "required"))
        for name, item in value.items():
            child = f"{path}.{name}" if path else str(name)
            if name not in props:
                if schema.get("additionalProperties") is False:
                    issues.append(issue(child, "unknown_field"))
                continue
            check_schema(props[name], item, child, issues)


def _period_start_year(period: str) -> int | None:
    m = re.fullmatch(r"([0-9]{4})(?:-([0-9]{2}))?", period)
    return int(m.group(1)) if m else None


def valid_academic_year(period: str) -> bool:
    m = re.fullmatch(r"([0-9]{4})-([0-9]{2})", period)
    return bool(m) and (int(m.group(1)) + 1) % 100 == int(m.group(2))


def _total(group: dict) -> int:
    return sum(v for v in group.values() if isinstance(v, int))


def _check_year(path: str, year: Any, period: str, issues: list[dict]) -> None:
    start = _period_start_year(period)
    if isinstance(year, int) and start is not None and year > start:
        issues.append(issue(path, "established_after_period"))


def _aishe_rules(spec: FormSpec, period: str, data: dict, issues: list[dict]) -> None:
    kind = {"aishe.dcf-i": "university", "aishe.dcf-ii": "college", "aishe.dcf-iii": "standalone"}[spec.form_code]
    basic = data.get("basic_details", {})
    if basic.get("institution_type") not in (None, kind):
        issues.append(issue("basic_details.institution_type", "form_institution_type_mismatch"))
    _check_year("basic_details.year_of_establishment", basic.get("year_of_establishment"), period, issues)
    for i, prog in enumerate(data.get("programmes", [])):
        gender, category = prog.get("enrolment_by_gender"), prog.get("enrolment_by_category")
        if isinstance(gender, dict) and isinstance(category, dict) and _total(gender) != _total(category):
            issues.append(issue(f"programmes[{i}].enrolment_by_category", "total_mismatch_gender_category"))
        if isinstance(gender, dict) and _total(gender) > prog.get("intake", 0) * 10 and prog.get("intake", 0) > 0:
            issues.append(issue(f"programmes[{i}].enrolment_by_gender", "enrolment_far_above_intake", WARNING))
    names = {p.get("name") for p in data.get("programmes", [])}
    for i, res in enumerate(data.get("examination_results", [])):
        if (
            isinstance(res.get("passed"), int)
            and isinstance(res.get("appeared"), int)
            and res["passed"] > res["appeared"]
        ):
            issues.append(issue(f"examination_results[{i}].passed", "passed_exceeds_appeared"))
        if res.get("programme") not in names:
            issues.append(issue(f"examination_results[{i}].programme", "unknown_programme"))
    fin = data.get("finance", {})
    if isinstance(fin.get("salary_expenditure"), int | float) and isinstance(fin.get("expenditure_total"), int | float):
        if fin["salary_expenditure"] > fin["expenditure_total"]:
            issues.append(issue("finance.salary_expenditure", "salary_exceeds_expenditure"))
    if kind == "college" and "teachers" in data and isinstance(data.get("staff", {}).get("teaching"), dict):
        if len(data["teachers"]) != _total(data["staff"]["teaching"]):
            issues.append(issue("teachers", "teacher_count_mismatch_staff"))
    if kind == "college":
        for i, t in enumerate(data.get("teachers", [])):
            d = t.get("date_of_joining")
            if isinstance(d, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", d):
                try:
                    if date.fromisoformat(d) > date.today():
                        issues.append(issue(f"teachers[{i}].date_of_joining", "date_in_future"))
                except ValueError:
                    issues.append(issue(f"teachers[{i}].date_of_joining", "pattern"))


def _nirf_rules(spec: FormSpec, period: str, data: dict, issues: list[dict]) -> None:
    _check_year(
        "institute.year_of_establishment", data.get("institute", {}).get("year_of_establishment"), period, issues
    )
    go = data.get("go", {})
    if isinstance(go.get("graduating_students"), int):
        for field in ("placed_students", "higher_studies_students"):
            if isinstance(go.get(field), int) and go[field] > go["graduating_students"]:
                issues.append(issue(f"go.{field}", "exceeds_graduating_students"))
        if (
            isinstance(go.get("placed_students"), int)
            and isinstance(go.get("higher_studies_students"), int)
            and go["placed_students"] + go["higher_studies_students"] > go["graduating_students"]
        ):
            issues.append(issue("go.higher_studies_students", "placed_plus_higher_studies_exceeds_graduating", WARNING))
    tlr = data.get("tlr", {})
    if isinstance(tlr.get("total_enrolment"), int) and isinstance(tlr.get("full_time_faculty"), int):
        if tlr["total_enrolment"] > 0 and tlr["full_time_faculty"] == 0:
            issues.append(issue("tlr.full_time_faculty", "no_faculty_for_enrolment", WARNING))


def _naac_rules(spec: FormSpec, period: str, data: dict, issues: list[dict]) -> None:
    _check_year(
        "institute.year_of_establishment", data.get("institute", {}).get("year_of_establishment"), period, issues
    )
    if spec.form_code in ("naac.ssr", "naac.aqar"):
        seen_criteria: set[int] = set()
        seen_metrics: set[str] = set()
        for i, crit in enumerate(data.get("criteria", [])):
            number = crit.get("criterion")
            if number in seen_criteria:
                issues.append(issue(f"criteria[{i}].criterion", "duplicate_criterion"))
            seen_criteria.add(number)
            for j, m in enumerate(crit.get("metrics", [])):
                metric = m.get("metric")
                path = f"criteria[{i}].metrics[{j}]"
                if isinstance(metric, str):
                    if not metric.startswith(f"{number}."):
                        issues.append(issue(f"{path}.metric", "metric_not_in_criterion"))
                    if metric in seen_metrics:
                        issues.append(issue(f"{path}.metric", "duplicate_metric"))
                    seen_metrics.add(metric)
                value = m.get("value")
                if m.get("kind") == "quantitative" and isinstance(value, str):
                    issues.append(issue(f"{path}.value", "quantitative_value_not_numeric"))
                if m.get("kind") == "qualitative" and isinstance(value, int | float) and not isinstance(value, bool):
                    issues.append(issue(f"{path}.value", "qualitative_value_not_text"))


_RULES = {"aishe": _aishe_rules, "nirf": _nirf_rules, "naac": _naac_rules}


def metrics_in(spec: FormSpec, data: dict) -> set[str]:
    """The metric numbers the data speaks of, which evidence is arranged under."""
    if spec.form_code == "naac.dvv-response":
        return {q["metric"] for q in data.get("queries", []) if isinstance(q.get("metric"), str)}
    return {
        m["metric"] for c in data.get("criteria", []) for m in c.get("metrics", []) if isinstance(m.get("metric"), str)
    }


def validate_data(spec: FormSpec, period: str, data: Any) -> list[dict]:
    """Schema first; the authority's rules only when the shape is sound (a rule on a malformed field would only add noise)."""
    issues: list[dict] = []
    if not valid_period(spec, period):
        issues.append(issue("period", "period_format"))
    check_schema(spec.data_schema, data, "", issues)
    if not any(i["severity"] == ERROR for i in issues):
        _RULES[spec.authority](spec, period, data, issues)
    return issues[:MAX_ISSUES]


def valid_period(spec: FormSpec, period: Any) -> bool:
    if not isinstance(period, str) or len(period) > 40 or not re.fullmatch(spec.period_pattern, period):
        return False
    return valid_academic_year(period) if spec.period_kind == "academic_year" else True


def validate_evidence(
    spec: FormSpec, data: dict, evidence: list[dict], found: dict[int, Any], limits: tuple[int, int]
) -> list[dict]:
    """Evidence rules. `found` maps an evidence index to the stored document (absent: the document is missing)."""
    issues: list[dict] = []
    if evidence and not spec.evidence:
        return [issue("evidence", "evidence_not_accepted_for_form")]
    accepts = {a for e in spec.evidence for a in e["accepts"]}
    max_file, max_total = limits
    total = 0
    known = metrics_in(spec, data) if spec.evidence else set()
    for i, ev in enumerate(evidence):
        doc = found.get(i)
        if doc is None:
            issues.append(issue(f"evidence[{i}].document_id", "evidence_missing"))
            continue
        ext = doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
        if ext not in accepts:
            issues.append(issue(f"evidence[{i}].document_id", "evidence_type_not_accepted"))
        if len(doc.content) > max_file:
            issues.append(issue(f"evidence[{i}].document_id", "evidence_too_large"))
        total += len(doc.content)
        if ev["metric"] not in known:
            issues.append(issue(f"evidence[{i}].metric", "evidence_metric_not_in_data", WARNING))
    if total > max_total:
        issues.append(issue("evidence", "package_too_large"))
    if spec.form_code == "naac.dvv-response":
        have = {ev["metric"] for ev in evidence}
        for i, q in enumerate(data.get("queries", [])):
            if q["metric"] not in have:
                issues.append(issue(f"queries[{i}].metric", "evidence_required"))
    return issues


def evidence_shape_issues(evidence: Any) -> list[dict]:
    """The evidence argument itself: a list of {metric, document_id, title}, bounded."""
    schema = {
        "type": "array",
        "maxItems": 2000,
        "items": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "pattern": r"^[1-7]\.[0-9]{1,2}(\.[0-9]{1,2})?$"},
                "document_id": {
                    "type": "string",
                    "pattern": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
                },
                "title": {"type": "string", "minLength": 1, "maxLength": 200},
            },
            "required": ["metric", "document_id", "title"],
            "additionalProperties": False,
        },
    }
    issues: list[dict] = []
    check_schema(schema, evidence, "evidence", issues)
    return issues


__all__ = ["AUTHORITIES", "validate_data", "validate_evidence", "evidence_shape_issues", "metrics_in", "valid_period"]
