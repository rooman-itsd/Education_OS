"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_core.db import new_id
from eos_testing import assert_no_cross_tenant_leak

ATHLETE_A = "11111111-1111-1111-1111-111111111111"


def seed(org) -> dict:
    p = org.plan(ATHLETE_A)
    org.post(f"/nutrition-plans/{p['id']}/reviews", {"reviewed_on": "2026-10-28", "outcome": "continue"})
    h = org.post(
        "/health-records",
        {"athlete_id": ATHLETE_A, "record_type": "allergy", "title": "x", "recorded_on": "2026-10-01"},
    )
    i = org.injury(ATHLETE_A)
    a = org.appointment(ATHLETE_A, new_id(), injury_id=i["id"])
    return {"plan": p, "health": h, "injury": i, "appointment": a}


def test_no_cross_tenant_leak(client, org, other_org):
    a, b = seed(org), seed(other_org)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/nutrition-plans", "/health-records", "/injuries", "/appointments"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(org.admin), token(other_org.admin))

    as_b = other_org.admin
    for path in (
        f"/nutrition-plans/{a['plan']['id']}",
        f"/nutrition-plans/{a['plan']['id']}/reviews",
        f"/health-records/{a['health']['id']}",
        f"/injuries/{a['injury']['id']}",
        f"/appointments/{a['appointment']['id']}",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    for path, body in (
        (f"/nutrition-plans/{a['plan']['id']}", {"title": "x"}),
        (f"/health-records/{a['health']['id']}", {"title": "x"}),
        (f"/injuries/{a['injury']['id']}", {"status": "resolved"}),
        (f"/appointments/{a['appointment']['id']}", {"status": "cancelled"}),
    ):
        assert client.patch(f"{BASE}{path}", json=body, headers=as_b).status_code == 404, path
    review = client.post(
        f"{BASE}/nutrition-plans/{a['plan']['id']}/reviews",
        json={"reviewed_on": "2026-10-28", "outcome": "end"},
        headers=as_b,
    )
    assert review.status_code == 404

    # another organisation's injury cannot be linked to an appointment here
    steal = {
        "athlete_id": ATHLETE_A,
        "practitioner_id": new_id(),
        "appointment_type": "physiotherapy",
        "injury_id": a["injury"]["id"],
        "scheduled_at": "2026-10-30T10:00:00Z",
        "status": "scheduled",
    }
    r = client.post(f"{BASE}/appointments", json=steal, headers=as_b)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_injury"
    assert b["plan"]["organisation_id"] == other_org.id
