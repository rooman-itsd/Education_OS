"""The HTTP surface against contracts/openapi.yaml: catalogue, athletes, results, assessments, benchmarks, history,
comparison, clearance and the squad summary, with the events and audit entries each change writes."""

from conftest import ATHLETE, BASE, COACH, MEDICAL, VIEWER, outbox
from eos_athlete_performance.application import service
from eos_athlete_performance.infrastructure.models import AuditEntry
from eos_core.db import SessionLocal
from sqlalchemy import select


def _audit(organisation_id: str) -> list[AuditEntry]:
    with SessionLocal() as db:
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        return list(db.scalars(q.order_by(AuditEntry.occurred_at)))


# ---------------------------------------------------------------- catalogue


def test_catalogue_create_list_get_update(client, org):
    d = org.discipline()
    assert d["organisation_id"] == org.id and d["active"] is True and "description" not in d
    m = org.metric(discipline_id=d["id"])
    t = org.post("/fitness-tests", {"name": "Pre-season", "metric_ids": [m["id"]]})
    assert client.get(f"{BASE}/disciplines", headers=org.admin).json()["total"] == 1
    assert client.get(f"{BASE}/metrics?discipline_id={d['id']}", headers=org.admin).json()["items"][0]["id"] == m["id"]
    assert client.get(f"{BASE}/fitness-tests/{t['id']}", headers=org.admin).json()["metric_ids"] == [m["id"]]

    r = client.patch(f"{BASE}/disciplines/{d['id']}", json={"active": False}, headers=org.admin)
    assert r.status_code == 200 and r.json()["active"] is False
    assert client.get(f"{BASE}/disciplines?active=true", headers=org.admin).json()["total"] == 0
    r = client.patch(f"{BASE}/metrics/{m['id']}", json={"unit": "sec"}, headers=org.admin)
    assert r.json()["unit"] == "sec"


def test_catalogue_refusals(client, org):
    d = org.discipline()
    dup = client.post(f"{BASE}/disciplines", json={"name": d["name"], "category": "team"}, headers=org.admin)
    assert dup.status_code == 400 and dup.json()["detail"]["code"] == "duplicate_name"
    bad = client.post(
        f"{BASE}/metrics",
        json={
            "name": "x",
            "unit": "s",
            "direction": "lower_is_better",
            "discipline_id": "99999999-9999-9999-9999-999999999999",
        },
        headers=org.admin,
    )
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "unknown_discipline"
    empty = client.post(f"{BASE}/fitness-tests", json={"name": "t", "metric_ids": []}, headers=org.admin)
    assert empty.json()["detail"]["code"] == "no_metrics"
    null = client.patch(f"{BASE}/disciplines/{d['id']}", json={"name": None}, headers=org.admin)
    assert null.status_code == 422
    assert client.get(f"{BASE}/metrics/unknown", headers=org.admin).status_code == 404


def test_permissions_are_checked(client, org):
    _, viewer = org.user(VIEWER)
    _, medical = org.user(MEDICAL)
    assert client.get(f"{BASE}/disciplines", headers=viewer).status_code == 200
    r = client.post(f"{BASE}/disciplines", json={"name": "x", "category": "team"}, headers=viewer)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    assert client.get(f"{BASE}/results", headers=viewer).status_code == 403
    assert client.get(f"{BASE}/reports/squad-summary", headers=medical).status_code == 403
    assert client.get(f"{BASE}/disciplines").status_code == 401


# ---------------------------------------------------------------- athletes


