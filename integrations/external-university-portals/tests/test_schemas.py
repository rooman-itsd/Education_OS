"""The exports are validated against the published schemas, which are vendored under tests/fixtures with their source
URL and licence (see the SOURCE.md next to each).

ELMO: the official XSD, checked with xmllint (libxml2; the test is skipped where it is not installed, as no XML schema
library is on the approved stack). EDC: no JSON Schema is published; the credential is validated with SHACL, and no
SHACL engine is on the approved stack either, so tests/edc_shacl.py checks every property's cardinality against the
official shapes and that every key is a term of the official JSON-LD context. It is calibrated on the Commission's own
sample credential below."""

import copy
import json
import shutil
import subprocess

import edc_shacl
import pytest
from eos_external_university_portals.application.formats import edc, elmo
from eup_support import FIXED_NOW, FIXTURES, transcript

XMLLINT = shutil.which("xmllint")
ELMO_DIR = FIXTURES / "elmo-schemas"
EDC_DIR = FIXTURES / "edc"
needs_xmllint = pytest.mark.skipif(XMLLINT is None, reason="xmllint (libxml2) not installed")
CREDENTIAL_ID = "6f1c3d2a-0b7e-4c55-9a51-1d6f0e9a7c10"
# The credential's seal and issue time are added when the issuer seals it; the Commission's own sample lacks it too.
EXEMPT = {("VerifiableCredential", "cred:issued"), ("EuropeanDigitalCredential", "cred:issued")}


def xsd_errors(xml: bytes, tmp_path) -> str:
    target = tmp_path / "doc.xml"
    target.write_bytes(xml)
    run = subprocess.run(  # noqa: S603
        [XMLLINT, "--noout", "--nonet", "--schema", "schema.xsd", str(target)],
        cwd=ELMO_DIR,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run.stderr if run.returncode else ""


def shacl(doc: dict) -> list[str]:
    ttl = (EDC_DIR / "EDC-generic-no-cv.ttl").read_text()
    ctx = json.loads((EDC_DIR / "edc-ap-context.jsonld").read_text())
    return edc_shacl.check(doc, ttl, ctx, exempt=EXEMPT)


def minimal() -> dict:
    t = transcript()
    t["learner"] = {"name": "Mononym", "date_of_birth": "2000-01-01"}
    t["programme"] = {"code": "P", "name": "Programme", "level": "master"}
    t["entries"] = [{"course_code": "C1", "title": "Course", "credits": 0, "credit_system": "ects", "status": "passed"}]
    t.pop("totals")
    return t


# ----------------------------------------------------------------- ELMO


@needs_xmllint
def test_the_vendored_official_example_validates_with_the_vendored_schema(tmp_path):
    assert xsd_errors((ELMO_DIR / "example.xml").read_bytes(), tmp_path) == ""


@needs_xmllint
@pytest.mark.parametrize("make", [transcript, minimal], ids=["full", "minimal"])
def test_elmo_export_validates_against_the_published_xsd(tmp_path, make):
    assert xsd_errors(elmo.write(make(), FIXED_NOW), tmp_path) == ""


@needs_xmllint
def test_the_validator_does_catch_a_broken_document(tmp_path):
    xml = elmo.write(transcript(), FIXED_NOW).replace(b"<status>passed</status>", b"<status>finished</status>", 1)
    assert "status" in xsd_errors(xml, tmp_path)


@needs_xmllint
def test_special_characters_survive_into_valid_xml(tmp_path):
    t = transcript()
    t["entries"][0]["title"] = 'Algorithms & <Data> "Structures" é中\U0001f600'
    xml = elmo.write(t, FIXED_NOW)
    assert xsd_errors(xml, tmp_path) == ""
    assert elmo.read(xml)[0]["entries"][0]["title"] == t["entries"][0]["title"]


def test_elmo_without_the_xsd_still_has_the_structure_the_schema_requires():
    """Where xmllint is missing the XSD test is skipped; this keeps the structural minimum covered everywhere."""
    xml = elmo.write(transcript(), FIXED_NOW).decode()
    for needle in (
        'xmlns="https://github.com/emrex-eu/elmo-schemas/tree/v2"',
        "<generatedDate>2026-11-05T12:00:00Z</generatedDate>",
        "<learner>",
        "<report>",
        "<issuer>",
        "<url>",
        "<issueDate>2025-11-01T00:00:00Z</issueDate>",
        "<scheme>indian_credit</scheme>",
    ):
        assert needle in xml


# ----------------------------------------------------------------- EDC


def test_the_checker_is_calibrated_on_the_commissions_sample():
    sample = json.loads((EDC_DIR / "Sample-CertOfPart-unsigned.jsonld").read_text())
    assert shacl(sample) == []
    broken = copy.deepcopy(sample)
    broken["credentialSubject"]["hasClaim"].pop("awardedBy")
    assert any("awardedBy" in v for v in shacl(broken))


@pytest.mark.parametrize("make", [transcript, minimal], ids=["full", "minimal"])
def test_edc_export_conforms_to_the_official_shapes(make):
    doc = json.loads(edc.write(make(), CREDENTIAL_ID, FIXED_NOW))
    assert shacl(doc) == []
    assert doc["credentialSchema"][0]["id"] == "http://data.europa.eu/snb/model/ap/edc-generic-full"
    assert doc["@context"] == edc.CONTEXT
    assert doc["type"] == ["VerifiableCredential", "EuropeanDigitalCredential"] and "proof" not in doc


def test_edc_export_uses_only_terms_the_official_context_defines():
    ctx = json.loads((EDC_DIR / "edc-ap-context.jsonld").read_text())["@context"]
    doc = json.loads(edc.write(transcript(), CREDENTIAL_ID, FIXED_NOW))
    seen: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                seen.add(k)
                if k not in ("title", "givenName", "familyName", "fullName", "legalName", "prefLabel", "noteLiteral"):
                    walk(v)
                else:
                    seen.update(set()) if isinstance(v, dict) else walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(doc)
    vc_terms = {"id", "type", "@context", "issuer", "credentialSubject", "validFrom", "credentialSchema"}
    assert seen - set(ctx) - vc_terms == set()
    for term in ("hasClaim", "awardedBy", "specifiedBy", "creditPoint", "provenBy", "grade", "gradingScheme"):
        assert term in seen


def test_edc_export_is_strict_json_with_only_passed_entries():
    text = edc.write(transcript(), CREDENTIAL_ID, FIXED_NOW).decode()
    doc = json.loads(text, parse_constant=lambda c: pytest.fail(c))
    assert [c["title"]["en"] for c in doc["credentialSubject"]["hasClaim"]] == [
        "Programming Fundamentals",
        "Discrete Mathematics",
    ]


def test_ects_is_the_only_credit_framework_in_the_edc_vocabulary():
    t = minimal()
    ects = json.loads(edc.write(t, CREDENTIAL_ID, FIXED_NOW))["credentialSubject"]["hasClaim"][0]["specifiedBy"][
        "creditPoint"
    ][0]
    assert ects["framework"]["id"] == "http://data.europa.eu/snb/education-credit/6fcec5c5af"
    t["entries"][0]["credit_system"] = "indian_credit"
    other = json.loads(edc.write(t, CREDENTIAL_ID, FIXED_NOW))["credentialSubject"]["hasClaim"][0]["specifiedBy"][
        "creditPoint"
    ][0]
    assert other["framework"]["id"] == "urn:eos:education-credit:indian_credit"
