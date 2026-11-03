"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows, and never
resolves another's read-model ids."""

import uuid

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import ADMIN, BASE, make_timetable, ok, slot  # noqa: E402
from eos_testing import assert_no_cross_tenant_leak  # noqa: E402


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[dict, dict, dict]:
    _, h = org.user(ADMIN)
    ids = org.academic()
    t = make_timetable(client, h, ids["period"], slots=[slot(ids), slot(ids, start="09:30:00", end="10:30:00")])
    return h, ids, t


def test_no_cross_tenant_leak(client, org, other_org):
    ha, _, _ = seed(client, org)
    hb, _, _ = seed(client, other_org)
    assert_no_cross_tenant_leak(client, f"{BASE}/timetables", token(ha), token(hb))


def test_another_organisations_timetable_is_not_found_on_every_operation(client, org, other_org):
    _, _, theirs = seed(client, other_org)
    h, ids, _ = seed(client, org)
    tid = theirs["id"]
    for response in (
        client.get(f"{BASE}/timetables/{tid}", headers=h),
        client.patch(f"{BASE}/timetables/{tid}", json={"name": "Stolen"}, headers=h),
        client.put(f"{BASE}/timetables/{tid}/slots", json={"slots": []}, headers=h),
        client.get(f"{BASE}/timetables/{tid}/conflicts", headers=h),
    ):
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "timetable_not_found"
    _, hb = other_org.user(ADMIN)
    stored = ok(client.get(f"{BASE}/timetables/{tid}", headers=hb))
    assert (stored["name"], stored["slot_count"]) == ("Odd term", 2)  # nothing was changed or removed


def test_another_organisations_read_model_ids_are_unknown(client, org, other_org):
    h, _, t = seed(client, org)
    theirs = other_org.academic()
    cases = [
        ("course_offering_id", "offering", "unknown_course_offering"),
        ("section_id", "section", "unknown_section"),
        ("instructor_assignment_id", "assignment", "unknown_instructor_assignment"),
    ]
    for field, key, code in cases:
        mine = org.academic(period_id=t["academic_period_id"])
        bad = slot(mine, **{field: theirs[key]})
        r = client.put(f"{BASE}/timetables/{t['id']}/slots", json={"slots": [bad]}, headers=h)
        assert (r.status_code, r.json()["detail"]["code"]) == (422, code)
    body = {"academic_period_id": theirs["period"], "name": "x", "slots": [slot(theirs)]}
    r = client.post(f"{BASE}/timetables", json=body, headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "unknown_course_offering")


def test_listings_and_filters_stay_inside_the_organisation(client, org, other_org):
    h, ids, t = seed(client, org)
    hb, _, theirs = seed(client, other_org)
    listed = ok(client.get(f"{BASE}/timetables", headers=h))
    assert t["id"] in {i["id"] for i in listed["items"]}
    assert theirs["id"] not in {i["id"] for i in listed["items"]}
    same_period = ok(client.get(f"{BASE}/timetables?academic_period_id={theirs['academic_period_id']}", headers=h))
    assert same_period == {"items": [], "total": 0}
    assert ok(client.get(f"{BASE}/timetables?academic_period_id={uuid.uuid4()}", headers=hb)) == {
        "items": [],
        "total": 0,
    }


def test_audit_entries_and_events_carry_only_their_own_organisation(client, org, other_org):
    from conftest import audit_entries, outbox

    h, _, t = seed(client, org)
    _, _, theirs = seed(client, other_org)
    assert {e.organisation_id for e in audit_entries(org.id)} == {org.id}
    assert audit_entries(org.id, theirs["id"]) == []
    assert all(e["organisation_id"] == org.id for e in outbox("timetable-attendance.timetable.created", org.id))
    assert not [
        e for e in outbox("timetable-attendance.timetable.created", org.id) if e["timetable_id"] == theirs["id"]
    ]
