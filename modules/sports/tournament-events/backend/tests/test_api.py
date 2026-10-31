"""The HTTP surface against contracts/openapi.yaml: tournaments and their lifecycle, entries, fixtures, results,
officials, logistics and the calendar, with the events and audit entries each change writes, and the refusals."""

from datetime import UTC, datetime

from conftest import ATHLETE, BASE, COACH, VIEWER, outbox
from eos_core.db import SessionLocal
from eos_tournament_events.infrastructure.models import AuditEntry
from sqlalchemy import select

A1 = "11111111-1111-1111-1111-111111111111"
A2 = "22222222-2222-2222-2222-222222222222"
A3 = "33333333-3333-3333-3333-333333333333"
DURING = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)  # 11:30 in Kolkata on the first day


def _audit(organisation_id: str, entity_type: str | None = None) -> list[AuditEntry]:
    with SessionLocal() as db:
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        if entity_type:
            q = q.where(AuditEntry.entity_type == entity_type)
        return list(db.scalars(q.order_by(AuditEntry.occurred_at, AuditEntry.id)))


def _code(r) -> str:
    return r.json()["detail"]["code"]


# ---------------------------------------------------------------- tournaments


def test_tournament_is_created_as_a_draft_and_published(client, org):
    t = org.tournament(publish=False, description="Annual meet", discipline_id=A3)
    assert t["status"] == "draft" and t["organisation_id"] == org.id and t["discipline_id"] == A3
    assert "hosting" not in t  # optional fields are left out, not null
    [created] = outbox(org.id, "tournament-events.tournament.created")
    assert created.payload == {
        "organisation_id": org.id,
        "tournament_id": t["id"],
        "name": t["name"],
        "level": "inter_university",
        "start_date": "2026-11-10",
        "end_date": "2026-11-12",
    }

    r = client.post(f"{BASE}/tournaments/{t['id']}/publish", headers=org.admin)
    assert r.status_code == 200 and r.json()["status"] == "published"
    [published] = outbox(org.id, "tournament-events.tournament.published")
    assert published.payload == {
        "organisation_id": org.id,
        "tournament_id": t["id"],
        "registration_closes_on": "2026-11-05",
    }
    again = client.post(f"{BASE}/tournaments/{t['id']}/publish", headers=org.admin)
    assert again.status_code == 400 and _code(again) == "not_draft"

    audit = {a.action: a for a in _audit(org.id, "tournament")}
    assert set(audit) == {"tournament.created", "tournament.published"}
    assert "description" not in audit["tournament.created"].after  # free text stays out of the audit trail
    assert audit["tournament.published"].before == {"status": "draft"}
    assert audit["tournament.published"].after == {"status": "published"}


def test_drafts_are_visible_only_to_organisers(client, org):
    draft = org.tournament(publish=False, name="Draft cup")
    live = org.tournament(name="Live cup")
    _, coach = org.user(COACH)
    _, viewer = org.user(VIEWER)
    for headers in (coach, viewer):
        listed = client.get(f"{BASE}/tournaments", headers=headers).json()
        assert [t["id"] for t in listed["items"]] == [live["id"]] and listed["total"] == 1
        assert client.get(f"{BASE}/tournaments?status=draft", headers=headers).json()["total"] == 0
        assert client.get(f"{BASE}/tournaments/{draft['id']}", headers=headers).status_code == 404
        assert client.get(f"{BASE}/tournaments/{draft['id']}/fixtures", headers=headers).status_code == 404
    assert client.get(f"{BASE}/tournaments/{draft['id']}/entries", headers=coach).status_code == 404
    assert client.get(f"{BASE}/tournaments/{draft['id']}/logistics", headers=coach).status_code == 404
    assert client.get(f"{BASE}/tournaments", headers=org.admin).json()["total"] == 2


def test_status_follows_the_dates_in_the_institution_timezone(client, org, later):
    t = org.tournament()
    later(datetime(2026, 11, 9, 18, 0, tzinfo=UTC))  # 23:30 on the 9th in Kolkata
    assert client.get(f"{BASE}/tournaments/{t['id']}", headers=org.admin).json()["status"] == "published"
    later(datetime(2026, 11, 9, 19, 0, tzinfo=UTC))  # 00:30 on the 10th in Kolkata
    assert client.get(f"{BASE}/tournaments/{t['id']}", headers=org.admin).json()["status"] == "ongoing"
    assert client.get(f"{BASE}/tournaments?status=ongoing", headers=org.admin).json()["total"] == 1
    assert client.get(f"{BASE}/tournaments?status=published", headers=org.admin).json()["total"] == 0
    later(datetime(2026, 11, 12, 19, 0, tzinfo=UTC))
    assert client.get(f"{BASE}/tournaments/{t['id']}", headers=org.admin).json()["status"] == "completed"
    assert client.get(f"{BASE}/tournaments?status=completed", headers=org.admin).json()["total"] == 1
    r = client.post(f"{BASE}/tournaments/{t['id']}/cancel", json={"reason": "late"}, headers=org.admin)
    assert r.status_code == 400 and _code(r) == "tournament_completed"
    r = client.patch(f"{BASE}/tournaments/{t['id']}", json={"venue": "x"}, headers=org.admin)
    assert _code(r) == "tournament_closed"