def test_athlete_profile_lifecycle_publishes_events(client, org):
    sprints, jumps = org.discipline(), org.discipline("Athletics (jumps)")
    coach_id, _ = org.user(COACH)
    user_id = "11111111-1111-1111-1111-111111111111"
    a = org.athlete(sprints["id"], user_id=user_id, coach_id=coach_id, discipline_ids=[jumps["id"]], gender="female")
    assert a["discipline_ids"] == [sprints["id"], jumps["id"]]
    [registered] = outbox(org.id, "athlete-performance.athlete.registered")
    assert registered.payload == {
        "organisation_id": org.id,
        "athlete_id": a["id"],
        "user_id": user_id,
        "primary_discipline_id": sprints["id"],
        "coach_id": coach_id,
    }

    r = client.patch(f"{BASE}/athletes/{a['id']}", json={"squad": "Senior", "full_name": "Asha R."}, headers=org.admin)
    assert r.status_code == 200 and r.json()["squad"] == "Senior"
    [updated] = outbox(org.id, "athlete-performance.athlete.updated")
    assert updated.payload["changed_fields"] == ["squad"] and updated.payload["status"] == "active"
    # a name-only change is audited but publishes nothing
    client.patch(f"{BASE}/athletes/{a['id']}", json={"full_name": "Asha Rao"}, headers=org.admin)
    assert len(outbox(org.id, "athlete-performance.athlete.updated")) == 1
    entries = [e for e in _audit(org.id) if e.entity_type == "athlete"]
    assert [e.action for e in entries] == ["athlete.created", "athlete.updated", "athlete.updated"]
    assert entries[1].after == {"squad": "Senior"}  # names are not copied into the audit trail
    assert "full_name" in entries[1].summary

    # changing the primary discipline keeps the others
    r = client.patch(f"{BASE}/athletes/{a['id']}", json={"primary_discipline_id": jumps["id"]}, headers=org.admin)
    assert r.json()["discipline_ids"] == [jumps["id"], sprints["id"]]


def test_athlete_filters_and_refusals(client, org):
    sprints, jumps = org.discipline(), org.discipline("Athletics (jumps)")
    coach_id, _ = org.user(COACH)
    org.athlete(sprints["id"], "Asha Rao", coach_id=coach_id, squad="Senior")
    org.athlete(jumps["id"], "Ben Okafor", discipline_ids=[sprints["id"]])
    org.athlete(jumps["id"], "Chen Li", status="alumni")

    def names(query: str) -> list[str]:
        return [a["full_name"] for a in client.get(f"{BASE}/athletes?{query}", headers=org.admin).json()["items"]]

    assert names("") == ["Asha Rao", "Ben Okafor", "Chen Li"]
    assert names(f"discipline_id={sprints['id']}") == ["Asha Rao", "Ben Okafor"]
    assert names(f"coach_id={coach_id}") == ["Asha Rao"]
    assert names("status=alumni") == ["Chen Li"]
    assert names("q=oka") == ["Ben Okafor"]
    assert names("limit=1&offset=1") == ["Ben Okafor"]

    r = client.post(
        f"{BASE}/athletes",
        json={
            "full_name": "x",
            "primary_discipline_id": sprints["id"],
            "status": "active",
            "date_of_birth": "2030-01-01",
        },
        headers=org.admin,
    )
    assert r.status_code == 400 and r.json()["detail"]["code"] == "in_future"
    r = client.post(
        f"{BASE}/athletes",
        json={"full_name": "x", "primary_discipline_id": "99999999-9999-9999-9999-999999999999", "status": "active"},
        headers=org.admin,
    )
    assert r.json()["detail"]["code"] == "unknown_discipline"
    user = "22222222-2222-2222-2222-222222222222"
    org.athlete(sprints["id"], "Dev", user_id=user)
    r = client.post(
        f"{BASE}/athletes",
        json={"full_name": "y", "primary_discipline_id": sprints["id"], "status": "active", "user_id": user},
        headers=org.admin,
    )
    assert r.json()["detail"]["code"] == "duplicate_user"


# ---------------------------------------------------------------- results


def test_results_record_list_correct(client, org):
    d = org.discipline()
    m = org.metric(discipline_id=d["id"])
    a = org.athlete(d["id"])
    coach_id, coach = org.user(COACH)
    r1 = org.result(a["id"], m["id"], 12.1, "2026-10-01T08:00:00+00:00", context="trial")
    r2 = org.post(
        "/results",
        {
            "athlete_id": a["id"],
            "metric_id": m["id"],
            "value": 11.9,
            "recorded_at": "2026-10-20T08:00:00+05:30",
            "context": "competition",
        },
        headers=coach,
    )
    assert r2["recorded_by"] == coach_id and r2["recorded_at"] == "2026-10-20T02:30:00+00:00"
    [ev, _] = outbox(org.id, "athlete-performance.result.recorded")
    assert (
        ev.payload["value"] == 12.1
        and ev.payload["context"] == "trial"
        and ev.payload["recorded_at"].startswith("2026-10-01")
    )

    listed = client.get(f"{BASE}/results?athlete_id={a['id']}", headers=coach).json()
    assert [x["id"] for x in listed["items"]] == [r2["id"], r1["id"]] and listed["total"] == 2
    assert client.get(f"{BASE}/results?context=trial", headers=coach).json()["total"] == 1
    assert client.get(f"{BASE}/results?from=2026-10-02&to=2026-10-20", headers=coach).json()["total"] == 1
    assert client.get(f"{BASE}/results?from=2026-10-21&to=2026-10-20", headers=coach).status_code == 400

    fixed = client.patch(f"{BASE}/results/{r1['id']}", json={"value": 12.0}, headers=coach)
    assert fixed.status_code == 200 and fixed.json()["value"] == 12.0
    [corr] = [e for e in _audit(org.id) if e.action == "result.corrected"]
    assert corr.before == {"value": 12.1} and corr.after == {"value": 12.0}

    future = client.post(
        f"{BASE}/results",
        json={
            "athlete_id": a["id"],
            "metric_id": m["id"],
            "value": 1,
            "recorded_at": "2026-11-01T00:00:00Z",
            "context": "training",
        },
        headers=coach,
    )
    assert future.status_code == 400 and future.json()["detail"]["code"] == "in_future"
    naive = client.post(
        f"{BASE}/results",
        json={
            "athlete_id": a["id"],
            "metric_id": m["id"],
            "value": 1,
            "recorded_at": "2026-10-01T00:00:00",
            "context": "training",
        },
        headers=coach,
    )
    assert naive.status_code == 422  # a time without its offset is ambiguous


