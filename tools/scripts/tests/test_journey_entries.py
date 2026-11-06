"""A dashboard journey's entry for a widget that is built must carry the texts the journey checks it with.

The journeys that walk a role layout (tests/e2e/dashboards/*.spec.ts calling `probe` from widgets.ts) list each widget
as a LayoutWidget. While the module does not export the widget, an entry may be bare (id, module, batch): the journey
skips it. Once the module exports it, `probe` and `expectBody` use `probe`, `title`, `empty` and `unavailable`, so the
day the module is enabled a bare entry fails e2e, on whichever pull request comes second rather than on the one that
left it bare (#517, #536 to #539). This test runs in the governance job, so a new bare entry fails where it is written.

"Exported" is decided as widgets.ts decides it: the id, quoted, in `<module>/frontend/src/widgets/index.ts`.
Reads files only: no Node, no installed modules."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOURNEYS = ROOT / "tests" / "e2e" / "dashboards"
TEXTS = ("title", "probe", "empty", "unavailable")

# Bare on main when this test was added (6 Nov 2026), each with the pull request that gives it its texts. Fixing one
# never fails this test; adding one does. Remove a line once its entry has texts (the list only shrinks).
WAITING = {
    # lms: #571
    **{(s, "lms.course-materials"): "#571" for s in (
        "actor", "athlete", "dancer", "engineering-student", "filmmaker", "hospitality-trainee", "law-student",
        "management-student", "medical-student", "musician", "research-scholar", "student")},
    **{(s, "lms.assignments-to-grade"): "#571" for s in (
        "chef-instructor", "choreographer", "clinical-supervisor", "coach", "corporate-mentor", "director",
        "legal-mentor", "music-teacher", "production-supervisor", "project-guide", "research-supervisor")},
    ("coach", "wearables.alerts"): "wearables enablement",
    ("management", "grievance.open"): "#572",
    ("management", "reporting.attendance-and-results-by-department"): "#579",
    ("management", "regulatory-reports.compliance-calendar"): "#589",
    ("hospital-coordinator", "regulatory-reports.due"): "#589",
    ("research-office", "regulatory-reports.due"): "#589",
    ("hospitality-trainee", "placement-career.openings"): "#542",
    ("management-student", "placement-career.openings"): "#542",
    ("industry-coordinator", "placement-career.openings-summary"): "#542",
    ("placement-officer", "placement-career.openings-summary"): "#542",
    ("placement-officer", "placement-career.drives"): "#542",
    ("management-student", "alumni.mentoring"): "#543",
}  # fmt: skip

# One LayoutWidget literal: a flat object (no nested braces) with an id.
ENTRY = re.compile(r"\{[^{}]*?\bid:\s*\"[^\"]+\"[^{}]*?\}", re.S)
VALUE = re.compile(r"\b(id|module)\s*:\s*\"([^\"]+)\"")
FIELD = re.compile(r"(?:^|[{,])\s*(\w+)\s*:")


def _module_dir(module: str) -> Path:
    """`<domain>/<module>` lives under modules/; `platform/<service>` and `integrations/<adapter>` at the top."""
    return ROOT / module if module.startswith(("platform/", "integrations/")) else ROOT / "modules" / module


@cache
def exported(module: str) -> str:
    """The module's widgets entry point, as widgets.ts reads it ("" when there is none)."""
    index = _module_dir(module) / "frontend" / "src" / "widgets" / "index.ts"
    return index.read_text(encoding="utf-8") if index.is_file() else ""


def _strip(source: str) -> str:
    """Comments and string contents out, so a `// title: ...` or a text holding `, title:` neither adds nor hides a
    field; the id and module values are read before this."""
    source = re.sub(r"(?m)//.*$", "", source)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', source)


def entries(spec: Path) -> list[dict]:
    out = []
    for literal in ENTRY.findall(re.sub(r"(?m)^\s*//.*$", "", spec.read_text(encoding="utf-8"))):
        values = dict(VALUE.findall(literal))
        if "id" in values and "module" in values:
            out.append({**values, "fields": set(FIELD.findall(_strip(literal)))})
    return out


def layout_journeys() -> list[Path]:
    """The journeys that check each widget through widgets.ts's probe (the others assert their own way)."""
    return [
        s
        for s in sorted(JOURNEYS.glob("*.spec.ts"))
        if re.search(r'from "\./widgets"', (t := s.read_text(encoding="utf-8"))) and re.search(r"\bprobe\(", t)
    ]


SPECS = layout_journeys()


def test_the_journeys_are_found():
    """Guards the parsing: if the folder or the entry shape changes, this fails instead of checking nothing."""
    assert len(SPECS) >= 30
    assert sum(len(entries(s)) for s in SPECS) >= 200


@pytest.mark.parametrize("spec", SPECS, ids=[s.name for s in SPECS])
def test_every_entry_names_a_module_that_exists(spec):
    missing = [f"{e['id']} -> {e['module']}" for e in entries(spec) if not _module_dir(e["module"]).is_dir()]
    assert not missing, f"{spec.name}: these entries name a module folder that does not exist: {missing}"


@pytest.mark.parametrize("spec", SPECS, ids=[s.name for s in SPECS])
def test_an_entry_for_a_built_widget_has_its_texts(spec):
    role = spec.name.removesuffix(".spec.ts")
    bare = [
        f"{e['id']} (missing {', '.join(t for t in TEXTS if t not in e['fields'])})"
        for e in entries(spec)
        if f'"{e["id"]}"' in exported(e["module"])
        and not all(t in e["fields"] for t in TEXTS)
        and (role, e["id"]) not in WAITING
    ]
    assert not bare, (
        f"{spec.name}: the module exports these widgets (frontend/src/widgets/index.ts), and the journey checks them "
        f"by {', '.join(TEXTS)} once it is enabled, so each entry needs all four: {bare}"
    )


# ------------------------------------------------------------------ the parsing itself, on made-up journeys


def _spec(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "x.spec.ts"
    p.write_text(f"const WIDGETS: LayoutWidget[] = [\n{body}\n];\n", encoding="utf-8")
    return p


def test_a_bare_entry_reads_as_bare_and_a_full_one_as_full(tmp_path):
    spec = _spec(
        tmp_path,
        '  { id: "projects.active", module: "practice/projects", batch: "#339" },\n'
        "  {\n"
        "    // Texts of the widget in PR #506 (not merged yet).\n"
        '    id: "projects.to-review",\n'
        '    module: "practice/projects",\n'
        '    batch: "#339",\n'
        '    title: "To review",\n'
        '    probe: "/projects/me/reviews?limit=5",\n'
        '    empty: "Nothing waiting for your review",\n'
        '    unavailable: "Projects data is not available yet.",\n'
        "  },",
    )
    got = {e["id"]: e["fields"] for e in entries(spec)}
    assert {"id", "module", "batch"} <= got["projects.active"] and not got["projects.active"] & set(TEXTS)
    assert set(TEXTS) <= got["projects.to-review"]


def test_commented_out_fields_and_colons_inside_texts_do_not_count(tmp_path):
    spec = _spec(
        tmp_path,
        '  { id: "projects.active", module: "practice/projects", batch: "#339",\n'
        '    // title: "Active projects",\n'
        '    probe: "/projects?limit=1", empty: "Note, title: none", unavailable: "Not yet." },',
    )
    assert entries(spec)[0]["fields"] == {"id", "module", "batch", "probe", "empty", "unavailable"}


def test_exported_reads_a_module_as_widgets_ts_does():
    assert '"projects.to-review"' in exported("practice/projects")
    assert exported("practice/no-such-module") == ""
