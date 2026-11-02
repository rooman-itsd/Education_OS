"""The HTTP surface against contracts/openapi.yaml: frameworks, skills, rubrics, assessments with verification and
voiding, the learner progress summary and timeline, with the events and audit entries each change writes."""

from conftest import BASE, COORDINATOR, EVALUATOR, LEARNER, SCALE, VIEWER, outbox
from eos_core.db import SessionLocal, new_id
from eos_skill_progress.infrastructure.models import AuditEntry
from sqlalchemy import event, select


def _audit(organisation_id: str) -> list[AuditEntry]:
    with SessionLocal() as db:
        q = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        return list(db.scalars(q.order_by(AuditEntry.occurred_at, AuditEntry.id)))


def _err(r) -> str:
    return r.json()["detail"]["code"]


# ---------------------------------------------------------------- frameworks


def test_framework_create_list_get_update(client, org):
    f = org.framework(description="Practical skills", status="draft")
    assert f["organisation_id"] == org.id and f["status"] == "draft" and f["code"] == "PRAC-2026"
    org.framework("OTHER", status="active")
    assert client.get(f"{BASE}/frameworks", headers=org.admin).json()["total"] == 2
    drafts = client.get(f"{BASE}/frameworks?status=draft", headers=org.admin).json()
    assert drafts["total"] == 1 and drafts["items"][0]["id"] == f["id"]
    page = client.get(f"{BASE}/frameworks?limit=1&offset=1", headers=org.admin).json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["items"][0]["id"] == f["id"]  # ordered by code

    r = client.patch(f"{BASE}/frameworks/{f['id']}", json={"status": "active", "title": "Core"}, headers=org.admin)
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["title"] == "Core"
    assert client.get(f"{BASE}/frameworks/{f['id']}", headers=org.admin).json()["title"] == "Core"
    [created] = [e for e in outbox(org.id, "skill-progress.framework.created") if e.payload["framework_id"] == f["id"]]
    assert created.payload == {
        "organisation_id": org.id,
        "framework_id": f["id"],
        "code": "PRAC-2026",
        "title": "Core practical competencies",
    }
    entries = {e.action: e for e in _audit(org.id) if e.entity_id == f["id"]}
    assert set(entries) == {"framework.created", "framework.status_changed"}
    assert entries["framework.status_changed"].before == {"status": "draft", "title": "Core practical competencies"}
    assert "description" not in entries["framework.created"].after  # free text stays out of the audit trail