# ---------------------------------------------------------------- assessments


def test_assessments(client, org):
    d = org.discipline()
    jump = org.metric("Vertical jump", "cm", "higher_is_better")
    fat = org.metric("Body fat", "%", "lower_is_better")
    sprint = org.metric()
    test = org.post("/fitness-tests", {"name": "Pre-season", "metric_ids": [jump["id"], fat["id"]]})
    a = org.athlete(d["id"])
    medic_id, medic = org.user(MEDICAL)
    body = {
        "athlete_id": a["id"],
        "fitness_test_id": test["id"],
        "assessed_on": "2026-10-28",
        "measurements": [{"metric_id": jump["id"], "value": 52}, {"metric_id": fat["id"], "value": 11.5}],
    }
    rec = org.post("/assessments", body, headers=medic)
    assert rec["assessor_id"] == medic_id and len(rec["measurements"]) == 2
    [ev] = outbox(org.id, "athlete-performance.assessment.recorded")
    assert ev.payload == {
        "organisation_id": org.id,
        "assessment_id": rec["id"],
        "athlete_id": a["id"],
        "fitness_test_id": test["id"],
        "assessed_on": "2026-10-28",
    }
    assert client.get(f"{BASE}/assessments?athlete_id={a['id']}", headers=medic).json()["total"] == 1
    assert client.get(f"{BASE}/assessments/{rec['id']}", headers=medic).json()["id"] == rec["id"]

    wrong = {**body, "measurements": [{"metric_id": sprint["id"], "value": 11}]}
    r = client.post(f"{BASE}/assessments", json=wrong, headers=medic)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "metric_not_in_test"
    r = client.post(
        f"{BASE}/assessments", json={**body, "fitness_test_id": "99999999-9999-9999-9999-999999999999"}, headers=medic
    )
    assert r.json()["detail"]["code"] == "unknown_fitness_test"


# ---------------------------------------------------------------- benchmarks, history, comparison


def _sprinter(org):
    d = org.discipline()
    sprint = org.metric()
    jump = org.metric("Vertical jump", "cm", "higher_is_better")
    a = org.athlete(d["id"], gender="female")
    return d, sprint, jump, a