def test_list_filters_and_pagination(client, org):
    org.tournament(publish=False, name="State 1", level="state", start_date="2026-12-01", end_date="2026-12-02")
    org.tournament(publish=False, name="State 2", level="state", start_date="2027-01-10", end_date="2027-01-12")
    org.tournament(publish=False, name="Nationals", level="national", registration_closes_on=None)
    page = client.get(f"{BASE}/tournaments?level=state&limit=1&offset=1", headers=org.admin).json()
    assert page["total"] == 2 and [t["name"] for t in page["items"]] == ["State 2"]
    # a tournament is in the period when any of its days is
    period = client.get(f"{BASE}/tournaments?from=2026-11-12&to=2026-12-01", headers=org.admin).json()
    assert sorted(t["name"] for t in period["items"]) == ["Nationals", "State 1"]
    assert client.get(f"{BASE}/tournaments?limit=201", headers=org.admin).status_code == 422
    bad = client.get(f"{BASE}/tournaments?from=2026-12-01&to=2026-11-01", headers=org.admin)
    assert bad.status_code == 400 and _code(bad) == "invalid_period"


def test_update_tournament(client, org):
    t = org.tournament(publish=False)
    r = client.patch(
        f"{BASE}/tournaments/{t['id']}", json={"venue": "Main Ground", "hosting": "home"}, headers=org.admin
    )
    assert r.status_code == 200 and r.json()["venue"] == "Main Ground" and r.json()["hosting"] == "home"
    r = client.patch(f"{BASE}/tournaments/{t['id']}", json={"hosting": None}, headers=org.admin)
    assert "hosting" not in r.json()
    updates = [(a.before, a.after) for a in _audit(org.id, "tournament") if a.action == "tournament.updated"]
    assert ({"venue": "University Stadium", "hosting": None}, {"venue": "Main Ground", "hosting": "home"}) in updates
    assert ({"hosting": "home"}, {"hosting": None}) in updates and len(updates) == 2

    bad = client.patch(f"{BASE}/tournaments/{t['id']}", json={"end_date": "2026-11-01"}, headers=org.admin)
    assert bad.status_code == 400 and _code(bad) == "end_before_start"
    bad = client.patch(
        f"{BASE}/tournaments/{t['id']}", json={"registration_closes_on": "2026-12-01"}, headers=org.admin
    )
    assert _code(bad) == "registration_after_end"
    assert client.patch(f"{BASE}/tournaments/{t['id']}", json={"name": None}, headers=org.admin).status_code == 422
    assert (
        client.patch(f"{BASE}/tournaments/{t['id']}", json={"discipline_id": "x"}, headers=org.admin).status_code == 422
    )
    assert (
        client.patch(f"{BASE}/tournaments/{t['id']}", json={"status": "published"}, headers=org.admin).status_code
        == 422
    )
    assert client.patch(f"{BASE}/tournaments/{A1}", json={"venue": "x"}, headers=org.admin).status_code == 404
    assert client.get(f"{BASE}/tournaments/not-a-uuid", headers=org.admin).status_code == 404


def test_create_tournament_refusals(client, org):
    body = {
        "name": "Cup",
        "discipline": "Football",
        "level": "state",
        "format": "knockout",
        "start_date": "2026-11-10",
        "end_date": "2026-11-09",
    }
    r = client.post(f"{BASE}/tournaments", json=body, headers=org.admin)
    assert r.status_code == 400 and _code(r) == "end_before_start"
    assert client.post(f"{BASE}/tournaments", json={**body, "level": "district"}, headers=org.admin).status_code == 422
    assert client.post(f"{BASE}/tournaments", json={**body, "extra": 1}, headers=org.admin).status_code == 422


