"""Use cases of projects (docs/prd.md, docs/user-stories.md). Each one checks the domain rules, changes state, writes
an audit entry, and publishes the matching event from contracts/events.yaml to the outbox in the same transaction.
Submission notes, files and review comments are never published (events.yaml); they are read through the API.

A person is identified by their identity user id (the token subject). A caller is a member of a project while they
have a team row without left_at, and guides it while they have a guide row without removed_at. Rows that change a
project's status, team or guides lock the project first (FOR UPDATE); rows that change a milestone lock the
milestone, so two concurrent requests never both pass the same check."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import MILESTONE_TRANSITIONS, PROJECT_TRANSITIONS, RuleViolationError
from ..infrastructure import repository as repo
from ..infrastructure.models import AuditEntry, Guide, Member, Milestone, Project, Review, Submission, as_utc, iso

MODULE = "projects"
PROJECT_READ = "projects:project:read"
PROJECT_MANAGE = "projects:project:manage"
GUIDANCE_READ = "projects:guidance:read"
MILESTONE_MANAGE = "projects:milestone:manage"
REVIEW_RECORD = "projects:review:record"
SELF_READ = "projects:self:read"
SELF_PROPOSE = "projects:self:propose"
SELF_SUBMIT = "projects:self:submit"

# Domain rule code -> HTTP status.
RULE_STATUS = {
    "invalid_status": 409,
    "no_lead": 409,
    "guide_required": 409,
    "member_is_guide": 409,
    "invalid_dates": 422,
    "reason_required": 422,
    "comments_required": 422,
    "outcome_required": 422,
}

# Business dates (due dates, overdue, days left, days waiting) are Indian, as in procurement and e-office (decided by
# the owner on #335). Asia/Kolkata has kept UTC+05:30 without daylight saving since 1945, so a fixed offset is exact
# and needs no tz database on the server.
BUSINESS_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def clock() -> datetime:
    """Current time; tests replace this."""
    return utcnow()


def today() -> date:
    """Today in Asia/Kolkata: the date due dates and overdue are judged against."""
    return clock().astimezone(BUSINESS_TZ).date()


def business_date(value: datetime) -> date:
    return as_utc(value).astimezone(BUSINESS_TZ).date()


@dataclass
class Actor:
    """Who is calling. Built by the API layer from the verified token."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class ProjectsError(Exception):
    """A refusal with an HTTP status and an error body ({code, message})."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> ProjectsError:
    return ProjectsError(404, "not_found", f"{what} not found in your organisation")


def _conflict(code: str, message: str) -> ProjectsError:
    return ProjectsError(409, code, message)


def _forbidden(code: str, message: str) -> ProjectsError:
    return ProjectsError(403, code, message)


def _flush_unique(db: Session, code: str, message: str) -> None:
    """Write now, so a duplicate that slipped past the checks and locks (two requests at once) is a 409, not a 500."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _conflict(code, message) from None


def _rule(v: RuleViolationError) -> ProjectsError:
    return ProjectsError(RULE_STATUS.get(v.code, 422), v.code, v.message)


def _check(fn, *args):
    try:
        return fn(*args)
    except RuleViolationError as v:
        raise _rule(v) from v


