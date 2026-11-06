"""The requester side: OAuth with PKCE S256, then listing and fetching a person's documents with their consent.
Wire format checked against recorded pairs (tests/fixtures); the full round trip against the mock simulator."""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from dgl_support import REDIRECT, Replay, ctx, err, fixed_clock, fixture, link_ctx, ok, pdf, sha
from eos_core.db import SessionLocal
from eos_digilocker.application.adapter import DigiLockerAdapter
from eos_digilocker.application.runtime import Runtime


def verifier_and_challenge():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def begin(adapter, org, challenge, **kw):
    inp = {"state": "state-abcdef", "code_challenge": challenge, "redirect_uri": REDIRECT, "scope_hint": ["HSCER"]}
    inp.update(kw)
    return adapter.invoke("begin_authorisation", ctx(org), inp)


def test_begin_authorisation_builds_the_pkce_s256_url(adapter, org, now):
    _, challenge = verifier_and_challenge()
    url = ok(begin(adapter, org, challenge))["authorize_url"]
    parsed = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert parsed.path.endswith("/oauth2/1/authorize")
    assert q["response_type"] == "code" and q["client_id"] == "REQ-APP-001"
    assert q["code_challenge"] == challenge and q["code_challenge_method"] == "S256"
    assert q["purpose"] == "educational" and q["req_doctype"] == "HSCER" and q["state"] == "state-abcdef"
    assert int(q["consent_valid_till"]) == int(now.timestamp()) + 30 * 86400
    assert "secret" not in url  # the client secret is never in a URL


def test_consent_validity_and_purpose_follow_the_deployment(adapter, org, monkeypatch, now):
    monkeypatch.setenv("DIGILOCKER_CONSENT_DAYS", "7")
    monkeypatch.setenv("DIGILOCKER_REQUESTER_PURPOSE", "verification")
    q = parse_qs(urlparse(ok(begin(adapter, org, verifier_and_challenge()[1]))["authorize_url"]).query)
    assert q["purpose"] == ["verification"] and int(q["consent_valid_till"][0]) == int(now.timestamp()) + 7 * 86400


def test_begin_authorisation_refuses_what_is_not_pkce_s256_or_not_https(adapter, org):
    _, challenge = verifier_and_challenge()
    for override in (
        {"code_challenge": "plain-verifier"},
        {"code_challenge": "a" * 42},
        {"redirect_uri": "http://evil.example/cb"},
        {"redirect_uri": "javascript:alert(1)"},
        {"redirect_uri": REDIRECT + "#frag"},
        {"state": "x"},
        {"scope_hint": ["bad code!"]},
    ):
        assert err(begin(adapter, org, challenge, **override))["code"] == "invalid_request", override


def test_requester_app_missing_is_not_configured_in_live_mode(adapter, org, monkeypatch):
    monkeypatch.delenv("DIGILOCKER_REQUESTER_CLIENT_ID")
    monkeypatch.setenv("DIGILOCKER_LIVE_BASE_URL", "https://api.example.invalid/public")
    inp = {"state": "state-abcdef", "code_challenge": verifier_and_challenge()[1], "redirect_uri": REDIRECT}
    assert err(adapter.invoke("begin_authorisation", ctx(org, mode="live"), inp))["code"] == "not_configured"


def replay_adapter(documents, *names):
    replay = Replay(*names)
    rt = Runtime(session_factory=SessionLocal, documents=documents, http_factory=replay.client, clock=fixed_clock)
    return DigiLockerAdapter(rt), replay


def test_token_exchange_matches_the_recorded_pair_and_drops_everything_but_the_tokens(documents, org, monkeypatch):
    adapter, replay = replay_adapter(documents, "oauth_token_exchange.json")
    fx = fixture("oauth_token_exchange.json")
    inp = {"code": "auth-code-fixture", "code_verifier": "v" * 50, "redirect_uri": REDIRECT}
    result = adapter.invoke("complete_authorisation", ctx(org, mode="sandbox"), inp)
    out = ok(result)
    assert out["secrets"] == {"access_token": "access-token-fixture", "refresh_token": "refresh-token-fixture"}
    assert out["provider_subject"] == "dl-holder-0001" and out["granted_scopes"] == []
    assert out["expires_at"].startswith("2026-11-05T05:30:00")
    blob = repr(result)
    for dropped in ("Asha Rao", "01012004", "eaadhaar", "ref-fixture-1"):
        assert dropped not in blob  # name, date of birth and the Aadhaar flag never leave the adapter
    assert fx["code_challenge"] and len(replay.seen) == 1


def test_a_refused_code_means_the_person_must_consent_again(documents, org):
    adapter, _ = replay_adapter(documents, "oauth_token_refused.json")
    # the recorded refusal is for the refresh request; a code exchange against it is unrecorded, so use refresh
    r = adapter.invoke("refresh_authorisation", link_ctx(org, mode="sandbox"), {})
    assert err(r)["code"] == "consent_required" and err(r)["provider_code"] == "invalid_grant"