def test_cancel_cancels_open_fixtures_and_closes_the_tournament(client, org):
    t = org.tournament()
    e = org.entry(t["id"], [A1])
    f1 = org.fixture(t["id"], [e["id"]])
    f2 = org.fixture(t["id"], [e["id"]], at="2026-11-11T04:30:00Z")
    assert client.post(f"{BASE}/tournaments/{t['id']}/cancel", json={}, headers=org.admin).status_code == 422
    assert (
        client.post(f"{BASE}/tournaments/{t['id']}/cancel", json={"reason": ""}, headers=org.admin).status_code == 422
    )
    r = client.post(f"{BASE}/tournaments/{t['id']}/cancel", json={"reason": "Venue flooded"}, headers=org.admin)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    [cancelled] = outbox(org.id, "tournament-events.tournament.cancelled")
    assert cancelled.payload == {"organisation_id": org.id, "tournament_id": t["id"], "reason": "Venue flooded"}
    for f in (f1, f2):
        assert client.get(f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}", headers=org.admin).json()["status"] == (
            "cancelled"
        )
    [audit] = [a for a in _audit(org.id, "tournament") if a.action == "tournament.cancelled"]
    assert audit.after == {"status": "cancelled"} and "Venue flooded" not in repr(audit.before)
    assert len([a for a in _audit(org.id, "fixture") if a.action == "fixture.cancelled"]) == 2

    again = client.post(f"{BASE}/tournaments/{t['id']}/cancel", json={"reason": "x"}, headers=org.admin)
    assert _code(again) == "already_cancelled"
    assert _code(client.post(f"{BASE}/tournaments/{t['id']}/publish", headers=org.admin)) == "not_draft"
    for path, body in (
        ("/entries", {"category": "Men's 200 m", "athlete_ids": [A2], "status": "pending"}),
        (
            "/fixtures",
            {"round": "Final", "entry_ids": [], "scheduled_at": "2026-11-12T04:30:00Z", "status": "scheduled"},
        ),
        ("/officials", {"name": "R. Iyer", "official_role": "referee"}),
    ):
        r = client.post(f"{BASE}/tournaments/{t['id']}{path}", json=body, headers=org.admin)
        assert r.status_code == 400 and _code(r) in ("entries_not_open", "tournament_closed"), path
    r = client.put(f"{BASE}/tournaments/{t['id']}/logistics", json={"travel_mode": "bus"}, headers=org.admin)
    assert _code(r) == "tournament_closed"
    # a cancelled tournament stays visible to readers but never on the calendar
    _, viewer = org.user(VIEWER)
    assert client.get(f"{BASE}/tournaments/{t['id']}", headers=viewer).status_code == 200
    cal = client.get(f"{BASE}/calendar?from=2026-11-01&to=2026-11-30", headers=viewer).json()
    assert cal["items"] == []


def test_permissions_are_checked(client, org):
    t = org.tournament()
    _, viewer = org.user(VIEWER)
    _, coach = org.user(COACH)
    _, athlete = org.user(ATHLETE)
    assert client.get(f"{BASE}/tournaments", headers=viewer).status_code == 200
    r = client.post(f"{BASE}/tournaments", json={}, headers=coach)
    assert r.status_code == 403 and _code(r) == "forbidden"
    assert client.post(f"{BASE}/tournaments/{t['id']}/publish", headers=coach).status_code == 403
    assert client.post(f"{BASE}/tournaments/{t['id']}/cancel", json={"reason": "x"}, headers=coach).status_code == 403
    assert client.get(f"{BASE}/tournaments/{t['id']}/entries", headers=viewer).status_code == 403
    assert client.get(f"{BASE}/tournaments/{t['id']}/officials", headers=athlete).status_code == 403
    assert client.post(f"{BASE}/tournaments/{t['id']}/fixtures", json={}, headers=coach).status_code == 403
    assert client.put(f"{BASE}/tournaments/{t['id']}/logistics", json={}, headers=coach).status_code == 403
    assert client.get(f"{BASE}/tournaments/{t['id']}/logistics", headers=viewer).status_code == 403
    body = {"category": "x", "athlete_ids": [A1], "status": "pending"}
    assert client.post(f"{BASE}/tournaments/{t['id']}/entries", json=body, headers=athlete).status_code == 403
    assert client.get(f"{BASE}/tournaments").status_code == 401
    assert client.get(f"{BASE}/tournaments", headers={"Authorization": "Bearer nope"}).status_code == 401


# ---------------------------------------------------------------- entries


