"""Admissions use cases. Every function works inside the caller's transaction (routes commit), filters every query
by the caller's organisation, and writes an audit row plus, where contracts/events.yaml names one, an outbox
event in that same transaction."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

import sqlalchemy as sa
from eos_core import events
from eos_core.db import utcnow
from sqlalchemy.orm import Session

from ..domain import enums as e
from ..domain import rules
from ..domain.rules import RuleViolationError
from ..infrastructure.models import (
    Application,
    ApplicationDocument,
    AuditEntry,
    MeritList,
    MeritListEntry,
    Offer,
    as_utc,
)

MODULE = "admissions"

CODE_STATUS = {
    "terminal_status": 409,
    "not_eligible": 409,
    "offer_already_exists": 409,
    "no_open_offer": 409,
    "documents_closed": 409,
    "merit_list_already_published": 409,
    "invalid_transition": 422,
    "reason_required": 422,
    "score_for_ineligible_application": 422,
    "duplicate_score": 422,
}


@dataclass
class Actor:
    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class AdmissionsError(Exception):
    """A refusal with an HTTP status and the contract's error body {code, message}."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _not_found(what: str) -> AdmissionsError:
    return AdmissionsError(404, "not_found", f"{what} not found")


def _check(rule, *args):
    try:
        return rule(*args)
    except RuleViolationError as v:
        raise AdmissionsError(CODE_STATUS.get(v.code, 422), v.code, v.message) from v


def _audit(
    db: Session, organisation_id: str, actor: str | None, action: str, entity: str, entity_id: str, detail=None
) -> None:
    db.add(
        AuditEntry(
            organisation_id=organisation_id,
            actor=actor,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
        )
    )


def _publish(db: Session, organisation_id: str, actor: str | None, name: str, payload: dict) -> None:
    events.publish(db, f"{MODULE}.{name}", organisation_id, {"organisation_id": organisation_id, **payload}, actor)


def _like(term: str) -> str:
    """A contains-pattern for ilike with the caller's % _ \\ taken literally."""
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------------------------------------------------------------- views


def _current_offer(offers: Sequence[Offer]) -> Offer | None:
    """The open offer if there is one, otherwise the most recent."""
    for offer in offers:
        if offer.status == e.OFFER_OPEN:
            return offer
    return max(offers, key=lambda o: as_utc(o.offered_at), default=None)


def _offer_view(offer: Offer | None, now: datetime) -> dict | None:
    if offer is None:
        return None
    data = offer.to_dict()
    data["status"] = rules.effective_offer_status(offer.status, as_utc(offer.expires_at), now)
    return data


def _views(db: Session, apps: Sequence[Application]) -> list[dict]:
    """Contract Application for each row: documents and offer loaded in two queries, not two per row."""
    ids = [a.id for a in apps]
    documents: dict[str, list[ApplicationDocument]] = {i: [] for i in ids}
    offers: dict[str, list[Offer]] = {i: [] for i in ids}
    if ids:
        for doc in (
            db.query(ApplicationDocument)
            .filter(ApplicationDocument.application_id.in_(ids))
            .order_by(ApplicationDocument.uploaded_at, ApplicationDocument.id)
        ):
            documents[doc.application_id].append(doc)
        for offer in db.query(Offer).filter(Offer.application_id.in_(ids)):
            offers[offer.application_id].append(offer)
    now = utcnow()
    out = []
    for app in apps:
        data = app.to_dict()
        data["documents"] = [d.to_dict() for d in documents[app.id]]
        data["offer"] = _offer_view(_current_offer(offers[app.id]), now)
        out.append(data)
    return out


def _view(db: Session, app: Application) -> dict:
    return _views(db, [app])[0]


def _merit_views(db: Session, lists: Sequence[MeritList]) -> list[dict]:
    ids = [m.id for m in lists]
    entries: dict[str, list[dict]] = {i: [] for i in ids}
    if ids:
        rows = (
            db.query(MeritListEntry, Application.reference_number)
            .join(Application, Application.id == MeritListEntry.application_id)
            .filter(MeritListEntry.merit_list_id.in_(ids))
            .order_by(MeritListEntry.merit_list_id, MeritListEntry.rank)
        )
        for entry, reference_number in rows:
            entries[entry.merit_list_id].append(entry.to_dict() | {"reference_number": reference_number})
    return [m.to_dict() | {"entries": entries[m.id]} for m in lists]


