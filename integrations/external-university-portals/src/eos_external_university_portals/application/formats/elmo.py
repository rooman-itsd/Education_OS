"""EMREX ELMO XML (elmo-schemas v2, https://github.com/emrex-eu/elmo-schemas, MIT) writer and reader.

Reading never trusts the file: no DOCTYPE or entity declaration is accepted (no entity expansion, no external
entities), the size is bounded by the caller, and every element is looked up by an exact path rather than walked
recursively. A signature in a file is reported (integrity `failed`, since this release cannot verify it), never
silently ignored.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405  untrusted input is screened by _screen() before parsing
from datetime import datetime
from typing import Any

from ..transcript import num, split_name

NS = "https://github.com/emrex-eu/elmo-schemas/tree/v2"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
DSIG = "{http://www.w3.org/2000/09/xmldsig#}Signature"
SCHEME = {"ects": "ects", "indian_credit": "indian_credit", "other": "other"}
STATUS_OUT = {"passed": "passed", "failed": "failed", "in_progress": "in-progress"}
STATUS_IN = {v: k for k, v in STATUS_OUT.items()}

ET.register_namespace("", NS)


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, _q(tag), attrs)
    if text is not None:
        el.text = text
    return el


def _title(parent: ET.Element, text: str) -> None:
    ET.SubElement(parent, _q("title"), {XML_LANG: "en"}).text = text


def write(transcript: dict, generated_at: datetime) -> bytes:
    root = ET.Element(_q("elmo"))
    _sub(root, "generatedDate", generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"))
    learner = _sub(root, "learner")
    lr = transcript["learner"]
    if "partner_student_id" in lr:
        _sub(learner, "identifier", lr["partner_student_id"], type="partnerStudentId")
    if "apaar_id" in lr:
        _sub(learner, "identifier", lr["apaar_id"], type="apaar")
    given, family = split_name(lr)
    _sub(learner, "givenNames", given)
    _sub(learner, "familyName", family)
    _sub(learner, "dateOfBirth", lr["date_of_birth"])
    report = _sub(root, "report")
    issuer = _sub(report, "issuer")
    iss = transcript["issuer"]
    _sub(issuer, "country", iss["country"], type="ISO")
    _sub(issuer, "identifier", iss["institution_code"], type="local")
    _title(issuer, iss["institution_name"])
    _sub(issuer, "url", iss["url"])  # required by the schema; the caller must supply it for this format
    prog = transcript["programme"]
    spec = _sub(report, "learningOpportunitySpecification")
    _sub(spec, "identifier", prog["code"], type="local")
    _title(spec, prog["name"])
    _sub(spec, "type", "Degree Programme")
    instance = _sub(_sub(spec, "specifies"), "learningOpportunityInstance")  # the schema requires it, even when empty
    if "eqf_level" in prog:
        level = _sub(instance, "level")
        _sub(level, "type", "EQF")
        _sub(level, "value", str(prog["eqf_level"]))
    for e in transcript["entries"]:
        part = _sub(_sub(spec, "hasPart"), "learningOpportunitySpecification")
        _sub(part, "identifier", e["course_code"], type="local")
        _title(part, e["title"])
        _sub(part, "type", "Course")
        inst = _sub(_sub(part, "specifies"), "learningOpportunityInstance")
        if "started_on" in e:
            _sub(inst, "start", e["started_on"])
        if "completed_on" in e:
            _sub(inst, "date", e["completed_on"])
        if "term" in e and "started_on" in e and "completed_on" in e:  # the schema wants title, start and end together
            term = _sub(inst, "academicTerm")
            _title(term, e["term"])
            _sub(term, "start", e["started_on"])
            _sub(term, "end", e["completed_on"])
        _sub(inst, "status", STATUS_OUT[e["status"]])
        if "grade_scheme" in e:
            _sub(inst, "gradingSchemeLocalId", e["grade_scheme"])
        if "grade" in e:
            _sub(inst, "resultLabel", e["grade"])
        credit = _sub(inst, "credit")
        _sub(credit, "scheme", SCHEME[e["credit_system"]])
        _sub(credit, "value", num(e["credits"]))
    _sub(report, "issueDate", transcript["issued_on"] + "T00:00:00Z")
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


# ------------------------------------------------------------------ reading


class ElmoError(ValueError):
    """The file is not an ELMO v2 document this reader can open. The message never quotes the file."""


def _screen(content: bytes) -> None:
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ElmoError("DOCTYPE and entity declarations are not accepted")


def _text(el: ET.Element | None) -> str | None:
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


def _lang_title(parent: ET.Element) -> str | None:
    titles = parent.findall(_q("title"))
    for t in titles:
        if t.get(XML_LANG, "").lower().startswith("en") and _text(t):
            return _text(t)
    return _text(titles[0]) if titles else None


def _date(value: str | None) -> str | None:
    if value and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value[:10]):
        return value[:10]
    return None


def read(content: bytes) -> tuple[dict, list[dict], str]:
    """(transcript, unmapped, integrity). Raises ElmoError for a file that is not ELMO v2."""
    _screen(content)
    try:
        root = ET.fromstring(content)  # noqa: S314  screened above: no DTD, no entities
    except (ET.ParseError, ValueError) as e:
        raise ElmoError("not well-formed XML") from e
    if root.tag != _q("elmo"):
        raise ElmoError("not an ELMO v2 document")
    unmapped: list[dict] = []
    integrity = "failed" if any(el.tag == DSIG for el in root.iter()) else "unsigned"

    learner = root.find(_q("learner"))
    report = root.find(_q("report"))
    if learner is None or report is None:
        raise ElmoError("an ELMO document needs a learner and a report")
    given, family = _text(learner.find(_q("givenNames"))), _text(learner.find(_q("familyName")))
    out_learner: dict[str, Any] = {"name": " ".join(x for x in (given, family) if x)}
    if given:
        out_learner["given_names"] = given
    if family:
        out_learner["family_name"] = family
    if dob := _date(_text(learner.find(_q("dateOfBirth")))):
        out_learner["date_of_birth"] = dob
    for ident in learner.findall(_q("identifier")):
        kind, value = ident.get("type"), _text(ident)
        if value and kind == "partnerStudentId":
            out_learner["partner_student_id"] = value
        elif value and kind == "apaar":
            out_learner["apaar_id"] = value

    issuer = report.find(_q("issuer"))
    out_issuer: dict[str, Any] = {}
    if issuer is not None:
        out_issuer = {
            "institution_name": _lang_title(issuer) or "",
            "institution_code": next((_text(i) for i in issuer.findall(_q("identifier")) if _text(i)), "") or "",
            "country": _text(issuer.find(_q("country"))) or "",
        }

    programme: dict[str, Any] = {}
    entries: list[dict] = []

    def visit(spec: ET.Element, position: str, depth: int) -> None:
        kind = (_text(spec.find(_q("type"))) or "").lower()
        title = _lang_title(spec)
        code = next((_text(i) for i in spec.findall(_q("identifier")) if i.get("type") == "local" and _text(i)), None)
        instance = spec.find(f"{_q('specifies')}/{_q('learningOpportunityInstance')}")
        if kind == "degree programme" and not programme:
            programme.update({"code": code or "", "name": title or "", "level": "degree programme"})
            level = instance.find(f"{_q('level')}[{_q('type')}='EQF']/{_q('value')}") if instance is not None else None
            if level is not None and _text(level) and re.fullmatch(r"[1-8]", _text(level)):
                programme["eqf_level"] = int(_text(level))
        elif kind in ("course", "module"):
            entry, reason = _entry(spec, instance, code, title)
            if reason:
                unmapped.append({"position": position, "reason": reason})
            else:
                entries.append(entry)
        if depth < 8:  # ELMO nests parts; a hostile file's depth is bounded here, not by the parser
            for i, part in enumerate(
                spec.findall(f"{_q('hasPart')}/{_q('learningOpportunitySpecification')}"), start=1
            ):
                visit(part, f"{position}/hasPart[{i}]", depth + 1)
        elif spec.find(_q("hasPart")) is not None:
            unmapped.append({"position": position, "reason": "too_deeply_nested"})

    for i, spec in enumerate(report.findall(_q("learningOpportunitySpecification")), start=1):
        visit(spec, f"report/learningOpportunitySpecification[{i}]", 0)
    transcript: dict[str, Any] = {
        "learner": out_learner,
        "issuer": out_issuer,
        "programme": programme,
        "entries": entries,
    }
    issued = _date(_text(report.find(_q("issueDate")))) or _date(_text(root.find(_q("generatedDate"))))
    if issued:
        transcript["issued_on"] = issued
    return transcript, unmapped, integrity


def _entry(spec: ET.Element, inst: ET.Element | None, code: str | None, title: str | None) -> tuple[dict, str | None]:
    if not title:
        return {}, "missing_title"
    if inst is None:
        return {}, "missing_instance"
    status_text = _text(inst.find(_q("status"))) or "passed"  # the schema says an absent status means passed
    if status_text not in STATUS_IN:
        return {}, "unknown_status"
    credits = [c for c in inst.findall(_q("credit")) if _text(c.find(_q("value")))]
    ects = [c for c in credits if (_text(c.find(_q("scheme"))) or "").lower() == "ects"]
    credit = (ects or credits or [None])[0]  # ECTS first, any other scheme otherwise
    if credit is None:
        return {}, "no_credit_value"
    try:
        value = float(_text(credit.find(_q("value"))) or "")
    except ValueError:
        return {}, "bad_credit_value"
    if not (0 <= value <= 1000) or value != value:
        return {}, "bad_credit_value"
    scheme = (_text(credit.find(_q("scheme"))) or "").lower()
    entry: dict[str, Any] = {
        "course_code": code or "",
        "title": title,
        "credits": value,
        "credit_system": scheme if scheme in ("ects", "indian_credit") else "other",
        "status": STATUS_IN[status_text],
    }
    if (g := _text(inst.find(_q("resultLabel")))) is not None:
        entry["grade"] = g[:30]
    if (g := _text(inst.find(_q("gradingSchemeLocalId")))) is not None:
        entry["grade_scheme"] = g[:60]
    if start := _date(_text(inst.find(_q("start")))):
        entry["started_on"] = start
    if end := _date(_text(inst.find(_q("date")))):
        entry["completed_on"] = end
    term = inst.find(f"{_q('academicTerm')}")
    if term is not None and (t := _lang_title(term)):
        entry["term"] = t[:60]
    return entry, None