def _audit(db: Session, actor: Actor | None, action: str, entity: str, entity_id: str, organisation_id: str) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor.user_id if actor else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            occurred_at=clock(),
        )
    )


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict) -> None:
    events.publish(
        db,
        f"{MODULE}.{name}",
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def _without_none(d: dict, *keys: str) -> dict:
    """Drop optional keys the contract types as plain strings (not nullable) when they have no value."""
    for key in keys:
        if d.get(key) is None:
            d.pop(key, None)
    return d


# ---------------------------------------------------------------- serialisation


def milestone_dict(m: Milestone, latest_at: datetime | None, now: date) -> dict:
    return _without_none(
        {
            "id": m.id,
            "organisation_id": m.organisation_id,
            "project_id": m.project_id,
            "title": m.title,
            "description": m.description,
            "due_on": iso(m.due_on),
            "weight": m.weight,
            "status": m.status,
            "overdue": rules.is_overdue(m.status, m.due_on, now),
            "latest_submission_at": iso(latest_at),
        },
        "description",
    )


def milestone_dicts(db: Session, milestones: list[Milestone]) -> list[dict]:
    latest = repo.latest_submission_at(db, [m.id for m in milestones])
    now = today()
    return [milestone_dict(m, latest.get(m.id), now) for m in milestones]


def project_dicts(db: Session, projects: list[Project]) -> list[dict]:
    """Projects with their lead, guides and progress (milestones accepted of total, cancelled not counted)."""
    ids = [p.id for p in projects]
    team, guides, milestones = repo.members_of(db, ids), repo.guides_of(db, ids), repo.milestones_of(db, ids)
    out = []
    for p in projects:
        accepted, total = rules.progress([m.status for m in milestones[p.id]])
        lead = next((m.person_id for m in team[p.id] if m.role == "lead"), None)
        out.append(
            _without_none(
                {
                    "id": p.id,
                    "organisation_id": p.organisation_id,
                    "title": p.title,
                    "summary": p.summary,
                    "kind": p.kind,
                    "academic_year": p.academic_year,
                    "starts_on": iso(p.starts_on),
                    "ends_on": iso(p.ends_on),
                    "external_partner": p.external_partner,
                    "status": p.status,
                    "lead_id": lead,
                    "guide_ids": [g.person_id for g in guides[p.id]],
                    "member_count": len(team[p.id]),
                    "milestones_total": total,
                    "milestones_accepted": accepted,
                    "outcome": p.outcome,
                    "score": p.score,
                    "reason": p.reason,
                },
                "summary",
                "kind",
                "academic_year",
            )
        )
    return out


def project_dict(db: Session, p: Project) -> dict:
    return project_dicts(db, [p])[0]


def member_dict(m: Member) -> dict:
    return {"person_id": m.person_id, "role": m.role, "joined_at": iso(m.joined_at), "left_at": iso(m.left_at)}


def guide_dict(g: Guide) -> dict:
    return {"person_id": g.person_id, "assigned_at": iso(g.assigned_at)}


def project_detail(db: Session, p: Project) -> dict:
    """The project with every member who ever joined (left_at set for those who left), its guides and milestones."""
    return {
        **project_dict(db, p),
        "members": [member_dict(m) for m in repo.members_of(db, [p.id], current_only=False)[p.id]],
        "guides": [guide_dict(g) for g in repo.guides_of(db, [p.id])[p.id]],
        "milestones": milestone_dicts(db, repo.milestones_of(db, [p.id])[p.id]),
    }


def review_dict(r: Review) -> dict:
    return _without_none(
        {
            "decision": r.decision,
            "comments": r.comments,
            "score": r.score,
            "reviewer_id": r.reviewer_id,
            "reviewed_at": iso(r.reviewed_at),
        },
        "comments",
    )


def submission_dict(s: Submission, review: Review | None) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "project_id": s.project_id,
        "milestone_id": s.milestone_id,
        "version": s.version,
        "note": s.note,
        "document_ids": list(s.document_ids or []),
        "submitted_by": s.submitted_by,
        "submitted_at": iso(s.submitted_at),
        "review": review_dict(review) if review else None,
    }


def _page(items: list[dict], next_cursor: str | None) -> dict:
    return {"items": items, "next_cursor": next_cursor}


# ---------------------------------------------------------------- who may do what


