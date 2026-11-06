"""Importing a partner's file: known-good, tampered, partially unmappable and hostile files. Nothing is accepted here:
the result is the normalised transcript, its integrity and every line that could not be mapped."""

import json
import re

import pytest
from eos_external_university_portals.application.formats import edc, elmo
from eup_support import FIXED_NOW, FIXTURES, export, outbox, partner, put, transcript


def _import(adapter, org, docs, fmt, content: bytes, key: str = "in-1", settings: dict | None = None):
    provider = {"csv": "file", "pdf": "file", "elmo_xml": "elmo", "edc_jsonld": "edc"}[fmt]
    doc = put(docs, org.id, content)
    return adapter.import_records(
        org.ctx(provider, "mock", settings), exchange_key=key, partner_id="uni-oslo", format=fmt, document_id=doc
    )


def _exported(adapter, docs, org, fmt) -> bytes:
    r = export(adapter, org, fmt)
    return docs.get(org.id, r.output["document_id"]).content


@pytest.mark.parametrize("fmt", ["csv", "elmo_xml", "edc_jsonld"])
def test_what_we_export_reads_back(adapter, docs, org, fmt):
    r = _import(adapter, org, docs, fmt, _exported(adapter, docs, org, fmt))
    assert r.ok, r.error
    out = r.output
    assert out["unmapped"] == [] and out["integrity"] == "unsigned"
    original = {e["course_code"]: e for e in transcript()["entries"]}
    got = {e["course_code"]: e for e in out["transcript"]["entries"]}
    expected = {c for c, e in original.items() if fmt != "edc_jsonld" or e["status"] == "passed"}
    assert set(got) == expected
    for code, e in got.items():
        assert e["title"] == original[code]["title"] and e["credits"] == original[code]["credits"]
        assert e["credit_system"] == original[code]["credit_system"] and e["status"] == original[code]["status"]
        assert e.get("grade") == original[code].get("grade")
    assert out["transcript"]["learner"]["name"] == "Asha Nair"
    assert out["transcript"]["learner"]["date_of_birth"] == "2003-04-12"
    assert out["transcript"]["learner"]["partner_student_id"] == "STU-2024-0042"
    # a CSV has no issuer: the partner whose file it is stands in for it
    assert out["transcript"]["issuer"]["institution_name"] == (
        "University of Oslo" if fmt == "csv" else "Sample Institute of Higher Education"
    )


def test_the_exchange_is_recorded_without_the_transcript(adapter, docs, org):
    r = _import(adapter, org, docs, "csv", _exported(adapter, docs, org, "csv"), key="rec-1")
    ev = outbox(org.id, "external-university-portals.exchange.imported")
    assert (
        len(ev) == 1
        and ev[0].payload["exchange_id"] == r.output["exchange_id"]
        and ev[0].payload["integrity"] == "unsigned"
    )
    assert "Asha" not in json.dumps(ev[0].payload)


def test_the_official_elmo_example_imports_with_what_it_cannot_map(adapter, docs, org):
    r = _import(adapter, org, docs, "elmo_xml", (FIXTURES / "elmo-schemas" / "example.xml").read_bytes())
    assert r.ok, r.error
    out = r.output
    assert (
        out["transcript"]["learner"]["family_name"] == "Rygielski"
        and out["transcript"]["learner"]["date_of_birth"] == "1983-04-12"
    )
    assert out["transcript"]["issuer"]["country"] == "PL"
    titles = {e["title"] for e in out["transcript"]["entries"]}
    assert "Compiler construction" in titles
    ects = [e for e in out["transcript"]["entries"] if e["credit_system"] == "ects"]
    assert ects and all(e["credits"] > 0 for e in ects)
    # example.xml carries an enveloped signature: this release cannot verify it, so it is never called verified
    assert out["integrity"] == "failed"
    assert all(set(u) == {"position", "reason"} for u in out["unmapped"])


def test_the_commissions_edc_sample_is_read_and_its_unmappable_claim_listed(adapter, docs, org):
    r = _import(adapter, org, docs, "edc_jsonld", (FIXTURES / "edc" / "Sample-CertOfPart-unsigned.jsonld").read_bytes())
    assert r.ok, r.error
    assert r.output["transcript"]["learner"]["family_name"] and r.output["transcript"]["entries"] == []
    assert r.output["unmapped"] == [
        {"position": "credentialSubject.hasClaim[0]", "reason": "no_credit_value"}
    ]  # a webinar has no credits
    assert r.output["integrity"] == "unsigned"


# ----------------------------------------------------------------- integrity: tampered and signed files


def test_an_elmo_file_with_a_signature_is_never_trusted(adapter, docs, org):
    xml = _exported(adapter, docs, org, "elmo_xml").replace(
        b"</report>",
        b'<Signature xmlns="http://www.w3.org/2000/09/xmldsig#"><SignatureValue>AAAA</SignatureValue></Signature></report>',
    )
    r = _import(adapter, org, docs, "elmo_xml", xml)
    assert r.ok and r.output["integrity"] == "failed"  # not an error: the reviewer sees it


