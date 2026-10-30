"""The HTTP surface against contracts/openapi.yaml: plans, sessions, drills, videos, drill tags and annotations, with
the events and audit entries each change writes, and the refusals the rules make."""

from conftest import ATHLETE, BASE, COACH, audit, outbox

UNKNOWN = "99999999-9999-9999-9999-999999999999"


def _code(r) -> str:
    return r.json()["detail"]["code"]


# ---------------------------------------------------------------- plans


def test_plan_lifecycle_publishes_and_audits(client, org):
    p = org.plan(description="Base fitness", objectives=["speed", "endurance"], status="draft")
    assert p["status"] == "draft" and p["organisation_id"] == org.id and p["objectives"] == ["speed", "endurance"]
    [created] = outbox(org.id, "training-video-analysis.plan.created")
    assert created.payload == {
        "organisation_id": org.id,
        "plan_id": p["id"],
        "title": "Pre-season block",
        "coach_id": org.admin_id,
        "start_date": "2026-10-01",
        "end_date": "2026-12-31",
    }
    assert created.actor == org.admin_id

    for status in ("active", "completed", "archived"):
        r = org.patch(f"/plans/{p['id']}", {"status": status})
        assert r.status_code == 200 and r.json()["status"] == status
    r = org.patch(f"/plans/{p['id']}", {"title": "Renamed"})
    assert r.status_code == 400 and _code(r) == "plan_archived"

    entries = audit(org.id, "plan")
    assert [e.action for e in entries] == ["plan.created"] + ["plan.updated"] * 3
    assert "title" not in entries[0].after and "description" not in entries[0].after  # free text stays out
    assert entries[1].before == {"status": "draft"} and entries[1].after == {"status": "active"}


def test_plan_filters_and_pagination(client, org):
    coach_id, _ = org.user(COACH)
    org.plan(title="A", start_date="2026-09-01")
    org.plan(title="B", coach_id=coach_id, status="draft")
    org.plan(title="C", start_date="2026-11-01", end_date="2026-11-30")
    body = org.get("/plans?limit=2").json()
    assert body["total"] == 3 and [p["title"] for p in body["items"]] == ["C", "B"]
    assert [p["title"] for p in org.get("/plans?limit=2&offset=2").json()["items"]] == ["A"]
    assert [p["title"] for p in org.get(f"/plans?coach_id={coach_id}").json()["items"]] == ["B"]
    assert org.get("/plans?status=draft").json()["total"] == 1
    assert org.get("/plans?limit=0").status_code == 422
    assert org.get("/plans?coach_id=nope").status_code == 422


def test_plan_refusals(client, org):
    r = client.post(
        f"{BASE}/plans",
        json={"title": "x", "coach_id": org.admin_id, "start_date": "2026-10-02", "end_date": "2026-10-01"},
        headers=org.admin,
    )
    assert r.status_code == 400 and _code(r) == "invalid_period"
    r = client.post(
        f"{BASE}/plans",
        json={
            "title": "x",
            "coach_id": org.admin_id,
            "start_date": "2026-10-01",
            "end_date": "2026-10-02",
            "status": "completed",
        },
        headers=org.admin,
    )
    assert r.status_code == 422  # a plan starts as draft or active
    p = org.plan()
    assert _code(org.patch(f"/plans/{p['id']}", {"status": "draft"})) == "invalid_transition"
    assert _code(org.patch(f"/plans/{p['id']}", {"end_date": "2026-09-01"})) == "invalid_period"
    assert org.patch(f"/plans/{p['id']}", {"title": None}).status_code == 422
    r = org.patch(f"/plans/{p['id']}", {"objectives": None, "description": None})
    assert r.status_code == 200 and r.json()["objectives"] == [] and "description" not in r.json()
    assert org.patch(f"/plans/{p['id']}", {"unknown": 1}).status_code == 422
    assert org.get(f"/plans/{UNKNOWN}").status_code == 404
    assert org.patch(f"/plans/{UNKNOWN}", {"title": "x"}).status_code == 404

    # moving the plan's dates may not strand its sessions
    org.session(plan_id=p["id"], scheduled_start="2026-12-20T03:00:00Z", scheduled_end="2026-12-20T04:00:00Z")
    r = org.patch(f"/plans/{p['id']}", {"end_date": "2026-12-15"})
    assert r.status_code == 400 and _code(r) == "sessions_outside_plan"
    assert org.patch(f"/plans/{p['id']}", {"end_date": "2026-12-20"}).status_code == 200


