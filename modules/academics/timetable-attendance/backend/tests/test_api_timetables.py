"""Timetable and slot operations end to end (FR-1, FR-2): create, list, get, update the details, replace the slots."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import ADMIN, BASE, FACULTY, HEAD, audit_entries, make_timetable, ok, outbox, slot  # noqa: E402


def err(response, status: int) -> dict:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()["detail"]


def test_create_returns_a_draft_with_no_slots(client, org):
    _, h = org.user(ADMIN)
    period = str(uuid.uuid4())
    t = make_timetable(client, h, period, name="  Odd term  ")
    assert (t["name"], t["status"], t["version"], t["slot_count"], t["slots"]) == ("Odd term", "draft", 0, 0, [])
    assert (t["organisation_id"], t["academic_period_id"], t["department_id"], t["published_at"]) == (
        org.id,
        period,
        None,
        None,
    )
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h)) == t


def test_create_with_a_department_and_with_slots_of_known_ids(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    department = str(uuid.uuid4())
    t = make_timetable(
        client,
        h,
        ids["period"],
        department_id=department,
        slots=[slot(ids, location_label=" Room 4 "), slot(ids, day="tuesday", effective_from="2026-11-09")],
    )
    assert (t["department_id"], t["slot_count"]) == (department, 2)
    first, second = t["slots"]
    assert (first["day_of_week"], first["start_time"], first["location_label"]) == ("monday", "09:00:00", "Room 4")
    assert (first["course_code"], first["course_title"], first["instructor_id"]) == (
        "CS101",
        "Programming",
        ids["instructor"],
    )
    assert second["effective_from"] == "2026-11-09" and "location_label" not in second


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"name": "x"}, "missing_field", "academic_period_id"),
        ({"academic_period_id": str(uuid.uuid4())}, "missing_field", "name"),
        ({"academic_period_id": "not-a-uuid", "name": "x"}, "invalid_id", "academic_period_id"),
        ({"academic_period_id": str(uuid.uuid4()), "name": "   "}, "invalid_name", "name"),
        ({"academic_period_id": str(uuid.uuid4()), "name": 5}, "invalid_text", "name"),
        ({"academic_period_id": str(uuid.uuid4()), "name": "x", "department_id": "d"}, "invalid_id", "department_id"),
        ({"academic_period_id": str(uuid.uuid4()), "name": "x", "status": "published"}, "unknown_field", "status"),
        ({"academic_period_id": str(uuid.uuid4()), "name": "x", "slots": "no"}, "invalid_body", "slots"),
    ],
)
def test_invalid_creates_are_400_with_the_code_and_field(client, org, body, code, field):
    _, h = org.user(ADMIN)
    d = err(client.post(f"{BASE}/timetables", json=body, headers=h), 400)
    assert (d["code"], d["details"]["field"]) == (code, field)


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"day_of_week": "funday"}, "invalid_choice", "slots[0].day_of_week"),
        ({"start_time": "late"}, "invalid_time", "slots[0].start_time"),
        ({"start_time": "11:00:00"}, "invalid_slot_times", "slots[0].end_time"),
        ({"start_time": "09:00:00+05:30"}, "invalid_time", "slots[0].start_time"),
        ({"section_id": "s"}, "invalid_id", "slots[0].section_id"),
        ({"effective_from": "20261109"}, "invalid_date", "slots[0].effective_from"),
        (
            {"effective_from": "2026-11-09", "effective_to": "2026-11-01"},
            "invalid_effective_dates",
            "slots[0].effective_to",
        ),
        ({"location_label": 4}, "invalid_text", "slots[0].location_label"),
        ({"colour": "red"}, "unknown_field", "colour"),
    ],
)
def test_invalid_slots_are_400_naming_the_slot_field(client, org, change, code, field):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    d = err(client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": [slot(ids, **change)]}, headers=h), 400)
    assert (d["code"], d["details"]["field"]) == (code, field)


def test_a_slot_missing_a_required_field_is_400(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    bad = slot(ids)
    del bad["section_id"]
    d = err(client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": [bad]}, headers=h), 400)
    assert d["code"] == "missing_field"
    assert err(client.put(f"{BASE}/timetables/{t['id']}/slots", json={}, headers=h), 400)["code"] == "missing_field"


def test_slots_of_unknown_academic_management_ids_are_422(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    for field, code in [
        ("course_offering_id", "unknown_course_offering"),
        ("section_id", "unknown_section"),
        ("instructor_assignment_id", "unknown_instructor_assignment"),
    ]:
        d = err(
            client.put(
                f"{BASE}/timetables/{t['id']}/slots",
                json={"slots": [slot(ids, **{field: str(uuid.uuid4())})]},
                headers=h,
            ),
            422,
        )
        assert (d["code"], d["details"]["field"]) == (code, field)
    created = client.post(
        f"{BASE}/timetables",
        json={"academic_period_id": ids["period"], "name": "x", "slots": [slot(ids, section_id=str(uuid.uuid4()))]},
        headers=h,
    )
    assert err(created, 422)["code"] == "unknown_section"
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h))["slot_count"] == 0  # nothing was saved


def test_slots_must_agree_with_each_other_and_with_the_period(client, org):
    _, h = org.user(ADMIN)
    ids, other = org.academic(), org.academic()
    t = make_timetable(client, h, ids["period"])
    url = f"{BASE}/timetables/{t['id']}/slots"
    assert err(client.put(url, json={"slots": [slot(ids, section_id=other["section"])]}, headers=h), 422)["code"] == (
        "section_not_in_offering"
    )
    assert err(
        client.put(url, json={"slots": [slot(ids, instructor_assignment_id=other["assignment"])]}, headers=h), 422
    )["code"] == ("assignment_mismatch")
    elsewhere = slot(other)  # a real offering, but of another academic period
    assert err(client.put(url, json={"slots": [elsewhere]}, headers=h), 422)["code"] == "offering_not_in_period"


def test_replace_slots_creates_changes_and_removes_and_keeps_unchanged_slot_ids(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    url = f"{BASE}/timetables/{t['id']}/slots"
    a, b = slot(ids), slot(ids, day="tuesday")
    first = ok(client.put(url, json={"slots": [a, b]}, headers=h))
    assert [s["day_of_week"] for s in first["slots"]] == ["monday", "tuesday"]
    keep_id = first["slots"][0]["id"]
    again = ok(client.put(url, json={"slots": [b, a]}, headers=h))
    assert [s["id"] for s in again["slots"]] == [s["id"] for s in first["slots"]]  # identical content keeps its id
    changed = ok(client.put(url, json={"slots": [a, slot(ids, day="friday")]}, headers=h))
    assert changed["slot_count"] == 2
    assert changed["slots"][0]["id"] == keep_id
    assert {s["day_of_week"] for s in changed["slots"]} == {"monday", "friday"}
    assert ok(client.put(url, json={"slots": []}, headers=h))["slots"] == []
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h))["slot_count"] == 0


def test_replace_with_the_same_slots_changes_nothing_audits_nothing_and_publishes_nothing(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    url = f"{BASE}/timetables/{t['id']}/slots"
    ok(client.put(url, json={"slots": [slot(ids)]}, headers=h))
    before = (len(audit_entries(org.id, t["id"])), len(outbox("timetable-attendance.timetable.updated", org.id)))
    ok(client.put(url, json={"slots": [slot(ids)]}, headers=h))
    assert (
        len(audit_entries(org.id, t["id"])),
        len(outbox("timetable-attendance.timetable.updated", org.id)),
    ) == before


def test_conflicting_slots_are_allowed_in_a_draft(client, org):
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    both = [slot(ids), slot(ids, start="09:30:00", end="10:30:00")]
    assert ok(client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": both}, headers=h))["slot_count"] == 2


def test_update_changes_the_name_and_department_only(client, org):
    _, h = org.user(HEAD)
    t = make_timetable(client, h)
    department = str(uuid.uuid4())
    u = ok(
        client.patch(
            f"{BASE}/timetables/{t['id']}", json={"name": " Even term ", "department_id": department}, headers=h
        )
    )
    assert (u["name"], u["department_id"], u["academic_period_id"], u["status"]) == (
        "Even term",
        department,
        t["academic_period_id"],
        "draft",
    )
    cleared = ok(client.patch(f"{BASE}/timetables/{t['id']}", json={"department_id": None}, headers=h))
    assert (cleared["name"], cleared["department_id"]) == ("Even term", None)
    assert ok(client.patch(f"{BASE}/timetables/{t['id']}", json={}, headers=h)) == cleared


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "  "}, "invalid_name"),
        ({"name": None}, "invalid_text"),
        ({"department_id": "d"}, "invalid_id"),
        ({"academic_period_id": str(uuid.uuid4())}, "unknown_field"),
        ({"version": 3}, "unknown_field"),
    ],
)
def test_invalid_updates_are_400_and_change_nothing(client, org, body, code):
    _, h = org.user(ADMIN)
    t = make_timetable(client, h)
    assert err(client.patch(f"{BASE}/timetables/{t['id']}", json=body, headers=h), 400)["code"] == code
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h)) == t


def test_a_published_timetable_cannot_be_changed_but_an_unpublished_one_can(client, org):
    """Publishing is a later batch, so the rows are set the way publishing will leave them."""
    from eos_core.db import SessionLocal
    from eos_timetable_attendance.infrastructure.models import TimetableRow

    _, h = org.user(ADMIN)
    t = make_timetable(client, h)

    def set_status(status: str) -> None:
        with SessionLocal() as db:
            row = db.get(TimetableRow, t["id"])
            row.status = status
            db.commit()

    set_status("published")
    d = err(client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "New"}, headers=h), 409)
    assert d["code"] == "timetable_published"
    assert (
        err(client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": []}, headers=h), 409)["code"]
        == "timetable_published"
    )
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=h))["name"] == "Odd term"
    set_status("unpublished")
    assert ok(client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "New"}, headers=h))["name"] == "New"


def test_list_filters_pages_and_counts_without_slots(client, org):
    _, h = org.user(ADMIN)
    p1, p2, dept = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    for name, period, extra in [("B", p1, {}), ("A", p1, {"department_id": dept}), ("C", p2, {})]:
        make_timetable(client, h, period, name=name, **extra)
    ids = org.academic(period_id=p1)
    first = ok(client.get(f"{BASE}/timetables?academic_period_id={p1}", headers=h))
    assert (first["total"], [t["name"] for t in first["items"]]) == (2, ["A", "B"])
    assert all("slots" not in t for t in first["items"])
    assert [t["name"] for t in ok(client.get(f"{BASE}/timetables?department_id={dept}", headers=h))["items"]] == ["A"]
    assert ok(client.get(f"{BASE}/timetables?status=published", headers=h)) == {"items": [], "total": 0}
    page = ok(client.get(f"{BASE}/timetables?limit=1&offset=1", headers=h))
    assert (page["total"], len(page["items"])) == (3, 1)
    b = first["items"][1]
    ok(
        client.put(
            f"{BASE}/timetables/{b['id']}/slots", json={"slots": [slot(ids), slot(ids, day="friday")]}, headers=h
        )
    )
    counted = ok(client.get(f"{BASE}/timetables?academic_period_id={p1}", headers=h))
    assert {t["name"]: t["slot_count"] for t in counted["items"]} == {"A": 0, "B": 2}


@pytest.mark.parametrize(
    ("query", "code"),
    [("academic_period_id=x", "invalid_id"), ("department_id=x", "invalid_id"), ("status=live", "invalid_choice")],
)
def test_list_rejects_malformed_filters_with_400(client, org, query, code):
    _, h = org.user(ADMIN)
    assert err(client.get(f"{BASE}/timetables?{query}", headers=h), 400)["code"] == code


def test_an_unknown_timetable_is_404_on_every_operation(client, org):
    _, h = org.user(ADMIN)
    missing = str(uuid.uuid4())
    for call in (
        client.get(f"{BASE}/timetables/{missing}", headers=h),
        client.patch(f"{BASE}/timetables/{missing}", json={"name": "x"}, headers=h),
        client.put(f"{BASE}/timetables/{missing}/slots", json={"slots": []}, headers=h),
        client.get(f"{BASE}/timetables/{missing}/conflicts", headers=h),
        client.get(f"{BASE}/timetables/not-a-uuid", headers=h),
    ):
        assert err(call, 404)["code"] == "timetable_not_found"


def test_the_organisation_is_the_tokens_never_the_requests(client, org, other_org):
    _, h = org.user(ADMIN)
    t = ok(
        client.post(
            f"{BASE}/timetables",
            json={"academic_period_id": str(uuid.uuid4()), "name": "x"},
            headers={**h, "X-Organisation-Id": other_org.id},
        ),
        201,
    )
    assert t["organisation_id"] == org.id
    refused = client.post(
        f"{BASE}/timetables",
        json={"academic_period_id": str(uuid.uuid4()), "name": "x", "organisation_id": other_org.id},
        headers=h,
    )
    assert err(refused, 400)["code"] == "unknown_field"


def test_faculty_may_read_but_not_write_and_a_student_may_do_neither(client, org):
    _, admin = org.user(ADMIN)
    _, faculty = org.user(FACULTY)
    _, student = org.user("timetable-attendance-student")
    t = make_timetable(client, admin)
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=faculty)) == t
    body = {"academic_period_id": str(uuid.uuid4()), "name": "x"}
    for call in (
        client.post(f"{BASE}/timetables", json=body, headers=faculty),
        client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "y"}, headers=faculty),
        client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": []}, headers=faculty),
        client.get(f"{BASE}/timetables", headers=student),
        client.get(f"{BASE}/timetables/{t['id']}", headers=student),
        client.get(f"{BASE}/timetables/{t['id']}/conflicts", headers=student),
    ):
        assert err(call, 403)["code"] == "forbidden"
    assert ok(client.get(f"{BASE}/timetables/{t['id']}", headers=admin))["name"] == "Odd term"


def test_create_audits_and_publishes_once_in_the_same_transaction(client, org):
    uid, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"], slots=[slot(ids), slot(ids, day="friday")])
    [entry] = audit_entries(org.id, t["id"])
    assert (entry.action, entry.entity_type, entry.actor, entry.organisation_id) == (
        "timetable.created",
        "timetable",
        uid,
        org.id,
    )
    assert entry.before is None
    assert entry.after == {
        "academic_period_id": ids["period"],
        "department_id": None,
        "name": "Odd term",
        "status": "draft",
        "slot_count": 2,
    }
    assert entry.summary == "timetable Odd term created"
    events = [e for e in outbox("timetable-attendance.timetable.created", org.id) if e["timetable_id"] == t["id"]]
    assert events == [
        {
            "organisation_id": org.id,
            "timetable_id": t["id"],
            "academic_period_id": ids["period"],
            "department_id": None,
            "name": "Odd term",
        }
    ]


def test_update_and_replace_audit_the_changed_fields_only(client, org):
    uid, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"])
    ok(client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "Renamed"}, headers=h))
    ok(client.patch(f"{BASE}/timetables/{t['id']}", json={"name": "Renamed"}, headers=h))  # no change: nothing recorded
    ok(
        client.put(
            f"{BASE}/timetables/{t['id']}/slots", json={"slots": [slot(ids), slot(ids, day="friday")]}, headers=h
        )
    )
    entries = audit_entries(org.id, t["id"])  # the clock is frozen, so the order of equal times is not meaningful
    assert len(entries) == 3
    created = next(e for e in entries if e.action == "timetable.created")
    renamed = next(e for e in entries if e.after == {"name": "Renamed"})
    replaced = next(e for e in entries if e.after and "slots_added" in e.after)
    assert (renamed.action, renamed.before, renamed.after, renamed.actor) == (
        "timetable.updated",
        {"name": "Odd term"},
        {"name": "Renamed"},
        uid,
    )
    assert renamed.summary == "timetable Renamed updated: name"
    assert (replaced.before, replaced.after) == (
        {"slot_count": 0},
        {"slot_count": 2, "slots_added": 2, "slots_removed": 0},
    )
    updated = [e for e in outbox("timetable-attendance.timetable.updated", org.id) if e["timetable_id"] == t["id"]]
    assert updated == [
        {"organisation_id": org.id, "timetable_id": t["id"], "changed_fields": ["name"], "slot_count": 0},
        {"organisation_id": org.id, "timetable_id": t["id"], "changed_fields": ["slots"], "slot_count": 2},
    ]
    assert created.action == "timetable.created"


def test_a_refused_change_writes_no_audit_and_no_event(client, org):
    _, h = org.user(ADMIN)
    t = make_timetable(client, h)
    audits, updates = len(audit_entries(org.id, t["id"])), len(outbox("timetable-attendance.timetable.updated", org.id))
    assert client.patch(f"{BASE}/timetables/{t['id']}", json={"name": " "}, headers=h).status_code == 400
    assert (
        client.put(
            f"{BASE}/timetables/{t['id']}/slots", json={"slots": [{"day_of_week": "monday"}]}, headers=h
        ).status_code
        == 400
    )
    assert (len(audit_entries(org.id, t["id"])), len(outbox("timetable-attendance.timetable.updated", org.id))) == (
        audits,
        updates,
    )