def _get(db: Session, model, row_id: str, what: str):
    row = repo.get(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _locked(db: Session, model, row_id: str, what: str):
    row = repo.for_update(db, model, row_id)
    if row is None:
        raise _not_found(what)
    return row


def _can_see(db: Session, actor: Actor, p: Project) -> bool:
    """projects:project:read sees every project; a guide the projects they guide; a member their own."""
    if actor.can(PROJECT_READ):
        return True
    if actor.can(GUIDANCE_READ) and repo.guiding(db, p.id, actor.user_id) is not None:
        return True
    return actor.can(SELF_READ) and repo.membership(db, p.id, actor.user_id) is not None


def _visible(db: Session, actor: Actor, project_id: str) -> Project:
    """The project, or 404 when it is not the caller's to see (another's project is never confirmed to exist)."""
    p = _get(db, Project, project_id, "project")
    if not _can_see(db, actor, p):
        raise _not_found("project")
    return p


def _led_while_proposed(db: Session, actor: Actor, p: Project) -> None:
    """projects:self:propose covers the caller's own proposal only: they lead it and it is still proposed."""
    m = repo.membership(db, p.id, actor.user_id)
    if m is None:
        raise _not_found("project")
    if m.role != "lead":
        raise _forbidden("not_lead", "only the lead may change the proposal")
    _check(rules.check_not_closed, p.status)
    if p.status != "proposed":
        raise _forbidden("not_proposed", "the lead may change the project only while it is proposed")


def _team_editable(db: Session, actor: Actor, project_id: str) -> Project:
    """The locked project whose team the caller may change: a coordinator while it is proposed or active, the
    lead while it is proposed."""
    p = _locked(db, Project, project_id, "project")
    if not actor.can(PROJECT_MANAGE):
        _led_while_proposed(db, actor, p)
    elif p.status not in rules.TEAM_OPEN:
        raise _conflict("invalid_status", f"the team of a {p.status} project cannot change")
    return p


def _require_guide(db: Session, actor: Actor, p: Project) -> None:
    if repo.guiding(db, p.id, actor.user_id) is None:
        raise _forbidden("not_guide", "you are not a guide of this project")


def _require_member(db: Session, actor: Actor, p: Project) -> None:
    if repo.membership(db, p.id, actor.user_id) is None:
        raise _forbidden("not_member", "you are not a member of this project")


def _milestone_manager(db: Session, actor: Actor, p: Project) -> None:
    """projects:project:manage on any project, projects:milestone:manage on the projects the caller guides."""
    if not actor.can(PROJECT_MANAGE):
        _require_guide(db, actor, p)


def _require_active(p: Project) -> None:
    if p.status != "active":
        raise _conflict("project_not_active", f"the project is {p.status}, not active")


# ---------------------------------------------------------------- projects


def list_projects(db: Session, actor: Actor, filters: dict, cursor: str | None, limit: int) -> dict:
    """Every project for projects:project:read; only the projects the caller guides for projects:guidance:read."""
    query = repo.projects_query(db, **filters)
    if not actor.can(PROJECT_READ):
        query = query.where(Project.id.in_(repo.guided_project_ids(db, actor.user_id)))
    rows, nxt = repo.page(db, query, cursor, limit)
    return _page(project_dicts(db, rows), nxt)


def _add_member(db: Session, p: Project, person_id: str, role: str) -> Member:
    m = Member(organisation_id=p.organisation_id, project_id=p.id, person_id=person_id, role=role, joined_at=clock())
    db.add(m)
    return m


def _set_guides(db: Session, p: Project, guide_ids: list[str]) -> bool:
    """Make `guide_ids` the project's current guides. Kept guides keep their assigned_at; removed ones get
    removed_at. True when anything changed."""
    current = {g.person_id: g for g in repo.guides_of(db, [p.id])[p.id]}
    changed = False
    for person_id, g in current.items():
        if person_id not in guide_ids:
            g.removed_at = clock()
            changed = True
    for person_id in guide_ids:
        if person_id not in current:
            db.add(Guide(organisation_id=p.organisation_id, project_id=p.id, person_id=person_id, assigned_at=clock()))
            changed = True
    db.flush()
    return changed


def _approved(db: Session, actor: Actor, p: Project) -> None:
    team = repo.members_of(db, [p.id])[p.id]
    _publish(
        db,
        actor,
        "project.approved",
        p.organisation_id,
        {
            "project_id": p.id,
            "title": p.title,
            "kind": p.kind,
            "member_ids": [m.person_id for m in team],
            "guide_ids": [g.person_id for g in repo.guides_of(db, [p.id])[p.id]],
            "starts_on": iso(p.starts_on),
            "ends_on": iso(p.ends_on),
        },
    )
    _audit(db, actor, "project.approved", "project", p.id, p.organisation_id)


def create_project(db: Session, actor: Actor, data: dict) -> dict:
    """A coordinator creates an active project with its team and guides; a learner proposes one and leads it."""
    _check(rules.check_period, data["starts_on"], data["ends_on"])
    coordinator = actor.can(PROJECT_MANAGE)
    if coordinator:
        member_ids = list(dict.fromkeys(data.get("member_ids") or []))
        lead_id = data.get("lead_id")
        if lead_id and lead_id not in member_ids:
            member_ids.insert(0, lead_id)
        guide_ids = list(dict.fromkeys(data.get("guide_ids") or []))
        _check(rules.check_team, member_ids, lead_id, guide_ids)
    p = Project(
        organisation_id=actor.organisation_id,
        title=data["title"],
        summary=data.get("summary"),
        kind=data.get("kind"),
        academic_year=data.get("academic_year"),
        starts_on=data["starts_on"],
        ends_on=data["ends_on"],
        external_partner=data.get("external_partner"),
        status="active" if coordinator else "proposed",
        created_by=actor.user_id,
    )
    db.add(p)
    db.flush()
    _audit(db, actor, "project.created", "project", p.id, p.organisation_id)
    if coordinator:
        for person_id in member_ids:
            _add_member(db, p, person_id, "lead" if person_id == lead_id else "member")
        _set_guides(db, p, guide_ids)
        p.decided_by, p.decided_at = actor.user_id, clock()
        _approved(db, actor, p)
    else:
        _add_member(db, p, actor.user_id, "lead")
        db.flush()
        _publish(
            db,
            actor,
            "project.proposed",
            p.organisation_id,
            {"project_id": p.id, "title": p.title, "kind": p.kind, "lead_id": actor.user_id},
        )
        _audit(db, actor, "project.proposed", "project", p.id, p.organisation_id)
    db.commit()
    return project_dict(db, p)


def get_project(db: Session, actor: Actor, project_id: str) -> dict:
    return project_detail(db, _visible(db, actor, project_id))


PROJECT_FIELDS = ("title", "summary", "kind", "academic_year", "starts_on", "ends_on", "external_partner")


def update_project(db: Session, actor: Actor, project_id: str, data: dict) -> dict:
    p = _locked(db, Project, project_id, "project")
    if actor.can(PROJECT_MANAGE):
        _check(rules.check_not_closed, p.status)
    else:
        _led_while_proposed(db, actor, p)
    if "title" in data and data["title"] is None:
        raise ProjectsError(422, "invalid_title", "title cannot be empty")
    starts = data.get("starts_on") or p.starts_on
    ends = data.get("ends_on") or p.ends_on
    _check(rules.check_period, starts, ends)
    for key in PROJECT_FIELDS:
        if key in data and (data[key] is not None or key not in ("starts_on", "ends_on")):
            setattr(p, key, data[key])
    _audit(db, actor, "project.updated", "project", p.id, p.organisation_id)
    db.commit()
    return project_dict(db, p)


def decide_project(db: Session, actor: Actor, project_id: str, data: dict) -> dict:
    p = _locked(db, Project, project_id, "project")
    if p.status != "proposed":
        raise _conflict("invalid_status", f"cannot decide a project that is {p.status}")
    if data["decision"] == "rejected":
        reason = _check(rules.check_reason, data.get("reason"), "reject a proposal")
        p.status = _check(rules.transition, PROJECT_TRANSITIONS, "reject", p.status)
        p.reason, p.decided_by, p.decided_at = reason, actor.user_id, clock()
        _publish(db, actor, "project.rejected", p.organisation_id, {"project_id": p.id, "reason": reason})
        _audit(db, actor, "project.rejected", "project", p.id, p.organisation_id)
        db.commit()
        return project_dict(db, p)
    guide_ids = list(dict.fromkeys(data.get("guide_ids") or []))
    _check(rules.check_guides, guide_ids, [m.person_id for m in repo.members_of(db, [p.id])[p.id]])
    _set_guides(db, p, guide_ids)
    p.status = _check(rules.transition, PROJECT_TRANSITIONS, "approve", p.status)
    p.decided_by, p.decided_at = actor.user_id, clock()
    _approved(db, actor, p)
    db.commit()
    return project_dict(db, p)


def add_member(db: Session, actor: Actor, project_id: str, person_id: str, role: str) -> dict:
    """Add a person to the team, or make a member the lead. A new lead demotes the current lead to member."""
    p = _team_editable(db, actor, project_id)
    if repo.guiding(db, p.id, person_id) is not None:
        raise _conflict("member_is_guide", "the person is a guide of this project")
    existing = repo.membership(db, p.id, person_id)
    if existing is not None and (existing.role == role or role == "member"):
        raise _conflict("already_member", f"the person is already the project's {existing.role}")
    if role == "lead":
        for m in repo.members_of(db, [p.id])[p.id]:
            if m.role == "lead" and m.person_id != person_id:
                m.role = "member"
                _audit(db, actor, "member.demoted", "project", p.id, p.organisation_id)
    if existing is not None:
        existing.role = "lead"
        m = existing
    else:
        m = _add_member(db, p, person_id, role)
    db.flush()
    _publish(db, actor, "member.added", p.organisation_id, {"project_id": p.id, "person_id": person_id, "role": m.role})
    _audit(db, actor, f"member.{'added' if existing is None else 'made_lead'}", "project", p.id, p.organisation_id)
    db.commit()
    return member_dict(m)


def remove_member(db: Session, actor: Actor, project_id: str, person_id: str) -> None:
    p = _team_editable(db, actor, project_id)
    m = repo.membership(db, p.id, person_id)
    if m is None:
        raise _not_found("member")
    if m.role == "lead":
        raise _conflict("member_is_lead", "make another member the lead before removing the lead")
    m.left_at = clock()
    _publish(db, actor, "member.removed", p.organisation_id, {"project_id": p.id, "person_id": person_id})
    _audit(db, actor, "member.removed", "project", p.id, p.organisation_id)
    db.commit()


def set_guides(db: Session, actor: Actor, project_id: str, guide_ids: list[str]) -> dict:
    p = _locked(db, Project, project_id, "project")
    _check(rules.check_not_closed, p.status)
    guide_ids = list(dict.fromkeys(guide_ids))
    _check(rules.check_guides, guide_ids, [m.person_id for m in repo.members_of(db, [p.id])[p.id]])
    if _set_guides(db, p, guide_ids):
        _publish(db, actor, "guide.assigned", p.organisation_id, {"project_id": p.id, "guide_ids": guide_ids})
        _audit(db, actor, "guide.assigned", "project", p.id, p.organisation_id)
    db.commit()
    return project_detail(db, p)


def cancel_project(db: Session, actor: Actor, project_id: str, reason: str) -> dict:
    p = _locked(db, Project, project_id, "project")
    reason = _check(rules.check_reason, reason, "cancel a project")
    p.status = _check(rules.transition, PROJECT_TRANSITIONS, "cancel", p.status)
    p.reason, p.decided_by, p.decided_at = reason, actor.user_id, clock()
    _publish(db, actor, "project.cancelled", p.organisation_id, {"project_id": p.id, "reason": reason})
    _audit(db, actor, "project.cancelled", "project", p.id, p.organisation_id)
    db.commit()
    return project_dict(db, p)


# ---------------------------------------------------------------- milestones


def list_milestones(db: Session, actor: Actor, project_id: str) -> list[dict]:
    p = _visible(db, actor, project_id)
    return milestone_dicts(db, repo.milestones_of(db, [p.id])[p.id])


def create_milestone(db: Session, actor: Actor, project_id: str, data: dict) -> dict:
    p = _locked(db, Project, project_id, "project")
    _milestone_manager(db, actor, p)
    _require_active(p)
    m = Milestone(
        organisation_id=p.organisation_id,
        project_id=p.id,
        title=data["title"],
        description=data.get("description"),
        due_on=data["due_on"],
        weight=data.get("weight"),
        status="pending",
    )
    db.add(m)
    db.flush()
    _publish(
        db,
        actor,
        "milestone.created",
        p.organisation_id,
        {"milestone_id": m.id, "project_id": p.id, "due_on": iso(m.due_on)},
    )
    _audit(db, actor, "milestone.created", "milestone", m.id, p.organisation_id)
    db.commit()
    return milestone_dicts(db, [m])[0]


def _milestone_and_project(db: Session, milestone_id: str) -> tuple[Milestone, Project]:
    """The locked milestone and its project."""
    m = _locked(db, Milestone, milestone_id, "milestone")
    return m, _get(db, Project, m.project_id, "project")


def update_milestone(db: Session, actor: Actor, milestone_id: str, data: dict) -> dict:
    m, p = _milestone_and_project(db, milestone_id)
    _milestone_manager(db, actor, p)
    _require_active(p)
    if m.status == "accepted":
        raise _conflict("milestone_accepted", "an accepted milestone cannot change")
    if m.status == "cancelled":
        raise _conflict("invalid_status", "a cancelled milestone cannot change")
    for key in ("title", "due_on"):
        if key in data and data[key] is None:
            raise ProjectsError(422, f"invalid_{key}", f"{key} cannot be empty")
    for key in ("title", "description", "due_on", "weight"):
        if key in data:
            setattr(m, key, data[key])
    if data.get("status") == "cancelled":
        m.status = _check(rules.transition, MILESTONE_TRANSITIONS, "cancel", m.status)
        m.cancel_reason = data.get("reason")
        _audit(db, actor, "milestone.cancelled", "milestone", m.id, m.organisation_id)
    else:
        _audit(db, actor, "milestone.updated", "milestone", m.id, m.organisation_id)
    db.commit()
    return milestone_dicts(db, [m])[0]


# ---------------------------------------------------------------- submissions and reviews


def _with_reviews(db: Session, rows: list[Submission]) -> list[dict]:
    reviews = repo.reviews_of(db, [s.id for s in rows])
    return [submission_dict(s, reviews.get(s.id)) for s in rows]


def list_submissions(db: Session, actor: Actor, milestone_id: str) -> list[dict]:
    m = _get(db, Milestone, milestone_id, "milestone")
    p = _visible(db, actor, m.project_id)
    return _with_reviews(db, repo.submissions(db, p.id, m.id))


def _new_submission(db: Session, actor: Actor, p: Project, milestone_id: str | None, data: dict) -> Submission:
    version = len(repo.submissions(db, p.id, milestone_id)) + 1
    s = Submission(
        organisation_id=p.organisation_id,
        project_id=p.id,
        milestone_id=milestone_id,
        version=version,
        note=data["note"],
        document_ids=list(dict.fromkeys(data.get("document_ids") or [])),
        submitted_by=actor.user_id,
        submitted_at=clock(),
    )
    db.add(s)
    _flush_unique(db, "already_submitted", f"version {version} was submitted at the same moment; reload and try again")
    return s


def submit_milestone(db: Session, actor: Actor, milestone_id: str, data: dict) -> dict:
    m, p = _milestone_and_project(db, milestone_id)
    _require_member(db, actor, p)
    _require_active(p)
    if m.status not in rules.MILESTONE_OPEN:
        raise _conflict("invalid_status", f"cannot submit a milestone that is {m.status}")
    m.status = rules.transition(MILESTONE_TRANSITIONS, "submit", m.status)
    s = _new_submission(db, actor, p, m.id, data)
    _publish(
        db,
        actor,
        "milestone.submitted",
        p.organisation_id,
        {
            "milestone_id": m.id,
            "project_id": p.id,
            "submission_id": s.id,
            "version": s.version,
            "submitted_by": actor.user_id,
        },
    )
    _audit(db, actor, "milestone.submitted", "milestone", m.id, p.organisation_id)
    db.commit()
    return submission_dict(s, None)


def review_milestone(db: Session, actor: Actor, milestone_id: str, data: dict) -> dict:
    """A guide accepts or returns the latest submission. The milestone is locked, so it is reviewed once."""
    m, p = _milestone_and_project(db, milestone_id)
    _require_guide(db, actor, p)
    if m.status != "submitted":
        raise _conflict("nothing_submitted", f"the milestone is {m.status}; there is no submission to review")
    if p.status in rules.PROJECT_CLOSED:
        raise _conflict("invalid_status", f"the project is {p.status}")
    _check(rules.check_review, data["decision"], data.get("comments"))
    latest = repo.latest_submission(db, p.id, m.id)
    accepted = data["decision"] == "accepted"
    db.add(
        Review(
            organisation_id=p.organisation_id,
            submission_id=latest.id,
            reviewer_id=actor.user_id,
            decision=data["decision"],
            comments=data.get("comments"),
            score=data.get("score"),
            reviewed_at=clock(),
        )
    )
    _flush_unique(db, "already_reviewed", "the submission was reviewed at the same moment")
    m.status = rules.transition(MILESTONE_TRANSITIONS, "accept" if accepted else "return", m.status)
    payload = {"milestone_id": m.id, "project_id": p.id, "reviewer_id": actor.user_id}
    if accepted:
        payload["score"] = data.get("score")
    _publish(db, actor, f"milestone.{m.status}", p.organisation_id, payload)
    _audit(db, actor, f"milestone.{m.status}", "milestone", m.id, p.organisation_id)
    db.commit()
    return milestone_dicts(db, [m])[0]


def submit_project(db: Session, actor: Actor, project_id: str, data: dict) -> dict:
    """The final submission. Milestones neither accepted nor cancelled are listed as a warning, not refused."""
    p = _locked(db, Project, project_id, "project")
    _require_member(db, actor, p)
    _require_active(p)
    p.status = rules.transition(PROJECT_TRANSITIONS, "submit", p.status)
    s = _new_submission(db, actor, p, None, data)
    open_ids = rules.not_accepted([(m.id, m.status) for m in repo.milestones_of(db, [p.id])[p.id]])
    _publish(
        db,
        actor,
        "project.submitted",
        p.organisation_id,
        {"project_id": p.id, "submission_id": s.id, "submitted_by": actor.user_id},
    )
    _audit(db, actor, "project.submitted", "project", p.id, p.organisation_id)
    db.commit()
    return {"submission": submission_dict(s, None), "project": project_dict(db, p), "milestones_not_accepted": open_ids}


def evaluate_project(db: Session, actor: Actor, project_id: str, data: dict) -> dict:
    """A guide completes the project with an outcome, or returns it for more work (active again)."""
    p = _locked(db, Project, project_id, "project")
    _require_guide(db, actor, p)
    if p.status != "submitted":
        raise _conflict("project_not_submitted", f"the project is {p.status}, not submitted")
    _check(rules.check_evaluation, data["decision"], data.get("outcome"))
    completed = data["decision"] == "completed"
    final = repo.latest_submission(db, p.id, None)
    db.add(
        Review(
            organisation_id=p.organisation_id,
            submission_id=final.id,
            reviewer_id=actor.user_id,
            decision="accepted" if completed else "returned",
            comments=data.get("comments"),
            score=data.get("score"),
            reviewed_at=clock(),
        )
    )
    _flush_unique(db, "already_reviewed", "the final submission was evaluated at the same moment")
    if completed:
        p.status = rules.transition(PROJECT_TRANSITIONS, "complete", p.status)
        p.outcome, p.score = data["outcome"].strip(), data.get("score")
        _publish(
            db,
            actor,
            "project.completed",
            p.organisation_id,
            {
                "project_id": p.id,
                "title": p.title,
                "kind": p.kind,
                "member_ids": [m.person_id for m in repo.members_of(db, [p.id])[p.id]],
                "guide_ids": [g.person_id for g in repo.guides_of(db, [p.id])[p.id]],
                "outcome": p.outcome,
                "score": p.score,
            },
        )
    else:
        p.status = rules.transition(PROJECT_TRANSITIONS, "return", p.status)
        _publish(db, actor, "project.returned", p.organisation_id, {"project_id": p.id, "reviewer_id": actor.user_id})
    _audit(db, actor, f"project.{p.status if completed else 'returned'}", "project", p.id, p.organisation_id)
    db.commit()
    return project_dict(db, p)


# ---------------------------------------------------------------- the caller's own (/me)

# /me/projects order: work in progress first, then proposals, then (with include_past) completed projects.
MY_ORDER = {"active": 0, "submitted": 0, "proposed": 1, "completed": 2}


def my_projects(db: Session, actor: Actor, include_past: bool) -> list[dict]:
    statuses = {"active", "submitted", "proposed"} | ({"completed"} if include_past else set())
    found = repo.projects_by_id(db, repo.member_project_ids(db, actor.user_id))
    rows = sorted(
        (p for p in found.values() if p.status in statuses),
        key=lambda p: (MY_ORDER[p.status], p.ends_on, p.title, p.id),
    )
    ids = [p.id for p in rows]
    team, milestones = repo.members_of(db, ids), repo.milestones_of(db, ids)
    out = []
    for p, d in zip(rows, project_dicts(db, rows), strict=True):
        mine = next(m for m in team[p.id] if m.person_id == actor.user_id)
        upcoming = next((m for m in milestones[p.id] if m.status in rules.MILESTONE_OPEN), None)
        out.append(
            {**d, "my_role": mine.role, "next_milestone": milestone_dicts(db, [upcoming])[0] if upcoming else None}
        )
    return out


def my_milestones(db: Session, actor: Actor, within_days: int) -> list[dict]:
    """Pending and returned milestones of the caller's active projects due within `within_days` (overdue ones
    included), earliest first, with the days left (negative when overdue)."""
    now = today()
    projects = {
        p.id: p
        for p in repo.projects_by_id(db, repo.member_project_ids(db, actor.user_id)).values()
        if p.status == "active"
    }
    rows = repo.open_milestones_due(db, list(projects), now + timedelta(days=within_days))
    return [
        {**d, "project_title": projects[m.project_id].title, "days_left": rules.days_between(now, m.due_on)}
        for m, d in zip(rows, milestone_dicts(db, rows), strict=True)
    ]


def my_reviews(db: Session, actor: Actor, limit: int) -> list[dict]:
    """Submitted milestones and submitted projects of the projects the caller guides, oldest submission first."""
    now = today()
    projects = repo.projects_by_id(db, repo.guided_project_ids(db, actor.user_id))
    work: list[tuple[Submission, Project, Milestone | None]] = []
    open_projects = [pid for pid, p in projects.items() if p.status not in rules.PROJECT_CLOSED]
    for m in repo.submitted_milestones(db, open_projects):
        s = repo.latest_submission(db, m.project_id, m.id)
        if s is not None:
            work.append((s, projects[m.project_id], m))
    for p in projects.values():
        if p.status == "submitted":
            s = repo.latest_submission(db, p.id, None)
            if s is not None:
                work.append((s, p, None))
    work.sort(key=lambda w: (as_utc(w[0].submitted_at), w[0].id))
    return [
        {
            "kind": "milestone" if m is not None else "final",
            "project_id": p.id,
            "project_title": p.title,
            "milestone_id": m.id if m is not None else None,
            "milestone_title": m.title if m is not None else None,
            "submission": submission_dict(s, None),
            "waiting_days": max(rules.days_between(business_date(s.submitted_at), now), 0),
        }
        for s, p, m in work[:limit]
    ]