def test_refresh_matches_the_recorded_pair(documents, org):
    adapter, _ = replay_adapter(documents, "oauth_token_refresh.json")
    out = ok(adapter.invoke("refresh_authorisation", link_ctx(org, mode="sandbox"), {}))
    assert out["secrets"] == {"access_token": "access-token-fixture-2", "refresh_token": "refresh-token-fixture-2"}


def test_refresh_without_a_refresh_token_is_consent_required(adapter, org):
    assert err(adapter.invoke("refresh_authorisation", ctx(org, secrets={}), {}))["code"] == "consent_required"


def test_full_round_trip_against_the_simulator_proves_pkce(adapter, mock, org, documents):
    mock.add_account("+919800000001", "dl-holder-0001")
    verifier, challenge = verifier_and_challenge()
    code = mock.grant_code("dl-holder-0001", "REQ-APP-001", challenge)
    done = ok(
        adapter.invoke(
            "complete_authorisation", ctx(org), {"code": code, "code_verifier": verifier, "redirect_uri": REDIRECT}
        )
    )
    assert done["provider_subject"] == "dl-holder-0001"
    # a wrong verifier is refused by the provider
    code2 = mock.grant_code("dl-holder-0001", "REQ-APP-001", challenge)
    bad = adapter.invoke(
        "complete_authorisation", ctx(org), {"code": code2, "code_verifier": "x" * 50, "redirect_uri": REDIRECT}
    )
    assert err(bad)["code"] == "consent_required" and not err(bad)["retryable"]
    # the refresh token rotates; the old one no longer works
    refreshed = ok(adapter.invoke("refresh_authorisation", ctx(org, secrets=done["secrets"]), {}))
    assert refreshed["secrets"]["access_token"] != done["secrets"]["access_token"]
    stale = adapter.invoke("refresh_authorisation", ctx(org, secrets=done["secrets"]), {})
    assert err(stale)["code"] == "consent_required"


def test_wrong_client_secret_is_auth_failed(adapter, mock, org, monkeypatch):
    monkeypatch.setenv("DIGILOCKER_REQUESTER_CLIENT_SECRET", "wrong")
    _, challenge = verifier_and_challenge()
    code = mock.grant_code("dl-holder-0001", "REQ-APP-001", challenge)
    r = adapter.invoke(
        "complete_authorisation", ctx(org), {"code": code, "code_verifier": "x" * 50, "redirect_uri": REDIRECT}
    )
    assert err(r)["code"] == "auth_failed" and err(r)["provider_code"] == "invalid_client"


def test_revoke_calls_the_provider_and_is_a_noop_with_nothing_granted(adapter, mock, org):
    token = mock._issue_tokens("dl-holder-0001", "REQ-APP-001")
    assert ok(
        adapter.invoke("revoke_authorisation", ctx(org, secrets={"refresh_token": token["refresh_token"]}), {})
    ) == {"revoked": True}
    assert mock.revoked == [token["refresh_token"]]
    assert ok(adapter.invoke("revoke_authorisation", ctx(org, secrets={}), {})) == {"revoked": False}


# ---------------------------------------------------------------- list and fetch


def test_list_holder_documents_matches_the_recorded_pair(documents, org):
    adapter, _ = replay_adapter(documents, "files_issued.json")
    c = link_ctx(org, mode="sandbox")
    out = ok(adapter.invoke("list_holder_documents", c, {"account_link_id": c["account_link"]["id"]}))
    assert out["items"] == [
        {
            "provider_uri": "in.gov.cbse-HSCER-2019-1234567",
            "issuer": "CBSE",
            "doc_type": "HSCER",
            "title": "Class XII Marksheet",
            "issued_on": "2019-02-08",
        }
    ]  # fmt: skip  (the hostile second entry, a URI with spaces, is dropped)


def test_fetch_verifies_the_hmac_and_stores_the_file(documents, org):
    adapter, _ = replay_adapter(documents, "file_by_uri.json")
    c = link_ctx(org, mode="sandbox")
    out = ok(adapter.invoke("fetch_holder_document", c, {
        "account_link_id": c["account_link"]["id"], "provider_uri": "in.gov.cbse-HSCER-2019-1234567",
        "purpose": "admission_verification"}))  # fmt: skip
    content = b"%PDF-1.4 class XII marksheet fixture"
    assert out["integrity_verified"] is True and out["sha256"] == sha(content)
    assert out["issuer"] == "in.gov.cbse" and out["doc_type"] == "HSCER"
    assert documents.get(org.id, out["document_id"]) == content