def test_entries_open_on_publish_and_close_on_the_deadline(client, org, later):
    draft = org.tournament(publish=False)
    body = {"category": "Men's 100 m", "athlete_ids": [A1], "status": "pending"}
    r = client.post(f"{BASE}/tournaments/{draft['id']}/entries", json=body, headers=org.admin)
    assert r.status_code == 400 and _code(r) == "entries_not_open"

    t = org.tournament()
    later(datetime(2026, 11, 5, 18, 0, tzinfo=UTC))  # 23:30 on the 5th in Kolkata: the last day
    assert client.post(f"{BASE}/tournaments/{t['id']}/entries", json=body, headers=org.admin).status_code == 201
    later(datetime(2026, 11, 5, 19, 0, tzinfo=UTC))  # 00:30 on the 6th
    r = client.post(f"{BASE}/tournaments/{t['id']}/entries", json={**body, "athlete_ids": [A2]}, headers=org.admin)
    assert _code(r) == "registration_closed"


def test_entry_lifecycle(client, org):
    t = org.tournament()
    _, coach = org.user(COACH)
    e = org.entry(t["id"], [A1, A2], category="4x100 m relay", team_name="Team A", status="pending")
    assert e["status"] == "pending" and e["athlete_ids"] == [A1, A2]
    assert outbox(org.id, "tournament-events.entry.confirmed") == []

    url = f"{BASE}/tournaments/{t['id']}/entries/{e['id']}"
    r = client.patch(url, json={"status": "confirmed"}, headers=coach)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    [confirmed] = outbox(org.id, "tournament-events.entry.confirmed")
    assert confirmed.payload == {
        "organisation_id": org.id,
        "tournament_id": t["id"],
        "entry_id": e["id"],
        "category": "4x100 m relay",
        "athlete_ids": [A1, A2],
    }
    # the same change again is no change: no event, no audit entry
    client.patch(url, json={"status": "confirmed"}, headers=coach)
    assert len(outbox(org.id, "tournament-events.entry.confirmed")) == 1
    # a confirmed entry whose athletes change is confirmed again with the new athletes
    client.patch(url, json={"athlete_ids": [A1, A3]}, headers=coach)
    assert outbox(org.id, "tournament-events.entry.confirmed")[-1].payload["athlete_ids"] == [A1, A3]

    assert _code(client.patch(url, json={"status": "pending"}, headers=coach)) == "invalid_transition"
    r = client.patch(url, json={"status": "withdrawn"}, headers=coach)
    assert r.json()["status"] == "withdrawn"
    assert _code(client.patch(url, json={"status": "confirmed"}, headers=coach)) == "entry_withdrawn"
    assert _code(client.patch(url, json={"team_name": "B"}, headers=coach)) == "entry_withdrawn"
    assert client.patch(url, json={}, headers=coach).status_code == 422
    assert client.patch(url, json={"status": None}, headers=coach).status_code == 422
    assert (
        client.patch(
            f"{BASE}/tournaments/{t['id']}/entries/{A1}", json={"status": "confirmed"}, headers=coach
        ).status_code
        == 404
    )
    assert sorted(a.action for a in _audit(org.id, "entry")) == ["entry.created"] + ["entry.updated"] * 3

    listed = client.get(f"{BASE}/tournaments/{t['id']}/entries?status=withdrawn", headers=coach).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == e["id"]


def test_entry_refusals(client, org):
    t = org.tournament()
    url = f"{BASE}/tournaments/{t['id']}/entries"
    body = {"category": "Men's 100 m", "athlete_ids": [A1], "status": "confirmed"}
    assert client.post(url, json=body, headers=org.admin).status_code == 201
    r = client.post(url, json={**body, "athlete_ids": [A2, A1]}, headers=org.admin)
    assert r.status_code == 400 and _code(r) == "already_entered"
    assert client.post(url, json={**body, "category": "Men's 200 m"}, headers=org.admin).status_code == 201
    assert _code(client.post(url, json={**body, "athlete_ids": []}, headers=org.admin)) == "no_athletes"
    assert _code(client.post(url, json={**body, "athlete_ids": [A3, A3]}, headers=org.admin)) == "duplicate_athlete"
    assert _code(client.post(url, json={**body, "athlete_ids": [A3], "status": "withdrawn"}, headers=org.admin)) == (
        "invalid_status"
    )
    assert client.post(url, json={**body, "athlete_ids": ["not-a-uuid"]}, headers=org.admin).status_code == 422
    assert client.post(f"{BASE}/tournaments/{A1}/entries", json=body, headers=org.admin).status_code == 404


