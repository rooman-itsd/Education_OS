"""Export, send and manual delivery: statuses, channels, idempotency, the restricted-country rule and the events."""

import uuid
from datetime import date, timedelta

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_external_university_portals.application.adapter import ExternalUniversityPortalsAdapter
from eos_external_university_portals.domain.models import Exchange
from eos_external_university_portals.infrastructure.documents import CourierError
from eup_support import FIXED_NOW, export, outbox, partner, put, transcript


def _deliver(adapter, org, exchange, mode="mock", settings=None, **kw):
    args = {
        "exchange_id": exchange,
        "delivered_on": "2026-11-05",
        "delivered_by": org.admin_id,
        "partner_reference": "UIO-2026-17",
    }
    args.update(kw)
    return adapter.record_manual_delivery(org.ctx("file", mode, settings), **args)


def test_export_returns_the_file_and_its_hash(adapter, docs, org):
    import hashlib

    r = export(adapter, org, "csv")
    out = r.output
    doc = docs.get(org.id, out["document_id"])
    assert (
        out["format"] == "csv"
        and out["sha256"] == hashlib.sha256(doc.content).hexdigest()
        and uuid.UUID(out["exchange_id"])
    )
    assert doc.filename.endswith(".csv") and doc.content_type == "text/csv"
    (ev,) = outbox(org.id, "external-university-portals.exchange.exported")
    assert ev.payload["exchange_id"] == out["exchange_id"] and "Asha" not in str(ev.payload)


def test_pdf_export_references_the_callers_signed_pdf_and_does_not_copy_it(adapter, docs, org):
    pdf = put(docs, org.id, b"%PDF-1.7 signed transcript", "signed.pdf")
    r = export(adapter, org, "pdf", document_id=pdf)
    assert r.output["document_id"] == pdf and len(docs._docs) == 1
    for bad in (None, "nope", str(uuid.uuid4()), put(docs, org.id, b"not a pdf")):
        r = export(adapter, org, "pdf", document_id=bad)
        assert r.error.code == "invalid_request", bad


def test_another_organisations_pdf_is_not_readable(adapter, docs, org, other_org):
    theirs = put(docs, other_org.id, b"%PDF-1.7 theirs")
    assert export(adapter, org, "pdf", document_id=theirs).error.code == "invalid_request"


def test_reusing_a_key_for_another_partner_or_format_conflicts(adapter, org):
    assert export(adapter, org, "csv", key="k1").ok
    assert (
        export(adapter, org, "csv", key="k1", settings=partner(partner_id="other"), partner_id="other").error.code
        == "conflict"
    )
    assert export(adapter, org, "edc_jsonld", key="k1").error.code == "conflict"


def test_exchange_keys_and_partner_ids_are_checked(adapter, org):
    for key in ("", "x" * 101, "has space", "a/b", "ü"):
        assert export(adapter, org, "csv", key=key).error.code == "invalid_request", key
    assert export(adapter, org, "csv", partner_id="someone-else").error.code == "invalid_request"
    assert export(adapter, org, "docx").error.code == "invalid_request"


# ----------------------------------------------------------------- channels


def test_download_and_partner_portal_answer_manual_action_required_with_the_file(adapter, org):
    for channel in ("download", "partner_portal"):
        s = partner(channel=channel)
        ex = export(adapter, org, "csv", settings=s).output
        r = adapter.send_records(org.ctx("file", settings=s), exchange_id=ex["exchange_id"])
        assert r.error.code == "manual_action_required" and ex["document_id"] in r.error.detail
        assert _status(ex["exchange_id"]) == "manual_action_required"


def test_record_manual_delivery_after_a_manual_action(adapter, org):
    ex = export(adapter, org, "csv").output
    adapter.send_records(org.ctx("file"), exchange_id=ex["exchange_id"])
    r = _deliver(adapter, org, ex["exchange_id"])
    assert (
        r.output == {"exchange_id": ex["exchange_id"], "status": "delivered_manually"}
        and r.provider_reference == "UIO-2026-17"
    )
    (ev,) = outbox(org.id, "external-university-portals.exchange.delivered")
    assert ev.payload["partner_reference"] == "UIO-2026-17" and ev.actor == org.admin_id
    assert _deliver(adapter, org, ex["exchange_id"]).error.code == "conflict"  # twice
    assert (
        adapter.send_records(org.ctx("file"), exchange_id=ex["exchange_id"]).error.code == "conflict"
    )  # nothing left to send