def test_permissions_are_checked(client, org):
    _, coach = org.user(COACH)
    _, athlete = org.user(ATHLETE)
    _, nobody = org.user("someone-else")
    assert client.get(f"{BASE}/plans", headers=athlete).status_code == 200
    r = client.post(
        f"{BASE}/plans",
        json={"title": "x", "coach_id": org.admin_id, "start_date": "2026-10-01", "end_date": "2026-10-02"},
        headers=athlete,
    )
    assert r.status_code == 403 and _code(r) == "forbidden"
    for path in ("/plans", "/sessions", "/drills", "/videos"):
        assert client.get(f"{BASE}{path}", headers=nobody).status_code == 403
    assert client.get(f"{BASE}/plans").status_code == 401
    assert client.get(f"{BASE}/plans", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    v = org.video()
    body = {"author_id": org.admin_id, "start_timestamp": 1, "content": "x"}
    assert client.post(f"{BASE}/videos/{v['id']}/annotations", json=body, headers=athlete).status_code == 403
    tag = {"drill_id": UNKNOWN, "start_timestamp": 0, "end_timestamp": 1}
    assert client.post(f"{BASE}/videos/{v['id']}/drill-tags", json=tag, headers=athlete).status_code == 403
    assert client.get(f"{BASE}/videos", headers=coach).status_code == 200


# ---------------------------------------------------------------- drills


def test_drill_catalogue(client, org):
    d = org.drill(equipment_needed=["ladder", "cones"], standard_duration_minutes=15, target_focus="Foot speed")
    org.drill("DRILL-CON-01", title="Shuttle runs", category="Conditioning", intensity="maximum")
    assert d["equipment_needed"] == ["ladder", "cones"] and "description" not in d
    assert org.get("/drills").json()["total"] == 2
    assert [x["code"] for x in org.get("/drills?category=Conditioning").json()["items"]] == ["DRILL-CON-01"]
    assert org.get("/drills?intensity=high").json()["items"][0]["id"] == d["id"]
    assert org.get("/drills?intensity=extreme").status_code == 422
    assert org.get(f"/drills/{d['id']}").json()["title"] == "Ladder agility shuffle"

    r = org.patch(f"/drills/{d['id']}", {"intensity": "medium", "target_focus": None})
    assert r.status_code == 200 and r.json()["intensity"] == "medium" and "target_focus" not in r.json()
    assert org.patch(f"/drills/{d['id']}", {"code": "X"}).status_code == 422  # the code is fixed

    dup = client.post(
        f"{BASE}/drills",
        json={"code": d["code"], "title": "Other", "category": "Agility", "intensity": "low"},
        headers=org.admin,
    )
    assert dup.status_code == 400 and _code(dup) == "duplicate_code"
    assert [e.action for e in audit(org.id, "drill")] == ["drill.created", "drill.created", "drill.updated"]


# ---------------------------------------------------------------- sessions


def test_session_schedule_complete_and_record(client, org):
    plan = org.plan()
    drill = org.drill()
    a1, a2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    s = org.session(
        plan_id=plan["id"],
        location="Main ground",
        attendee_ids=[a1, a2, a1],
        drill_ids=[drill["id"]],
        scheduled_start="2026-10-29T06:30:00+05:30",
        scheduled_end="2026-10-29T08:00:00+05:30",
    )
    assert s["status"] == "scheduled" and s["attendee_ids"] == [a1, a2]
    assert s["scheduled_start"] == "2026-10-29T01:00:00+00:00"  # returned in UTC
    [scheduled] = outbox(org.id, "training-video-analysis.session.scheduled")
    assert scheduled.payload == {
        "organisation_id": org.id,
        "session_id": s["id"],
        "plan_id": plan["id"],
        "coach_id": org.admin_id,
        "scheduled_start": "2026-10-29T01:00:00+00:00",
        "location": "Main ground",
    }

    r = org.patch(f"/sessions/{s['id']}", {"status": "in_progress"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    assert outbox(org.id, "training-video-analysis.session.completed") == []
    r = org.patch(f"/sessions/{s['id']}", {"status": "completed", "actual_duration_minutes": 85})
    assert r.status_code == 200 and r.json()["actual_duration_minutes"] == 85
    [completed] = outbox(org.id, "training-video-analysis.session.completed")
    assert completed.payload == {
        "organisation_id": org.id,
        "session_id": s["id"],
        "completed_at": "2026-10-30T09:00:00+00:00",
        "duration_minutes": 85,
    }

    # after the session: attendance and notes may still be recorded, the schedule may not change
    r = org.patch(f"/sessions/{s['id']}", {"attendee_ids": [a2], "notes": "Good tempo"})
    assert r.status_code == 200 and r.json()["attendee_ids"] == [a2] and r.json()["notes"] == "Good tempo"
    r = org.patch(f"/sessions/{s['id']}", {"scheduled_start": "2026-10-29T02:00:00Z"})
    assert r.status_code == 400 and _code(r) == "session_closed"
    assert _code(org.patch(f"/sessions/{s['id']}", {"status": "cancelled"})) == "invalid_transition"
    # completing again publishes nothing more
    org.patch(f"/sessions/{s['id']}", {"status": "completed"})
    assert len(outbox(org.id, "training-video-analysis.session.completed")) == 1

    entries = audit(org.id, "session")
    assert [e.action for e in entries] == [
        "session.scheduled",
        "session.updated",
        "session.completed",
        "session.updated",
    ]
    assert entries[3].after == {"attendee_ids": [a2]} and "notes" in entries[3].summary


def test_session_completion_defaults_to_the_scheduled_length(client, org):
    s = org.session()
    org.patch(f"/sessions/{s['id']}", {"status": "completed"})
    [completed] = outbox(org.id, "training-video-analysis.session.completed")
    assert completed.payload["duration_minutes"] == 90


def test_session_refusals(client, org):
    plan = org.plan(start_date="2026-10-01", end_date="2026-10-31")
    r = client.post(
        f"{BASE}/sessions",
        json={
            "coach_id": org.admin_id,
            "title": "x",
            "scheduled_start": "2026-10-29T02:00:00Z",
            "scheduled_end": "2026-10-29T01:00:00Z",
        },
        headers=org.admin,
    )
    assert _code(r) == "invalid_period"

    def schedule(**kw):
        body = {
            "coach_id": org.admin_id,
            "title": "x",
            "scheduled_start": "2026-10-29T01:00:00Z",
            "scheduled_end": "2026-10-29T02:00:00Z",
        }
        return client.post(f"{BASE}/sessions", json={**body, **kw}, headers=org.admin)

    assert _code(schedule(plan_id=UNKNOWN)) == "unknown_plan"
    assert _code(schedule(drill_ids=[UNKNOWN])) == "unknown_drill"
    assert schedule(attendee_ids=["not-a-uuid"]).status_code == 422
    assert schedule(scheduled_start="2026-10-29T01:00:00").status_code == 422  # times carry their offset
    # 31 Oct 20:00 UTC is already 1 Nov at the institution's +05:30
    late = schedule(plan_id=plan["id"], scheduled_start="2026-10-31T20:00:00Z", scheduled_end="2026-10-31T21:00:00Z")
    assert _code(late) == "outside_plan"
    org.patch(f"/plans/{plan['id']}", {"status": "completed"})
    assert _code(schedule(plan_id=plan["id"])) == "plan_closed"

    future = org.session(scheduled_start="2026-11-05T01:00:00Z", scheduled_end="2026-11-05T02:00:00Z")
    assert _code(org.patch(f"/sessions/{future['id']}", {"status": "completed"})) == "not_started"
    assert _code(org.patch(f"/sessions/{future['id']}", {"actual_duration_minutes": 30})) == "not_completed"
    assert _code(org.patch(f"/sessions/{future['id']}", {"scheduled_end": "2026-11-05T00:30:00Z"})) == "invalid_period"
    assert org.patch(f"/sessions/{future['id']}", {"status": "paused"}).status_code == 422
    assert org.patch(f"/sessions/{future['id']}", {"title": None}).status_code == 422
    r = org.patch(f"/sessions/{future['id']}", {"status": "cancelled"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert _code(org.patch(f"/sessions/{future['id']}", {"title": "again"})) == "session_closed"
    assert org.get(f"/sessions/{UNKNOWN}").status_code == 404


def test_session_list_filters(client, org):
    plan = org.plan()
    coach_id, _ = org.user(COACH)
    s1 = org.session(plan_id=plan["id"], scheduled_start="2026-10-28T19:00:00Z", scheduled_end="2026-10-28T20:00:00Z")
    s2 = org.session(coach_id=coach_id, scheduled_start="2026-10-29T10:00:00Z", scheduled_end="2026-10-29T11:00:00Z")
    s3 = org.session(scheduled_start="2026-11-02T10:00:00Z", scheduled_end="2026-11-02T11:00:00Z")
    org.patch(f"/sessions/{s3['id']}", {"status": "cancelled"})

    def ids(query: str) -> list[str]:
        r = org.get(f"/sessions?{query}")
        assert r.status_code == 200, r.text
        return [s["id"] for s in r.json()["items"]]

    assert ids("") == [s1["id"], s2["id"], s3["id"]]
    assert ids(f"plan_id={plan['id']}") == [s1["id"]]
    assert ids(f"coach_id={coach_id}") == [s2["id"]]
    assert ids("status=cancelled") == [s3["id"]]
    # local dates: 28 Oct 19:00 UTC is 29 Oct 00:30 at +05:30
    assert ids("from_date=2026-10-29&to_date=2026-10-29") == [s1["id"], s2["id"]]
    assert ids("to_date=2026-10-28") == []
    assert ids("limit=1&offset=1") == [s2["id"]]
    r = org.get("/sessions?from_date=2026-10-30&to_date=2026-10-29")
    assert r.status_code == 400 and _code(r) == "invalid_period"


# ---------------------------------------------------------------- videos, drill tags, annotations


def test_video_registration_and_metadata(client, org):
    s = org.session()
    v = org.video(session_id=s["id"], resolution="1920x1080")
    assert v["duration_seconds"] == 245.5 and v["session_id"] == s["id"] and v["uploader_id"] == org.admin_id
    [uploaded] = outbox(org.id, "training-video-analysis.video.uploaded")
    assert uploaded.payload == {
        "organisation_id": org.id,
        "video_id": v["id"],
        "session_id": s["id"],
        "title": "Sprint mechanics cam A",
        "duration_seconds": 245.5,
        "video_url": "https://files.example.com/videos/abc.mp4",
    }
    org.video(recorded_at="2026-10-30T08:00:00Z")
    assert org.get("/videos").json()["total"] == 2
    assert [x["id"] for x in org.get(f"/videos?session_id={s['id']}").json()["items"]] == [v["id"]]
    assert org.get(f"/videos?uploader_id={org.admin_id}").json()["total"] == 2

    r = org.patch(f"/videos/{v['id']}", {"title": "Cam A", "thumbnail_url": "https://files.example.com/t.jpg"})
    assert r.status_code == 200 and r.json()["thumbnail_url"] == "https://files.example.com/t.jpg"
    assert org.patch(f"/videos/{v['id']}", {"video_url": "https://elsewhere/x.mp4"}).status_code == 422
    [_, _, updated] = audit(org.id, "video")
    assert updated.action == "video.updated" and updated.after == {} and "thumbnail_url" in updated.summary


def test_video_refusals(client, org):
    def register(**kw):
        body = {
            "uploader_id": org.admin_id,
            "title": "x",
            "video_url": "https://files.example.com/x.mp4",
            "duration_seconds": 10,
            "recorded_at": "2026-10-29T02:00:00Z",
        }
        return client.post(f"{BASE}/videos", json={**body, **kw}, headers=org.admin)

    assert _code(register(session_id=UNKNOWN)) == "unknown_session"
    assert _code(register(recorded_at="2026-10-30T09:00:01Z")) == "in_future"
    assert register(video_url="not a url").status_code == 422
    assert register(duration_seconds=0).status_code == 422
    assert register(duration_seconds="NaN").status_code == 422
    assert org.get(f"/videos/{UNKNOWN}").status_code == 404
    assert org.get(f"/videos/{UNKNOWN}/annotations").status_code == 404
    assert org.get(f"/videos/{UNKNOWN}/drill-tags").status_code == 404


def test_drill_tags(client, org):
    d1, d2 = org.drill(), org.drill("DRILL-CON-01", title="Shuttle runs")
    v = org.video(duration_seconds=120)
    t2 = org.post(f"/videos/{v['id']}/drill-tags", {"drill_id": d2["id"], "start_timestamp": 60, "end_timestamp": 120})
    t1 = org.post(
        f"/videos/{v['id']}/drill-tags",
        {"drill_id": d1["id"], "start_timestamp": 12, "end_timestamp": 65.4, "notes": "x"},
    )
    assert t1["drill_title"] == "Ladder agility shuffle" and t1["video_id"] == v["id"]
    tags = org.get(f"/videos/{v['id']}/drill-tags").json()
    assert [t["id"] for t in tags] == [t1["id"], t2["id"]]  # timeline order
    assert [t["drill_title"] for t in tags] == ["Ladder agility shuffle", "Shuttle runs"]
    events = outbox(org.id, "training-video-analysis.video.tagged")
    assert events[0].payload == {
        "organisation_id": org.id,
        "video_id": v["id"],
        "drill_id": d2["id"],
        "start_timestamp": 60.0,
        "end_timestamp": 120.0,
    }
    assert all("notes" not in (e.after or {}) for e in audit(org.id, "drill_tag"))

    def tag(**kw):
        body = {"drill_id": d1["id"], "start_timestamp": 0, "end_timestamp": 10, **kw}
        return client.post(f"{BASE}/videos/{v['id']}/drill-tags", json=body, headers=org.admin)

    assert _code(tag(drill_id=UNKNOWN)) == "unknown_drill"
    assert _code(tag(end_timestamp=121)) == "outside_video"
    assert _code(tag(start_timestamp=10, end_timestamp=10)) == "invalid_timestamp"
    assert _code(tag(start_timestamp=-1)) == "invalid_timestamp"
    body = {"drill_id": d1["id"], "start_timestamp": 0, "end_timestamp": 1}
    assert client.post(f"{BASE}/videos/{UNKNOWN}/drill-tags", json=body, headers=org.admin).status_code == 404


def test_annotations_lifecycle(client, org):
    coach_id, coach = org.user(COACH)
    v = org.video(duration_seconds=100)
    athlete = "11111111-1111-1111-1111-111111111111"
    a = org.annotation(
        v["id"], start_timestamp=42.5, end_timestamp=48, category="biomechanical", tagged_athlete_ids=[athlete]
    )
    assert a["author_id"] == org.admin_id and a["tagged_athlete_ids"] == [athlete] and a["video_id"] == v["id"]
    b = org.post(
        f"/videos/{v['id']}/annotations",
        {
            "author_id": coach_id,
            "start_timestamp": 10,
            "content": "Good drive phase",
            "drawing_markup": {"arrows": [1]},
        },
        coach,
    )
    assert b["category"] == "technical" and b["drawing_markup"] == {"arrows": [1]}
    [added, _] = outbox(org.id, "training-video-analysis.annotation.added")
    assert added.payload == {
        "organisation_id": org.id,
        "annotation_id": a["id"],
        "video_id": v["id"],
        "author_id": org.admin_id,
        "start_timestamp": 42.5,
        "category": "biomechanical",
    }
    assert [x["id"] for x in org.get(f"/videos/{v['id']}/annotations").json()] == [b["id"], a["id"]]
    assert org.get(f"/videos/{v['id']}/annotations/{a['id']}").json()["content"] == "Knee angle too low"

    # only the author changes an annotation
    r = org.patch(f"/videos/{v['id']}/annotations/{b['id']}", {"content": "edited by someone else"})
    assert r.status_code == 403 and _code(r) == "not_the_author"
    r = org.patch(
        f"/videos/{v['id']}/annotations/{b['id']}", {"content": "Great drive", "tagged_athlete_ids": [athlete]}, coach
    )
    assert r.status_code == 200 and r.json()["content"] == "Great drive" and r.json()["tagged_athlete_ids"] == [athlete]
    r = org.patch(f"/videos/{v['id']}/annotations/{a['id']}", {"end_timestamp": None})
    assert r.status_code == 200 and "end_timestamp" not in r.json()

    # anyone with annotation:write may remove one (moderation); the audit keeps who and when, not the text
    r = client.delete(f"{BASE}/videos/{v['id']}/annotations/{b['id']}", headers=org.admin)
    assert r.status_code == 204
    assert org.get(f"/videos/{v['id']}/annotations/{b['id']}").status_code == 404
    assert client.delete(f"{BASE}/videos/{v['id']}/annotations/{b['id']}", headers=org.admin).status_code == 404

    entries = audit(org.id, "annotation")
    assert [e.action for e in entries] == [
        "annotation.added",
        "annotation.added",
        "annotation.updated",
        "annotation.updated",
        "annotation.deleted",
    ]
    for e in entries:
        for fields in (e.before or {}, e.after or {}):
            assert "content" not in fields and "drawing_markup" not in fields
    assert entries[-1].actor == org.admin_id and entries[-1].before["author_id"] == coach_id


def test_annotation_refusals(client, org):
    v = org.video(duration_seconds=100)
    other = org.video()

    def add(**kw):
        body = {"author_id": org.admin_id, "start_timestamp": 1, "content": "x", **kw}
        return client.post(f"{BASE}/videos/{v['id']}/annotations", json=body, headers=org.admin)

    r = add(author_id=UNKNOWN)
    assert r.status_code == 400 and _code(r) == "not_the_author"
    assert _code(add(start_timestamp=101)) == "outside_video"
    assert _code(add(start_timestamp=5, end_timestamp=4)) == "invalid_timestamp"
    assert add(category="rant").status_code == 422
    assert add(content="").status_code == 422
    assert add(tagged_athlete_ids=["x"]).status_code == 422
    a = add().json()
    assert _code(org.patch(f"/videos/{v['id']}/annotations/{a['id']}", {"end_timestamp": 500})) == "outside_video"
    assert org.patch(f"/videos/{v['id']}/annotations/{a['id']}", {"content": None}).status_code == 422
    # an annotation is reached only through its own video
    assert org.get(f"/videos/{other['id']}/annotations/{a['id']}").status_code == 404
    assert client.delete(f"{BASE}/videos/{other['id']}/annotations/{a['id']}", headers=org.admin).status_code == 404