# ---------------------------------------------------------------- lookups


def _get_application(db: Session, organisation_id: str, application_id: str) -> Application:
    app = (
        db.query(Application)
        .filter(Application.organisation_id == organisation_id, Application.id == application_id)
        .one_or_none()
    )
    if app is None:
        raise _not_found("application")
    return app


def _get_merit_list(db: Session, organisation_id: str, merit_list_id: str) -> MeritList:
    merit = (
        db.query(MeritList)
        .filter(MeritList.organisation_id == organisation_id, MeritList.id == merit_list_id)
        .one_or_none()
    )
    if merit is None:
        raise _not_found("merit list")
    return merit


def _open_offer(db: Session, app: Application) -> Offer | None:
    return (
        db.query(Offer)
        .filter(
            Offer.organisation_id == app.organisation_id, Offer.application_id == app.id, Offer.status == e.OFFER_OPEN
        )
        .one_or_none()
    )


# ---------------------------------------------------------------- staff: applications


def list_applications(
    db: Session,
    actor: Actor,
    *,
    programme_id: str | None = None,
    academic_year: str | None = None,
    statuses: Iterable[str] | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    query = db.query(Application).filter(Application.organisation_id == actor.organisation_id)
    if programme_id:
        query = query.filter(Application.programme_id == programme_id)
    if academic_year:
        query = query.filter(Application.academic_year == academic_year)
    if statuses:
        query = query.filter(Application.status.in_(list(statuses)))
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.filter(
            sa.or_(
                Application.applicant_first_name.ilike(pattern, escape="\\"),
                Application.applicant_last_name.ilike(pattern, escape="\\"),
                Application.applicant_email.ilike(pattern, escape="\\"),
                Application.reference_number.ilike(pattern, escape="\\"),
            )
        )
    total = query.count()
    rows = (
        query.order_by(Application.submitted_at.desc(), Application.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": _views(db, rows), "total": total, "page": page, "page_size": page_size}


def get_application(db: Session, actor: Actor, application_id: str) -> dict:
    return _view(db, _get_application(db, actor.organisation_id, application_id))


def change_status(db: Session, actor: Actor, application_id: str, status: str, reason: str) -> dict:
    app = _get_application(db, actor.organisation_id, application_id)
    previous = app.status
    _check(rules.validate_status_change, previous, status, reason)
    now = utcnow()
    if status == e.WITHDRAWN and previous == e.OFFERED:
        offer = _open_offer(db, app)
        if offer is not None:
            offer.status = e.WITHDRAWN
            offer.decided_at = now
    app.status = status
    if status in e.TERMINAL:
        app.decided_at = now
    reason = reason.strip()
    _audit(
        db,
        app.organisation_id,
        actor.user_id,
        "status_changed",
        "application",
        app.id,
        {"previous_status": previous, "status": status, "reason": reason},
    )
    _publish(
        db,
        app.organisation_id,
        actor.user_id,
        "application.status-changed",
        {
            "application_id": app.id,
            "reference_number": app.reference_number,
            "status": status,
            "previous_status": previous,
            "reason": reason,
        },
    )
    db.flush()
    return _view(db, app)


def verify_document(
    db: Session, actor: Actor, application_id: str, document_id: str, verification_status: str, note: str | None
) -> dict:
    """document_id may be the row id or the platform/documents id."""
    app = _get_application(db, actor.organisation_id, application_id)
    doc = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.organisation_id == app.organisation_id,
            ApplicationDocument.application_id == app.id,
            sa.or_(ApplicationDocument.id == document_id, ApplicationDocument.document_id == document_id),
        )
        .order_by(ApplicationDocument.uploaded_at.desc())
        .first()
    )
    if doc is None:
        raise _not_found("document")
    doc.verification_status = verification_status
    doc.verification_note = note
    doc.verified_by = actor.user_id
    doc.verified_at = utcnow()
    _audit(
        db,
        app.organisation_id,
        actor.user_id,
        "document_verified",
        "application_document",
        doc.id,
        {"verification_status": verification_status},
    )
    db.flush()
    return doc.to_dict()


def make_offer(
    db: Session, actor: Actor, application_id: str, note: str | None = None, expires_at: datetime | None = None
) -> dict:
    app = _get_application(db, actor.organisation_id, application_id)
    now = utcnow()
    current = _open_offer(db, app)
    lapsed = (
        current is not None
        and rules.effective_offer_status(current.status, as_utc(current.expires_at), now) == e.OFFER_EXPIRED
    )
    if lapsed:
        # Write the expiry down: the slot the unique open-offer index guards is free again, and an offered
        # application whose offer lapsed is back where an eligible one is, so staff can offer again.
        current.status = e.OFFER_EXPIRED
        current.decided_at = now
        db.flush()
        _audit(db, app.organisation_id, actor.user_id, "offer_expired", "offer", current.id, {"application_id": app.id})
    _check(rules.check_can_offer, e.ELIGIBLE if lapsed else app.status, current is not None and not lapsed)
    offer = Offer(
        organisation_id=app.organisation_id,
        application_id=app.id,
        status=e.OFFER_OPEN,
        note=note,
        expires_at=as_utc(expires_at),  # SQLite stores the wall-clock fields and drops the offset; keep every row UTC
        offered_by=actor.user_id,
    )
    db.add(offer)
    app.status = e.OFFERED
    db.flush()
    _audit(db, app.organisation_id, actor.user_id, "offer_made", "offer", offer.id, {"application_id": app.id})
    _publish(
        db,
        app.organisation_id,
        actor.user_id,
        "offer.made",
        {"application_id": app.id, "reference_number": app.reference_number, "offer_id": offer.id},
    )
    db.flush()
    return _view(db, app)


# ---------------------------------------------------------------- staff: merit lists


def list_merit_lists(
    db: Session, actor: Actor, *, programme_id: str | None = None, academic_year: str | None = None
) -> list[dict]:
    query = db.query(MeritList).filter(MeritList.organisation_id == actor.organisation_id)
    if programme_id:
        query = query.filter(MeritList.programme_id == programme_id)
    if academic_year:
        query = query.filter(MeritList.academic_year == academic_year)
    return _merit_views(db, query.order_by(MeritList.created_at.desc(), MeritList.id).all())


def get_merit_list(db: Session, actor: Actor, merit_list_id: str) -> dict:
    return _merit_views(db, [_get_merit_list(db, actor.organisation_id, merit_list_id)])[0]


def generate_merit_list(
    db: Session,
    actor: Actor,
    *,
    programme_id: str,
    academic_year: str,
    title: str | None = None,
    scores: Iterable[tuple[str, float]] = (),
) -> dict:
    """A draft list of the applications currently eligible for the programme and academic year."""
    pool = (
        db.query(Application.id, Application.submitted_at)
        .filter(
            Application.organisation_id == actor.organisation_id,
            Application.programme_id == programme_id,
            Application.academic_year == academic_year,
            Application.status == e.ELIGIBLE,
        )
        .all()
    )
    score_map = _check(rules.validate_scores, list(scores), {app_id for app_id, _ in pool})
    ranked = rules.rank_entries([(app_id, as_utc(submitted)) for app_id, submitted in pool], score_map)
    merit = MeritList(
        organisation_id=actor.organisation_id,
        programme_id=programme_id,
        academic_year=academic_year,
        title=title,
        status=e.DRAFT,
        created_by=actor.user_id,
    )
    db.add(merit)
    db.flush()
    db.add_all(
        MeritListEntry(
            organisation_id=actor.organisation_id,
            merit_list_id=merit.id,
            application_id=r.application_id,
            rank=r.rank,
            score=r.score,
        )
        for r in ranked
    )
    _audit(
        db,
        actor.organisation_id,
        actor.user_id,
        "merit_list_generated",
        "merit_list",
        merit.id,
        {"entries": len(ranked)},
    )
    db.flush()
    return _merit_views(db, [merit])[0]


def publish_merit_list(db: Session, actor: Actor, merit_list_id: str) -> dict:
    merit = _get_merit_list(db, actor.organisation_id, merit_list_id)
    _check(rules.check_can_publish, merit.status)
    merit.status = e.PUBLISHED
    merit.published_at = utcnow()
    _audit(db, merit.organisation_id, actor.user_id, "merit_list_published", "merit_list", merit.id)
    _publish(
        db,
        merit.organisation_id,
        actor.user_id,
        "merit-list.published",
        {"merit_list_id": merit.id, "programme_id": merit.programme_id, "academic_year": merit.academic_year},
    )
    db.flush()
    return _merit_views(db, [merit])[0]


# ---------------------------------------------------------------- staff: reports and queues


def funnel_report(
    db: Session, actor: Actor, *, programme_id: str | None = None, academic_year: str | None = None
) -> dict:
    """Counts only: no applicant data, so management can read it."""
    query = db.query(Application.status, sa.func.count(Application.id)).filter(
        Application.organisation_id == actor.organisation_id
    )
    if programme_id:
        query = query.filter(Application.programme_id == programme_id)
    if academic_year:
        query = query.filter(Application.academic_year == academic_year)
    counts = dict(query.group_by(Application.status).all())
    return {"programme_id": programme_id, "academic_year": academic_year, **rules.funnel(counts)}


def list_documents(
    db: Session, actor: Actor, *, verification_status: str = e.PENDING, page: int = 1, page_size: int = 50
) -> dict:
    """Oldest upload first. The pending queue leaves out applications already closed: nothing to verify there."""
    query = (
        db.query(
            ApplicationDocument,
            Application.reference_number,
            Application.applicant_first_name,
            Application.applicant_last_name,
        )
        .join(Application, Application.id == ApplicationDocument.application_id)
        .filter(
            ApplicationDocument.organisation_id == actor.organisation_id,
            Application.organisation_id == actor.organisation_id,
            ApplicationDocument.verification_status == verification_status,
        )
    )
    if verification_status == e.PENDING:
        query = query.filter(Application.status.notin_(sorted(e.TERMINAL)))
    total = query.count()
    rows = (
        query.order_by(ApplicationDocument.uploaded_at, ApplicationDocument.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        doc.to_dict() | {"reference_number": reference, "applicant_name": f"{first} {last}"}
        for doc, reference, first, last in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------- public (anonymous applicant)
# organisation_id comes from the org_slug the host resolved. The applicant proves who they are with the
# reference number and email; for applicant actions the audit and event actor is the application itself.


def _reference_settings() -> tuple[str, int]:
    prefix = os.environ.get("ADMISSIONS_REFERENCE_PREFIX", "ADM").strip() or "ADM"
    retries = int(os.environ.get("ADMISSIONS_REFERENCE_COLLISION_RETRIES", "3"))
    return prefix, max(retries, 1)


def _new_reference(db: Session, organisation_id: str) -> str:
    prefix, attempts = _reference_settings()
    for _ in range(attempts):
        reference = rules.generate_reference_number(prefix)
        taken = db.query(Application.id).filter(
            Application.organisation_id == organisation_id, Application.reference_number == reference
        )
        if taken.first() is None:
            return reference
    # The unique index is the final word; reaching here means attempts collisions in a 16.7M space.
    raise AdmissionsError(503, "reference_unavailable", "Could not allocate a reference number; try again")


def _by_reference(db: Session, organisation_id: str, reference_number: str) -> Application:
    app = (
        db.query(Application)
        .filter(
            Application.organisation_id == organisation_id,
            Application.reference_number == reference_number.strip().upper(),
        )
        .one_or_none()
    )
    if app is None:
        raise _not_found("application")
    return app


def _verified(db: Session, organisation_id: str, reference_number: str, email: str) -> Application:
    """The application, if the email matches; 404 for an unknown reference, 403 for the wrong email."""
    app = _by_reference(db, organisation_id, reference_number)
    if rules.normalise_email(email) != app.applicant_email:
        raise AdmissionsError(403, "email_mismatch", "Email does not match this application")
    return app


def submit(
    db: Session,
    organisation_id: str,
    *,
    first_name: str,
    last_name: str,
    email: str,
    programme_id: str,
    academic_year: str,
    phone: str | None = None,
    date_of_birth: date | None = None,
    selection_process_round_id: str | None = None,
    portfolio_item_id: str | None = None,
) -> dict:
    app = Application(
        organisation_id=organisation_id,
        reference_number=_new_reference(db, organisation_id),
        applicant_first_name=first_name.strip(),
        applicant_last_name=last_name.strip(),
        applicant_email=rules.normalise_email(email),
        applicant_phone=phone,
        applicant_date_of_birth=date_of_birth,
        programme_id=programme_id,
        academic_year=academic_year,
        selection_process_round_id=selection_process_round_id,
        portfolio_item_id=portfolio_item_id,
        status=e.SUBMITTED,
        submitted_at=utcnow(),
    )
    db.add(app)
    db.flush()
    _audit(db, organisation_id, app.id, "submitted", "application", app.id)
    _publish(
        db,
        organisation_id,
        app.id,
        "application.submitted",
        {
            "application_id": app.id,
            "reference_number": app.reference_number,
            "programme_id": app.programme_id,
            "academic_year": app.academic_year,
            "applicant_email": app.applicant_email,
        },
    )
    db.flush()
    return _view(db, app)


def track(db: Session, organisation_id: str, reference_number: str, email: str) -> dict:
    """Unlike the other public calls, a wrong email is a 404 here too: tracking reveals nothing either way."""
    try:
        app = _verified(db, organisation_id, reference_number, email)
    except AdmissionsError as exc:
        raise _not_found("application") from exc
    return _view(db, app)


def attach_document(
    db: Session,
    organisation_id: str,
    reference_number: str,
    *,
    email: str,
    type: str,
    document_id: str,
    label: str | None = None,
) -> dict:
    app = _verified(db, organisation_id, reference_number, email)
    _check(rules.check_documents_open, app.status)
    doc = ApplicationDocument(
        organisation_id=organisation_id,
        application_id=app.id,
        type=type,
        document_id=document_id,
        label=label,
        verification_status=e.PENDING,
    )
    db.add(doc)
    db.flush()
    _audit(db, organisation_id, app.id, "document_attached", "application_document", doc.id, {"type": type})
    db.flush()
    return doc.to_dict()


def _decidable_offer(db: Session, app: Application) -> Offer:
    offer = _open_offer(db, app)
    effective = rules.effective_offer_status(offer.status, as_utc(offer.expires_at), utcnow()) if offer else "none"
    _check(rules.check_offer_decidable, effective)
    return offer


def accept_offer(db: Session, organisation_id: str, reference_number: str, *, email: str) -> dict:
    app = _verified(db, organisation_id, reference_number, email)
    offer = _decidable_offer(db, app)
    now = utcnow()
    offer.status = e.ACCEPTED
    offer.decided_at = now
    app.status = e.ACCEPTED
    app.decided_at = now
    _audit(db, organisation_id, app.id, "offer_accepted", "offer", offer.id, {"application_id": app.id})
    _publish(
        db,
        organisation_id,
        app.id,
        "application.accepted",
        {
            "application_id": app.id,
            "reference_number": app.reference_number,
            "programme_id": app.programme_id,
            "academic_year": app.academic_year,
            "applicant_first_name": app.applicant_first_name,
            "applicant_last_name": app.applicant_last_name,
            "applicant_email": app.applicant_email,
        },
    )
    db.flush()
    return _view(db, app)


def decline_offer(
    db: Session, organisation_id: str, reference_number: str, *, email: str, reason: str | None = None
) -> dict:
    app = _verified(db, organisation_id, reference_number, email)
    offer = _decidable_offer(db, app)
    now = utcnow()
    reason = (reason or "").strip()
    offer.status = e.DECLINED
    offer.decided_at = now
    offer.decline_reason = reason or None
    app.status = e.DECLINED
    app.decided_at = now
    _audit(db, organisation_id, app.id, "offer_declined", "offer", offer.id, {"application_id": app.id})
    _publish(
        db,
        organisation_id,
        app.id,
        "application.declined",
        {"application_id": app.id, "reference_number": app.reference_number, "reason": reason},
    )
    db.flush()
    return _view(db, app)