def test_an_athlete_sees_only_their_own_entries(client, org):
    t = org.tournament()
    mine = org.entry(t["id"], [A1])
    relay = org.entry(t["id"], [A2, A1], category="4x100 m relay")
    org.entry(t["id"], [A2], category="Men's 200 m")
    user_id, athlete = org.user(ATHLETE)
    url = f"{BASE}/tournaments/{t['id']}/entries"
    assert client.get(url, headers=athlete).json() == {"items": [], "total": 0}  # not linked yet: nothing

    org.link(A1, user_id)
    seen = client.get(url, headers=athlete).json()
    assert seen["total"] == 2 and {e["id"] for e in seen["items"]} == {mine["id"], relay["id"]}
    assert client.get(f"{url}?limit=1", headers=athlete).json()["total"] == 2
    # the profile role is narrowed the same way; a coach who is also an athlete sees everyone's
    _, profile_athlete = org.user("athlete", user_id=user_id)
    assert client.get(url, headers=profile_athlete).json()["total"] == 2
    _, coach_athlete = org.user(ATHLETE, COACH, user_id=user_id)
    assert client.get(url, headers=coach_athlete).json()["total"] == 3
    # fixtures, results and logistics of a published tournament are the same for every reader
    assert client.get(f"{BASE}/tournaments/{t['id']}/fixtures", headers=athlete).status_code == 200
    assert client.get(f"{BASE}/tournaments/{t['id']}/logistics", headers=athlete).status_code == 200


# ---------------------------------------------------------------- fixtures


def test_fixture_scheduling_and_rescheduling(client, org):
    t = org.tournament()
    e1, e2 = org.entry(t["id"], [A1]), org.entry(t["id"], [A2])
    f = org.fixture(
        t["id"], [e1["id"], e2["id"]], at="2026-11-10T10:00:00+05:30", category="Men's 100 m", venue="Track 1"
    )
    assert f["scheduled_at"] == "2026-11-10T04:30:00+00:00" and f["status"] == "scheduled"
    [scheduled] = outbox(org.id, "tournament-events.fixture.scheduled")
    assert scheduled.payload == {
        "organisation_id": org.id,
        "tournament_id": t["id"],
        "fixture_id": f["id"],
        "scheduled_at": "2026-11-10T04:30:00+00:00",
        "venue": "Track 1",
    }
    url = f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}"
    assert client.get(url, headers=org.admin).json()["id"] == f["id"]

    # the same instant in another offset is not a change
    client.patch(url, json={"scheduled_at": "2026-11-10T04:30:00Z"}, headers=org.admin)
    assert len(outbox(org.id, "tournament-events.fixture.scheduled")) == 1
    assert client.patch(url, json={"status": "postponed"}, headers=org.admin).json()["status"] == "postponed"
    assert len(outbox(org.id, "tournament-events.fixture.scheduled")) == 1
    r = client.patch(url, json={"status": "scheduled", "scheduled_at": "2026-11-11T04:30:00Z"}, headers=org.admin)
    assert r.json()["scheduled_at"] == "2026-11-11T04:30:00+00:00"
    assert (
        outbox(org.id, "tournament-events.fixture.scheduled")[-1].payload["scheduled_at"] == "2026-11-11T04:30:00+00:00"
    )
    assert _code(client.patch(url, json={"status": "completed"}, headers=org.admin)) == "record_result"
    assert client.patch(url, json={"status": "in_progress"}, headers=org.admin).status_code == 200
    assert _code(client.patch(url, json={"status": "scheduled"}, headers=org.admin)) == "invalid_transition"
    assert client.patch(url, json={"status": "cancelled"}, headers=org.admin).status_code == 200
    assert _code(client.patch(url, json={"venue": "Track 2"}, headers=org.admin)) == "fixture_closed"
    assert sorted(a.action for a in _audit(org.id, "fixture")) == ["fixture.scheduled"] + ["fixture.updated"] * 4