def test_a_file_with_a_wrong_hmac_is_never_kept(documents, org):
    adapter, _ = replay_adapter(documents, "file_by_uri_bad_hmac.json")
    c = link_ctx(org, mode="sandbox")
    r = adapter.invoke("fetch_holder_document", c, {
        "account_link_id": c["account_link"]["id"], "provider_uri": "in.gov.cbse-HSCER-2019-1234567",
        "purpose": "record_verification"})  # fmt: skip
    assert err(r)["provider_code"] == "hmac_mismatch" and err(r)["code"] == "provider_error"
    assert documents.files == {}


def test_round_trip_list_and_fetch_against_the_simulator(adapter, mock, documents, org):
    mock.add_account("+919800000001", "dl-holder-0001")
    mock.add_file("dl-holder-0001", "in.gov.cbse-HSCER-2019-1", pdf("hscer"), doctype="HSCER", issuer="CBSE",
                  issuerid="in.gov.cbse", description="Class XII Marksheet")  # fmt: skip
    token = mock._issue_tokens("dl-holder-0001", "REQ-APP-001")["access_token"]
    c = link_ctx(org, access=token)
    link = c["account_link"]["id"]
    [item] = ok(adapter.invoke("list_holder_documents", c, {"account_link_id": link}))["items"]
    out = ok(
        adapter.invoke(
            "fetch_holder_document",
            c,
            {"account_link_id": link, "provider_uri": item["provider_uri"], "purpose": "admission_verification"},
        )
    )
    assert documents.get(org.id, out["document_id"]) == pdf("hscer")
    # pull on demand by search parameters
    via = ok(
        adapter.invoke(
            "fetch_holder_document",
            c,
            {
                "account_link_id": link,
                "lookup": {"issuer_id": "in.gov.cbse", "doc_type": "HSCER", "roll": "1"},
                "purpose": "admission_verification",
            },
        )
    )
    assert via["issuer"] == "in.gov.cbse"
    # a corrupted file from the provider is refused
    mock.corrupt_file_hmac = True
    r = adapter.invoke(
        "fetch_holder_document",
        c,
        {"account_link_id": link, "provider_uri": item["provider_uri"], "purpose": "admission_verification"},
    )
    assert err(r)["code"] == "provider_error"


def test_no_link_or_the_wrong_link_means_consent_required(adapter, org):
    body = {
        "account_link_id": str(uuid4()),
        "provider_uri": "in.gov.cbse-HSCER-2019-1",
        "purpose": "admission_verification",
    }
    assert err(adapter.invoke("fetch_holder_document", ctx(org), body))["code"] == "consent_required"
    assert (
        err(adapter.invoke("list_holder_documents", ctx(org), {"account_link_id": body["account_link_id"]}))["code"]
        == "consent_required"
    )
    c = link_ctx(org)  # a link, but not the one the caller named
    assert err(adapter.invoke("fetch_holder_document", c, body))["code"] == "consent_required"
    no_token = ctx(org, link={"id": body["account_link_id"]}, secrets={})
    assert err(adapter.invoke("fetch_holder_document", no_token, body))["code"] == "consent_required"


def test_an_expired_token_is_consent_required(adapter, org):
    c = link_ctx(org, access="expired-token")
    r = adapter.invoke("list_holder_documents", c, {"account_link_id": c["account_link"]["id"]})
    assert err(r)["code"] == "consent_required" and not err(r)["retryable"]


def test_fetch_input_is_validated(adapter, org):
    c = link_ctx(org)
    link = c["account_link"]["id"]
    for body in (
        {"purpose": "admission_verification"},
        {"provider_uri": "a-b-c", "lookup": {"issuer_id": "x", "doc_type": "y"}, "purpose": "admission_verification"},
        {"provider_uri": "bad uri\n", "purpose": "admission_verification"},
        {"provider_uri": "a-b-c", "purpose": "marketing"},
        {"lookup": {"issuer_id": "x"}, "purpose": "record_verification"},
    ):
        assert (
            err(adapter.invoke("fetch_holder_document", c, {"account_link_id": link, **body}))["code"]
            == "invalid_request"
        ), body


def test_a_file_larger_than_the_limit_is_refused(adapter, mock, documents, org, monkeypatch):
    monkeypatch.setenv("DIGILOCKER_MAX_DOCUMENT_BYTES", "1024")
    mock.add_file("dl-holder-0001", "in.gov.x-D-1", b"%PDF" + b"0" * 2048, doctype="D", issuer="X", issuerid="in.gov.x")
    token = mock._issue_tokens("dl-holder-0001", "REQ-APP-001")["access_token"]
    c = link_ctx(org, access=token)
    r = adapter.invoke(
        "fetch_holder_document",
        c,
        {
            "account_link_id": c["account_link"]["id"],
            "provider_uri": "in.gov.x-D-1",
            "purpose": "admission_verification",
        },
    )
    assert err(r)["code"] == "invalid_request" and documents.files == {}