def test_record_delivery_validates_its_input(adapter, org):
    ex = export(adapter, org, "csv").output["exchange_id"]
    cases = [
        {"exchange_id": "nope"},
        {"delivered_by": "nope"},
        {"delivered_on": (date.today() + timedelta(days=9)).isoformat()},
        {"delivered_on": "1999-12-31"},
        {"delivered_on": "2026-02-30"},
        {"delivered_on": 20261105},
        {"partner_reference": ""},
        {"partner_reference": "x" * 101},
        {"partner_reference": "a;b"},
    ]
    for override in cases:
        override = {"exchange_id" if k == "exchange_id" else k: v for k, v in override.items()}
        r = _deliver(adapter, org, override.pop("exchange_id", ex), **override)
        assert r.error and r.error.code == "invalid_request", override
    assert _status(ex) == "prepared"


def test_unknown_exchange_is_not_found(adapter, org):
    unknown = str(uuid.uuid4())
    assert adapter.send_records(org.ctx(), exchange_id=unknown).error.code == "not_found"
    assert _deliver(adapter, org, unknown).error.code == "not_found"


def test_email_sends_a_time_limited_link_not_an_attachment(adapter, courier, org, monkeypatch):
    monkeypatch.setenv("EXTERNAL_UNIVERSITY_PORTALS_LINK_TTL_HOURS", "48")
    s = partner(channel="email", email="records@uio.example")
    ex = export(adapter, org, "csv", settings=s, mode="live").output
    r = adapter.send_records(
        org.ctx("file", "live", s), exchange_id=ex["exchange_id"], message="Transcript for Asha Nair, as requested."
    )
    assert r.output == {
        "exchange_id": ex["exchange_id"],
        "status": "sent",
        "channel": "email",
        "provider_reference": "mock-000001",
    }
    (sent,) = courier.sent
    assert (
        sent["to"] == "records@uio.example"
        and sent["document_id"] == ex["document_id"]
        and sent["expires_in_hours"] == 48
    )
    assert "attachment" not in sent and sent["message"].startswith("Transcript")
    assert _status(ex["exchange_id"]) == "sent"
    with platform_scope(), SessionLocal() as db:
        assert db.get(Exchange, ex["exchange_id"]).link_expires_at.replace(tzinfo=None) == (
            FIXED_NOW + timedelta(hours=48)
        ).replace(tzinfo=None)
    (ev,) = outbox(org.id, "external-university-portals.exchange.sent")
    assert ev.payload["status"] == "sent" and "Asha" not in str(ev.payload)
    assert adapter.send_records(org.ctx("file", "live", s), exchange_id=ex["exchange_id"]).error.code == "conflict"


@pytest.mark.parametrize("mode", ["mock", "sandbox"])
def test_mock_and_sandbox_never_deliver(adapter, courier, org, mode):
    s = partner(channel="email", email="records@uio.example")
    ex = export(adapter, org, "csv", settings=s, mode=mode).output
    r = adapter.send_records(org.ctx("file", mode, s), exchange_id=ex["exchange_id"])
    assert r.output["status"] == "prepared" and r.output["provider_reference"] == f"{mode}-not-delivered"
    assert courier.sent == [] and _status(ex["exchange_id"]) == "prepared"


def test_email_failures_map_to_port_errors(adapter, courier, org):
    s = partner(channel="email", email="records@uio.example")
    ex = export(adapter, org, "csv", settings=s, mode="live").output["exchange_id"]
    courier.fail = CourierError(retryable=True)
    r = adapter.send_records(org.ctx("file", "live", s), exchange_id=ex)
    assert r.error.code == "transport_unavailable" and r.error.retryable is True and _status(ex) == "prepared"
    courier.fail = CourierError(retryable=False)
    assert adapter.send_records(org.ctx("file", "live", s), exchange_id=ex).error.code == "rejected"
    courier.fail = None
    assert adapter.send_records(org.ctx("file", "live", s), exchange_id=ex).ok  # a later retry works


