"""The HTTP surface against contracts/openapi.yaml: plans and reviews, health records, injuries and appointments,
with the events and audit entries each change writes, and who may see which rows and fields."""

from conftest import ATHLETE, BASE, COACH, MEDICAL, NUTRITIONIST, outbox
from eos_core.db import SessionLocal, new_id
from eos_sports_nutrition_health.infrastructure.models import AuditEntry
from sqlalchemy import select

ATHLETE_A = "11111111-1111-1111-1111-111111111111"
ATHLETE_B = "22222222-2222-2222-2222-222222222222"


def _audit(organisation_id: str) -> list[AuditEntry]:
    with SessionLocal() as db:
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        return list(db.scalars(q.order_by(AuditEntry.occurred_at)))


# ---------------------------------------------------------------- nutrition plans


def test_plan_lifecycle(client, org):
    nutritionist_id, nutritionist = org.user(NUTRITIONIST)
    meals = [{"meal": "Breakfast", "items": "Oats, eggs"}]
    p = org.plan(ATHLETE_A, daily_calories=3200, protein_g=160, meals=meals)
    assert p["status"] == "active" and p["meals"] == meals and "end_date" not in p
    [ev] = outbox(org.id, "sports-nutrition-health.plan.created")
    assert ev.payload == {
        "organisation_id": org.id,
        "plan_id": p["id"],
        "athlete_id": ATHLETE_A,
        "goal": "performance",
        "start_date": "2026-10-01",
        "review_due_on": "2026-11-01",
    }

    r = client.post(
        f"{BASE}/nutrition-plans/{p['id']}/reviews",
        json={"reviewed_on": "2026-10-28", "outcome": "adjust", "body_weight_kg": 71.5, "next_review_on": "2026-11-15"},
        headers=nutritionist,
    )
    assert r.status_code == 201 and r.json()["reviewed_by"] == nutritionist_id
    assert client.get(f"{BASE}/nutrition-plans/{p['id']}", headers=nutritionist).json()["review_due_on"] == "2026-11-15"
    [rev] = outbox(org.id, "sports-nutrition-health.plan.reviewed")
    assert rev.payload["outcome"] == "adjust" and rev.payload["next_review_on"] == "2026-11-15"
    reviews = client.get(f"{BASE}/nutrition-plans/{p['id']}/reviews", headers=nutritionist).json()
    assert reviews["total"] == 1

    client.post(
        f"{BASE}/nutrition-plans/{p['id']}/reviews",
        json={"reviewed_on": "2026-10-29", "outcome": "end"},
        headers=nutritionist,
    )
    ended = client.get(f"{BASE}/nutrition-plans/{p['id']}", headers=nutritionist).json()
    assert ended["status"] == "completed" and "review_due_on" not in ended
    again = client.post(
        f"{BASE}/nutrition-plans/{p['id']}/reviews",
        json={"reviewed_on": "2026-10-29", "outcome": "continue"},
        headers=nutritionist,
    )
    assert again.status_code == 400 and again.json()["detail"]["code"] == "plan_closed"
    edit = client.patch(f"{BASE}/nutrition-plans/{p['id']}", json={"title": "x"}, headers=nutritionist)
    assert edit.json()["detail"]["code"] == "plan_closed"
    archive = client.patch(f"{BASE}/nutrition-plans/{p['id']}", json={"status": "archived"}, headers=nutritionist)
    assert archive.status_code == 200 and archive.json()["status"] == "archived"
    reopen = client.patch(f"{BASE}/nutrition-plans/{p['id']}", json={"status": "active"}, headers=nutritionist)
    assert reopen.json()["detail"]["code"] == "plan_closed"
    entries = [e for e in _audit(org.id) if e.entity_type == "plan"]
    assert all("meals" not in (e.after or {}) for e in entries)