def test_framework_refusals(client, org):
    f = org.framework()
    dup = client.post(f"{BASE}/frameworks", json={"code": f["code"], "title": "x"}, headers=org.admin)
    assert dup.status_code == 400 and _err(dup) == "duplicate_code"
    back = client.patch(f"{BASE}/frameworks/{f['id']}", json={"status": "draft"}, headers=org.admin)
    assert back.status_code == 400 and _err(back) == "invalid_transition"
    archived = client.post(
        f"{BASE}/frameworks", json={"code": "Z", "title": "x", "status": "archived"}, headers=org.admin
    )
    assert archived.status_code == 422  # a framework is created active or draft
    assert client.patch(f"{BASE}/frameworks/{f['id']}", json={"title": None}, headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/frameworks/not-an-id", headers=org.admin).status_code == 404
    assert client.patch(f"{BASE}/frameworks/{new_id()}", json={"title": "x"}, headers=org.admin).status_code == 404


# ---------------------------------------------------------------- skills


def test_skill_create_nest_list_update(client, org):
    f = org.framework()
    parent = org.skill(f["id"], category="Mechanics")
    child = org.skill(f["id"], "SKILL-02", parent_skill_id=parent["id"], category="Mechanics")
    assert child["parent_skill_id"] == parent["id"] and child["level_scale"] == SCALE
    assert "parent_skill_id" not in parent and "updated_at" not in parent
    other = org.framework("OTHER")
    org.skill(other["id"], "SKILL-01")  # codes are unique per framework

    q = client.get(f"{BASE}/skills?framework_id={f['id']}", headers=org.admin).json()
    assert q["total"] == 2
    q = client.get(f"{BASE}/skills?parent_skill_id={parent['id']}", headers=org.admin).json()
    assert [s["id"] for s in q["items"]] == [child["id"]]
    assert client.get(f"{BASE}/skills?category=Mechanics", headers=org.admin).json()["total"] == 2
    assert client.get(f"{BASE}/skills?framework_id=nope", headers=org.admin).status_code == 422

    scale = {
        "type": "pass_fail",
        "levels": [{"key": "fail", "label": "Fail", "rank": 0}, {"key": "pass", "label": "Pass", "rank": 1}],
    }
    r = client.patch(f"{BASE}/skills/{child['id']}", json={"level_scale": scale, "category": None}, headers=org.admin)
    assert r.status_code == 200 and r.json()["level_scale"]["type"] == "pass_fail" and "category" not in r.json()
    [created] = [e for e in outbox(org.id, "skill-progress.skill.created") if e.payload["skill_id"] == child["id"]]
    assert created.payload == {
        "organisation_id": org.id,
        "skill_id": child["id"],
        "framework_id": f["id"],
        "code": "SKILL-02",
        "title": "Technique SKILL-02",
    }
    [updated] = [e for e in _audit(org.id) if e.entity_id == child["id"] and e.action == "skill.updated"]
    assert "level_scale" in updated.summary and updated.after == {"category": None}


def test_skill_refusals(client, org):
    f = org.framework()
    s = org.skill(f["id"])
    other = org.framework("OTHER")
    body = {"framework_id": f["id"], "code": "S2", "title": "t", "level_scale": SCALE}

    r = client.post(f"{BASE}/skills", json={**body, "code": s["code"]}, headers=org.admin)
    assert _err(r) == "duplicate_code"
    r = client.post(f"{BASE}/skills", json={**body, "framework_id": new_id()}, headers=org.admin)
    assert _err(r) == "unknown_framework"
    r = client.post(
        f"{BASE}/skills", json={**body, "framework_id": other["id"], "parent_skill_id": s["id"]}, headers=org.admin
    )
    assert _err(r) == "parent_in_other_framework"
    r = client.post(
        f"{BASE}/skills",
        json={**body, "level_scale": {"type": "numeric_range", "levels": SCALE["levels"]}},
        headers=org.admin,
    )
    assert _err(r) == "range_required"
    r = client.post(
        f"{BASE}/skills",
        json={**body, "level_scale": {"type": "pass_fail", "levels": SCALE["levels"]}},
        headers=org.admin,
    )
    assert _err(r) == "pass_fail_levels"
    r = client.post(f"{BASE}/skills", json={**body, "level_scale": {"type": "grades", "levels": []}}, headers=org.admin)
    assert r.status_code == 422
    r = client.patch(
        f"{BASE}/skills/{s['id']}", json={"level_scale": {"type": "discrete_stages", "levels": []}}, headers=org.admin
    )
    assert _err(r) == "no_levels"
    r = client.patch(f"{BASE}/skills/{s['id']}", json={"code": "X"}, headers=org.admin)
    assert r.status_code == 422  # a skill's code and framework are fixed

    client.patch(f"{BASE}/frameworks/{other['id']}", json={"status": "archived"}, headers=org.admin)
    r = client.post(f"{BASE}/skills", json={**body, "framework_id": other["id"]}, headers=org.admin)
    assert _err(r) == "framework_archived"


# ---------------------------------------------------------------- rubrics


def test_rubrics_for_a_skill_or_a_framework(client, org):
    f, s, skill_rubric = org.setup()
    assert skill_rubric["framework_id"] == f["id"] and skill_rubric["criteria"][0]["weight"] == 2
    assert skill_rubric["criteria"][1]["weight"] == 1.0  # the contract's default
    framework_rubric = org.rubric(framework_id=f["id"], title="General rubric")
    assert "skill_id" not in framework_rubric

    assert client.get(f"{BASE}/rubrics?framework_id={f['id']}", headers=org.admin).json()["total"] == 2
    by_skill = client.get(f"{BASE}/rubrics?skill_id={s['id']}", headers=org.admin).json()
    assert [r["id"] for r in by_skill["items"]] == [skill_rubric["id"]]
    assert client.get(f"{BASE}/rubrics/{framework_rubric['id']}", headers=org.admin).json()["title"] == "General rubric"
    [ev] = [e for e in outbox(org.id, "skill-progress.rubric.created") if e.payload["rubric_id"] == skill_rubric["id"]]
    assert ev.payload == {
        "organisation_id": org.id,
        "rubric_id": skill_rubric["id"],
        "skill_id": s["id"],
        "title": "Practicum rubric",
    }
    [fw] = [
        e for e in outbox(org.id, "skill-progress.rubric.created") if e.payload["rubric_id"] == framework_rubric["id"]
    ]
    assert "skill_id" not in fw.payload


def test_rubric_refusals(client, org):
    f, s, _ = org.setup()
    other = org.framework("OTHER")
    body = {"title": "r", "criteria": [{"key": "a", "title": "A", "max_points": 5}]}
    assert _err(client.post(f"{BASE}/rubrics", json=body, headers=org.admin)) == "target_required"
    r = client.post(
        f"{BASE}/rubrics", json={**body, "skill_id": s["id"], "framework_id": other["id"]}, headers=org.admin
    )
    assert _err(r) == "skill_not_in_framework"
    r = client.post(f"{BASE}/rubrics", json={**body, "skill_id": new_id()}, headers=org.admin)
    assert _err(r) == "unknown_skill"
    r = client.post(f"{BASE}/rubrics", json={**body, "framework_id": f["id"], "criteria": []}, headers=org.admin)
    assert _err(r) == "no_criteria"
    bad = {**body, "framework_id": f["id"], "criteria": [{"key": "a", "title": "A", "max_points": 5, "weight": -1}]}
    assert _err(client.post(f"{BASE}/rubrics", json=bad, headers=org.admin)) == "invalid_weight"
    assert client.get(f"{BASE}/rubrics/{new_id()}", headers=org.admin).status_code == 404


# ---------------------------------------------------------------- assessments


def test_record_assessment_publishes_and_audits(client, org):
    f, s, rubric = org.setup()
    learner = new_id()
    a = org.assess(
        learner,
        s,
        rubric,
        assessed_at="2026-10-29T15:30:00+05:30",
        feedback="Steady tempo; work on dynamics",
        evidence_urls=["https://example.org/recital.mp4"],
        level="proficient",  # by key; stored and returned as the label
    )
    assert a["status"] == "submitted" and a["level_achieved"] == "Proficient"
    assert a["assessed_at"] == "2026-10-29T10:00:00+00:00"  # stored in UTC
    assert a["evidence_urls"] == ["https://example.org/recital.mp4"]
    assert a["criterion_scores"][1] == {"criterion_key": "expression", "points": 7, "level_key": "strong"}
    assert client.get(f"{BASE}/assessments/{a['id']}", headers=org.admin).json() == a

    [recorded] = outbox(org.id, "skill-progress.assessment.recorded")
    assert recorded.payload == {
        "organisation_id": org.id,
        "assessment_id": a["id"],
        "learner_id": learner,
        "evaluator_id": org.evaluator_id,
        "skill_id": s["id"],
        "rubric_id": rubric["id"],
        "overall_score": 75,
        "level_achieved": "Proficient",
        "recorded_at": "2026-10-30T09:00:00+00:00",
    }
    [progress] = outbox(org.id, "skill-progress.progress.updated")
    assert progress.payload == {
        "organisation_id": org.id,
        "learner_id": learner,
        "framework_id": f["id"],
        "updated_at": "2026-10-30T09:00:00+00:00",
    }
    assert outbox(org.id, "skill-progress.milestone.achieved") == []  # the first assessment is the baseline
    [entry] = [e for e in _audit(org.id) if e.entity_id == a["id"]]
    assert entry.action == "assessment.recorded" and entry.actor == org.evaluator_id
    assert (
        "feedback" not in entry.after and "criterion_scores" not in entry.after and "evidence_urls" not in entry.after
    )
    assert entry.after["level_achieved"] == "Proficient"


def test_assessed_at_defaults_to_now(org):
    _, s, rubric = org.setup()
    a = org.assess(new_id(), s, rubric)
    assert a["assessed_at"] == "2026-10-30T09:00:00+00:00"


def test_framework_wide_rubric_applies_to_its_skills(org):
    f, s, _ = org.setup()
    general = org.rubric(framework_id=f["id"])
    assert org.assess(new_id(), s, general)["rubric_id"] == general["id"]


def test_record_assessment_refusals(client, org):
    f, s, rubric = org.setup()
    other_skill = org.skill(f["id"], "SKILL-02")
    other_rubric = org.rubric(other_skill["id"])
    learner = new_id()

    def post(score=75, level="Proficient", **kw):
        body = {**org.body(learner, s, rubric, score, level), **kw}
        return client.post(f"{BASE}/assessments", json=body, headers=org.evaluator)

    assert _err(post(rubric_id=other_rubric["id"])) == "rubric_not_for_skill"
    assert _err(post(skill_id=new_id())) == "unknown_skill"
    assert _err(post(rubric_id=new_id())) == "unknown_rubric"
    assert _err(post(evaluator_id=learner)) == "self_assessment"
    # a learner who also holds an evaluator role cannot record their own assessment under another evaluator's name
    _, dual = org.user(LEARNER, EVALUATOR, user_id=learner)
    r = client.post(f"{BASE}/assessments", json=org.body(learner, s, rubric), headers=dual)
    assert _err(r) == "self_assessment"
    assert _err(post(assessed_at="2026-10-30T09:00:01+00:00")) == "in_future"
    assert post(assessed_at="2026-10-30T09:00:00").status_code == 422  # a time without a timezone is refused
    assert _err(post(level="Master")) == "unknown_level"
    assert _err(post(score=60)) == "level_score_mismatch"
    assert _err(post(score=120, level="Expert")) == "score_out_of_range"
    assert _err(post(criterion_scores=[{"criterion_key": "technique", "points": 8}])) == "missing_score"
    too_many = [{"criterion_key": "technique", "points": 11}, {"criterion_key": "expression", "points": 1}]
    assert _err(post(criterion_scores=too_many)) == "points_out_of_range"
    bad_level = [
        {"criterion_key": "technique", "points": 1},
        {"criterion_key": "expression", "points": 1, "level_key": "x"},
    ]
    assert _err(post(criterion_scores=bad_level)) == "unknown_level"
    assert post(learner_id="").status_code == 422
    assert post(evidence_urls=["not a url"]).status_code == 422

    client.patch(f"{BASE}/frameworks/{f['id']}", json={"status": "archived"}, headers=org.admin)
    assert _err(post()) == "framework_not_active"
    assert client.get(f"{BASE}/assessments", headers=org.admin).json()["total"] == 0  # nothing half-written
    assert outbox(org.id, "skill-progress.assessment.recorded") == []


def test_list_assessments_filters_and_pages(client, org):
    _, s, rubric = org.setup()
    s2 = org.skill(s["framework_id"], "SKILL-02")
    r2 = org.rubric(s2["id"])
    learner, other = new_id(), new_id()
    a1 = org.assess(learner, s, rubric, assessed_at="2026-10-01T10:00:00Z")
    a2 = org.assess(learner, s2, r2, assessed_at="2026-10-15T23:30:00Z")
    a3 = org.assess(other, s, rubric, assessed_at="2026-10-20T10:00:00Z")

    def ids(query: str) -> list[str]:
        return [a["id"] for a in client.get(f"{BASE}/assessments?{query}", headers=org.admin).json()["items"]]

    assert ids("") == [a3["id"], a2["id"], a1["id"]]  # newest first
    assert ids(f"learner_id={learner}") == [a2["id"], a1["id"]]
    assert ids(f"skill_id={s['id']}") == [a3["id"], a1["id"]]
    assert ids(f"evaluator_id={org.evaluator_id}&limit=1&offset=1") == [a2["id"]]
    assert ids("from_date=2026-10-15&to_date=2026-10-15") == [a2["id"]]  # the whole UTC day, inclusive
    r = client.get(f"{BASE}/assessments?from_date=2026-10-20&to_date=2026-10-01", headers=org.admin)
    assert r.status_code == 400 and _err(r) == "invalid_period"
    assert client.get(f"{BASE}/assessments?limit=0", headers=org.admin).status_code == 422
    assert client.get(f"{BASE}/assessments?learner_id=x", headers=org.admin).status_code == 422


def test_verify_and_void(client, org):
    f, s, rubric = org.setup()
    learner = new_id()
    a = org.assess(learner, s, rubric)

    # the evaluator neither holds approve nor may verify their own assessment
    assert client.post(f"{BASE}/assessments/{a['id']}/verify", headers=org.evaluator).status_code == 403
    _, self_admin = org.user("skill-progress-admin", user_id=org.evaluator_id)
    r = client.post(f"{BASE}/assessments/{a['id']}/verify", headers=self_admin)
    assert r.status_code == 400 and _err(r) == "own_assessment"
    _, learner_admin = org.user("skill-progress-admin", user_id=learner)  # nor may the learner verify it
    r = client.post(f"{BASE}/assessments/{a['id']}/verify", headers=learner_admin)
    assert r.status_code == 400 and _err(r) == "own_assessment"

    r = client.post(f"{BASE}/assessments/{a['id']}/verify", headers=org.admin)
    assert r.status_code == 200 and r.json()["status"] == "verified"
    again = client.post(f"{BASE}/assessments/{a['id']}/verify", headers=org.admin)
    assert again.status_code == 400 and _err(again) == "invalid_transition"

    r = client.post(f"{BASE}/assessments/{a['id']}/void", headers=org.admin)
    assert r.status_code == 200 and r.json()["status"] == "voided"
    for action in ("verify", "void"):
        r = client.post(f"{BASE}/assessments/{a['id']}/{action}", headers=org.admin)
        assert r.status_code == 400 and _err(r) == "invalid_transition"
    assert client.post(f"{BASE}/assessments/{new_id()}/void", headers=org.admin).status_code == 404

    actions = sorted((e.action, e.before, e.after) for e in _audit(org.id) if e.entity_id == a["id"] and e.before)
    assert actions == [
        ("assessment.verified", {"status": "submitted"}, {"status": "verified"}),
        ("assessment.voided", {"status": "verified"}, {"status": "voided"}),
    ]
    assert len(outbox(org.id, "skill-progress.progress.updated")) == 2  # recorded, then voided
    # a voided assessment stays on record but no longer counts
    assert client.get(f"{BASE}/assessments/{a['id']}", headers=org.admin).json()["status"] == "voided"
    progress = client.get(f"{BASE}/learners/{learner}/progress", headers=org.admin).json()
    assert progress["skills_evaluated"] == 0 and progress["current_skills"] == []


# ---------------------------------------------------------------- progress and timeline


def test_progress_and_timeline_with_milestones(client, org):
    f, s, rubric = org.setup()
    s2 = org.skill(f["id"], "SKILL-02", category="Ensemble")
    r2 = org.rubric(s2["id"])
    other_framework = org.framework("OTHER")
    s3 = org.skill(other_framework["id"], "SKILL-03")
    r3 = org.rubric(s3["id"])
    learner = new_id()

    a1 = org.assess(learner, s, rubric, 50, "Developing", assessed_at="2026-09-01T10:00:00Z")
    a2 = org.assess(learner, s, rubric, 72, "Proficient", assessed_at="2026-09-15T10:00:00Z")
    a3 = org.assess(learner, s, rubric, 95, "Expert", assessed_at="2026-10-01T10:00:00Z")
    a4 = org.assess(learner, s2, r2, 45, "Developing", assessed_at="2026-10-02T10:00:00Z")
    org.assess(learner, s3, r3, 30, "Novice", assessed_at="2026-10-03T10:00:00Z")
    org.assess(new_id(), s, rubric, 99, "Expert")  # another learner

    milestones = [e.payload for e in outbox(org.id, "skill-progress.milestone.achieved")]
    assert sorted((m["milestone_name"], m["level_achieved"]) for m in milestones if m["learner_id"] == learner) == [
        ("highest_level_reached", "Expert"),
        ("level_advanced", "Expert"),
        ("level_advanced", "Proficient"),
    ]
    [first_try] = [
        m for m in milestones if m["learner_id"] != learner
    ]  # another learner's first assessment, at the top
    assert first_try == {
        "organisation_id": org.id,
        "learner_id": first_try["learner_id"],
        "skill_id": s["id"],
        "milestone_name": "highest_level_reached",
        "level_achieved": "Expert",
        "achieved_at": "2026-10-30T09:00:00+00:00",
    }

    summary = client.get(f"{BASE}/learners/{learner}/progress", headers=org.evaluator).json()
    assert summary["learner_id"] == learner and summary["organisation_id"] == org.id
    assert summary["skills_evaluated"] == 3
    by_skill = {row["skill_id"]: row for row in summary["current_skills"]}
    assert by_skill[s["id"]] == {
        "skill_id": s["id"],
        "skill_title": s["title"],
        "latest_score": 95,
        "latest_level": "Expert",
        "total_evaluations": 3,
        "latest_assessed_at": "2026-10-01T10:00:00+00:00",
    }
    assert by_skill[s2["id"]]["category"] == "Ensemble"
    narrowed = client.get(f"{BASE}/learners/{learner}/progress?framework_id={f['id']}", headers=org.evaluator).json()
    assert {row["skill_id"] for row in narrowed["current_skills"]} == {s["id"], s2["id"]}
    r = client.get(f"{BASE}/learners/{learner}/progress?framework_id={new_id()}", headers=org.evaluator)
    assert r.status_code == 404
    nobody = client.get(f"{BASE}/learners/{new_id()}/progress", headers=org.evaluator).json()
    assert nobody["skills_evaluated"] == 0

    timeline = client.get(f"{BASE}/learners/{learner}/timeline?skill_id={s['id']}", headers=org.evaluator).json()
    kinds = [(e["event_type"], e["level"]) for e in timeline["items"]]
    assert kinds == [
        ("assessment", "Developing"),
        ("assessment", "Proficient"),
        ("level_advanced", "Proficient"),
        ("assessment", "Expert"),
        ("level_advanced", "Expert"),
        ("milestone_achieved", "Expert"),
    ]
    assert timeline["total"] == 6
    assert [e["id"] for e in timeline["items"] if e["event_type"] == "assessment"] == [a1["id"], a2["id"], a3["id"]]
    assert timeline["items"][-1]["title"] == f"{s['title']}: reached Expert, the highest level"
    assert timeline["items"][-1]["occurred_at"] == "2026-10-01T10:00:00+00:00"
    again = client.get(f"{BASE}/learners/{learner}/timeline?skill_id={s['id']}", headers=org.evaluator).json()
    assert [e["id"] for e in again["items"]] == [e["id"] for e in timeline["items"]]  # derived ids are stable

    full = client.get(f"{BASE}/learners/{learner}/timeline?limit=2", headers=org.evaluator).json()
    assert full["total"] == 8 and [e["id"] for e in full["items"]][0] == a4["id"]  # the most recent, oldest first

    # voiding the assessment that reached the top takes its milestones off the timeline
    client.post(f"{BASE}/assessments/{a3['id']}/void", headers=org.admin)
    timeline = client.get(f"{BASE}/learners/{learner}/timeline?skill_id={s['id']}", headers=org.evaluator).json()
    assert [e["event_type"] for e in timeline["items"]] == ["assessment", "assessment", "level_advanced"]
    summary = client.get(f"{BASE}/learners/{learner}/progress", headers=org.evaluator).json()
    assert {r["skill_id"]: r["latest_level"] for r in summary["current_skills"]}[s["id"]] == "Proficient"


def test_a_changed_scale_keeps_recorded_levels(client, org):
    _, s, rubric = org.setup()
    learner = new_id()
    org.assess(learner, s, rubric, 95, "Expert", assessed_at="2026-10-01T10:00:00Z")
    levels = [*SCALE["levels"], {"key": "master", "label": "Master", "rank": 5, "min_score": 98}]
    client.patch(f"{BASE}/skills/{s['id']}", json={"level_scale": {**SCALE, "levels": levels}}, headers=org.admin)
    org.assess(learner, s, rubric, 99, "Master")
    timeline = client.get(f"{BASE}/learners/{learner}/timeline", headers=org.admin).json()["items"]
    assert [e["event_type"] for e in timeline] == [
        "assessment",
        "milestone_achieved",  # Expert was the top when it was recorded
        "assessment",
        "level_advanced",
        "milestone_achieved",
    ]


def test_progress_and_timeline_queries_do_not_grow_with_the_data(client, org):
    """No N+1: the summary and the timeline take the same number of queries for one skill or many."""
    f = org.framework()
    learner = new_id()

    def count_queries(path: str) -> int:
        from eos_core.db import engine

        seen = []

        def on_query(*_):
            seen.append(1)

        event.listen(engine, "before_cursor_execute", on_query)
        try:
            assert client.get(f"{BASE}{path}", headers=org.admin).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", on_query)
        return len(seen)

    def add_skill(i: int) -> None:
        s = org.skill(f["id"], f"S-{i}")
        r = org.rubric(s["id"])
        org.assess(learner, s, r, 50, "Developing")
        org.assess(learner, s, r, 75, "Proficient")

    add_skill(0)
    small = (count_queries(f"/learners/{learner}/progress"), count_queries(f"/learners/{learner}/timeline"))
    for i in range(1, 6):
        add_skill(i)
    large = (count_queries(f"/learners/{learner}/progress"), count_queries(f"/learners/{learner}/timeline"))
    assert small == large


# ---------------------------------------------------------------- permissions and self-scope


def test_permissions_are_checked(client, org):
    f, s, rubric = org.setup()
    _, viewer = org.user(VIEWER)
    assert client.get(f"{BASE}/frameworks", headers=viewer).status_code == 200
    r = client.post(f"{BASE}/frameworks", json={"code": "X", "title": "x"}, headers=viewer)
    assert r.status_code == 403 and _err(r) == "forbidden"
    assert client.post(f"{BASE}/frameworks", json={"code": "X", "title": "x"}, headers=org.evaluator).status_code == 403
    body = org.body(new_id(), s, rubric)
    assert client.post(f"{BASE}/assessments", json=body, headers=viewer).status_code == 403
    a = org.assess(new_id(), s, rubric)
    assert client.post(f"{BASE}/assessments/{a['id']}/void", headers=org.evaluator).status_code == 403
    assert client.get(f"{BASE}/frameworks").status_code == 401
    assert client.get(f"{BASE}/frameworks", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_profile_roles_hold_module_roles(client, org):
    """music-teacher's layout lists skill-progress-evaluator, so a music teacher records assessments."""
    _, s, rubric = org.setup()
    teacher_id, teacher = org.user("music-teacher")
    body = {**org.body(new_id(), s, rubric), "evaluator_id": teacher_id}
    assert client.post(f"{BASE}/assessments", json=body, headers=teacher).status_code == 201


def test_a_learner_sees_only_their_own_records(client, org):
    _, s, rubric = org.setup()
    me, mine = org.user(LEARNER)
    someone = new_id()
    own = org.assess(me, s, rubric)
    theirs = org.assess(someone, s, rubric)

    items = client.get(f"{BASE}/assessments", headers=mine).json()
    assert [a["id"] for a in items["items"]] == [own["id"]] and items["total"] == 1
    assert client.get(f"{BASE}/assessments?learner_id={someone}", headers=mine).json()["total"] == 0
    assert client.get(f"{BASE}/assessments/{own['id']}", headers=mine).status_code == 200
    assert client.get(f"{BASE}/assessments/{theirs['id']}", headers=mine).status_code == 404
    assert client.get(f"{BASE}/learners/{me}/progress", headers=mine).json()["skills_evaluated"] == 1
    assert client.get(f"{BASE}/learners/{me}/timeline", headers=mine).json()["total"] == 1
    assert client.get(f"{BASE}/learners/{someone}/progress", headers=mine).status_code == 404
    assert client.get(f"{BASE}/learners/{someone}/timeline", headers=mine).status_code == 404
    # frameworks, skills and rubrics are not personal
    assert client.get(f"{BASE}/skills", headers=mine).json()["total"] == 1

    # an observer with the same viewer role, who is not a learner, sees the organisation
    _, coordinator = org.user(COORDINATOR)
    assert client.get(f"{BASE}/assessments", headers=coordinator).json()["total"] == 2
    assert client.get(f"{BASE}/learners/{someone}/progress", headers=coordinator).json()["skills_evaluated"] == 1
    # a learner who also evaluates is not narrowed
    _, both = org.user(LEARNER, EVALUATOR)
    assert client.get(f"{BASE}/assessments", headers=both).json()["total"] == 2
