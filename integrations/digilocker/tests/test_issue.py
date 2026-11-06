"""issue, replace, withdraw and get_issuance: Pull by default, Push where the account is known, never Aadhaar,
and nothing personal stored in the clear."""

from dgl_support import PUSH_ID, ctx, err, issue_input, ok, pdf, rows, settings
from eos_digilocker.domain.models import IssuanceHistory, IssuedDocument
from eos_digilocker.domain.rules import push_hmac


def issue(adapter, org, body, **kw):
    return adapter.invoke("issue", ctx(org, **kw), body)


def test_issue_defaults_to_pull_and_records_the_document(adapter, documents, org):
    result = issue(adapter, org, issue_input(documents, org))
    out = ok(result)
    assert out["status"] == "available_for_pull"
    assert out["provider_uri"] == "in.ac.example-DGCER-DEG-2026-0001" == result["provider_reference"]
    [row] = rows(IssuedDocument, org.id)
    assert row.organisation_id == org.id and row.doc_type == "DGCER" and row.push_pending is None
    [h] = rows(IssuanceHistory, org.id)
    assert h.action == "issued" and h.issued_document_id == row.id


def test_nothing_personal_is_stored_in_the_clear(adapter, documents, org):
    ok(issue(adapter, org, issue_input(documents, org, number="DEG-7")))
    [row] = [r for r in rows(IssuedDocument, org.id)]
    stored = " ".join(str(getattr(row, c.name)) for c in IssuedDocument.__table__.columns)
    assert "RN-2026-0042" not in stored and "2026-0042" not in stored  # search values: hash only
    assert row.holder_name_normalised == "asha rao" and len(row.search_key_hash) == 64


def test_the_same_issuance_key_and_document_changes_nothing(adapter, documents, org):
    body = issue_input(documents, org)
    first, again = ok(issue(adapter, org, body)), ok(issue(adapter, org, body))
    assert first == again and len(rows(IssuedDocument, org.id)) == 1 and len(rows(IssuanceHistory, org.id)) == 1


def test_the_same_key_with_another_document_is_a_conflict(adapter, documents, org):
    ok(issue(adapter, org, issue_input(documents, org)))
    other = issue_input(documents, org, label="another", number="DEG-2026-0002")
    assert err(issue(adapter, org, other))["code"] == "conflict"


def test_a_document_number_is_unique_per_organisation_and_kind(adapter, documents, org, other_org):
    ok(issue(adapter, org, issue_input(documents, org)))
    clash = issue_input(documents, org, key="res-2:degree", label="x")
    assert err(issue(adapter, org, clash))["code"] == "conflict"
    # another organisation may use the same number
    ok(issue(adapter, other_org, issue_input(documents, other_org)))


def test_a_file_whose_hash_differs_is_refused(adapter, documents, org):
    body = issue_input(documents, org)
    body["document_sha256"] = "0" * 64
    e = err(issue(adapter, org, body))
    assert e["code"] == "invalid_request" and not e["retryable"]
    assert rows(IssuedDocument, org.id) == []


def test_another_organisations_document_is_not_found(adapter, documents, org, other_org):
    body = issue_input(documents, other_org)  # a document of other_org
    assert err(issue(adapter, org, body))["code"] == "invalid_request"


def test_search_keys_must_be_the_doc_types_fields(adapter, documents, org):
    body = issue_input(documents, org)
    body["holder"]["search_keys"] = {"roll_number": "1"}
    assert err(issue(adapter, org, body))["code"] == "invalid_request"
    body["holder"]["search_keys"] = {"roll_number": "1", "year": 2026, "extra": "x"}
    assert err(issue(adapter, org, body))["code"] == "invalid_request"


def test_a_doc_kind_the_connection_does_not_map_is_not_configured(adapter, documents, org):
    body = issue_input(documents, org, doc_kind="transcript")
    assert err(issue(adapter, org, body))["code"] == "not_configured"


def test_bad_input_is_invalid_request_never_an_exception(adapter, documents, org):
    base = issue_input(documents, org)
    bad = [
        {"issuance_key": ""},
        {"issuance_key": "x" * 101},
        {"document_sha256": "zz"},
        {"doc_kind": "nonsense"},
        {"document_id": "not-a-uuid"},
        {"issued_on": "05/11/2026"},
        {"title": "t" * 201},
        {"document_number": "n" * 61},
        {"document_number": "bad\x00number"},
        {"data": {"cgpa": float("nan")}},
        {"data": {"cgpa": float("inf")}},
        {"data": {"x" * 61: 1}},
        {"valid_from": "2026-12-01", "valid_to": "2026-01-01"},
        {"holder": {**base["holder"], "mobile": "98765"}},
        {"holder": {**base["holder"], "gender": "X"}},
        {"holder": {**base["holder"], "name": ""}},
        {"holder": {**base["holder"], "search_keys": {"roll_number": "r" * 101, "year": "1"}}},
    ]
    for override in bad:
        e = err(issue(adapter, org, {**base, **override}))
        assert e["code"] == "invalid_request", override
        assert "Asha" not in e["detail"] and "RN-2026" not in e["detail"]  # field names, never values
    assert rows(IssuedDocument, org.id) == []