def test_plan_filters_and_refusals(client, org):
    org.plan(ATHLETE_A, review_due_on="2026-11-01")
    org.plan(ATHLETE_B, review_due_on="2026-12-01", status="draft")
    org.plan(ATHLETE_B, review_due_on=None)

    def count(query: str) -> int:
        return client.get(f"{BASE}/nutrition-plans?{query}", headers=org.admin).json()["total"]

    assert count("") == 3
    assert count(f"athlete_id={ATHLETE_B}") == 2
    assert count("status=draft") == 1
    assert count("review_due_before=2026-11-01") == 1  # inclusive; plans without a review date are not due
    bad = client.post(
        f"{BASE}/nutrition-plans",
        json={
            "athlete_id": ATHLETE_A,
            "title": "x",
            "goal": "recovery",
            "start_date": "2026-10-10",
            "end_date": "2026-10-01",
            "status": "draft",
        },
        headers=org.admin,
    )
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "invalid_dates"
    neg = client.post(
        f"{BASE}/nutrition-plans",
        json={
            "athlete_id": ATHLETE_A,
            "title": "x",
            "goal": "recovery",
            "start_date": "2026-10-10",
            "status": "draft",
            "fat_g": -1,
        },
        headers=org.admin,
    )
    assert neg.status_code == 422
    assert (
        client.post(f"{BASE}/nutrition-plans", json={"athlete_id": "", "title": "x"}, headers=org.admin).status_code
        == 422
    )


# ---------------------------------------------------------------- health records


def test_health_records_are_for_medical_roles_only(client, org):
    medic_id, medic = org.user(MEDICAL)
    h = org.post(
        "/health-records",
        {
            "athlete_id": ATHLETE_A,
            "record_type": "allergy",
            "title": "Peanuts",
            "details": "Anaphylaxis",
            "recorded_on": "2026-10-01",
        },
        headers=medic,
    )
    assert h["recorded_by"] == medic_id and h["details"] == "Anaphylaxis"
    assert client.get(f"{BASE}/health-records?record_type=allergy", headers=medic).json()["total"] == 1
    for role in (COACH, NUTRITIONIST, ATHLETE, "org-admin"):
        _, headers = org.user(role)
        assert client.get(f"{BASE}/health-records", headers=headers).status_code == 403, role
        assert client.get(f"{BASE}/health-records/{h['id']}", headers=headers).status_code == 403, role
    r = client.patch(f"{BASE}/health-records/{h['id']}", json={"details": "Severe"}, headers=medic)
    assert r.json()["details"] == "Severe"
    entries = [e for e in _audit(org.id) if e.entity_type == "health_record"]
    assert [e.action for e in entries] == ["health_record.created", "health_record.updated"]
    assert entries[0].after == {"athlete_id": ATHLETE_A, "record_type": "allergy", "recorded_on": "2026-10-01"}
    assert entries[1].after == {}  # the clinical text is never copied
    assert outbox(org.id) == []  # health records publish nothing


# ---------------------------------------------------------------- injuries