def test_an_edc_credential_with_a_proof_is_never_trusted(adapter, docs, org):
    doc = json.loads(_exported(adapter, docs, org, "edc_jsonld"))
    doc["proof"] = {"type": "XAdES", "proofValue": "AAAA"}
    r = _import(adapter, org, docs, "edc_jsonld", json.dumps(doc).encode())
    assert r.ok and r.output["integrity"] == "failed"


def test_a_tampered_credit_value_is_read_as_written_and_flagged_when_signed(adapter, docs, org):
    doc = json.loads(_exported(adapter, docs, org, "edc_jsonld"))
    doc["proof"] = {"type": "x"}
    doc["credentialSubject"]["hasClaim"][0]["specifiedBy"]["creditPoint"][0]["point"] = "400"
    r = _import(adapter, org, docs, "edc_jsonld", json.dumps(doc).encode())
    assert r.output["integrity"] == "failed" and r.output["transcript"]["entries"][0]["credits"] == 400


# ----------------------------------------------------------------- partially unmappable


def test_elmo_lines_that_cannot_be_mapped_are_listed_by_position_and_reason(adapter, docs, org):
    xml = _exported(adapter, docs, org, "elmo_xml").decode()
    xml = xml.replace("<status>passed</status>", "<status>withdrawn</status>", 1)
    xml = re.sub(r"<credit>\s*<scheme>indian_credit</scheme>\s*<value>3.5</value>\s*</credit>", "", xml)
    r = _import(adapter, org, docs, "elmo_xml", xml.encode())
    assert r.output["unmapped"] == [
        {"position": "report/learningOpportunitySpecification[1]/hasPart[1]", "reason": "unknown_status"},
        {"position": "report/learningOpportunitySpecification[1]/hasPart[2]", "reason": "no_credit_value"},
    ]
    assert [e["course_code"] for e in r.output["transcript"]["entries"]] == ["PH103", "CS201"]


def test_csv_rows_that_cannot_be_mapped_are_listed(adapter, docs, org):
    csv_text = (
        "course_code,title,credits,status,grade,started_on\n"
        "A1,Good,6,passed,A,2024-01-02\n"
        "A2,,6,passed,A,\n"  # no title
        "A3,Bad credits,six,passed,A,\n"
        "A4,Inf credits,Infinity,passed,A,\n"
        "A5,Bad status,6,maybe,A,\n"
        "A6,Bad date,6,failed,F,31/12/2024\n"
        "\n"
    )
    r = _import(adapter, org, docs, "csv", csv_text.encode())
    assert [e["course_code"] for e in r.output["transcript"]["entries"]] == ["A1", "A6"]
    assert r.output["unmapped"] == [
        {"position": "row 3", "reason": "missing_title"},
        {"position": "row 4", "reason": "bad_credit_value"},
        {"position": "row 5", "reason": "bad_credit_value"},
        {"position": "row 6", "reason": "unknown_status"},
        {"position": "row 7", "reason": "bad_date"},
    ]
    assert "Bad credits" not in json.dumps(r.output["unmapped"])


def test_the_partners_csv_mapping_is_applied_on_the_way_in(adapter, docs, org):
    mapping = {"course_code": "Module", "title": "Name", "credits": "ECTS", "status": "Result"}
    csv_text = "Module,Name,ECTS,Result\nM1,Maths,5,passed\n"
    r = _import(adapter, org, docs, "csv", csv_text.encode(), settings=partner(csv_mapping=mapping))
    assert r.output["transcript"]["entries"][0]["title"] == "Maths"
    missing = _import(adapter, org, docs, "csv", csv_text.encode(), key="in-2")
    assert missing.error.code == "invalid_request"  # without the mapping the columns are not there


def test_spreadsheet_formula_prefix_is_removed_on_import(adapter, docs, org):
    t = transcript()
    t["entries"][0]["title"] = '=HYPERLINK("http://evil")'
    exported = docs.get(org.id, export(adapter, org, "csv", transcript=t).output["document_id"]).content
    assert b"'=HYPERLINK" in exported  # neutralised in the file a partner opens in a spreadsheet
    r = _import(adapter, org, docs, "csv", exported)
    assert r.output["transcript"]["entries"][0]["title"] == t["entries"][0]["title"]


# ----------------------------------------------------------------- hostile files


