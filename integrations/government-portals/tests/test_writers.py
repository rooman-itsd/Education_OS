"""The file writers on their own: CSV safety, the PDF's structure, and the bundle."""

import io
import re
import zipfile

from eos_government_portals.application.pdf import build_pdf
from eos_government_portals.application.writers import OutFile, _cell, _csv, make_bundle


def test_spreadsheet_formulas_are_neutralised():
    for text in ("=1+1", "+1", "-1+2", "@SUM(A1)", "\tcmd", "\rcmd"):
        assert _cell(text).startswith("'")
    assert _cell("plain") == "plain" and _cell(-5) == "-5" and _cell(0.5) == "0.5" and _cell(1e12) == "1000000000000"


def test_csv_has_a_byte_order_mark_for_excel_and_quotes_properly():
    out = _csv(["a", "b"], [["x,y", 'say "hi"'], ["line1\nline2", "é"]])
    assert out.startswith(b"\xef\xbb\xbf")
    assert '"x,y","say ""hi"""' in out.decode("utf-8-sig")


def test_pdf_is_well_formed_and_deterministic():
    lines = [f"line {i} (with) parens \\ and ü and 中" for i in range(120)]
    a, b = build_pdf("T (x)", lines), build_pdf("T (x)", lines)
    assert a == b and a.startswith(b"%PDF-1.4\n") and a.endswith(b"%%EOF\n")
    assert a.count(b"/Type /Page ") == 3  # 120 lines over pages of 52
    startxref = int(re.search(rb"startxref\n(\d+)\n", a).group(1))
    assert a[startxref : startxref + 4] == b"xref"
    for n, off in enumerate(re.findall(rb"(\d{10}) 00000 n", a), start=1):
        assert a[int(off) :].startswith(b"%d 0 obj" % n)
    assert b"\\(with\\)" in a and b"\\\\" in a


def test_an_empty_pdf_still_has_a_page():
    assert build_pdf("Empty", []).count(b"/Type /Page ") == 1


def test_bundle_is_a_zip_with_fixed_timestamps():
    files = [OutFile("keying_sheet", "b.csv", "text/csv", b"b"), OutFile("upload", "a.csv", "text/csv", b"a")]
    data = make_bundle("x", files)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.namelist() == ["a.csv", "b.csv"]
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    assert make_bundle("x", files) == data
