"""GET /reports/funnel (counts per stage) and GET /documents (the verification queue)."""

from __future__ import annotations

from datetime import timedelta

from conftest import add_application, add_document, make_actor
from eos_admissions.application import service as svc
from eos_admissions.domain import enums as e
from eos_core.db import new_id, utcnow

# ---------------------------------------------------------------- funnel


def test_funnel_counts_by_status_and_stage(db, staff, org):
    for status, count in {e.SUBMITTED: 3, e.ELIGIBLE: 2, e.OFFERED: 1, e.ACCEPTED: 2, e.REJECTED: 1}.items():
        for _ in range(count):
            add_application(db, org, status=status)
    report = svc.funnel_report(db, staff)
    assert report["total"] == 9
    assert report["stages"] == {"applied": 9, "eligible": 5, "offered": 3, "accepted": 2}
    assert report["by_status"][e.SUBMITTED] == 3 and report["by_status"][e.WITHDRAWN] == 0
    assert (report["programme_id"], report["academic_year"]) == (None, None)


def test_funnel_filters(db, staff, org):
    programme = new_id()
    add_application(db, org, programme_id=programme, status=e.ACCEPTED)
    add_application(db, org, programme_id=programme, academic_year="2027-28")
    add_application(db, org)
    assert svc.funnel_report(db, staff, programme_id=programme)["total"] == 2
    one = svc.funnel_report(db, staff, programme_id=programme, academic_year="2026-27")
    assert (one["total"], one["stages"]["accepted"], one["programme_id"]) == (1, 1, programme)


def test_funnel_of_an_empty_organisation(db, staff):
    report = svc.funnel_report(db, staff)
    assert report["total"] == 0
    assert set(report["by_status"]) == set(e.APPLICATION_STATUSES)


def test_funnel_never_counts_another_organisation(db, staff, org, other_org):
    add_application(db, other_org, status=e.ACCEPTED)
    assert svc.funnel_report(db, staff)["total"] == 0
    assert svc.funnel_report(db, make_actor(other_org))["total"] == 1


# ---------------------------------------------------------------- document queue


def test_queue_is_oldest_first_with_reference_and_name(db, staff, org):
    now = utcnow()
    app = add_application(db, org, status=e.UNDER_REVIEW, applicant_first_name="Ana", applicant_last_name="Silva")
    newer = add_document(db, app, uploaded_at=now)
    older = add_document(db, app, uploaded_at=now - timedelta(hours=2))
    queue = svc.list_documents(db, staff)
    assert [d["id"] for d in queue["items"]] == [older.id, newer.id]
    assert queue["items"][0]["reference_number"] == app.reference_number
    assert queue["items"][0]["applicant_name"] == "Ana Silva"
    assert queue["total"] == 2


def test_pending_queue_leaves_out_closed_applications(db, staff, org):
    open_doc = add_document(db, add_application(db, org, status=e.SUBMITTED))
    offered_doc = add_document(db, add_application(db, org, status=e.OFFERED))
    for status in sorted(e.TERMINAL):
        add_document(db, add_application(db, org, status=status))
    assert {d["id"] for d in svc.list_documents(db, staff)["items"]} == {open_doc.id, offered_doc.id}


def test_queue_filters_by_verification_status(db, staff, org):
    rejected_app = add_application(db, org, status=e.REJECTED)
    verified = add_document(db, rejected_app, verification_status=e.VERIFIED)
    add_document(db, add_application(db, org), verification_status=e.REJECTED)
    assert [d["id"] for d in svc.list_documents(db, staff, verification_status=e.VERIFIED)["items"]] == [verified.id]
    assert svc.list_documents(db, staff, verification_status=e.REJECTED)["total"] == 1


def test_queue_pages(db, staff, org):
    app = add_application(db, org)
    for _ in range(5):
        add_document(db, app)
    page = svc.list_documents(db, staff, page=2, page_size=2)
    assert (page["total"], len(page["items"]), page["page"]) == (5, 2, 2)


def test_queue_never_lists_another_organisation(db, staff, org, other_org):
    add_document(db, add_application(db, other_org))
    assert svc.list_documents(db, staff)["total"] == 0
