from __future__ import annotations

from datetime import UTC, timedelta, timezone

import pytest
from conftest import add_application, add_document, add_offer, make_actor
from eos_admissions.application import service as svc
from eos_admissions.application.service import AdmissionsError
from eos_admissions.domain import enums as e
from eos_admissions.infrastructure.models import Offer
from eos_core.db import new_id, utcnow


def refused(fn, *args, **kwargs) -> tuple[int, str]:
    with pytest.raises(AdmissionsError) as exc:
        fn(*args, **kwargs)
    return exc.value.status, exc.value.code


# ---------------------------------------------------------------- list and read


def test_list_filters_search_and_pages(db, staff, org):
    programme = new_id()
    first = add_application(db, org, programme_id=programme, applicant_first_name="Zara", submitted_at=utcnow())
    second = add_application(
        db, org, programme_id=programme, status=e.ELIGIBLE, submitted_at=utcnow() + timedelta(minutes=1)
    )
    add_application(db, org, academic_year="2027-28")
    add_application(db, new_id())

    everything = svc.list_applications(db, staff)
    assert everything["total"] == 3

    by_programme = svc.list_applications(db, staff, programme_id=programme)
    assert [a["id"] for a in by_programme["items"]] == [second.id, first.id]

    assert svc.list_applications(db, staff, statuses=[e.ELIGIBLE])["total"] == 1
    assert svc.list_applications(db, staff, academic_year="2027-28")["total"] == 1
    assert [a["id"] for a in svc.list_applications(db, staff, q="zar")["items"]] == [first.id]
    assert svc.list_applications(db, staff, q=first.reference_number.lower())["total"] == 1
    assert svc.list_applications(db, staff, q="100%")["total"] == 0

    page = svc.list_applications(db, staff, page=2, page_size=2)
    assert (page["total"], len(page["items"]), page["page"], page["page_size"]) == (3, 1, 2, 2)


def test_view_includes_documents_and_current_offer(db, staff, org):
    app = add_application(db, org, status=e.OFFERED)
    add_document(db, app)
    add_offer(db, app, status=e.OFFER_EXPIRED, offered_at=utcnow() - timedelta(days=3))
    current = add_offer(db, app)
    view = svc.get_application(db, staff, app.id)
    assert len(view["documents"]) == 1
    assert view["offer"]["id"] == current.id


def test_view_shows_an_open_offer_past_expiry_as_expired_without_writing(db, staff, org):
    app = add_application(db, org, status=e.OFFERED)
    offer = add_offer(db, app, expires_at=utcnow() - timedelta(minutes=1))
    assert svc.get_application(db, staff, app.id)["offer"]["status"] == e.OFFER_EXPIRED
    db.refresh(offer)
    assert offer.status == e.OFFER_OPEN


def test_other_organisation_gets_not_found(db, org, other_org):
    app = add_application(db, org, status=e.ELIGIBLE)
    outsider = make_actor(other_org)
    assert refused(svc.get_application, db, outsider, app.id) == (404, "not_found")
    assert refused(svc.change_status, db, outsider, app.id, e.WITHDRAWN, "x") == (404, "not_found")
    assert refused(svc.make_offer, db, outsider, app.id) == (404, "not_found")
    assert svc.list_applications(db, outsider)["total"] == 0


# ---------------------------------------------------------------- status


def test_change_status_records_decision_time_only_when_terminal(db, staff, org):
    app = add_application(db, org)
    view = svc.change_status(db, staff, app.id, e.UNDER_REVIEW, "  documents complete  ")
    assert view["status"] == e.UNDER_REVIEW and view["decided_at"] is None
    view = svc.change_status(db, staff, app.id, e.INELIGIBLE, "below minimum grade")
    assert view["status"] == e.INELIGIBLE and view["decided_at"] is not None


