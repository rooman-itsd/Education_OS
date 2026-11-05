"""The reports behind the staff widgets: upcoming drives (placement-career.drives) and the openings summary
(placement-career.openings-summary)."""

from pc_support import BASE, applied, code, company, day, drive, move, ok, opening

ZERO = dict.fromkeys(
    ("applied", "shortlisted", "in_process", "offered", "accepted", "declined", "rejected", "withdrawn"), 0
)


def test_upcoming_drives(client, org, clock):
    co = company(client, org)
    today = drive(client, org, co, scheduled_on=day(0), registration_closes_on=None)
    soon = drive(client, org, co, scheduled_on=day(30), registration_closes_on=None, venue=None)
    later = drive(client, org, co, scheduled_on=day(31), registration_closes_on=None)
    drive(client, org, co, scheduled_on=day(5), registration_closes_on=None, schedule=False)  # a draft is not upcoming
    o = opening(client, org, dr=today, applications_close_on=day(0))
    opening(client, org, dr=today, publish=False, applications_close_on=day(0))  # a draft opening is not counted
    a = applied(client, org, o)
    applied(client, org, o, who="student2")
    ok(move(client, org, a, "shortlisted"))
    report = ok(client.get(f"{BASE}/reports/drives-upcoming", headers=org.officer))
    assert report["next_30_days"] == 2
    assert [d["id"] for d in report["drives"]] == [today["id"], soon["id"], later["id"]]
    first = report["drives"][0]
    assert first == {
        "id": today["id"],
        "title": today["title"],
        "company": today["company"],
        "scheduled_on": day(0),
        "venue": "Main auditorium",
        "registration_closes_on": None,
        "openings_count": 1,
        "applications": {**ZERO, "applied": 1, "shortlisted": 1},
    }
    assert report["drives"][1]["applications"] == ZERO and report["drives"][1]["venue"] is None
    limited = ok(client.get(f"{BASE}/reports/drives-upcoming", params={"limit": 1}, headers=org.viewer))
    assert [d["id"] for d in limited["drives"]] == [today["id"]] and limited["next_30_days"] == 2
    clock.advance(days=1)  # today's drive has passed
    report = ok(client.get(f"{BASE}/reports/drives-upcoming", headers=org.coordinator))
    assert [d["id"] for d in report["drives"]] == [soon["id"], later["id"]] and report["next_30_days"] == 2
    for bad in (0, 51):
        assert (
            client.get(f"{BASE}/reports/drives-upcoming", params={"limit": bad}, headers=org.officer).status_code == 422
        )


def test_openings_summary(client, org):
    co = company(client, org, name="Zeta Corp")
    late = opening(client, org, co=co, applications_close_on=day(9))
    soon = opening(client, org, co=co, applications_close_on=day(2))
    opening(client, org, co=co, publish=False)
    closed = opening(client, org, co=co)
    cancelled = opening(client, org, co=co, publish=False)
    ok(client.post(f"{BASE}/openings/{cancelled['id']}/cancel", json={"reason": "x"}, headers=org.officer))
    a1 = applied(client, org, soon)
    a2 = applied(client, org, closed)
    applied(client, org, soon, who="student2")
    w = applied(client, org, late, who="student2")
    ok(client.post(f"{BASE}/me/applications/{w['id']}/withdraw", headers=org.student2))
    for application in (a1, a2):
        for step in ("shortlisted", "in_process", "offered", "accepted"):
            ok(move(client, org, application, step))
    ok(client.post(f"{BASE}/openings/{closed['id']}/close", headers=org.officer))
    report = ok(client.get(f"{BASE}/reports/openings-summary", headers=org.viewer))
    assert report["openings"] == {"draft": 1, "open": 2, "closed": 1}
    assert report["applications"] == {**ZERO, "applied": 1, "accepted": 2, "withdrawn": 1}
    assert report["students_placed"] == 1  # one student, two accepted offers
    assert report["closing_soon"] == [
        {
            "id": soon["id"],
            "title": soon["title"],
            "company_name": "Zeta Corp",
            "applications_close_on": day(2),
            "applications_count": 2,
        },
        {
            "id": late["id"],
            "title": late["title"],
            "company_name": "Zeta Corp",
            "applications_close_on": day(9),
            "applications_count": 1,
        },
    ]
    limited = ok(client.get(f"{BASE}/reports/openings-summary", params={"limit": 1}, headers=org.officer))
    assert [o["id"] for o in limited["closing_soon"]] == [soon["id"]]
    assert client.get(f"{BASE}/reports/openings-summary", params={"limit": 51}, headers=org.officer).status_code == 422


def test_empty_reports(client, org):
    assert ok(client.get(f"{BASE}/reports/drives-upcoming", headers=org.officer)) == {"next_30_days": 0, "drives": []}
    assert ok(client.get(f"{BASE}/reports/openings-summary", headers=org.officer)) == {
        "openings": {"draft": 0, "open": 0, "closed": 0},
        "applications": ZERO,
        "students_placed": 0,
        "closing_soon": [],
    }


def test_reports_need_report_read(client, org):
    for path in ("/reports/drives-upcoming", "/reports/openings-summary"):
        for who in ("student", "student2", "nobody"):
            assert code(client.get(f"{BASE}{path}", headers=org.headers[who]), 403) == "forbidden"
