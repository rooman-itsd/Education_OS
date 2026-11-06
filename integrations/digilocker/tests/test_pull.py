"""The Pull Issuer API: DigiLocker's Pull URI and Pull Doc requests, recorded in tests/fixtures and signed with a
known issuer API key at a pinned time. Matching is on hashed search keys AND name and date of birth; never Aadhaar."""

import base64
from xml.etree import ElementTree

from dgl_support import ISSUER_ID, ctx, fixture, issue_input, ok, pdf, rows
from eos_digilocker.domain.models import IssuedDocument, PullRequestLog
from eos_digilocker.domain.rules import keyhash


def issued(adapter, documents, org, **kw):
    out = ok(adapter.invoke("issue", ctx(org), issue_input(documents, org, **kw)))
    return out


def pull(adapter, org, channel, raw, **kw):
    r = adapter.invoke("handle_provider_request", ctx(org, **kw), {"channel": channel, "headers": {}, "raw_body": raw})
    return r["output"]


def status(out) -> str:
    return ElementTree.fromstring(out["body"]).find("ResponseStatus").get("Status")


def test_a_matching_search_returns_the_uri_and_the_pdf(adapter, documents, org):
    issued(adapter, documents, org)
    out = pull(adapter, org, "pull-uri", fixture("pull_uri_request.xml"))
    assert out["status"] == 200 and out["content_type"] == "application/xml"
    root = ElementTree.fromstring(out["body"])
    assert root.tag == "PullURIResponse" and root.get("txn") == "TXN-0001"
    assert root.find("ResponseStatus").attrib == {"Status": "1", "ts": "2026-11-05T10:00:00+05:30", "txn": "TXN-0001"}
    assert root.find("DocDetails/URI").text == f"{ISSUER_ID}-DGCER-DEG-2026-0001"
    assert base64.b64decode(root.find("DocDetails/DocContent").text) == pdf("degree")
    assert b"<cgpa>8.4</cgpa>" in base64.b64decode(root.find("DocDetails/DataContent").text)


def test_golden_pull_uri_response(adapter, documents, org):
    issued(adapter, documents, org)
    out = pull(adapter, org, "pull-uri", fixture("pull_uri_request.xml"))
    expected = (
        '<?xml version="1.0" encoding="UTF-8"?><PullURIResponse ver="1.0" ts="2026-11-05T10:00:00+05:30" txn="TXN-0001">'
        '<ResponseStatus Status="1" ts="2026-11-05T10:00:00+05:30" txn="TXN-0001" /><DocDetails>'
        f"<URI>in.ac.example-DGCER-DEG-2026-0001</URI><DocContent>{base64.b64encode(pdf('degree')).decode()}</DocContent>"
        f"<DataContent>{base64.b64encode(b'<Certificate type="DGCER"><cgpa>8.4</cgpa><programme>B.Sc. Physics</programme></Certificate>').decode()}</DataContent>"
        "</DocDetails></PullURIResponse>"
    )
    assert out["body"].decode() == expected


def test_udf_parameters_and_spelling_variants_still_match(adapter, documents, org):
    issued(adapter, documents, org)
    out = pull(adapter, org, "pull-uri", fixture("pull_uri_request_udf.xml"))  # UDF1/UDF2, "ASHA  RAO", DOB 01-01-2004
    assert status(out) == "1"


def test_name_and_date_of_birth_must_both_match(adapter, documents, org):
    issued(adapter, documents, org)
    assert status(pull(adapter, org, "pull-uri", fixture("pull_uri_request_wrong_dob.xml"))) == "0"
    wrong_name = fixture("pull_uri_request.xml").replace(b"Asha Rao", b"Asha Rai")
    assert status(pull(adapter, org, "pull-uri", wrong_name)) == "0"
    unknown = pull(adapter, org, "pull-uri", fixture("pull_uri_request_unknown_roll.xml"))
    assert unknown["status"] == 200 and status(unknown) == "0"
    assert ElementTree.fromstring(unknown["body"]).find("DocDetails") is None


def test_two_holders_with_the_same_details_answer_status_zero(adapter, documents, org):
    issued(adapter, documents, org)
    issued(adapter, documents, org, key="res-2:degree", number="DEG-2026-0002", label="twin")
    assert status(pull(adapter, org, "pull-uri", fixture("pull_uri_request.xml"))) == "0"  # never guess


def test_aadhaar_is_neither_used_nor_stored(adapter, documents, org):
    issued(adapter, documents, org)
    pull(adapter, org, "pull-uri", fixture("pull_uri_request.xml"))  # carries <UID>999999990019</UID>
    dumped = " ".join(repr(vars(r)) for r in rows(IssuedDocument, org.id) + rows(PullRequestLog, org.id))
    assert "999999990019" not in dumped
    only_uid = (
        fixture("pull_uri_request.xml")
        .replace(b"<roll_number>RN-2026-0042</roll_number>", b"")
        .replace(b"<year>2026</year>", b"")
    )
    assert status(pull(adapter, org, "pull-uri", only_uid)) == "0"  # Aadhaar alone finds nothing


def test_unauthorised_requests_are_refused_with_401(adapter, documents, org):
    issued(adapter, documents, org)
    for name in ("pull_uri_request_bad_keyhash.xml", "pull_uri_request_stale.xml"):
        out = pull(adapter, org, "pull-uri", fixture(name))
        assert out["status"] == 401 and b"DGCER" not in out["body"], name
    other_issuer = fixture("pull_uri_request.xml").replace(b'orgId="in.ac.example"', b'orgId="in.ac.other"')
    assert pull(adapter, org, "pull-uri", other_issuer)["status"] == 401
    no_ts = fixture("pull_uri_request.xml").replace(b'ts="2026-11-05T10:00:00+05:30"', b"")
    assert pull(adapter, org, "pull-uri", no_ts)["status"] == 401
    assert rows(PullRequestLog, org.id) == []  # nothing is logged for a request that was not authorised


