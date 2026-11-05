"""GET /me/mentoring (widget alumni.mentoring): the student's own active mentor with contact details, and upcoming
sessions without staff notes. Contact details reach a student only this way (A5)."""

from datetime import timedelta

import pytest
from al_support import BASE, NOW, TODAY, assigned, code, iso, mentor, scheduled


def _me(client, org, who="student"):
    r = client.get(f"{BASE}/me/mentoring", headers=org.headers[who])
    assert r.status_code == 200, r.text
    return r.json()


def test_no_mentor_is_the_empty_state(client, org):
    assert _me(client, org) == {"assignment": None, "upcoming_sessions": []}


def test_the_student_sees_their_mentor_with_contact_details(client, org):
    m = mentor(client, org)
    x = assigned(client, org, m, focus="Finance careers")
    me = _me(client, org)
    assert me["assignment"] == {
        "id": x["id"],
        "started_on": TODAY,
        "focus": "Finance careers",
        "mentor": {
            "id": m["id"],
            "full_name": m["full_name"],
            "graduation_year": m["graduation_year"],
            "programme": m["programme"],
            "current_company": m["current_company"],
            "current_designation": m["current_designation"],
            "industry": m["industry"],
            "city": m["city"],
            "email": m["email"],
            "phone": m["phone"],
            "linkedin_url": m["linkedin_url"],
        },
    }
    assert "STAFF-ONLY" not in str(me)
    # another student of the same organisation sees nothing of it
    assert _me(client, org, "student2") == {"assignment": None, "upcoming_sessions": []}


def test_upcoming_is_scheduled_from_now_soonest_first_at_most_five(client, org, clock):
    x = assigned(client, org, started_on="2026-10-01")
    past = scheduled(client, org, x, NOW - timedelta(hours=1))  # nobody marked it completed
    now = scheduled(client, org, x, NOW)  # at now counts as upcoming
    later = [scheduled(client, org, x, NOW + timedelta(days=d)) for d in (6, 2, 5, 3, 4, 1)]
    cancelled = scheduled(client, org, x, NOW + timedelta(minutes=30))
    client.post(f"{BASE}/mentoring/sessions/{cancelled['id']}/cancel", headers=org.coord)
    done = scheduled(client, org, x, NOW + timedelta(minutes=10))
    client.post(
        f"{BASE}/mentoring/sessions/{done['id']}/complete", json={"notes": "STAFF-ONLY-SESSION-NOTE"}, headers=org.coord
    )
    me = _me(client, org)
    got = [s["id"] for s in me["upcoming_sessions"]]
    by_time = sorted(later, key=lambda s: s["scheduled_at"])
    assert got == [now["id"]] + [s["id"] for s in by_time[:4]]
    assert past["id"] not in got
    first = me["upcoming_sessions"][0]
    assert set(first) == {"id", "scheduled_at", "duration_minutes", "mode", "location", "topic"}
    assert first["scheduled_at"] == iso(NOW)
    assert "STAFF-ONLY" not in str(me)
    clock.advance(seconds=1)  # the session at NOW is now past
    assert now["id"] not in [s["id"] for s in _me(client, org)["upcoming_sessions"]]


def test_an_ended_assignment_is_not_shown(client, org):
    m = mentor(client, org)
    x = assigned(client, org, m)
    scheduled(client, org, x, NOW + timedelta(days=1))
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    assert _me(client, org) == {"assignment": None, "upcoming_sessions": []}


def test_a_new_mentor_replaces_the_old_one(client, org):
    old = mentor(client, org, full_name="Old Mentor")
    x = assigned(client, org, old)
    client.post(f"{BASE}/mentoring/assignments/{x['id']}/end", headers=org.coord)
    new = mentor(client, org, full_name="New Mentor", email="new@example.com")
    y = assigned(client, org, new)
    me = _me(client, org)
    assert me["assignment"]["id"] == y["id"] and me["assignment"]["mentor"]["email"] == "new@example.com"
    assert "Old Mentor" not in str(me)


@pytest.mark.parametrize("who", ["coord", "faculty", "nobody"])
def test_me_needs_alumni_self_read(client, org, who):
    r = client.get(f"{BASE}/me/mentoring", headers=org.headers[who])
    assert r.status_code == 403 and code(r) == "forbidden"
