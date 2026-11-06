"""Golden files: for each form and cycle, a fixture data set produces exactly the expected keying sheet, templates,
website copy and bundle. Regenerate deliberately with `UPDATE_GOLDEN=1 pytest` and review the diff: a changed golden
file is a changed portal format."""

import hashlib
import io
import os
import zipfile

import pytest
from gp_support import CASES, GOLDEN, load_case, prepare


def _bundle_listing(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        assert z.testzip() is None
        lines = [f"{hashlib.sha256(z.read(n)).hexdigest()}  {n}" for n in sorted(z.namelist())]
    return ("\n".join(lines) + "\n").encode()


def _files(result, docs, org_id):
    out = {}
    for f in result.output["files"]:
        doc = docs.get(org_id, f["document_id"])
        out[f["filename"]] = (f["role"], doc.content)
    return out


@pytest.mark.parametrize("name", CASES)
def test_package_matches_golden_files(adapter, docs, org, name):
    result = prepare(adapter, org, docs, load_case(name))
    assert result.ok, result.error
    assert result.output["status"] == "prepared" and result.output["issues"] == []
    produced = {}
    for filename, (role, content) in _files(result, docs, org.id).items():
        if role == "bundle":
            produced[filename + ".listing"] = _bundle_listing(content)
        else:
            produced[filename] = content
    expected_dir = GOLDEN / name / "expected"
    if os.environ.get("UPDATE_GOLDEN"):
        for filename, content in produced.items():
            target = expected_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    on_disk = {str(p.relative_to(expected_dir)): p.read_bytes() for p in expected_dir.rglob("*") if p.is_file()}
    assert sorted(produced) == sorted(on_disk), "the package's files are not the golden set"
    for filename, content in produced.items():
        assert content == on_disk[filename], f"{filename} differs from its golden file"


@pytest.mark.parametrize("name", CASES)
def test_output_is_deterministic(adapter, docs, org, name):
    case = load_case(name)
    a = prepare(adapter, org, docs, case)
    b = prepare(adapter, org, docs, case)
    fa, fb = _files(a, docs, org.id), _files(b, docs, org.id)
    for filename in fa:
        if fa[filename][0] == "evidence":
            continue
        assert fa[filename][1] == fb[filename][1]


def test_every_catalogued_form_has_a_golden_case_or_a_sibling():
    """Every authority and every kind of form is covered: three DCFs, a NIRF category, four NAAC stages."""
    codes = {load_case(c)["form_code"] for c in CASES}
    assert {
        "aishe.dcf-i",
        "aishe.dcf-ii",
        "aishe.dcf-iii",
        "nirf.dcs.overall",
        "naac.iiqa",
        "naac.ssr",
        "naac.aqar",
        "naac.dvv-response",
    } <= codes
