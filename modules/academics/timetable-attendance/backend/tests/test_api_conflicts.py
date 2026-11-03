"""GET /timetables/{id}/conflicts (FR-4) through the API, with the read models filled as the consumers will fill them."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import ADMIN, BASE, make_timetable, ok, slot  # noqa: E402


def put(client, h, timetable_id, slots):
    return ok(client.put(f"{BASE}/timetables/{timetable_id}/slots", json={"slots": slots}, headers=h))


def conflicts(client, h, timetable_id) -> dict:
    return ok(client.get(f"{BASE}/timetables/{timetable_id}/conflicts", headers=h))


def publish_row(timetable_id: str) -> None:
    """Publishing is a later batch, so the row is set the way publishing will leave it."""
    from eos_core.db import SessionLocal
    from eos_timetable_attendance.infrastructure.models import TimetableRow

    with SessionLocal() as db:
        db.get(TimetableRow, timetable_id).status = "published"
        db.commit()


def test_no_slots_or_clean_slots_have_no_conflicts(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    assert conflicts(client, h, t["id"]) == {"blocking": False, "items": []}
    put(client, h, t["id"], [slot(ids), slot(ids, start="10:00:00", end="11:00:00"), slot(ids, day="tuesday")])
    assert conflicts(client, h, t["id"]) == {"blocking": False, "items": []}  # back to back, other day


def test_a_shared_section_and_instructor_block_and_are_listed_with_the_overlap(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    put(client, h, t["id"], [slot(ids), slot(ids, start="09:30:00", end="10:30:00")])
    body = conflicts(client, h, t["id"])
    assert body["blocking"] is True
    assert [(c["kind"], c["blocking"]) for c in body["items"]] == [("section", True), ("instructor", True)]
    first = body["items"][0]
    assert (first["day_of_week"], first["overlap_start"], first["overlap_end"], first["shared_id"]) == (
        "monday",
        "09:30:00",
        "10:00:00",
        ids["section"],
    )
    assert body["items"][1]["shared_id"] == ids["instructor"]
    assert "other_timetable_id" not in first
    slot_ids = {s["id"] for s in ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h))["slots"]}
    assert {first["slot_id"], first["other_slot_id"]} == slot_ids


def test_two_assignments_of_one_instructor_clash_on_the_instructor(client, org):
    _, h = org.user(ADMIN)
    one = org.academic()
    two = org.academic(period_id=one["period"], instructor_id=one["instructor"])  # same teacher, another course
    t = make_timetable(client, h, one["period"])
    put(client, h, t["id"], [slot(one), slot(two)])
    body = conflicts(client, h, t["id"])
    assert [(c["kind"], c["shared_id"]) for c in body["items"]] == [("instructor", one["instructor"])]


def test_a_shared_location_is_only_a_warning(client, org):
    _, h = org.user(ADMIN)
    one = org.academic()
    two = org.academic(period_id=one["period"])
    t = make_timetable(client, h, one["period"])
    put(client, h, t["id"], [slot(one, location_label="Room 4"), slot(two, location_label=" room 4 ")])
    body = conflicts(client, h, t["id"])
    assert body["blocking"] is False
    [c] = body["items"]
    assert (c["kind"], c["blocking"], c["shared_id"]) == ("location", False, "room 4")


def test_conflicts_with_a_published_timetable_of_the_same_period_name_it(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    published = make_timetable(client, h, ids["period"], name="Published")
    put(client, h, published["id"], [slot(ids)])
    draft = make_timetable(client, h, ids["period"], name="Draft")
    put(client, h, draft["id"], [slot(ids, start="09:30:00", end="10:30:00")])
    assert conflicts(client, h, draft["id"])["items"] == []  # a draft is not compared with another draft
    publish_row(published["id"])
    body = conflicts(client, h, draft["id"])
    assert body["blocking"] is True
    assert {c["other_timetable_id"] for c in body["items"]} == {published["id"]}
    assert {c["kind"] for c in body["items"]} == {"section", "instructor"}
    other_period = make_timetable(client, h, org.academic()["period"], name="Other period")
    assert conflicts(client, h, other_period["id"])["items"] == []


def test_another_organisations_published_slots_never_conflict(client, org, other_org):
    _, h = org.user(ADMIN)
    _, theirs = other_org.user(ADMIN)
    ids = org.academic()
    mine = make_timetable(client, h, ids["period"])
    put(client, h, mine["id"], [slot(ids)])
    # the other organisation publishes a timetable of the same period id
    t = make_timetable(client, theirs, ids["period"])
    publish_row(t["id"])
    assert conflicts(client, h, mine["id"]) == {"blocking": False, "items": []}