def test_injury_lifecycle_and_clinical_notes(client, org):
    _, medic = org.user(MEDICAL)
    _, coach = org.user(COACH)
    i = org.injury(ATHLETE_A, clinical_notes="Grade 2 tear", expected_return_on="2026-11-20")
    [ev] = outbox(org.id, "sports-nutrition-health.injury.reported")
    assert ev.payload == {
        "organisation_id": org.id,
        "injury_id": i["id"],
        "athlete_id": ATHLETE_A,
        "severity": "moderate",
        "occurred_on": "2026-10-20",
        "expected_return_on": "2026-11-20",
    }
    assert client.get(f"{BASE}/injuries/{i['id']}", headers=medic).json()["clinical_notes"] == "Grade 2 tear"
    seen = client.get(f"{BASE}/injuries/{i['id']}", headers=coach).json()
    assert "clinical_notes" not in seen and seen["expected_return_on"] == "2026-11-20"
    assert "clinical_notes" not in client.get(f"{BASE}/injuries", headers=coach).json()["items"][0]

    client.patch(f"{BASE}/injuries/{i['id']}", json={"status": "recovering"}, headers=medic)
    assert outbox(org.id, "sports-nutrition-health.injury.resolved") == []
    client.patch(f"{BASE}/injuries/{i['id']}", json={"status": "resolved"}, headers=medic)
    [res] = outbox(org.id, "sports-nutrition-health.injury.resolved")
    assert res.payload["resolved_on"] == "2026-10-29"
    assert client.get(f"{BASE}/injuries?status=resolved", headers=coach).json()["total"] == 1
    assert client.patch(f"{BASE}/injuries/{i['id']}", json={"status": "resolved"}, headers=medic).status_code == 200
    assert len(outbox(org.id, "sports-nutrition-health.injury.resolved")) == 1  # resolving twice publishes once
    assert client.patch(f"{BASE}/injuries/{i['id']}", json={"status": "x"}, headers=coach).status_code == 403

    future = client.post(
        f"{BASE}/injuries",
        json={
            "athlete_id": ATHLETE_A,
            "body_part": "Knee",
            "severity": "minor",
            "occurred_on": "2026-11-05",
            "status": "active",
        },
        headers=medic,
    )
    assert future.json()["detail"]["code"] == "in_future"
    early = client.patch(f"{BASE}/injuries/{i['id']}", json={"expected_return_on": "2026-10-01"}, headers=medic)
    assert early.json()["detail"]["code"] == "invalid_dates"
    assert all("clinical_notes" not in (e.after or {}) for e in _audit(org.id))


# ---------------------------------------------------------------- appointments


def test_appointments(client, org):
    physio_id, physio = org.user(MEDICAL)
    _, coach = org.user(COACH)
    injury = org.injury(ATHLETE_A)
    a = org.appointment(ATHLETE_A, physio_id, injury_id=injury["id"], notes="Bring scans", headers=physio)
    assert a["duration_minutes"] == 30 and a["notes"] == "Bring scans"
    [ev] = outbox(org.id, "sports-nutrition-health.appointment.scheduled")
    assert ev.payload["scheduled_at"] == "2026-10-30T10:00:00+00:00" and ev.payload["practitioner_id"] == physio_id
    assert "notes" not in client.get(f"{BASE}/appointments/{a['id']}", headers=coach).json()

    org.appointment(ATHLETE_B, physio_id, scheduled_at="2026-10-31T10:00:00+05:30")
    assert client.get(f"{BASE}/appointments?on=2026-10-30", headers=physio).json()["total"] == 1
    assert client.get(f"{BASE}/appointments?on=2026-10-31", headers=physio).json()["total"] == 1  # 04:30 UTC
    assert client.get(f"{BASE}/appointments?practitioner_id={physio_id}", headers=physio).json()["total"] == 2

    early = client.patch(f"{BASE}/appointments/{a['id']}", json={"status": "completed"}, headers=physio)
    assert early.status_code == 400 and early.json()["detail"]["code"] == "not_yet_held"
    moved = client.patch(
        f"{BASE}/appointments/{a['id']}", json={"scheduled_at": "2026-10-29T08:00:00Z"}, headers=physio
    )
    assert moved.json()["scheduled_at"] == "2026-10-29T08:00:00+00:00"
    done = client.patch(f"{BASE}/appointments/{a['id']}", json={"status": "completed"}, headers=physio)
    assert done.json()["status"] == "completed"
    [comp] = outbox(org.id, "sports-nutrition-health.appointment.completed")
    assert comp.payload["completed_at"] == "2026-10-29T09:00:00+00:00"
    closed = client.patch(f"{BASE}/appointments/{a['id']}", json={"status": "cancelled"}, headers=physio)
    assert closed.json()["detail"]["code"] == "appointment_closed"
    assert (
        client.patch(f"{BASE}/appointments/{a['id']}", json={"notes": "Went well"}, headers=physio).status_code == 200
    )

    other = org.injury(ATHLETE_B)
    wrong = client.post(
        f"{BASE}/appointments",
        json={
            "athlete_id": ATHLETE_A,
            "practitioner_id": physio_id,
            "appointment_type": "medical",
            "injury_id": other["id"],
            "scheduled_at": "2026-10-30T10:00:00Z",
            "status": "scheduled",
        },
        headers=physio,
    )
    assert wrong.json()["detail"]["code"] == "injury_of_another_athlete"
    cancelled = client.post(
        f"{BASE}/appointments",
        json={
            "athlete_id": ATHLETE_A,
            "practitioner_id": physio_id,
            "appointment_type": "medical",
            "scheduled_at": "2026-10-30T10:00:00Z",
            "status": "cancelled",
        },
        headers=physio,
    )
    assert cancelled.json()["detail"]["code"] == "invalid_status"
    past = org.appointment(ATHLETE_A, physio_id, scheduled_at="2026-10-28T10:00:00Z", status="completed")
    assert past["status"] == "completed"
    assert len(outbox(org.id, "sports-nutrition-health.appointment.completed")) == 2