def test_email_needs_an_address_and_a_courier(adapter, docs, org):
    no_address = partner(channel="email")
    ex = export(adapter, org, "csv", settings=no_address).output["exchange_id"]
    assert adapter.send_records(org.ctx("file", "live", no_address), exchange_id=ex).error.code == "not_configured"
    no_courier = ExternalUniversityPortalsAdapter(
        documents=docs, clock=lambda: FIXED_NOW
    )  # documents injected, no courier
    s = partner(channel="email", email="a@b.example")
    ex2 = export(no_courier, org, "csv", settings=s, mode="live").output["exchange_id"]
    assert no_courier.send_records(org.ctx("file", "live", s), exchange_id=ex2).error.code == "not_configured"


def test_the_api_channel_is_unsupported_until_ewp(adapter, org):
    s = partner(channel="api")
    ex = export(adapter, org, "csv", settings=s).output["exchange_id"]
    assert adapter.send_records(org.ctx("file", settings=s), exchange_id=ex).error.code == "unsupported"


def test_a_partner_in_a_restricted_country_gets_nothing(adapter, courier, org, monkeypatch):
    s = partner(country="KP", channel="email", email="x@y.example")
    ok_export = export(adapter, org, "csv", key="before", settings=s)
    assert ok_export.ok  # nothing restricted yet
    monkeypatch.setenv("EXTERNAL_UNIVERSITY_PORTALS_RESTRICTED_COUNTRIES", "kp, xx ,  not-a-code")
    assert export(adapter, org, "csv", key="after", settings=s).error.code == "rejected"
    assert (
        adapter.send_records(org.ctx("file", "live", s), exchange_id=ok_export.output["exchange_id"]).error.code
        == "rejected"
    )
    assert courier.sent == []
    assert export(adapter, org, "csv", key="fine", settings=partner(country="NO")).ok


def test_send_and_record_are_scoped_to_the_connections_partner(adapter, org):
    ex = export(adapter, org, "csv").output["exchange_id"]
    other = partner(partner_id="someone-else")
    assert adapter.send_records(org.ctx("file", settings=other), exchange_id=ex).error.code == "not_found"
    assert (
        adapter.record_manual_delivery(
            org.ctx("file", settings=other),
            exchange_id=ex,
            delivered_on="2026-11-05",
            delivered_by=org.admin_id,
            partner_reference="R",
        ).error.code
        == "not_found"
    )


def test_an_inbound_exchange_cannot_be_sent_or_delivered(adapter, docs, org):
    doc = put(docs, org.id, b"course_code,title,credits,status\nC,T,1,passed\n")
    ex = adapter.import_records(
        org.ctx(), exchange_key="inb", partner_id="uni-oslo", format="csv", document_id=doc
    ).output["exchange_id"]
    assert adapter.send_records(org.ctx(), exchange_id=ex).error.code == "not_found"
    assert _deliver(adapter, org, ex).error.code == "conflict"


def test_message_is_bounded(adapter, org):
    ex = export(adapter, org, "csv").output["exchange_id"]
    for bad in (5, ["x"], "x" * 2001):
        assert adapter.send_records(org.ctx(), exchange_id=ex, message=bad).error.code == "invalid_request"


def test_the_transcript_is_not_kept(adapter, org):
    ex = export(adapter, org, "csv", key="nokeep").output["exchange_id"]
    with platform_scope(), SessionLocal() as db:
        row = db.get(Exchange, ex)
        assert "Asha" not in repr(row.__dict__) and "Nair" not in repr(row.__dict__)
        assert row.person_id == transcript()["learner"]["person_id"] and row.caller_reference == "nokeep"


def _status(exchange_id: str) -> str:
    with platform_scope(), SessionLocal() as db:
        return db.get(Exchange, exchange_id).status
