"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from datetime import UTC, datetime

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak

A1 = "11111111-1111-1111-1111-111111111111"


def seed(org) -> dict:
    t = org.tournament()
    e = org.entry(t["id"], [A1])
    f = org.fixture(t["id"], [e["id"]])
    o = org.post(f"/tournaments/{t['id']}/officials", {"name": "R. Iyer", "official_role": "referee"})
    r = org.client.put(f"{BASE}/tournaments/{t['id']}/logistics", json={"travel_mode": "bus"}, headers=org.admin)
    assert r.status_code == 200
    return {"tournament": t, "entry": e, "fixture": f, "official": o}


def test_no_cross_tenant_leak(client, org, other_org, later):
    a, b = seed(org), seed(other_org)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    assert_no_cross_tenant_leak(client, f"{BASE}/tournaments", token(org.admin), token(other_org.admin))
    for name in ("entries", "fixtures", "officials"):
        rows = client.get(f"{BASE}/tournaments/{a['tournament']['id']}/{name}", headers=org.admin).json()["items"]
        assert rows and {r["organisation_id"] for r in rows} == {org.id}

    as_b = other_org.admin
    t = a["tournament"]["id"]
    for path in (
        f"/tournaments/{t}",
        f"/tournaments/{t}/entries",
        f"/tournaments/{t}/fixtures",
        f"/tournaments/{t}/fixtures/{a['fixture']['id']}",
        f"/tournaments/{t}/fixtures/{a['fixture']['id']}/result",
        f"/tournaments/{t}/officials",
        f"/tournaments/{t}/logistics",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    assert client.patch(f"{BASE}/tournaments/{t}", json={"venue": "x"}, headers=as_b).status_code == 404
    assert client.post(f"{BASE}/tournaments/{t}/cancel", json={"reason": "x"}, headers=as_b).status_code == 404
    assert client.post(f"{BASE}/tournaments/{t}/publish", headers=as_b).status_code == 404
    body = {"category": "x", "athlete_ids": [A1], "status": "pending"}
    assert client.post(f"{BASE}/tournaments/{t}/entries", json=body, headers=as_b).status_code == 404
    entry_url = f"{BASE}/tournaments/{t}/entries/{a['entry']['id']}"
    assert client.patch(entry_url, json={"status": "withdrawn"}, headers=as_b).status_code == 404
    assert client.delete(f"{BASE}/tournaments/{t}/officials/{a['official']['id']}", headers=as_b).status_code == 404
    assert client.put(f"{BASE}/tournaments/{t}/logistics", json={}, headers=as_b).status_code == 404

    # B's own tournament cannot reach A's entries or fixtures by id
    tb = b["tournament"]["id"]
    later(datetime(2026, 11, 10, 6, 0, tzinfo=UTC))
    steal = {
        "round": "Final",
        "entry_ids": [a["entry"]["id"]],
        "scheduled_at": "2026-11-10T04:30:00Z",
        "status": "scheduled",
    }
    r = client.post(f"{BASE}/tournaments/{tb}/fixtures", json=steal, headers=as_b)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_entry"
    r = client.put(
        f"{BASE}/tournaments/{tb}/fixtures/{a['fixture']['id']}/result",
        json={"placings": [{"entry_id": a["entry"]["id"]}]},
        headers=as_b,
    )
    assert r.status_code == 404
    r = client.post(
        f"{BASE}/tournaments/{tb}/officials",
        json={"name": "X", "official_role": "judge", "fixture_id": a["fixture"]["id"]},
        headers=as_b,
    )
    assert r.json()["detail"]["code"] == "unknown_fixture"

    cal = client.get(f"{BASE}/calendar?from=2026-11-01&to=2026-11-30", headers=as_b).json()["items"]
    assert cal and {i["tournament_id"] for i in cal} == {tb}