def test_change_status_refusals(db, staff, org):
    submitted = add_application(db, org)
    rejected = add_application(db, org, status=e.REJECTED)
    assert refused(svc.change_status, db, staff, rejected.id, e.UNDER_REVIEW, "r") == (409, "terminal_status")
    assert refused(svc.change_status, db, staff, submitted.id, e.ELIGIBLE, "r") == (422, "invalid_transition")
    assert refused(svc.change_status, db, staff, submitted.id, e.UNDER_REVIEW, "  ") == (422, "reason_required")
    assert refused(svc.change_status, db, staff, new_id(), e.UNDER_REVIEW, "r") == (404, "not_found")


def test_withdrawing_an_offered_application_closes_its_offer(db, staff, org):
    app = add_application(db, org, status=e.OFFERED)
    offer = add_offer(db, app)
    view = svc.change_status(db, staff, app.id, e.WITHDRAWN, "applicant asked")
    assert view["status"] == e.WITHDRAWN
    assert view["offer"]["status"] == e.WITHDRAWN
    db.refresh(offer)
    assert offer.decided_at is not None


# ---------------------------------------------------------------- documents


def test_verify_document_by_row_id_or_platform_id(db, staff, org):
    app = add_application(db, org, status=e.UNDER_REVIEW)
    first, second = add_document(db, app), add_document(db, app)
    by_row = svc.verify_document(db, staff, app.id, first.id, e.VERIFIED, "clear scan")
    assert (by_row["verification_status"], by_row["verification_note"], by_row["verified_by"]) == (
        e.VERIFIED,
        "clear scan",
        staff.user_id,
    )
    assert by_row["verified_at"] is not None
    by_platform = svc.verify_document(db, staff, app.id, second.document_id, e.REJECTED, None)
    assert by_platform["id"] == second.id and by_platform["verification_status"] == e.REJECTED


def test_verify_document_must_belong_to_the_application(db, staff, org):
    app, other = add_application(db, org), add_application(db, org)
    doc = add_document(db, other)
    assert refused(svc.verify_document, db, staff, app.id, doc.id, e.VERIFIED, None) == (404, "not_found")


# ---------------------------------------------------------------- offers


def test_make_offer(db, staff, org):
    app = add_application(db, org, status=e.ELIGIBLE)
    expires = utcnow() + timedelta(days=14)
    view = svc.make_offer(db, staff, app.id, "Welcome", expires)
    assert view["status"] == e.OFFERED
    assert view["offer"]["status"] == e.OFFER_OPEN
    assert view["offer"]["note"] == "Welcome"
    assert view["offer"]["offered_by"] == staff.user_id


def test_make_offer_refusals(db, staff, org):
    under_review = add_application(db, org, status=e.UNDER_REVIEW)
    assert refused(svc.make_offer, db, staff, under_review.id) == (409, "not_eligible")
    offered = add_application(db, org, status=e.ELIGIBLE)
    svc.make_offer(db, staff, offered.id)
    assert refused(svc.make_offer, db, staff, offered.id) == (409, "offer_already_exists")
    assert db.query(Offer).filter(Offer.application_id == offered.id).count() == 1


def test_make_offer_again_after_the_previous_one_expired(db, staff, org):
    app = add_application(db, org, status=e.ELIGIBLE)
    svc.make_offer(db, staff, app.id, expires_at=utcnow() - timedelta(minutes=1))
    assert svc.get_application(db, staff, app.id)["offer"]["status"] == e.OFFER_EXPIRED
    view = svc.make_offer(db, staff, app.id, "Second chance", utcnow() + timedelta(days=7))
    assert view["status"] == e.OFFERED
    assert view["offer"]["status"] == e.OFFER_OPEN
    assert view["offer"]["note"] == "Second chance"
    statuses = sorted(o.status for o in db.query(Offer).filter(Offer.application_id == app.id))
    assert statuses == [e.OFFER_EXPIRED, e.OFFER_OPEN]
    # still at most one open offer, and a live one still blocks
    assert refused(svc.make_offer, db, staff, app.id) == (409, "offer_already_exists")


