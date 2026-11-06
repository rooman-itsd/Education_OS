"""Publishing and unpublishing a timetable end to end (FR-3): POST /timetables/{id}/publish and /unpublish.

What these tests rely on, because the rest of the module is not built yet:
- The instructor assignment of every slot is a row written directly by `Org.academic()` (conftest): the consumer that
  would fill `assignment_ref` is not built, because the identity mapping of the assignee is unconfirmed.
- The scheduled classes that unpublishing cancels are rows inserted directly (`seed_class`), because generating
  classes (`generate-classes`, and the generation step of publishing) is not served until the organisation's time zone
  is decided (docs/reviewer-decisions.md, section 10). Publishing therefore creates no class and says so
  (`scheduled_class_count: 0`); one test pins that.
- Attendance sessions are inserted directly (`seed_session`): opening one is a later batch."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    ADMIN,
    BASE,
    FACULTY,
    HEAD,
    NOW,
    STUDENT,
    audit_entries,
    deliver,
    make_timetable,
    ok,
    outbox,
    slot,
    term_created,
)
from eos_core.db import SessionLocal  # noqa: E402
from eos_timetable_attendance.application.consumers import TERM_CREATED  # noqa: E402
from eos_timetable_attendance.infrastructure import repository as repo  # noqa: E402
from eos_timetable_attendance.infrastructure.models import (  # noqa: E402
    AttendanceSessionRow,
    ScheduledClassRow,
    TimetableRow,
    iso,
)

PUBLISHED_EVENT = "timetable-attendance.timetable.published"
UNPUBLISHED_EVENT = "timetable-attendance.timetable.unpublished"
CLASS_CANCELLED_EVENT = "timetable-attendance.scheduled-class.cancelled"


def err(response, status: int) -> dict:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()["detail"]


def know_term(org, period_id: str) -> None:
    """The term reaches the read model through the real consumer, as academic-management publishes it."""
    deliver(org.id, TERM_CREATED, term_created(period_id))


def publish(client, h, timetable_id: str):
    return client.post(f"{BASE}/timetables/{timetable_id}/publish", headers=h)


def unpublish(client, h, timetable_id: str, **kwargs):
    return client.post(f"{BASE}/timetables/{timetable_id}/unpublish", headers=h, **kwargs)


def ready(client, org, h, *, slots=True, **over) -> tuple[dict, dict]:
    """A draft timetable of a known term with one clean slot, and the ids it uses."""
    ids = org.academic()
    know_term(org, ids["period"])
    return make_timetable(client, h, ids["period"], slots=[slot(ids)] if slots else [], **over), ids


def when(days: float = 0, hours: float = 0) -> datetime:
    return NOW + timedelta(days=days, hours=hours)


def seed_class(org, timetable_id, ids, starts_at: datetime, *, status="scheduled", slot_id=None, **over) -> str:
    """A scheduled class as generation will leave it (generation is not served yet; see the module docstring)."""
    with SessionLocal() as db:
        row = ScheduledClassRow(
            organisation_id=org.id,
            timetable_id=timetable_id,
            slot_id=slot_id,
            academic_period_id=ids["period"],
            course_offering_id=ids["offering"],
            section_id=ids["section"],
            instructor_assignment_id=ids["assignment"],
            instructor_id=ids["instructor"],
            class_date=starts_at.date(),
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            status=status,
            **over,
        )
        db.add(row)
        db.commit()
        return row.id


def seed_session(org, class_id: str, status: str = "open") -> None:
    with SessionLocal() as db:
        db.add(
            AttendanceSessionRow(
                organisation_id=org.id,
                scheduled_class_id=class_id,
                status=status,
                opened_at=NOW,
                opened_by=str(uuid.uuid4()),
                marking_deadline=NOW + timedelta(hours=24),
            )
        )
        db.commit()


def class_states(org, timetable_id: str | None = None) -> dict[str, tuple[str, str | None]]:
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        rows = db.scalars(repo.q(db, ScheduledClassRow))
        return {r.id: (r.status, r.cancel_reason) for r in rows if timetable_id in (None, r.timetable_id)}


def stored(org, timetable_id: str) -> tuple[str, int]:
    with SessionLocal() as db:
        db.info["organisation_id"] = org.id
        row = repo.get(db, TimetableRow, timetable_id)
        return row.status, row.version


# ---------------------------------------------------------------- publish


def test_publishing_a_draft_makes_it_published_at_version_one(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    body = ok(publish(client, h, t["id"]))
    assert (body["status"], body["version"], body["published_at"]) == ("published", 1, iso(NOW))
    assert body["slots"] == t["slots"] and body["slot_count"] == 1  # nothing else changed
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h)) == body


def test_publishing_writes_one_event_and_one_audit_entry_in_the_same_change(client, org):
    user, h = org.user(ADMIN)
    t, _ = ready(client, org, h, department_id=str(uuid.uuid4()))
    ok(publish(client, h, t["id"]))
    assert outbox(PUBLISHED_EVENT, org.id) == [
        {
            "organisation_id": org.id,
            "timetable_id": t["id"],
            "academic_period_id": t["academic_period_id"],
            "department_id": t["department_id"],
            "version": 1,
            "published_at": iso(NOW),
            "scheduled_class_count": 0,
        }
    ]
    published = [e for e in audit_entries(org.id, t["id"]) if e.action == "timetable.published"]
    assert len(published) == 1
    (entry,) = published
    assert (entry.actor, entry.entity_type, entry.entity_id) == (user, "timetable", t["id"])
    assert entry.before == {"status": "draft", "version": 0, "published_at": None}
    assert entry.after == {"status": "published", "version": 1, "published_at": iso(NOW)}


def test_publishing_generates_no_class_until_the_time_zone_is_decided(client, org):
    """Pins the documented limit (reviewer-decisions section 10): the contract says publishing generates classes, and
    this does not. When generation is built, this test changes with it."""
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    assert class_states(org) == {}
    assert outbox(PUBLISHED_EVENT, org.id)[0]["scheduled_class_count"] == 0


def test_a_timetable_without_slots_can_be_published(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h, slots=False)
    assert ok(publish(client, h, t["id"]))["status"] == "published"


def test_the_department_head_can_publish_too(client, org):
    _, h = org.user(HEAD)
    t, _ = ready(client, org, h)
    assert ok(publish(client, h, t["id"]))["status"] == "published"


def test_publishing_again_after_unpublishing_is_a_new_version(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    assert ok(unpublish(client, h, t["id"]))["version"] == 1  # unpublishing keeps the version
    second = ok(publish(client, h, t["id"]))
    assert (second["status"], second["version"]) == ("published", 2)
    assert [p["version"] for p in outbox(PUBLISHED_EVENT, org.id)] == [1, 2]


def test_blocking_conflicts_refuse_publication_with_409_and_the_conflict_list(client, org):
    _, h = org.user(ADMIN)
    t, ids = ready(client, org, h, slots=False)
    ok(
        client.put(
            f"{BASE}/timetables/{t['id']}/slots",
            json={"slots": [slot(ids), slot(ids, start="09:30:00", end="10:30:00")]},
            headers=h,
        )
    )
    detail = err(publish(client, h, t["id"]), 409)
    assert (detail["code"], detail["details"]["blocking_conflicts"]) == ("blocking_conflicts", 2)
    listed = detail["details"]["conflicts"]
    assert [(c["kind"], c["blocking"]) for c in listed] == [("section", True), ("instructor", True)]
    assert listed == ok(client.get(f"{BASE}/timetables/{t['id']}/conflicts", headers=h))["items"]
    assert stored(org, t["id"]) == ("draft", 0)
    assert outbox(PUBLISHED_EVENT, org.id) == []
    assert [e for e in audit_entries(org.id, t["id"]) if e.action == "timetable.published"] == []


def test_a_location_warning_alone_does_not_block_publication(client, org):
    _, h = org.user(ADMIN)
    t, ids = ready(client, org, h, slots=False)
    other = org.academic(period_id=ids["period"])
    ok(
        client.put(
            f"{BASE}/timetables/{t['id']}/slots",
            json={
                "slots": [
                    slot(ids, location_label="Room 1"),
                    slot(other, start="09:30:00", end="10:30:00", location_label="room 1"),
                ]
            },
            headers=h,
        )
    )
    items = ok(client.get(f"{BASE}/timetables/{t['id']}/conflicts", headers=h))
    assert items["items"] and items["blocking"] is False
    assert ok(publish(client, h, t["id"]))["status"] == "published"


def test_a_conflict_with_another_published_timetable_of_the_period_blocks(client, org):
    _, h = org.user(ADMIN)
    first, ids = ready(client, org, h)
    ok(publish(client, h, first["id"]))
    second = make_timetable(client, h, ids["period"], name="Second", slots=[slot(ids)])
    detail = err(publish(client, h, second["id"]), 409)
    assert detail["code"] == "blocking_conflicts"
    assert {c["other_timetable_id"] for c in detail["details"]["conflicts"]} == {first["id"]}
    assert stored(org, second["id"]) == ("draft", 0)


def test_a_published_timetable_cannot_be_published_again(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    detail = err(publish(client, h, t["id"]), 409)
    assert detail["code"] == "already_published"
    assert stored(org, t["id"]) == ("published", 1)
    assert len(outbox(PUBLISHED_EVENT, org.id)) == 1


def test_an_unknown_term_refuses_publication_with_409_and_changes_nothing(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()  # the offering is known, the term is not
    t = make_timetable(client, h, ids["period"], slots=[slot(ids)])
    detail = err(publish(client, h, t["id"]), 409)
    assert (detail["code"], detail["details"]["academic_period_id"]) == ("unknown_term", ids["period"])
    assert stored(org, t["id"]) == ("draft", 0)
    assert outbox(PUBLISHED_EVENT, org.id) == []
    assert [e for e in audit_entries(org.id, t["id"]) if e.action == "timetable.published"] == []


def test_a_term_known_to_another_organisation_does_not_count(client, org, other_org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    know_term(other_org, ids["period"])  # same period id, other organisation
    t = make_timetable(client, h, ids["period"], slots=[slot(ids)])
    assert err(publish(client, h, t["id"]), 409)["code"] == "unknown_term"


def test_a_published_timetable_cannot_be_edited(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    assert err(client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "x"}, headers=h), 409)["code"]
    ok(unpublish(client, h, t["id"]))
    assert ok(client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "x"}, headers=h))["name"] == "x"


# ---------------------------------------------------------------- unpublish


def test_unpublishing_keeps_the_version_and_cancels_only_future_classes_without_a_session(client, org):
    user, h = org.user(ADMIN)
    t, ids = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    tid = t["id"]
    slot_id = t["slots"][0]["id"]
    future = seed_class(org, tid, ids, when(days=7), slot_id=slot_id)
    later = seed_class(org, tid, ids, when(days=14), slot_id=slot_id)
    past = seed_class(org, tid, ids, when(days=-7), slot_id=slot_id)
    started = seed_class(org, tid, ids, when(hours=-1))  # began an hour before "now" (same date as the next: no slot)
    on_the_dot = seed_class(org, tid, ids, when(), slot_id=slot_id)  # starts exactly now: not in the future
    with_open = seed_class(org, tid, ids, when(days=8), slot_id=slot_id)
    with_closed = seed_class(org, tid, ids, when(days=9), slot_id=slot_id)
    seed_session(org, with_open, "open")
    seed_session(org, with_closed, "closed")
    already = seed_class(org, tid, ids, when(days=10), status="cancelled", cancel_reason="holiday")
    done = seed_class(org, tid, ids, when(days=11), status="completed")
    before = class_states(org)

    body = ok(unpublish(client, h, tid, json={"reason": "  term re-planned  "}))
    assert (body["status"], body["version"]) == ("unpublished", 1)
    after = class_states(org)
    cancelled = {future, later}
    assert {cid for cid in after if after[cid] != before[cid]} == cancelled
    assert all(after[cid] == ("cancelled", "term re-planned") for cid in cancelled)
    for untouched in (past, started, on_the_dot, with_open, with_closed, already, done):
        assert after[untouched] == before[untouched], untouched
    assert after[already] == ("cancelled", "holiday")

    assert outbox(UNPUBLISHED_EVENT, org.id) == [
        {
            "organisation_id": org.id,
            "timetable_id": tid,
            "academic_period_id": ids["period"],
            "version": 1,
            "unpublished_at": iso(NOW),
            "cancelled_class_count": 2,
        }
    ]
    events = outbox(CLASS_CANCELLED_EVENT, org.id)
    assert {e["scheduled_class_id"] for e in events} == cancelled
    for e in events:
        assert (e["course_offering_id"], e["section_id"], e["reason"], e["cancelled_at"]) == (
            ids["offering"],
            ids["section"],
            "term re-planned",
            iso(NOW),
        )
    class_audit = [e for e in audit_entries(org.id) if e.action == "scheduled-class.cancelled"]
    assert {e.entity_id for e in class_audit} == cancelled
    for e in class_audit:
        assert (e.actor, e.entity_type, e.reason) == (user, "scheduled_class", "term re-planned")
        assert e.before == {"status": "scheduled", "cancel_reason": None}
        assert e.after == {"status": "cancelled", "cancel_reason": "term re-planned"}
    (entry,) = [e for e in audit_entries(org.id, tid) if e.action == "timetable.unpublished"]
    assert (entry.actor, entry.reason) == (user, "term re-planned")
    assert entry.before == {"status": "published"}
    assert entry.after == {"status": "unpublished", "cancelled_class_count": 2}


def test_unpublishing_without_a_reason_cancels_without_one(client, org):
    _, h = org.user(ADMIN)
    t, ids = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    future = seed_class(org, t["id"], ids, when(days=7))
    ok(unpublish(client, h, t["id"]))  # no body at all
    assert class_states(org)[future] == ("cancelled", None)
    assert outbox(CLASS_CANCELLED_EVENT, org.id)[0]["reason"] is None
    assert [e.reason for e in audit_entries(org.id, t["id"]) if e.action == "timetable.unpublished"] == [None]


def test_unpublishing_leaves_other_timetables_and_ad_hoc_classes_alone(client, org):
    _, h = org.user(ADMIN)
    t, ids = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    other = make_timetable(client, h, ids["period"], name="Other")
    mine = seed_class(org, t["id"], ids, when(days=7))
    theirs = seed_class(org, other["id"], ids, when(days=7))
    adhoc = seed_class(org, None, ids, when(days=7))
    ok(unpublish(client, h, t["id"], json={}))
    states = class_states(org)
    assert states[mine][0] == "cancelled"
    assert states[theirs][0] == states[adhoc][0] == "scheduled"
    assert outbox(UNPUBLISHED_EVENT, org.id)[0]["cancelled_class_count"] == 1


def test_unpublishing_a_timetable_with_nothing_to_cancel_still_unpublishes(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    assert ok(unpublish(client, h, t["id"]))["status"] == "unpublished"
    assert outbox(UNPUBLISHED_EVENT, org.id)[0]["cancelled_class_count"] == 0
    assert outbox(CLASS_CANCELLED_EVENT, org.id) == []


@pytest.mark.parametrize("status", ["draft", "unpublished"])
def test_only_a_published_timetable_can_be_unpublished(client, org, status):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    if status == "unpublished":
        ok(publish(client, h, t["id"]))
        ok(unpublish(client, h, t["id"]))
    detail = err(unpublish(client, h, t["id"]), 409)
    assert detail["code"] == "not_published"
    assert len(outbox(UNPUBLISHED_EVENT, org.id)) == (1 if status == "unpublished" else 0)


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"reason": "   "}, "invalid_text", "reason"),
        ({"reason": 5}, "invalid_text", "reason"),
        ({"reason": "x" * 501}, "text_too_long", "reason"),
        ({"why": "x"}, "unknown_field", "why"),
        (["reason"], "invalid_body", "body"),
    ],
)
def test_an_invalid_unpublish_body_is_400_and_changes_nothing(client, org, body, code, field):
    _, h = org.user(ADMIN)
    t, ids = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    future = seed_class(org, t["id"], ids, when(days=7))
    detail = err(unpublish(client, h, t["id"], json=body), 400)
    assert (detail["code"], detail["details"]["field"]) == (code, field)
    assert stored(org, t["id"]) == ("published", 1)
    assert class_states(org)[future][0] == "scheduled"


# ---------------------------------------------------------------- permissions and tenants


@pytest.mark.parametrize("role", [FACULTY, STUDENT])
def test_without_the_publish_key_both_operations_are_403_and_change_nothing(client, org, role):
    _, admin = org.user(ADMIN)
    t, _ = ready(client, org, admin)
    _, h = org.user(role)
    for call in (publish, unpublish):
        r = call(client, h, t["id"])
        assert r.status_code == 403, (call.__name__, r.text)
        assert r.json()["detail"]["code"] == "forbidden"
    assert stored(org, t["id"]) == ("draft", 0)


def test_no_token_is_401(client, org):
    _, admin = org.user(ADMIN)
    t, _ = ready(client, org, admin)
    assert client.post(f"{BASE}/timetables/{t['id']}/publish").status_code == 401
    assert client.post(f"{BASE}/timetables/{t['id']}/unpublish").status_code == 401


def test_another_organisations_timetable_is_404_and_stays_untouched(client, org, other_org):
    _, h = org.user(ADMIN)
    t, ids = ready(client, org, h)
    ok(publish(client, h, t["id"]))
    future = seed_class(org, t["id"], ids, when(days=7))
    _, outsider = other_org.user(ADMIN)
    assert err(publish(client, outsider, t["id"]), 404)["code"] == "timetable_not_found"
    assert err(unpublish(client, outsider, t["id"]), 404)["code"] == "timetable_not_found"
    assert stored(org, t["id"]) == ("published", 1)
    assert class_states(org)[future][0] == "scheduled"
    assert outbox(UNPUBLISHED_EVENT, org.id) == [] and outbox(UNPUBLISHED_EVENT, other_org.id) == []


def test_an_unknown_timetable_is_404(client, org):
    _, h = org.user(ADMIN)
    missing = str(uuid.uuid4())
    assert err(publish(client, h, missing), 404)["code"] == "timetable_not_found"
    assert err(unpublish(client, h, missing), 404)["code"] == "timetable_not_found"


def test_publishing_in_one_organisation_does_not_conflict_with_the_same_slots_in_another(client, org, other_org):
    """Conflicts look at the published timetables of the same organisation only."""
    _, h = org.user(ADMIN)
    _, h2 = other_org.user(ADMIN)
    a, _ = ready(client, org, h)
    b, _ = ready(client, other_org, h2)
    assert ok(publish(client, h, a["id"]))["status"] == "published"
    assert ok(publish(client, h2, b["id"]))["status"] == "published"


def test_the_utc_instant_is_what_is_stored_for_published_at(client, org):
    _, h = org.user(ADMIN)
    t, _ = ready(client, org, h)
    body = ok(publish(client, h, t["id"]))
    assert datetime.fromisoformat(body["published_at"]) == NOW.astimezone(UTC)