def test_fixture_refusals(client, org):
    draft = org.tournament(publish=False)
    body = {"round": "Heat 1", "entry_ids": [], "scheduled_at": "2026-11-10T04:30:00Z", "status": "scheduled"}
    r = client.post(f"{BASE}/tournaments/{draft['id']}/fixtures", json=body, headers=org.admin)
    assert r.status_code == 400 and _code(r) == "tournament_not_published"

    t = org.tournament()
    e = org.entry(t["id"], [A1])
    w = org.entry(t["id"], [A2], status="pending")
    client.patch(f"{BASE}/tournaments/{t['id']}/entries/{w['id']}", json={"status": "withdrawn"}, headers=org.admin)
    url = f"{BASE}/tournaments/{t['id']}/fixtures"
    assert client.post(url, json=body, headers=org.admin).status_code == 201  # participants still to be decided
    cases = [
        ({"entry_ids": [A3]}, "unknown_entry"),
        ({"entry_ids": [w["id"]]}, "entry_withdrawn"),
        ({"entry_ids": [e["id"], e["id"]]}, "duplicate_entry"),
        ({"entry_ids": [e["id"]], "category": "Women's 100 m"}, "category_mismatch"),
        ({"scheduled_at": "2026-11-09T18:00:00Z"}, "outside_tournament_dates"),  # 23:30 on the 9th in Kolkata
        ({"scheduled_at": "2026-11-12T18:30:00Z"}, "outside_tournament_dates"),  # 00:00 on the 13th
        ({"status": "completed"}, "invalid_status"),
    ]
    for change, code in cases:
        r = client.post(url, json={**body, **change}, headers=org.admin)
        assert r.status_code == 400 and _code(r) == code, (change, r.text)
    ok = client.post(url, json={**body, "scheduled_at": "2026-11-09T19:00:00Z"}, headers=org.admin)  # 00:30 on the 10th
    assert ok.status_code == 201
    assert client.post(url, json={**body, "scheduled_at": "2026-11-10T04:30:00"}, headers=org.admin).status_code == 422
    other = org.tournament(name="Other")
    elsewhere = org.entry(other["id"], [A3])
    assert _code(client.post(url, json={**body, "entry_ids": [elsewhere["id"]]}, headers=org.admin)) == "unknown_entry"
    assert client.get(f"{url}/{A1}", headers=org.admin).status_code == 404


def test_fixture_list_filters_by_local_day_and_status(client, org):
    t = org.tournament()
    late = org.fixture(t["id"], [], at="2026-11-10T19:00:00Z")  # 00:30 on the 11th in Kolkata
    early = org.fixture(t["id"], [], at="2026-11-10T02:00:00Z")
    url = f"{BASE}/tournaments/{t['id']}/fixtures"
    day = client.get(f"{url}?from=2026-11-10&to=2026-11-10", headers=org.admin).json()
    assert [f["id"] for f in day["items"]] == [early["id"]]
    assert [f["id"] for f in client.get(url, headers=org.admin).json()["items"]] == [early["id"], late["id"]]
    client.patch(f"{url}/{late['id']}", json={"status": "postponed"}, headers=org.admin)
    assert client.get(f"{url}?status=postponed", headers=org.admin).json()["total"] == 1
    assert client.get(f"{url}?limit=1&offset=1", headers=org.admin).json()["items"][0]["id"] == late["id"]


# ---------------------------------------------------------------- results


def test_recording_a_result_completes_the_fixture(client, org, later):
    t = org.tournament()
    e1, e2 = org.entry(t["id"], [A1]), org.entry(t["id"], [A2, A3], category="Men's 100 m relay")
    f = org.fixture(t["id"], [e1["id"], e2["id"]])
    url = f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}/result"
    body = {
        "placings": [
            {"entry_id": e2["id"], "position": 1, "mark": 10.85, "unit": "s", "score": "1st"},
            {"entry_id": e1["id"], "position": 2, "mark": 11.02, "unit": "s"},
        ],
        "notes": "Wind +1.2",
    }
    r = client.put(url, json=body, headers=org.admin)
    assert r.status_code == 400 and _code(r) == "fixture_not_started"
    assert client.get(url, headers=org.admin).status_code == 404

    later(DURING)
    _, coach = org.user(COACH)
    r = client.put(url, json=body, headers=coach)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["fixture_id"] == f["id"] and result["placings"][0]["score"] == "1st"
    assert result["recorded_at"] == "2026-11-10T06:00:00+00:00" and result["notes"] == "Wind +1.2"
    assert client.get(url, headers=coach).json() == result
    fixture = client.get(f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}", headers=coach).json()
    assert fixture["status"] == "completed"
    [recorded] = outbox(org.id, "tournament-events.result.recorded")
    assert recorded.payload == {
        "organisation_id": org.id,
        "tournament_id": t["id"],
        "fixture_id": f["id"],
        "placings": [
            {"entry_id": e2["id"], "athlete_ids": [A2, A3], "position": 1, "mark": 10.85, "unit": "s"},
            {"entry_id": e1["id"], "athlete_ids": [A1], "position": 2, "mark": 11.02, "unit": "s"},
        ],
    }
    # a retry of the same PUT changes nothing and publishes nothing
    assert client.put(url, json=body, headers=coach).status_code == 200
    assert len(outbox(org.id, "tournament-events.result.recorded")) == 1
    # a correction replaces the placings and is published again
    body["placings"][0]["mark"] = 10.86
    assert client.put(url, json=body, headers=coach).json()["placings"][0]["mark"] == 10.86
    assert len(outbox(org.id, "tournament-events.result.recorded")) == 2
    actions = sorted(a.action for a in _audit(org.id) if a.entity_type in ("result", "fixture"))
    assert actions == ["fixture.completed", "fixture.scheduled", "result.corrected", "result.recorded"]
    assert all("notes" not in (a.after or {}) for a in _audit(org.id, "result"))
    r = client.patch(f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}", json={"venue": "x"}, headers=org.admin)
    assert _code(r) == "fixture_closed"