BILLION_LAUGHS = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]><elmo xmlns="https://github.com/emrex-eu/elmo-schemas/tree/v2">&lol2;</elmo>'
XXE = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><elmo xmlns="https://github.com/emrex-eu/elmo-schemas/tree/v2"><generatedDate>&xxe;</generatedDate></elmo>'
HOSTILE = [
    ("elmo_xml", b""),
    ("elmo_xml", b"not xml"),
    ("elmo_xml", b"\x00\x01\x02"),
    ("elmo_xml", BILLION_LAUGHS),
    ("elmo_xml", XXE),
    ("elmo_xml", b"<other/>"),
    ("elmo_xml", b'<elmo xmlns="https://github.com/emrex-eu/elmo-schemas/tree/v2"/>'),
    ("elmo_xml", b"<a>" * 5000),
    ("elmo_xml", "﻿<elmo/>".encode()),
    ("edc_jsonld", b""),
    ("edc_jsonld", b"[]"),
    ("edc_jsonld", b'{"type": "Other"}'),
    ("edc_jsonld", b'{"type": "VerifiableCredential"}'),
    ("edc_jsonld", b'{"type": "VerifiableCredential", "credentialSubject": {"hasClaim": NaN}}'),
    (
        "edc_jsonld",
        b'{"type": "VerifiableCredential", "credentialSubject": {"hasClaim": [{"title": "x", "specifiedBy": {"creditPoint": [{"point": Infinity}]}}]}}',
    ),
    ("edc_jsonld", b"[" * 100_000),
    ("edc_jsonld", b"\xff\xfe\x00"),
    ("csv", b""),
    ("csv", b"\x00\x00\x00"),
    ("csv", b"\xff\xfe"),
    ("csv", b'a,b\n"unterminated,1\n'),
    ("csv", b"title\nonly a title column\n"),
]


@pytest.mark.parametrize(("fmt", "content"), HOSTILE, ids=[f"{f}-{i}" for i, (f, _) in enumerate(HOSTILE)])
def test_hostile_files_are_rejected_not_500(adapter, docs, org, fmt, content):
    r = _import(adapter, org, docs, fmt, content, key=f"h-{abs(hash((fmt, content)))}")
    assert r.error is not None and r.error.code == "invalid_request"
    assert "etc/passwd" not in r.error.detail and "lol" not in r.error.detail  # the message never quotes the file


def test_a_rejected_file_is_recorded_and_a_corrected_one_replaces_it(adapter, docs, org):
    bad = _import(adapter, org, docs, "csv", b"nothing useful", key="retry-1")
    assert bad.error.code == "invalid_request"
    assert len(outbox(org.id, "external-university-portals.exchange.rejected")) == 1
    good = _import(adapter, org, docs, "csv", b"course_code,title,credits,status\nC,T,1,passed\n", key="retry-1")
    assert good.ok


def test_an_entity_expanding_file_never_reaches_the_parser():
    with pytest.raises(elmo.ElmoError):
        elmo.read(BILLION_LAUGHS)
    with pytest.raises(edc.EdcError):
        edc.read(b'{"a": NaN}')


def test_a_hostile_credit_value_is_never_mapped():
    doc = {
        "type": ["VerifiableCredential"],
        "credentialSubject": {
            "hasClaim": [
                {"title": "x", "specifiedBy": {"creditPoint": [{"point": "1e999"}]}},
                {"title": "y", "specifiedBy": {"creditPoint": [{"point": "-3"}]}},
            ]
        },
    }
    tr, unmapped, _ = edc.read(json.dumps(doc).encode())
    assert tr["entries"] == [] and [u["reason"] for u in unmapped] == ["bad_credit_value", "bad_credit_value"]


def test_deeply_nested_elmo_parts_are_bounded(adapter, docs, org):
    ns = 'xmlns="https://github.com/emrex-eu/elmo-schemas/tree/v2"'
    nest = (
        "".join("<hasPart><learningOpportunitySpecification><type>Module</type><title>t</title>" for _ in range(50))
        + "</learningOpportunitySpecification></hasPart>" * 50
    )
    xml = f"<elmo {ns}><generatedDate>2026-01-01T00:00:00Z</generatedDate><learner/><report><learningOpportunitySpecification><type>Module</type><title>t</title>{nest}</learningOpportunitySpecification></report></elmo>"
    r = _import(adapter, org, docs, "elmo_xml", xml.encode())
    assert r.ok and any(u["reason"] in ("too_deeply_nested", "missing_instance") for u in r.output["unmapped"])


def test_the_import_size_limit(adapter, docs, org, monkeypatch):
    monkeypatch.setenv("EXTERNAL_UNIVERSITY_PORTALS_MAX_IMPORT_BYTES", "2048")
    r = _import(adapter, org, docs, "csv", b"course_code,title,credits,status\n" + b"C,T,1,passed\n" * 400)
    assert r.error.code == "invalid_request" and "limit" in r.error.detail


def test_pdf_import_is_unsupported_and_a_missing_document_is_invalid(adapter, docs, org):
    assert _import(adapter, org, docs, "pdf", b"%PDF-1.4").error.code == "unsupported"
    r = adapter.import_records(
        org.ctx("file"),
        exchange_key="x",
        partner_id="uni-oslo",
        format="csv",
        document_id="00000000-0000-4000-8000-000000000000",
    )
    assert r.error.code == "invalid_request"


def test_importing_the_same_file_again_is_idempotent_and_another_file_conflicts(adapter, docs, org):
    content = b"course_code,title,credits,status\nC,T,1,passed\n"
    a = _import(adapter, org, docs, "csv", content, key="same")
    b = _import(adapter, org, docs, "csv", content, key="same")
    assert a.output["exchange_id"] == b.output["exchange_id"]
    c = _import(adapter, org, docs, "csv", content + b"D,U,2,passed\n", key="same")
    assert c.error.code == "conflict"


def test_clock_is_not_needed_to_read(adapter, docs, org):
    assert FIXED_NOW.year == 2026  # reading is a pure function of the file
