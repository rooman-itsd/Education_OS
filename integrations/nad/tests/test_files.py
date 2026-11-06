"""The upload files, byte for byte (template version 1, docs in eos_nad/domain/rules.py). Golden files in
tests/fixtures/golden were reviewed by hand; a change to the format must change them and bump the template version."""

import csv
import io

from eos_nad.domain.rules import AWARD_COLUMNS, CREDIT_COLUMNS, MAX_SUBJECTS, num, text
from nad_support import awards_batch, credits_batch, ctx, err, fixture, ok, record

HEAD_START = (
    "NAD INSTITUTION ID,INSTITUTION NAME,REGISTRATION NO,CANDIDATE NAME,MOTHER NAME,FATHER NAME,GENDER,DATE OF BIRTH,"
    "ABC ID,COURSE NAME,PROGRAMME CODE,PROGRAMME LEVEL,MODE OF STUDY,SESSION,TERM,EXAM MONTH,EXAM YEAR,RESULT,DIVISION,"
    "CGPA,PERCENTAGE,TOTAL CREDITS,CERTIFICATE NO,DATE OF ISSUE,SUBJECT 1 CODE,SUBJECT 1 NAME,SUBJECT 1 MAX MARKS,"
    "SUBJECT 1 MARKS,SUBJECT 1 GRADE,SUBJECT 1 GRADE POINT,SUBJECT 1 CREDITS,SUBJECT 2 CODE,"
)
FIRST_ROW_START = (
    "NAD-INST-0042,Example College of Science,EN-2023-0001,Asha Rao,Sunita Rao,Mohan Rao,F,01/01/2004,123456789012,"
    "B.Sc. Physics,BSC-PHY,undergraduate,full_time,2025-26,6,10,2026,PASS,First Class with Distinction,8.40,84.00,8,"
    'DEG-2026-0001,30/10/2026,PHY101,Mechanics,100,88,A,9,4,PHY102,"Optics, Waves and Sound",100,74.5,B+,8,4,'
)


def files_of(adapter, documents, org, op, body, **kw):
    out = ok(adapter.invoke(op, ctx(org, **kw), body))
    return out, [documents.get(org.id, f["document_id"]) for f in out["upload_files"]]


def golden(name: str) -> bytes:
    return fixture(f"golden/{name}")


def test_awards_file_matches_the_golden_file_and_the_spec(adapter, documents, org):
    out, [content] = files_of(adapter, documents, org, "publish_awards", awards_batch())
    assert content == golden("awards_degree_v1.csv")
    lines = content.decode("utf-8").split("\r\n")
    assert lines[0].startswith(HEAD_START) and lines[0].endswith(",MARKS REC STATUS")
    assert lines[1].startswith(FIRST_ROW_START) and lines[1].endswith(",N")
    assert lines[-1] == "" and len(lines) == 5  # header, 3 rows, trailing CRLF
    assert out["upload_files"][0]["rows"] == 3 and out["upload_files"][0]["filename"].endswith("-01.csv")
    assert not content.startswith(b"\xef\xbb\xbf")  # UTF-8 without a byte-order mark


def test_every_row_has_exactly_the_headers_columns(adapter, documents, org):
    _, [content] = files_of(adapter, documents, org, "publish_awards", awards_batch())
    parsed = list(csv.reader(io.StringIO(content.decode())))
    assert parsed[0] == AWARD_COLUMNS["1"] and len(parsed[0]) == 24 + 7 * MAX_SUBJECTS + 1
    assert {len(r) for r in parsed} == {len(parsed[0])}


def test_quoting_and_spreadsheet_formulas(adapter, documents, org):
    _, [content] = files_of(adapter, documents, org, "publish_awards", awards_batch())
    rows = list(csv.DictReader(io.StringIO(content.decode())))
    assert rows[1]["CANDIDATE NAME"] == 'Ravi "RK" Kumar'  # quoted by the writer, read back unchanged
    assert rows[2]["CANDIDATE NAME"] == "'=SUM(A1) Müller"  # a formula is defused with a leading apostrophe
    assert rows[2]["RESULT"] == "PASS" and rows[2]["PERCENTAGE"] == "61.50" and rows[2]["CGPA"] == ""
    assert rows[2]["DATE OF BIRTH"] == "29/02/2004" and rows[2]["GENDER"] == "T"


def test_corrections_are_flagged_m_and_new_records_n(adapter, documents, org):
    ok(adapter.invoke("publish_awards", ctx(org), awards_batch()))
    _, [content] = files_of(adapter, documents, org, "correct_awards", fixture("corrections_batch.json"))
    assert content == golden("corrections_degree_v1.csv")
    assert content.decode().split("\r\n")[1].endswith(",M")


def test_credits_file_matches_the_golden_file(adapter, documents, org):
    _, [content] = files_of(adapter, documents, org, "publish_credits", credits_batch())
    assert content == golden("credits_v1.csv")
    assert content.decode().split("\r\n")[0] == ",".join(CREDIT_COLUMNS["1"])


def test_large_batches_are_split_into_files_of_at_most_max_rows(adapter, documents, org, monkeypatch):
    monkeypatch.setenv("NAD_MAX_ROWS_PER_FILE", "2")
    out, files = files_of(adapter, documents, org, "publish_credits", credits_batch())
    assert [f["rows"] for f in out["upload_files"]] == [2, 1]
    assert files == [golden("credits_v1_split_01.csv"), golden("credits_v1_split_02.csv")]
    monkeypatch.setenv("NAD_MAX_ROWS_PER_FILE", "2")
    batch = awards_batch(batch_key="split-awards", records=[record(i) for i in range(5)])
    out, files = files_of(adapter, documents, org, "publish_awards", batch)
    assert [f["rows"] for f in out["upload_files"]] == [2, 2, 1]
    assert [f["filename"][-7:] for f in out["upload_files"]] == ["-01.csv", "-02.csv", "-03.csv"]
    assert all(c.decode().startswith("NAD INSTITUTION ID,") for c in files)  # every file has its own header


def test_an_unknown_template_version_is_refused_not_guessed(adapter, org, monkeypatch):
    monkeypatch.setenv("NAD_AWARDS_CSV_TEMPLATE_VERSION", "2")
    e = err(adapter.invoke("publish_awards", ctx(org), awards_batch()))
    assert e["code"] == "not_configured" and "version 2" in e["detail"]
    monkeypatch.setenv("NAD_CREDITS_CSV_TEMPLATE_VERSION", "9")
    assert err(adapter.invoke("publish_credits", ctx(org), credits_batch()))["code"] == "not_configured"


def test_number_and_text_formatting_rules():
    assert [num(x) for x in (None, 8, 8.0, 74.5, 7.25, 0, 100.0, 1e-3, 3.50)] == [
        "",
        "8",
        "8",
        "74.5",
        "7.25",
        "0",
        "100",
        "0.001",
        "3.5",
    ]
    assert text("  a \t b\n") == "a b" and text("@x") == "'@x" and text("-1") == "'-1" and text(None) == ""