def test_the_keyhash_is_sha256_of_key_and_timestamp():
    # computed independently: sha256("issuer-api-key-fixture" + "2026-11-05T10:00:00+05:30")
    assert keyhash("issuer-api-key-fixture", "2026-11-05T10:00:00+05:30") == (
        "5a5caf72c71493b8f91647ead89bdaa57b8c35f900600c940acd2becd4fdb09e"
    )


def test_malformed_and_hostile_xml_is_a_400_never_a_500(adapter, documents, org):
    for raw in (b"", b"not xml", b"<PullURIRequest", fixture("pull_xxe_request.xml"), b"x" * 300_000, b"<Other/>"):
        out = pull(adapter, org, "pull-uri", raw)
        assert out["status"] == 400, raw[:30]
    utf16 = fixture("pull_xxe_request.xml").decode().encode("utf-16")  # another encoding must not hide the DOCTYPE
    assert pull(adapter, org, "pull-uri", utf16)["status"] == 400
    bad_txn = fixture("pull_uri_request.xml").replace(b'txn="TXN-0001"', b'txn="a b;c"')
    assert pull(adapter, org, "pull-uri", bad_txn)["status"] == 400
    r = adapter.invoke("handle_provider_request", ctx(org), {"channel": "pull-uri"})
    assert r["error"]["code"] == "invalid_request"
    assert pull(adapter, org, "pull-nothing", b"<x/>")["status"] == 404


def test_a_connection_without_an_issuer_key_is_unavailable_outside_mock_mode(adapter, documents, org, monkeypatch):
    issued(adapter, documents, org)
    monkeypatch.setenv("DIGILOCKER_LIVE_BASE_URL", "https://api.example.invalid/public")
    out = pull(adapter, org, "pull-uri", fixture("pull_uri_request.xml"), mode="live", secrets={})
    assert out["status"] == 503


def test_pull_doc_serves_the_pdf_logs_it_and_reports_the_pull(adapter, documents, org):
    issued(adapter, documents, org)
    out = pull(adapter, org, "pull-doc", fixture("pull_doc_request.xml"))
    root = ElementTree.fromstring(out["body"])
    assert root.tag == "PullDocResponse" and status(out) == "1"
    assert base64.b64decode(root.find("DocDetails/DocContent").text) == pdf("degree")
    [n] = out["notifications"]
    assert n["port"] == "certificate-issuance" and n["kind"] == "document_pulled"
    assert n["data"]["issuance_key"] == "res-1:degree" and n["data"]["provider_uri"].endswith("DEG-2026-0001")
    [row] = rows(IssuedDocument, org.id)
    assert row.last_pulled_at is not None
    [log] = rows(PullRequestLog, org.id)
    assert (log.channel, log.txn, log.matched, log.issued_document_id) == ("pull-doc", "TXN-0100", True, row.id)
    got = ok(adapter.invoke("get_issuance", ctx(org), {"issuance_key": "res-1:degree"}))
    assert got["last_pulled_at"]


def test_a_redelivered_request_is_answered_again_and_logged_once(adapter, documents, org):
    issued(adapter, documents, org)
    first = pull(adapter, org, "pull-doc", fixture("pull_doc_request.xml"))
    again = pull(adapter, org, "pull-doc", fixture("pull_doc_request.xml"))
    assert first["body"] == again["body"]
    assert len(rows(PullRequestLog, org.id)) == 1


def test_a_withdrawn_document_answers_status_zero_on_both_channels(adapter, documents, org):
    issued(adapter, documents, org)
    ok(adapter.invoke("withdraw", ctx(org), {"issuance_key": "res-1:degree", "reason": "cancelled"}))
    assert status(pull(adapter, org, "pull-doc", fixture("pull_doc_request.xml"))) == "0"
    assert status(pull(adapter, org, "pull-uri", fixture("pull_uri_request.xml"))) == "0"


def test_a_file_that_changed_since_issue_is_never_served(adapter, documents, org):
    out = issued(adapter, documents, org)
    row = rows(IssuedDocument, org.id)[0]
    documents.files[(org.id, row.document_id)] = b"tampered"
    assert status(pull(adapter, org, "pull-doc", fixture("pull_doc_request.xml"))) == "0"
    assert out["status"] == "available_for_pull"


def test_unknown_uri_and_other_organisations_documents(adapter, documents, org, other_org):
    issued(adapter, documents, org)
    unknown = fixture("pull_doc_request.xml").replace(b"DEG-2026-0001", b"NOPE")
    assert status(pull(adapter, org, "pull-doc", unknown)) == "0"
    # the same issuer id on another organisation's connection must not see this organisation's document
    assert status(pull(adapter, other_org, "pull-doc", fixture("pull_doc_request.xml"))) == "0"
    assert status(pull(adapter, other_org, "pull-uri", fixture("pull_uri_request.xml"))) == "0"


def test_format_decides_what_is_returned(adapter, documents, org):
    issued(adapter, documents, org)
    only_xml = fixture("pull_uri_request.xml").replace(b'format="both"', b'format="xml"')
    root = ElementTree.fromstring(pull(adapter, org, "pull-uri", only_xml)["body"])
    assert root.find("DocDetails/DocContent") is None and root.find("DocDetails/DataContent") is not None
