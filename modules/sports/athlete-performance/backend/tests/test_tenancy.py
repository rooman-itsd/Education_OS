"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE, MEDICAL
from eos_testing import assert_no_cross_tenant_leak


def seed(org) -> dict:
    d = org.discipline()
    m = org.metric()
    t = org.post("/fitness-tests", {"name": "Speed", "metric_ids": [m["id"]]})
    a = org.athlete(d["id"])
    r = org.result(a["id"], m["id"], 12.0)
    s = org.post(
        "/assessments",
        {
            "athlete_id": a["id"],
            "fitness_test_id": t["id"],
            "assessed_on": "2026-10-28",
            "measurements": [{"metric_id": m["id"], "value": 12}],
        },
    )
    b = org.post("/benchmarks", {"metric_id": m["id"], "level": "state", "target_value": 12.5})
    _, medic = org.user(MEDICAL)
    org.client.put(f"{BASE}/athletes/{a['id']}/clearance", json={"status": "cleared"}, headers=medic)
    return {"discipline": d, "metric": m, "test": t, "athlete": a, "result": r, "assessment": s, "benchmark": b}


def test_no_cross_tenant_leak(client, org, other_org):
    a, b = seed(org), seed(other_org)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/disciplines", "/metrics", "/fitness-tests", "/athletes", "/results", "/assessments", "/benchmarks"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(org.admin), token(other_org.admin))

    as_b = other_org.admin
    for path in (
        f"/disciplines/{a['discipline']['id']}",
        f"/metrics/{a['metric']['id']}",
        f"/fitness-tests/{a['test']['id']}",
        f"/athletes/{a['athlete']['id']}",
        f"/results/{a['result']['id']}",
        f"/assessments/{a['assessment']['id']}",
        f"/benchmarks/{a['benchmark']['id']}",
        f"/athletes/{a['athlete']['id']}/history?metric_id={a['metric']['id']}",
        f"/athletes/{a['athlete']['id']}/benchmark-comparison",
        f"/athletes/{a['athlete']['id']}/clearance",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    assert client.patch(f"{BASE}/athletes/{a['athlete']['id']}", json={"squad": "x"}, headers=as_b).status_code == 404
    assert client.patch(f"{BASE}/results/{a['result']['id']}", json={"value": 1}, headers=as_b).status_code == 404
    assert (
        client.put(
            f"{BASE}/athletes/{a['athlete']['id']}/clearance", json={"status": "cleared"}, headers=as_b
        ).status_code
        == 404
    )

    # another organisation's ids are unknown here, so they cannot be referenced
    steal = {
        "athlete_id": a["athlete"]["id"],
        "metric_id": b["metric"]["id"],
        "value": 1,
        "recorded_at": "2026-10-20T00:00:00Z",
        "context": "trial",
    }
    r = client.post(f"{BASE}/results", json=steal, headers=as_b)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_athlete"
    # names are unique per organisation, not globally
    assert a["discipline"]["name"] == b["discipline"]["name"]
    summary = client.get(f"{BASE}/reports/squad-summary", headers=as_b).json()["items"]
    assert [row["athlete_id"] for row in summary] == [b["athlete"]["id"]]