def test_expires_at_is_stored_as_utc_whatever_offset_the_caller_sent(db, staff, org):
    app = add_application(db, org, status=e.ELIGIBLE)
    an_hour_ahead = (utcnow() + timedelta(hours=1)).astimezone(timezone(timedelta(hours=-8)))
    svc.make_offer(db, staff, app.id, expires_at=an_hour_ahead)
    db.flush()
    db.expire_all()  # read the row back from the database, not from memory
    view = svc.get_application(db, staff, app.id)
    assert view["offer"]["status"] == e.OFFER_OPEN
    assert view["offer"]["expires_at"] == an_hour_ahead.astimezone(UTC).isoformat()


# ---------------------------------------------------------------- merit lists


def test_generate_merit_list_ranks_only_the_eligible_pool(db, staff, org):
    programme, now = new_id(), utcnow()
    early = add_application(db, org, programme_id=programme, status=e.ELIGIBLE, submitted_at=now)
    late = add_application(db, org, programme_id=programme, status=e.ELIGIBLE, submitted_at=now + timedelta(hours=1))
    top = add_application(db, org, programme_id=programme, status=e.ELIGIBLE, submitted_at=now + timedelta(hours=2))
    add_application(db, org, programme_id=programme, status=e.UNDER_REVIEW)
    add_application(db, org, programme_id=programme, status=e.ELIGIBLE, academic_year="2027-28")
    add_application(db, org, status=e.ELIGIBLE)

    merit = svc.generate_merit_list(
        db, staff, programme_id=programme, academic_year="2026-27", title="Round 1", scores=[(top.id, 91.5)]
    )
    assert merit["status"] == e.DRAFT and merit["title"] == "Round 1" and merit["published_at"] is None
    assert [(x["application_id"], x["rank"], x["score"]) for x in merit["entries"]] == [
        (top.id, 1, 91.5),
        (early.id, 2, None),
        (late.id, 3, None),
    ]
    assert merit["entries"][0]["reference_number"] == top.reference_number


def test_generate_merit_list_score_refusals(db, staff, org):
    programme = new_id()
    eligible = add_application(db, org, programme_id=programme, status=e.ELIGIBLE)
    pending = add_application(db, org, programme_id=programme, status=e.UNDER_REVIEW)
    args = {"programme_id": programme, "academic_year": "2026-27"}
    assert refused(svc.generate_merit_list, db, staff, **args, scores=[(pending.id, 50.0)]) == (
        422,
        "score_for_ineligible_application",
    )
    assert refused(svc.generate_merit_list, db, staff, **args, scores=[(eligible.id, 1.0), (eligible.id, 2.0)]) == (
        422,
        "duplicate_score",
    )


def test_empty_pool_gives_an_empty_draft(db, staff):
    merit = svc.generate_merit_list(db, staff, programme_id=new_id(), academic_year="2026-27")
    assert merit["entries"] == []


def test_publish_merit_list_once(db, staff, org):
    merit = svc.generate_merit_list(db, staff, programme_id=new_id(), academic_year="2026-27")
    published = svc.publish_merit_list(db, staff, merit["id"])
    assert published["status"] == e.PUBLISHED and published["published_at"] is not None
    assert refused(svc.publish_merit_list, db, staff, merit["id"]) == (409, "merit_list_already_published")


def test_list_and_get_merit_lists(db, staff, org, other_org):
    programme = new_id()
    mine = svc.generate_merit_list(db, staff, programme_id=programme, academic_year="2026-27")
    svc.generate_merit_list(db, staff, programme_id=new_id(), academic_year="2026-27")
    svc.generate_merit_list(db, make_actor(other_org), programme_id=programme, academic_year="2026-27")
    assert len(svc.list_merit_lists(db, staff)) == 2
    assert [m["id"] for m in svc.list_merit_lists(db, staff, programme_id=programme)] == [mine["id"]]
    assert svc.get_merit_list(db, staff, mine["id"])["id"] == mine["id"]
    assert refused(svc.get_merit_list, db, make_actor(other_org), mine["id"]) == (404, "not_found")