def test_result_refusals(client, org, later):
    t = org.tournament()
    e = org.entry(t["id"], [A1])
    f = org.fixture(t["id"], [e["id"]])
    later(DURING)
    url = f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}/result"
    cases = [
        ([], "no_placings"),
        ([{"entry_id": A3, "position": 1}], "entry_not_in_fixture"),
        ([{"entry_id": e["id"]}, {"entry_id": e["id"]}], "duplicate_placing"),
        ([{"entry_id": e["id"], "position": 0}], "invalid_position"),
    ]
    for placings, code in cases:
        r = client.put(url, json={"placings": placings}, headers=org.admin)
        assert r.status_code == 400 and _code(r) == code, code
    assert (
        client.put(url, json={"placings": [{"entry_id": e["id"], "mark": "fast"}]}, headers=org.admin).status_code
        == 422
    )

    client.patch(f"{BASE}/tournaments/{t['id']}/fixtures/{f['id']}", json={"status": "postponed"}, headers=org.admin)
    r = client.put(url, json={"placings": [{"entry_id": e["id"], "position": 1}]}, headers=org.admin)
    assert _code(r) == "fixture_not_playable"
    assert (
        client.put(
            f"{BASE}/tournaments/{t['id']}/fixtures/{A1}/result", json={"placings": []}, headers=org.admin
        ).status_code
        == 404
    )
    _, viewer = org.user(VIEWER)
    assert client.put(url, json={"placings": []}, headers=viewer).status_code == 403


# ---------------------------------------------------------------- officials


def test_officials(client, org):
    t = org.tournament()
    f = org.fixture(t["id"], [])
    url = f"{BASE}/tournaments/{t['id']}/officials"
    staff = A2
    o = org.post(
        f"/tournaments/{t['id']}/officials",
        {"name": "R. Iyer", "official_role": "referee", "user_id": staff, "fixture_id": f["id"]},
    )
    assert o["confirmed"] is False and o["fixture_id"] == f["id"]
    whole = org.post(
        f"/tournaments/{t['id']}/officials", {"name": "S. Rao", "official_role": "team_manager", "confirmed": True}
    )
    assert "fixture_id" not in whole
    [assigned, _] = outbox(org.id, "tournament-events.official.assigned")
    assert assigned.payload == {
        "organisation_id": org.id,
        "tournament_id": t["id"],
        "official_id": o["id"],
        "fixture_id": f["id"],
        "official_role": "referee",
    }
    dup = client.post(
        url,
        json={"name": "Someone", "official_role": "referee", "user_id": staff, "fixture_id": f["id"]},
        headers=org.admin,
    )
    assert dup.status_code == 400 and _code(dup) == "already_assigned"
    dup = client.post(url, json={"name": "S. Rao", "official_role": "team_manager"}, headers=org.admin)
    assert _code(dup) == "already_assigned"
    bad = client.post(url, json={"name": "X", "official_role": "judge", "fixture_id": A3}, headers=org.admin)
    assert _code(bad) == "unknown_fixture"
    assert client.post(url, json={"name": "X", "official_role": "coach"}, headers=org.admin).status_code == 422

    _, coach = org.user(COACH)
    listed = client.get(f"{url}?limit=1", headers=coach).json()
    assert listed["total"] == 2 and listed["items"][0]["id"] in {o["id"], whole["id"]}  # same created_at: either
    assert client.delete(f"{url}/{o['id']}", headers=coach).status_code == 403
    r = client.delete(f"{url}/{o['id']}", headers=org.admin)
    assert r.status_code == 204 and r.content == b""
    assert client.delete(f"{url}/{o['id']}", headers=org.admin).status_code == 404
    audit = _audit(org.id, "official")
    assert sorted(a.action for a in audit) == ["official.assigned", "official.assigned", "official.removed"]
    assert all("R. Iyer" not in repr((a.before, a.after)) for a in audit)  # names are not copied into the audit


# ---------------------------------------------------------------- logistics


