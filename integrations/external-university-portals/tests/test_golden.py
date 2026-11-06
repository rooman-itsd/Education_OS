"""Golden files: the fixture transcript produces exactly these CSV, ELMO XML and EDC JSON-LD files (with a fixed clock).
Regenerate deliberately with `UPDATE_GOLDEN=1 pytest` and review the diff: a changed golden file is a changed format."""

import os

import pytest
from eup_support import FIXTURES, Org, export
from eup_support import partner as partner_settings

GOLDEN = FIXTURES.parent / "golden"
CASES = [
    ("transcript.csv", "csv", {}),
    (
        "transcript-mapped.csv",
        "csv",
        {"csv_mapping": {"course_code": "Module", "title": "Module title", "credits": "ECTS", "status": "Result"}},
    ),
    ("transcript.elmo.xml", "elmo_xml", {}),
    ("transcript.edc.jsonld", "edc_jsonld", {}),
]


@pytest.mark.parametrize(("name", "fmt", "extra"), CASES, ids=[c[0] for c in CASES])
def test_export_matches_the_golden_file(adapter, docs, name, fmt, extra):
    org = Org("0d9c1f4e-5b2a-4c3d-8e7f-6a5b4c3d2e1f")  # the EDC credential id derives from the organisation and key
    r = export(adapter, org, fmt, key=f"golden-{name}", settings=partner_settings(**extra))
    assert r.ok, r.error
    content = docs.get(org.id, r.output["document_id"]).content
    target = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        target.write_bytes(content)
    assert content == target.read_bytes(), f"{name} differs from its golden file"


@pytest.mark.parametrize(("name", "fmt", "extra"), CASES, ids=[c[0] for c in CASES])
def test_export_is_deterministic_and_idempotent_per_key(adapter, docs, org, name, fmt, extra):
    a = export(adapter, org, fmt, key="det-1", settings=partner_settings(**extra))
    b = export(adapter, org, fmt, key="det-1", settings=partner_settings(**extra))
    assert a.output == b.output  # same key: the same exchange, not a second file
    c = export(adapter, org, fmt, key="det-2", settings=partner_settings(**extra))
    assert c.output["document_id"] != a.output["document_id"]
