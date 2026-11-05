"""The portals' own files: keying sheets, upload templates, the NIRF website copy, evidence arranged by metric, and a
zip of the lot. Pure functions: data in, bytes out, no clock, no randomness, so every output is golden-file testable.

Excel templates are written as CSV (UTF-8 with a byte order mark so Excel opens it with the right encoding): no
spreadsheet library is on the approved stack. A portal that insists on .xlsx takes the CSV pasted into its template.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..infrastructure.documents import StoredDocument
from .catalogue import NIRF_GROUPS, FormSpec
from .pdf import build_pdf

BOM = b"\xef\xbb\xbf"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class OutFile:
    role: str  # upload | keying_sheet | website_copy | evidence | bundle
    filename: str
    content_type: str
    content: bytes
    metric: str | None = None
    document_id: str | None = None  # set for evidence: the original document, not a copy


def _cell(value: Any) -> str:
    """One CSV cell. A text that a spreadsheet would run as a formula is neutralised with a leading apostrophe."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(Decimal(repr(value)).normalize(), "f")
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv(header: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for row in rows:
        w.writerow([_cell(v) for v in row])
    return BOM + buf.getvalue().encode("utf-8")


def _slug(text: str, limit: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "file"


def _stem(spec: FormSpec, period: str) -> str:
    return f"{spec.form_code.replace('.', '-')}-{period}"


def label(name: str) -> str:
    return name.replace("_", " ")


# ---------------------------------------------------------------- AISHE

AISHE_SECTIONS = [
    ("1. Basic details", "basic_details"),
    ("2. Departments", "departments"),
    ("3. Programmes and enrolment", "programmes"),
    ("4. Examination results", "examination_results"),
    ("5. Staff", "staff"),
    ("6. Teacher information", "teachers"),
    ("7. Infrastructure", "infrastructure"),
    ("8. Finance", "finance"),
]


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        out: list[tuple[str, Any]] = []
        for k, v in value.items():
            out += _flatten(v, f"{prefix}{label(k)}." if isinstance(v, dict) else f"{prefix}{label(k)}")
        return out
    return [(prefix, value)]


def aishe_rows(data: dict) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for title, key in AISHE_SECTIONS:
        if key not in data:
            continue
        section = data[key]
        if isinstance(section, list):
            for i, item in enumerate(section, start=1):
                for field, value in _flatten(item):
                    rows.append([title, i, field.rstrip("."), value])
                if key == "programmes":
                    total = sum(item["enrolment_by_gender"].values())
                    rows.append([title, i, "total enrolment (checked against category total)", total])
        else:
            for field, value in _flatten(section):
                rows.append([title, "", field.rstrip("."), value])
    return rows


# ---------------------------------------------------------------- NIRF


def nirf_rows(data: dict) -> list[list[Any]]:
    rows: list[list[Any]] = [["Institute", field, value] for field, value in _flatten(data["institute"])]
    for key, (title, fields) in NIRF_GROUPS.items():
        for name in fields:
            rows.append([title, label(name), data[key][name]])
    rows.append(["Perception", "collected by NIRF from its own surveys", "nothing to key"])
    return rows


def nirf_website_copy(spec: FormSpec, period: str, data: dict) -> bytes:
    """The data as submitted, for the institution's NIRF tab. Aggregates only: nothing in it names a person."""
    category = spec.form_code.removeprefix("nirf.dcs.").replace("-", " ")
    lines = [
        f"{data['institute']['name']}",
        f"NIRF {period} data submission, {category} category",
        "Data as submitted to the National Institutional Ranking Framework.",
        "",
    ]
    for key, (title, fields) in NIRF_GROUPS.items():
        lines.append(title)
        lines += [f"   {label(name).capitalize()}: {_cell(data[key][name])}" for name in fields]
        lines.append("")
    return build_pdf(f"{data['institute']['name']} - NIRF {period}", lines)


# ---------------------------------------------------------------- NAAC


def naac_metric_rows(data: dict) -> list[list[Any]]:
    return [
        [c["criterion"], m["metric"], m["kind"], m["value"]]
        for c in sorted(data["criteria"], key=lambda c: c["criterion"])
        for m in sorted(c["metrics"], key=lambda m: [int(p) for p in m["metric"].split(".")])
    ]


def arrange_evidence(evidence: list[dict], docs: dict[int, StoredDocument]) -> list[OutFile]:
    """Evidence named by metric number: evidence/<metric>/<NN>-<title>.<ext>. The original document is referenced by
    id; its bytes are carried here only so the bundle can contain them."""
    counters: dict[str, int] = {}
    out = []
    for i, ev in enumerate(evidence):
        doc = docs[i]
        counters[ev["metric"]] = counters.get(ev["metric"], 0) + 1
        ext = doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else "bin"
        name = f"evidence/{ev['metric']}/{counters[ev['metric']]:02d}-{_slug(ev['title'])}.{ext}"
        out.append(OutFile("evidence", name, doc.content_type, doc.content, ev["metric"], ev["document_id"]))
    return out


def evidence_index(files: list[OutFile], evidence: list[dict]) -> bytes:
    rows = [
        [f.metric, f.filename, ev["title"], hashlib.sha256(f.content).hexdigest()]
        for f, ev in zip(files, evidence, strict=True)
    ]
    return _csv(["metric", "file", "title", "sha256"], rows)


def make_bundle(name: str, files: list[OutFile]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files, key=lambda f: f.filename):
            info = zipfile.ZipInfo(f.filename, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.content)
    return buf.getvalue()


# ---------------------------------------------------------------- dispatch


def build_files(
    spec: FormSpec, period: str, data: dict, evidence: list[dict], docs: dict[int, StoredDocument]
) -> list[OutFile]:
    """Every file of the package, the bundle last. `docs` maps an evidence index to its stored document."""
    stem = _stem(spec, period)
    files: list[OutFile] = []
    if spec.authority == "aishe":
        files.append(
            OutFile(
                "keying_sheet",
                f"{stem}-keying-sheet.csv",
                "text/csv",
                _csv(["section", "item", "field", "value"], aishe_rows(data)),
            )
        )
    elif spec.authority == "nirf":
        files.append(
            OutFile(
                "keying_sheet",
                f"{stem}-keying-sheet.csv",
                "text/csv",
                _csv(["parameter", "field", "value"], nirf_rows(data)),
            )
        )
        files.append(
            OutFile(
                "website_copy", f"{stem}-website-copy.pdf", "application/pdf", nirf_website_copy(spec, period, data)
            )
        )
    elif spec.form_code == "naac.iiqa":
        rows = [[label(f), v] for f, v in _flatten({k: v for k, v in data.items()})]
        files.append(OutFile("keying_sheet", f"{stem}-keying-sheet.csv", "text/csv", _csv(["field", "value"], rows)))
    elif spec.form_code == "naac.dvv-response":
        rows = [[q["query_id"], q["metric"], q["clarification"]] for q in data["queries"]]
        files.append(
            OutFile(
                "keying_sheet",
                f"{stem}-keying-sheet.csv",
                "text/csv",
                _csv(["query id", "metric", "clarification"], rows),
            )
        )
        files.append(
            OutFile("upload", f"{stem}-responses.csv", "text/csv", _csv(["query_id", "metric", "clarification"], rows))
        )
    else:  # naac.ssr, naac.aqar
        rows = naac_metric_rows(data)
        files.append(
            OutFile(
                "keying_sheet",
                f"{stem}-keying-sheet.csv",
                "text/csv",
                _csv(["criterion", "metric", "kind", "value"], rows),
            )
        )
        files.append(
            OutFile(
                "upload",
                f"{stem}-data-template.csv",
                "text/csv",
                _csv(["metric", "kind", "value"], [r[1:] for r in rows]),
            )
        )
    arranged = arrange_evidence(evidence, docs) if evidence else []
    index = (
        [OutFile("bundle", "evidence/INDEX.csv", "text/csv", evidence_index(arranged, evidence))] if arranged else []
    )
    # The index is a bundle member only; it is not listed as a package file of its own.
    members = files + arranged + index
    bundle = OutFile("bundle", f"{stem}-bundle.zip", "application/zip", make_bundle(stem, members))
    return files + arranged + [bundle]


CHECKLISTS = {
    "aishe": [
        (
            "Sign in to the AISHE portal with the institution's nodal officer login. Education OS never holds it.",
            "Login",
        ),
        ("Open the Web DCF for the survey year and the form named in the package.", "Web DCF"),
        ("Key each section from the keying sheet, in the order of the sheet.", "Web DCF sections"),
        ("Compare the portal's computed totals with the totals in the sheet before submitting.", "Web DCF review"),
        ("Submit, then save the acknowledgement and the AISHE form id.", "Submission"),
        ("Record the filing in Education OS with the portal reference and the acknowledgement.", "Education OS"),
    ],
    "nirf": [
        ("Sign in to the NIRF Data Capturing System with the registered institution's login.", "Login"),
        ("Open the category named in the package for the ranking year.", "Data Capturing System"),
        ("Key each parameter from the keying sheet.", "Parameters"),
        ("Submit within the NIRF window and save the confirmation and the application id.", "Submission"),
        ("Publish the website copy PDF under the NIRF tab of the institution's website.", "Institution website"),
        ("Record the filing in Education OS with the portal reference and the acknowledgement.", "Education OS"),
    ],
    "naac": [
        ("Sign in to the NAAC portal with the institution's HEI account.", "Login"),
        ("Open the stage named in the package (IIQA, SSR, AQAR or DVV).", "Assessment portal"),
        ("Key the values from the keying sheet, or upload the data template where the portal takes one.", "Data entry"),
        ("Upload the evidence files from the bundle under the metric each is named for.", "Evidence upload"),
        ("Submit and save the acknowledgement and the NAAC track id.", "Submission"),
        ("Record the filing in Education OS with the portal reference and the acknowledgement.", "Education OS"),
    ],
}


def checklist_for(spec: FormSpec) -> list[dict]:
    return [
        {"step": i, "detail": d, "portal_section": s} for i, (d, s) in enumerate(CHECKLISTS[spec.authority], start=1)
    ]