def test_benchmarks_history_and_comparison(client, org):
    d, sprint, jump, a = _sprinter(org)
    general = org.post("/benchmarks", {"metric_id": sprint["id"], "level": "state", "target_value": 12.0})
    specific = org.post(
        "/benchmarks",
        {
            "metric_id": sprint["id"],
            "discipline_id": d["id"],
            "level": "state",
            "gender": "female",
            "target_value": 11.8,
        },
    )
    org.post("/benchmarks", {"metric_id": jump["id"], "level": "state", "target_value": 55})
    dup = client.post(
        f"{BASE}/benchmarks", json={"metric_id": sprint["id"], "level": "state", "target_value": 1}, headers=org.admin
    )
    assert dup.status_code == 400 and dup.json()["detail"]["code"] == "duplicate_benchmark"
    assert len(outbox(org.id, "athlete-performance.benchmark.set")) == 3

    org.result(a["id"], sprint["id"], 12.2, "2026-10-01T08:00:00+00:00")
    org.result(a["id"], sprint["id"], 11.7, "2026-10-20T08:00:00+00:00")
    test = org.post("/fitness-tests", {"name": "Speed", "metric_ids": [sprint["id"]]})
    org.post(
        "/assessments",
        {
            "athlete_id": a["id"],
            "fitness_test_id": test["id"],
            "assessed_on": "2026-10-10",
            "measurements": [{"metric_id": sprint["id"], "value": 12.0}],
        },
    )

    h = client.get(f"{BASE}/athletes/{a['id']}/history?metric_id={sprint['id']}", headers=org.admin).json()
    assert [(p["value"], p["source"]) for p in h["points"]] == [
        (12.2, "result"),
        (12.0, "assessment"),
        (11.7, "result"),
    ]
    assert h["points"][1]["at"] == "2026-10-10T00:00:00+00:00"
    assert h["benchmark"]["id"] == specific["id"]
    h = client.get(
        f"{BASE}/athletes/{a['id']}/history?metric_id={sprint['id']}&from=2026-10-05&to=2026-10-10", headers=org.admin
    ).json()
    assert [p["value"] for p in h["points"]] == [12.0]
    assert client.get(f"{BASE}/athletes/{a['id']}/history", headers=org.admin).status_code == 422  # metric_id required

    c = client.get(f"{BASE}/athletes/{a['id']}/benchmark-comparison", headers=org.admin).json()["items"]
    by_metric = {row["metric_id"]: row for row in c}
    assert by_metric[sprint["id"]]["benchmark_id"] == specific["id"]
    assert by_metric[sprint["id"]]["status"] == "meets" and round(by_metric[sprint["id"]]["gap"], 2) == 0.1
    assert by_metric[jump["id"]] == {
        "metric_id": jump["id"],
        "benchmark_id": by_metric[jump["id"]]["benchmark_id"],
        "target_value": 55,
        "status": "no_result",
    }
    assert client.get(f"{BASE}/athletes/{a['id']}/benchmark-comparison?level=national", headers=org.admin).json() == {
        "items": []
    }

    r = client.patch(f"{BASE}/benchmarks/{general['id']}", json={"target_value": 11.5}, headers=org.admin)
    assert r.json()["target_value"] == 11.5
    assert len(outbox(org.id, "athlete-performance.benchmark.set")) == 4
    client.patch(f"{BASE}/benchmarks/{general['id']}", json={"source": "Federation 2026"}, headers=org.admin)
    assert len(outbox(org.id, "athlete-performance.benchmark.set")) == 4


# ---------------------------------------------------------------- clearance


def test_clearance(client, org):
    d = org.discipline()
    a = org.athlete(d["id"])
    _, coach = org.user(COACH)
    medic_id, medic = org.user(MEDICAL)
    assert client.get(f"{BASE}/athletes/{a['id']}/clearance", headers=coach).json() == {
        "athlete_id": a["id"],
        "status": "not_cleared",
    }
    assert (
        client.put(f"{BASE}/athletes/{a['id']}/clearance", json={"status": "cleared"}, headers=coach).status_code == 403
    )

    body = {"status": "restricted", "valid_until": "2026-12-31", "restrictions": "No sprint starts"}
    r = client.put(f"{BASE}/athletes/{a['id']}/clearance", json=body, headers=medic)
    assert r.status_code == 200
    assert r.json() == {
        "athlete_id": a["id"],
        "status": "restricted",
        "valid_until": "2026-12-31",
        "restrictions": "No sprint starts",
        "set_by": medic_id,
        "set_at": "2026-10-29T09:00:00+00:00",
    }
    [ev] = outbox(org.id, "athlete-performance.clearance.changed")
    assert ev.payload == {
        "organisation_id": org.id,
        "athlete_id": a["id"],
        "status": "restricted",
        "valid_until": "2026-12-31",
    }
    [entry] = [e for e in _audit(org.id) if e.entity_type == "clearance"]
    assert "restrictions" not in entry.after  # clinical free text stays out of the audit trail

    # the same values again change nothing; only the restrictions text changing publishes nothing
    client.put(f"{BASE}/athletes/{a['id']}/clearance", json=body, headers=medic)
    client.put(f"{BASE}/athletes/{a['id']}/clearance", json={**body, "restrictions": "Light work only"}, headers=medic)
    assert len(outbox(org.id, "athlete-performance.clearance.changed")) == 1
    client.put(f"{BASE}/athletes/{a['id']}/clearance", json={"status": "cleared"}, headers=medic)
    assert len(outbox(org.id, "athlete-performance.clearance.changed")) == 2

    past = client.put(
        f"{BASE}/athletes/{a['id']}/clearance", json={"status": "cleared", "valid_until": "2026-01-01"}, headers=medic
    )
    assert past.status_code == 400 and past.json()["detail"]["code"] == "in_past"
    assert client.put(f"{BASE}/athletes/nope/clearance", json={"status": "cleared"}, headers=medic).status_code == 404