def test_logistics(client, org):
    t = org.tournament()
    url = f"{BASE}/tournaments/{t['id']}/logistics"
    assert client.get(url, headers=org.admin).json() == {}
    body = {
        "travel_mode": "train",
        "departure_at": "2026-11-08T21:00:00+05:30",
        "return_at": "2026-11-13T06:00:00Z",
        "accommodation": "Hostel B, rooms 1-6",
        "travelling_count": 14,
        "contact_person_id": A3,
        "notes": "Carry ID cards",
    }
    r = client.put(url, json=body, headers=org.admin)
    assert r.status_code == 200 and r.json()["departure_at"] == "2026-11-08T15:30:00+00:00"
    _, athlete = org.user(ATHLETE)
    assert client.get(url, headers=athlete).json() == r.json()
    # PUT replaces: what is left out is cleared
    r = client.put(url, json={"travel_mode": "bus", "travelling_count": 12}, headers=org.admin)
    assert r.json() == {"travel_mode": "bus", "travelling_count": 12}
    audit = _audit(org.id, "logistics")
    assert [a.action for a in audit] == ["logistics.set", "logistics.set"]
    assert all("accommodation" not in (a.after or {}) and "notes" not in (a.after or {}) for a in audit)
    # the same logistics again is no change
    client.put(url, json={"travel_mode": "bus", "travelling_count": 12}, headers=org.admin)
    assert len(_audit(org.id, "logistics")) == 2

    bad = client.put(
        url, json={"departure_at": "2026-11-09T00:00:00Z", "return_at": "2026-11-08T00:00:00Z"}, headers=org.admin
    )
    assert bad.status_code == 400 and _code(bad) == "return_before_departure"
    assert _code(client.put(url, json={"travelling_count": -1}, headers=org.admin)) == "invalid_count"
    assert client.put(url, json={"departure_at": "2026-11-09T00:00:00"}, headers=org.admin).status_code == 422
    assert client.put(url, json={"travel_mode": "ship"}, headers=org.admin).status_code == 422


# ---------------------------------------------------------------- calendar


def test_calendar_shows_published_tournaments_and_their_fixtures(client, org):
    t = org.tournament(name="Athletics Meet")
    e = org.entry(t["id"], [A1])
    heat = org.fixture(t["id"], [e["id"]], at="2026-11-10T04:30:00Z", category="Men's 100 m")
    final = org.fixture(t["id"], [e["id"]], at="2026-11-12T10:00:00Z", round="Final", venue="Track 2")
    off = org.fixture(t["id"], [e["id"]], at="2026-11-11T04:30:00Z")
    client.patch(f"{BASE}/tournaments/{t['id']}/fixtures/{off['id']}", json={"status": "cancelled"}, headers=org.admin)
    org.tournament(publish=False, name="Draft cup")
    _, viewer = org.user(VIEWER)

    items = client.get(f"{BASE}/calendar?from=2026-11-01&to=2026-11-30", headers=viewer).json()["items"]
    assert [(i["kind"], i["id"]) for i in items] == [
        ("tournament", t["id"]),
        ("fixture", heat["id"]),
        ("fixture", final["id"]),
    ]
    assert items[0] == {
        "kind": "tournament",
        "id": t["id"],
        "tournament_id": t["id"],
        "title": "Athletics Meet",
        "starts_at": "2026-11-09T18:30:00+00:00",  # midnight in Kolkata
        "ends_at": "2026-11-12T18:30:00+00:00",
        "venue": "University Stadium",
    }
    assert items[1]["title"] == "Athletics Meet: Heat 1 (Men's 100 m)" and items[1]["venue"] == "University Stadium"
    assert items[2]["venue"] == "Track 2" and items[2]["tournament_id"] == t["id"]

    # the 12th in Kolkata ends at 18:30 UTC; the final at 10:00 UTC is on it, the heat is not
    day = client.get(f"{BASE}/calendar?from=2026-11-12&to=2026-11-12", headers=viewer).json()["items"]
    assert [i["id"] for i in day] == [t["id"], final["id"]]
    assert client.get(f"{BASE}/calendar?from=2026-12-01&to=2026-12-31", headers=viewer).json() == {"items": []}


def test_calendar_refusals(client, org):
    _, viewer = org.user(VIEWER)
    assert client.get(f"{BASE}/calendar", headers=viewer).status_code == 422
    assert client.get(f"{BASE}/calendar?from=2026-11-01", headers=viewer).status_code == 422
    r = client.get(f"{BASE}/calendar?from=2026-11-02&to=2026-11-01", headers=viewer)
    assert r.status_code == 400 and _code(r) == "invalid_period"
    r = client.get(f"{BASE}/calendar?from=2026-01-01&to=2027-06-01", headers=viewer)
    assert r.status_code == 400 and _code(r) == "period_too_long"
    _, nobody = org.user("someone-else")
    assert client.get(f"{BASE}/calendar?from=2026-11-01&to=2026-11-02", headers=nobody).status_code == 403