def test_missing_or_broken_settings_are_not_configured(adapter, documents, org):
    body = issue_input(documents, org)
    assert err(adapter.invoke("issue", ctx(org, settings={}), body))["code"] == "not_configured"
    assert err(adapter.invoke("issue", ctx(org, settings={"issuer_id": "bad id!"}), body))["code"] == "not_configured"


# ---------------------------------------------------------------- push


def push_ctx(**kw):
    return {"settings": settings(push_enabled=True), **kw}


def test_push_with_a_known_wallet_account(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    out = ok(issue(adapter, org, body, **push_ctx()))
    assert out["status"] == "pushed"
    sent = mock.pushed[out["provider_uri"]]
    assert sent["action"] == "A" and sent["digilockerid"] == "dl-holder-0001" and sent["issuedate"] == "05112026"
    assert sent["doctype"] == "DGCER" and sent["docid"] == "DEG-2026-0001"
    [row] = rows(IssuedDocument, org.id)
    assert row.pushed_at is not None and row.push_pending is None


def test_push_finds_the_account_by_mobile_and_never_stores_it(adapter, documents, mock, org):
    mock.add_account("+919800000001", "dl-holder-0001")
    body = issue_input(documents, org)
    body["holder"]["mobile"] = "+919800000001"
    out = ok(issue(adapter, org, body, **push_ctx()))
    assert out["status"] == "pushed"
    [row] = rows(IssuedDocument, org.id)
    assert "9800000001" not in " ".join(str(getattr(row, c.name)) for c in IssuedDocument.__table__.columns)
    assert "9800000001" not in repr([h.detail for h in rows(IssuanceHistory, org.id)])


def test_no_account_found_leaves_the_document_available_for_pull(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["mobile"] = "+919800000009"
    assert ok(issue(adapter, org, body, **push_ctx()))["status"] == "available_for_pull"
    assert mock.pushed == {}


def test_push_disabled_never_calls_digilocker(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    assert ok(issue(adapter, org, body))["status"] == "available_for_pull"
    assert mock.requests == []


def test_push_enabled_without_credentials_is_not_configured(adapter, documents, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    e = err(issue(adapter, org, body, secrets={"issuer_api_key": "k"}, **push_ctx()))
    assert e["code"] == "not_configured"
    [row] = rows(IssuedDocument, org.id)
    assert row.status == "available_for_pull"  # still pullable; a retry after the fix pushes it


def test_a_refused_push_keeps_the_document_pullable_and_a_retry_sends_it(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    wrong = {"issuer_api_key": "k", "push_client_id": PUSH_ID, "push_client_secret": "wrong-secret"}
    e = err(issue(adapter, org, body, secrets=wrong, **push_ctx()))
    assert e["code"] == "auth_failed" and not e["retryable"] and e["provider_code"] == "invalid_hmac"
    [row] = rows(IssuedDocument, org.id)
    assert row.status == "available_for_pull" and row.push_pending == "A"
    assert [h.action for h in rows(IssuanceHistory, org.id)] == ["issued", "push_failed"]
    out = ok(issue(adapter, org, body, **push_ctx()))  # credentials fixed
    assert out["status"] == "pushed"
    assert len(rows(IssuedDocument, org.id)) == 1


def test_a_push_that_cannot_reach_digilocker_is_retryable(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    mock.fail_with = 503
    e = err(issue(adapter, org, body, **push_ctx()))
    assert e["code"] == "provider_error" and e["retryable"]
    mock.fail_with = None
    assert ok(issue(adapter, org, body, **push_ctx()))["status"] == "pushed"


def test_the_push_hmac_is_checked_by_the_provider(mock):
    fields = ["a", "b"]
    assert push_hmac("s", fields) != push_hmac("t", fields)


# ---------------------------------------------------------------- replace, withdraw, get


def test_replace_swaps_the_document_behind_the_same_uri(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    first = ok(issue(adapter, org, body, **push_ctx()))
    document_id, sha256 = documents.add(org.id, pdf("revised"))
    rep = {
        "issuance_key": body["issuance_key"],
        "document_id": document_id,
        "document_sha256": sha256,
        "reason": "revised result",
    }
    out = ok(adapter.invoke("replace", ctx(org, **push_ctx()), rep))
    assert out["provider_uri"] == first["provider_uri"] and out["issuance_id"] == first["issuance_id"]
    assert mock.pushed[first["provider_uri"]]["action"] == "U"
    [row] = rows(IssuedDocument, org.id)
    assert row.sha256 == sha256 and row.data_xml is None  # a corrected result must not keep the old data copy
    again = ok(adapter.invoke("replace", ctx(org, **push_ctx()), rep))
    assert again["status"] == "pushed" and [h.action for h in rows(IssuanceHistory, org.id)].count("replaced") == 1


def test_replace_needs_a_live_issuance_and_the_right_file(adapter, documents, org):
    document_id, sha256 = documents.add(org.id, pdf("r"))
    rep = {"issuance_key": "nope", "document_id": document_id, "document_sha256": sha256, "reason": "x"}
    assert err(adapter.invoke("replace", ctx(org), rep))["code"] == "not_found"
    body = issue_input(documents, org)
    ok(issue(adapter, org, body))
    rep["issuance_key"] = body["issuance_key"]
    rep["document_sha256"] = "1" * 64
    assert err(adapter.invoke("replace", ctx(org), rep))["code"] == "invalid_request"
    ok(adapter.invoke("withdraw", ctx(org), {"issuance_key": body["issuance_key"], "reason": "x"}))
    rep["document_sha256"] = sha256
    assert err(adapter.invoke("replace", ctx(org), rep))["code"] == "not_found"


def test_withdraw_stops_the_pull_and_deletes_the_pushed_uri(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    ok(issue(adapter, org, body, **push_ctx()))
    w = {"issuance_key": body["issuance_key"], "reason": "cancelled"}
    assert ok(adapter.invoke("withdraw", ctx(org, **push_ctx()), w))["status"] == "withdrawn"
    assert mock.pushed["in.ac.example-DGCER-DEG-2026-0001"]["action"] == "D"
    assert ok(adapter.invoke("withdraw", ctx(org, **push_ctx()), w))["status"] == "withdrawn"  # idempotent
    [row] = rows(IssuedDocument, org.id)
    assert row.withdrawn_at is not None and row.wallet_account_id is None and row.push_pending is None


def test_a_failed_delete_push_is_retried_but_the_pull_has_already_stopped(adapter, documents, mock, org):
    body = issue_input(documents, org)
    body["holder"]["wallet_account_id"] = "dl-holder-0001"
    ok(issue(adapter, org, body, **push_ctx()))
    mock.fail_with = 500
    w = {"issuance_key": body["issuance_key"], "reason": "cancelled"}
    assert err(adapter.invoke("withdraw", ctx(org, **push_ctx()), w))["code"] == "provider_error"
    [row] = rows(IssuedDocument, org.id)
    assert row.status == "withdrawn" and row.push_pending == "D"
    mock.fail_with = None
    ok(adapter.invoke("withdraw", ctx(org, **push_ctx()), w))
    assert mock.pushed["in.ac.example-DGCER-DEG-2026-0001"]["action"] == "D"


def test_withdraw_unknown_is_not_found_and_get_issuance_reports_local_state(adapter, documents, mock, org):
    assert err(adapter.invoke("withdraw", ctx(org), {"issuance_key": "nope", "reason": "x"}))["code"] == "not_found"
    body = issue_input(documents, org)
    issued = ok(issue(adapter, org, body))
    got = ok(adapter.invoke("get_issuance", ctx(org), {"issuance_key": body["issuance_key"]}))
    assert got["issuance_id"] == issued["issuance_id"] and got["status"] == "available_for_pull"
    assert got["provider_uri"] == issued["provider_uri"] and got["issued_at"] and got["last_pulled_at"] is None
    assert mock.requests == []  # without calling the provider
    assert err(adapter.invoke("get_issuance", ctx(org), {"issuance_key": "nope"}))["code"] == "not_found"


def test_one_organisation_cannot_touch_anothers_issuance(adapter, documents, org, other_org):
    body = issue_input(documents, org)
    ok(issue(adapter, org, body))
    for op, data in (("get_issuance", {}), ("withdraw", {"reason": "x"})):
        r = adapter.invoke(op, ctx(other_org), {"issuance_key": body["issuance_key"], **data})
        assert err(r)["code"] == "not_found"