# ---------------------------------------------------------------- squad summary


def test_squad_summary(client, org):
    d, sprint, jump, a = _sprinter(org)
    b = org.athlete(d["id"], "Ben Okafor", squad="Senior")
    org.athlete(d["id"], "Chen Li", status="alumni")
    org.result(a["id"], sprint["id"], 12.2, "2026-10-01T08:00:00+00:00")
    org.result(a["id"], sprint["id"], 11.9, "2026-10-20T08:00:00+00:00")
    org.result(a["id"], jump["id"], 50, "2026-10-20T08:00:00+00:00")
    org.result(b["id"], jump["id"], 50, "2026-10-01T08:00:00+00:00")
    org.result(b["id"], jump["id"], 45, "2026-10-20T08:00:00+00:00")
    _, medic = org.user(MEDICAL)
    client.put(f"{BASE}/athletes/{a['id']}/clearance", json={"status": "cleared"}, headers=medic)
    _, viewer = org.user(VIEWER)

    rows = client.get(f"{BASE}/reports/squad-summary", headers=viewer).json()["items"]
    assert [r["full_name"] for r in rows] == ["Asha Rao", "Ben Okafor"]  # active athletes only
    asha, ben = rows
    assert asha["clearance"] == "cleared" and ben["clearance"] == "not_cleared"
    assert {m["metric_id"]: m["trend"] for m in asha["metrics"]} == {sprint["id"]: "improving", jump["id"]: "no_data"}
    assert ben["metrics"] == [{"metric_id": jump["id"], "latest_value": 45, "trend": "declining"}]
    only = client.get(f"{BASE}/reports/squad-summary?squad=Senior", headers=viewer).json()["items"]
    assert [r["full_name"] for r in only] == ["Ben Okafor"]


# ---------------------------------------------------------------- athletes see only their own data


def test_an_athlete_sees_only_their_own_data(client, org):
    d, sprint, _, mine = _sprinter(org)
    me = "33333333-3333-3333-3333-333333333333"
    client.patch(f"{BASE}/athletes/{mine['id']}", json={"user_id": me}, headers=org.admin)
    theirs = org.athlete(d["id"], "Ben Okafor")
    my_result = org.result(mine["id"], sprint["id"], 12.0)
    their_result = org.result(theirs["id"], sprint["id"], 11.0)
    _, athlete = org.user(ATHLETE, user_id=me)
    _, profile_athlete = org.user("athlete", user_id=me)  # the sports-college profile role behaves the same

    for headers in (athlete, profile_athlete):
        assert [a["id"] for a in client.get(f"{BASE}/athletes", headers=headers).json()["items"]] == [mine["id"]]
        assert client.get(f"{BASE}/athletes/{theirs['id']}", headers=headers).status_code == 404
        assert [r["id"] for r in client.get(f"{BASE}/results", headers=headers).json()["items"]] == [my_result["id"]]
        assert client.get(f"{BASE}/results?athlete_id={theirs['id']}", headers=headers).json()["total"] == 0
        assert client.get(f"{BASE}/results/{their_result['id']}", headers=headers).status_code == 404
        assert client.get(f"{BASE}/athletes/{theirs['id']}/clearance", headers=headers).status_code == 404
        assert client.get(f"{BASE}/athletes/{mine['id']}/clearance", headers=headers).status_code == 200
        assert (
            client.get(f"{BASE}/athletes/{theirs['id']}/history?metric_id={sprint['id']}", headers=headers).status_code
            == 404
        )

    # an athlete who is also a coach is not limited to their own profile
    _, both = org.user("athlete", "coach", user_id=me)
    assert client.get(f"{BASE}/athletes", headers=both).json()["total"] == 2
    # an athlete user with no profile sees nothing
    _, stranger = org.user(ATHLETE)
    assert client.get(f"{BASE}/results", headers=stranger).json() == {"items": [], "total": 0}


# ---------------------------------------------------------------- review fixes (#352)