# ---------------------------------------------------------------- athletes see only their own rows


def test_an_athlete_sees_only_their_own_rows(client, org):
    me = new_id()
    org.link(ATHLETE_A, me)
    physio_id, _ = org.user(MEDICAL)
    mine = org.plan(ATHLETE_A)
    theirs = org.plan(ATHLETE_B)
    my_injury = org.injury(ATHLETE_A, clinical_notes="private")
    their_injury = org.injury(ATHLETE_B)
    org.appointment(ATHLETE_A, physio_id, notes="private")
    their_appt = org.appointment(ATHLETE_B, physio_id)
    _, athlete = org.user(ATHLETE, user_id=me)
    _, profile_athlete = org.user("athlete", user_id=me)

    for headers in (athlete, profile_athlete):
        assert [p["id"] for p in client.get(f"{BASE}/nutrition-plans", headers=headers).json()["items"]] == [mine["id"]]
        assert client.get(f"{BASE}/nutrition-plans?athlete_id={ATHLETE_B}", headers=headers).json()["total"] == 0
        assert client.get(f"{BASE}/nutrition-plans/{theirs['id']}", headers=headers).status_code == 404
        assert client.get(f"{BASE}/nutrition-plans/{theirs['id']}/reviews", headers=headers).status_code == 404
        injuries = client.get(f"{BASE}/injuries", headers=headers).json()["items"]
        assert [i["id"] for i in injuries] == [my_injury["id"]] and "clinical_notes" not in injuries[0]
        assert client.get(f"{BASE}/injuries/{their_injury['id']}", headers=headers).status_code == 404
        appts = client.get(f"{BASE}/appointments", headers=headers).json()["items"]
        assert len(appts) == 1 and "notes" not in appts[0]
        assert client.get(f"{BASE}/appointments/{their_appt['id']}", headers=headers).status_code == 404

    # an athlete who is also a coach sees the organisation
    _, both = org.user("athlete", "coach", user_id=me)
    assert client.get(f"{BASE}/nutrition-plans", headers=both).json()["total"] == 2
    # an athlete user who is not linked yet sees nothing, never someone else's rows
    _, unlinked = org.user(ATHLETE)
    assert client.get(f"{BASE}/injuries", headers=unlinked).json() == {"items": [], "total": 0}


def test_permissions_are_checked(client, org):
    _, coach = org.user(COACH)
    _, nutritionist = org.user(NUTRITIONIST)
    assert client.get(f"{BASE}/nutrition-plans", headers=coach).status_code == 200
    body = {"athlete_id": ATHLETE_A, "title": "x", "goal": "recovery", "start_date": "2026-10-10", "status": "draft"}
    r = client.post(f"{BASE}/nutrition-plans", json=body, headers=coach)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    assert client.post(f"{BASE}/injuries", json={}, headers=nutritionist).status_code == 403
    assert client.get(f"{BASE}/injuries").status_code == 401
