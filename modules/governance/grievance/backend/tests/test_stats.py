"""Open and overdue counts behind the two widgets (docs/prd.md "Dashboard widgets", "Deadlines")."""

from datetime import datetime, timedelta


def test_empty_counts(campus):
    c = campus
    r = c.ok(c.get("/stats/open", c.viewer))
    assert r == {
        "total_open": 0,
        "overdue": 0,
        "tracks": [
            {"track": t, "open": 0, "overdue": 0} for t in ("student_grievance", "ragging", "sexual_harassment")
        ],
    }
    r = c.ok(c.get("/stats/open-by-committee", c.coordinator))
    assert r["total_open"] == 0 and len(r["committees"]) == 4
    assert all(x["open"] == 0 and x["by_status"] == [] for x in r["committees"])


def test_open_counts_by_committee_status_and_track(campus, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    a, b = c.file(), c.file()
    c.move(b["id"], "acknowledged")
    done = c.file()
    c.ok(c.post(f"/me/grievances/{done['id']}/withdraw", None, c.complainant))  # final: not counted
    ragging = c.file("ragging")
    appealed = c.file()
    c.decide(appealed["id"])
    c.ok(c.post(f"/me/grievances/{appealed['id']}/appeal", {"reason": "I disagree with the findings."}, c.complainant))
    assert a["status"] == "submitted"
    by_committee = {x["kind"]: x for x in c.ok(c.get("/stats/open-by-committee", c.coordinator))["committees"]}
    assert by_committee["sgrc"]["open"] == 2
    assert by_committee["sgrc"]["by_status"] == [
        {"status": "submitted", "count": 1},
        {"status": "acknowledged", "count": 1},
    ]
    assert by_committee["ombudsperson"]["open"] == 1  # the appeal counts where it is heard
    assert by_committee["ombudsperson"]["by_status"] == [{"status": "appealed", "count": 1}]
    assert by_committee["anti_ragging"]["open"] == 1
    total = c.ok(c.get("/stats/open-by-committee", c.coordinator))["total_open"]
    assert total == 4
    by_track = {x["track"]: x for x in c.ok(c.get("/stats/open", c.viewer))["tracks"]}
    assert (by_track["student_grievance"]["open"], by_track["ragging"]["open"]) == (3, 1)
    assert ragging["status"] == "submitted"


def test_overdue_follows_the_per_track_settings(campus, monkeypatch, clock):
    c = campus
    monkeypatch.setenv("GRIEVANCE_STUDENT_GRIEVANCE_ACKNOWLEDGE_DAYS", "2")
    monkeypatch.setenv("GRIEVANCE_STUDENT_GRIEVANCE_DECIDE_DAYS", "10")
    monkeypatch.setenv("GRIEVANCE_RAGGING_ACKNOWLEDGE_DAYS", "1")  # no decide-by for ragging
    case, ragging = c.file(), c.file("ragging")
    detail = c.ok(c.get(f"/grievances/{case['id']}", c.member()))
    filed = datetime.fromisoformat(case["filed_at"])
    assert detail["due_at"] == (filed + timedelta(days=2)).isoformat() and detail["overdue"] is False
    clock.advance(days=3)
    assert c.ok(c.get(f"/grievances/{case['id']}", c.member()))["overdue"] is True
    assert c.ok(c.get(f"/grievances/{ragging['id']}", c.member("anti_ragging")))["overdue"] is True
    stats = c.ok(c.get("/stats/open", c.viewer))
    assert stats["overdue"] == 2
    by_committee = {x["kind"]: x for x in c.ok(c.get("/stats/open-by-committee", c.coordinator))["committees"]}
    assert by_committee["sgrc"]["overdue"] == 1 and by_committee["anti_ragging"]["overdue"] == 1
    # acknowledging moves the deadline to the decide-by date
    c.move(case["id"], "acknowledged")
    detail = c.ok(c.get(f"/grievances/{case['id']}", c.member()))
    assert detail["due_at"] == (filed + timedelta(days=10)).isoformat() and detail["overdue"] is False
    c.move(ragging["id"], "acknowledged", "anti_ragging")
    ragging_now = c.ok(c.get(f"/grievances/{ragging['id']}", c.member("anti_ragging")))
    assert ragging_now["due_at"] is None and ragging_now["overdue"] is False  # no decide-by set
    clock.advance(days=8)
    assert c.ok(c.get(f"/grievances/{case['id']}", c.member()))["overdue"] is True
    assert c.ok(c.get("/stats/open", c.viewer))["overdue"] == 1


def test_without_settings_nothing_is_ever_overdue(campus, clock):
    c = campus
    case = c.file()
    clock.advance(days=4000)
    detail = c.ok(c.get(f"/grievances/{case['id']}", c.member()))
    assert detail["due_at"] is None and detail["overdue"] is False
    assert c.ok(c.get("/stats/open", c.viewer))["overdue"] == 0


def test_overdue_filter_and_paging_on_the_committee_list(campus, monkeypatch, clock):
    c = campus
    monkeypatch.setenv("GRIEVANCE_STUDENT_GRIEVANCE_ACKNOWLEDGE_DAYS", "2")
    old = [c.file()["id"] for _ in range(3)]
    clock.advance(days=5)
    new = [c.file()["id"] for _ in range(2)]
    late = c.ok(c.get("/grievances?overdue=true&limit=2", c.member()))
    assert [x["id"] for x in late["items"]] == [old[2], old[1]] and late["next_cursor"]
    rest = c.ok(c.get(f"/grievances?overdue=true&limit=2&cursor={late['next_cursor']}", c.member()))
    assert [x["id"] for x in rest["items"]] == [old[0]] and rest["next_cursor"] is None
    fresh = c.ok(c.get("/grievances?overdue=false", c.member()))
    assert [x["id"] for x in fresh["items"]] == [new[1], new[0]]
    assert len(c.ok(c.get("/grievances", c.member()))["items"]) == 5


def test_list_filters(campus):
    c = campus
    sgrc2 = c.ok(
        c.post(
            "/committees",
            {"name": "SGRC 2", "kind": "sgrc", "members": [{"person_id": c.members["sgrc"][0], "role": "member"}]},
        )
    )
    a = c.file(committee_id=c.committees["sgrc"]["id"])
    b = c.file(committee_id=sgrc2["id"])
    c.move(b["id"], "acknowledged")
    ids = lambda q: sorted(x["id"] for x in c.ok(c.get(f"/grievances{q}", c.member()))["items"])  # noqa: E731
    assert ids("") == sorted([a["id"], b["id"]])
    assert ids(f"?committee_id={sgrc2['id']}") == [b["id"]]
    assert ids("?status=acknowledged") == [b["id"]]
    assert ids("?status=submitted,acknowledged") == sorted([a["id"], b["id"]])
    assert ids("?track=ragging") == []
    assert ids("?track=student_grievance&status=submitted") == [a["id"]]