def test_an_expired_clearance_reads_as_not_cleared(client, org, monkeypatch):
    from datetime import UTC, datetime

    d = org.discipline()
    a = org.athlete(d["id"])
    medic_id, medic = org.user(MEDICAL)
    _, viewer = org.user(VIEWER)
    client.put(
        f"{BASE}/athletes/{a['id']}/clearance", json={"status": "cleared", "valid_until": "2026-10-30"}, headers=medic
    )
    assert client.get(f"{BASE}/athletes/{a['id']}/clearance", headers=medic).json()["status"] == "cleared"

    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 10, 31, 9, 0, tzinfo=UTC))  # valid_until has passed
    lapsed = client.get(f"{BASE}/athletes/{a['id']}/clearance", headers=medic).json()
    assert lapsed["status"] == "not_cleared"
    assert lapsed["valid_until"] == "2026-10-30" and lapsed["set_by"] == medic_id  # when it ran out stays visible
    [row] = client.get(f"{BASE}/reports/squad-summary", headers=viewer).json()["items"]
    assert row["clearance"] == "not_cleared"


def test_ids_must_be_uuids(client, org):
    d = org.discipline()
    m = org.metric()
    a = org.athlete(d["id"])
    r = org.result(a["id"], m["id"], 12.0)
    for path, body in (
        (f"/results/{r['id']}", {"athlete_id": ""}),
        (f"/results/{r['id']}", {"metric_id": "not-a-uuid"}),
        (f"/athletes/{a['id']}", {"primary_discipline_id": ""}),
        (f"/athletes/{a['id']}", {"discipline_ids": [""]}),
        (f"/metrics/{m['id']}", {"discipline_id": ""}),
    ):
        assert client.patch(f"{BASE}{path}", json=body, headers=org.admin).status_code == 422, (path, body)
    bench = {"metric_id": "", "level": "state", "target_value": 1}
    assert client.post(f"{BASE}/benchmarks", json=bench, headers=org.admin).status_code == 422
    test = {"name": "t", "metric_ids": [m["id"], ""]}
    assert client.post(f"{BASE}/fitness-tests", json=test, headers=org.admin).status_code == 422
    # the result is untouched
    assert client.get(f"{BASE}/results/{r['id']}", headers=org.admin).json()["athlete_id"] == a["id"]


def test_same_day_assessments_keep_the_order_they_were_recorded(client, org, monkeypatch):
    from datetime import UTC, datetime

    d = org.discipline()
    m = org.metric()
    a = org.athlete(d["id"])
    t = org.post("/fitness-tests", {"name": "Speed", "metric_ids": [m["id"]]})
    ids = []
    for minute, value in ((0, 12.4), (5, 12.1), (10, 11.8)):
        monkeypatch.setattr(service, "clock", lambda minute=minute: datetime(2026, 10, 29, 9, minute, tzinfo=UTC))
        body = {
            "athlete_id": a["id"],
            "fitness_test_id": t["id"],
            "assessed_on": "2026-10-29",
            "measurements": [{"metric_id": m["id"], "value": value}],
        }
        ids.append(org.post("/assessments", body)["id"])
    h = client.get(f"{BASE}/athletes/{a['id']}/history?metric_id={m['id']}", headers=org.admin).json()
    assert [p["value"] for p in h["points"]] == [12.4, 12.1, 11.8]
    listed = client.get(f"{BASE}/assessments?athlete_id={a['id']}", headers=org.admin).json()["items"]
    assert [x["id"] for x in listed] == ids[::-1]  # newest first


def test_a_date_one_day_ahead_of_utc_is_accepted(client, org):
    d = org.discipline()
    m = org.metric()
    a = org.athlete(d["id"])
    t = org.post("/fitness-tests", {"name": "Speed", "metric_ids": [m["id"]]})
    body = {"athlete_id": a["id"], "fitness_test_id": t["id"], "measurements": [{"metric_id": m["id"], "value": 12}]}
    # the clock says 29 Oct 09:00 UTC; 30 Oct is already "today" east of UTC near midnight, 31 Oct is not
    assert (
        client.post(f"{BASE}/assessments", json={**body, "assessed_on": "2026-10-30"}, headers=org.admin).status_code
        == 201
    )
    late = client.post(f"{BASE}/assessments", json={**body, "assessed_on": "2026-10-31"}, headers=org.admin)
    assert late.status_code == 400 and late.json()["detail"]["code"] == "in_future"
