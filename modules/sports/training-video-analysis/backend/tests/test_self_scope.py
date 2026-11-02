"""An athlete sees only their own sessions, the plans those belong to, their videos and the annotations about them
(or about no one), read-only. Another athlete's rows answer 404, and other athletes' ids are not shown."""

from conftest import ATHLETE, BASE, COACH

UNKNOWN = "99999999-9999-9999-9999-999999999999"


def _seed(org):
    me, as_me = org.athlete_user()
    other, as_other = org.athlete_user()
    plan_mine, plan_theirs = org.plan(title="Mine"), org.plan(title="Theirs")
    org.plan(title="Nobody's")
    s_mine = org.session(plan_id=plan_mine["id"], attendee_ids=[me, other])
    org.patch(f"/sessions/{s_mine['id']}", {"notes": "Watch the other athlete's hamstring"})
    s_theirs = org.session(plan_id=plan_theirs["id"], attendee_ids=[other])
    v_mine = org.video(session_id=s_mine["id"])
    v_theirs = org.video(session_id=s_theirs["id"])
    v_tagged = org.video()  # no session: visible to me only through an annotation that tags me
    about_me = org.annotation(v_tagged["id"], tagged_athlete_ids=[me, other])
    general = org.annotation(v_mine["id"], content="Whole squad: tempo")
    about_other = org.annotation(v_mine["id"], content="Other athlete: hip drop", tagged_athlete_ids=[other])
    return {
        "me": me,
        "other": other,
        "as_me": as_me,
        "as_other": as_other,
        "plan_mine": plan_mine,
        "plan_theirs": plan_theirs,
        "s_mine": s_mine,
        "s_theirs": s_theirs,
        "v_mine": v_mine,
        "v_theirs": v_theirs,
        "v_tagged": v_tagged,
        "about_me": about_me,
        "general": general,
        "about_other": about_other,
    }


def test_athlete_lists_show_only_their_own(client, org):
    x = _seed(org)
    as_me = x["as_me"]
    sessions = org.get("/sessions", as_me).json()
    assert [s["id"] for s in sessions["items"]] == [x["s_mine"]["id"]] and sessions["total"] == 1
    [s] = sessions["items"]
    assert s["attendee_ids"] == [x["me"]] and "notes" not in s  # not the other athlete, not the coach's notes
    assert [p["id"] for p in org.get("/plans", as_me).json()["items"]] == [x["plan_mine"]["id"]]
    videos = {v["id"] for v in org.get("/videos", as_me).json()["items"]}
    assert videos == {x["v_mine"]["id"], x["v_tagged"]["id"]}
    notes = org.get(f"/videos/{x['v_mine']['id']}/annotations", as_me).json()
    assert [n["id"] for n in notes] == [x["general"]["id"]]
    [tagged] = org.get(f"/videos/{x['v_tagged']['id']}/annotations", as_me).json()
    assert tagged["tagged_athlete_ids"] == [x["me"]]
    # the coach sees everything, with every athlete
    assert len(org.get(f"/videos/{x['v_mine']['id']}/annotations").json()) == 2
    assert org.get(f"/sessions/{x['s_mine']['id']}").json()["attendee_ids"] == [x["me"], x["other"]]
    # filters cannot widen the view
    assert org.get(f"/sessions?plan_id={x['plan_theirs']['id']}", as_me).json()["total"] == 0
    assert org.get(f"/videos?session_id={x['s_theirs']['id']}", as_me).json()["total"] == 0
    # the drill catalogue is shared
    org.drill()
    assert org.get("/drills", as_me).json()["total"] == 1


def test_another_athletes_rows_are_not_found(client, org):
    x = _seed(org)
    as_me = x["as_me"]
    for path in (
        f"/sessions/{x['s_theirs']['id']}",
        f"/plans/{x['plan_theirs']['id']}",
        f"/videos/{x['v_theirs']['id']}",
        f"/videos/{x['v_theirs']['id']}/annotations",
        f"/videos/{x['v_theirs']['id']}/drill-tags",
        f"/videos/{x['v_mine']['id']}/annotations/{x['about_other']['id']}",
        f"/sessions/{UNKNOWN}",
    ):
        r = org.get(path, as_me)
        assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found", path
    for path in (
        f"/sessions/{x['s_mine']['id']}",
        f"/plans/{x['plan_mine']['id']}",
        f"/videos/{x['v_mine']['id']}",
        f"/videos/{x['v_mine']['id']}/drill-tags",
        f"/videos/{x['v_mine']['id']}/annotations/{x['general']['id']}",
        f"/videos/{x['v_tagged']['id']}/annotations/{x['about_me']['id']}",
    ):
        assert org.get(path, as_me).status_code == 200, path
    # and the other athlete sees what is about them
    assert (
        org.get(f"/videos/{x['v_mine']['id']}/annotations/{x['about_other']['id']}", x["as_other"]).status_code == 200
    )


def test_athletes_cannot_change_anything(client, org):
    x = _seed(org)
    as_me = x["as_me"]
    assert org.patch(f"/sessions/{x['s_mine']['id']}", {"title": "x"}, as_me).status_code == 403
    assert org.patch(f"/plans/{x['plan_mine']['id']}", {"title": "x"}, as_me).status_code == 403
    assert org.patch(f"/videos/{x['v_mine']['id']}", {"title": "x"}, as_me).status_code == 403
    path = f"{BASE}/videos/{x['v_mine']['id']}/annotations/{x['general']['id']}"
    assert client.delete(path, headers=as_me).status_code == 403


def test_an_unlinked_athlete_sees_nothing_and_a_coach_athlete_sees_all(client, org):
    x = _seed(org)
    _, unlinked = org.user(ATHLETE)
    assert org.get("/sessions", unlinked).json()["total"] == 0
    assert org.get("/videos", unlinked).json()["total"] == 0
    assert org.get("/plans", unlinked).json()["total"] == 0
    assert org.get(f"/sessions/{x['s_mine']['id']}", unlinked).status_code == 404
    # someone who also coaches is not limited to their own rows
    _, both = org.user(ATHLETE, COACH)
    assert org.get("/sessions", both).json()["total"] == 2
    # the profile role `athlete` is self-only too
    _, profile_athlete = org.user("athlete", user_id=None)
    assert org.get("/sessions", profile_athlete).json()["total"] == 0
