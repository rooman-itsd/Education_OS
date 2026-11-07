"""Company records (story O1). A company is a record, not a login. An inactive company gets no new drives or openings;
its existing ones continue. The recruiter contact and notes are staff only: they are rendered here and nowhere else."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import rules
from ..infrastructure.models import Company, Drive, Opening
from . import common as c
from .access import Actor
from .errors import conflict


def _counts(db: Session, actor: Actor, company_ids: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Drives and openings of each company that the caller may see."""
    if not company_ids:
        return {}, {}
    drives = db.execute(
        c.count(db, Drive)
        .add_columns(Drive.company_id)
        .where(Drive.company_id.in_(company_ids), Drive.status.in_(c.drive_statuses(actor)))
        .group_by(Drive.company_id)
    ).all()
    openings = db.execute(
        c.count(db, Opening)
        .add_columns(Opening.company_id)
        .where(Opening.company_id.in_(company_ids), Opening.status.in_(c.opening_statuses(actor)))
        .group_by(Opening.company_id)
    ).all()
    return {cid: n for n, cid in drives}, {cid: n for n, cid in openings}


def company_dict(co: Company, drives: int, openings: int) -> dict:
    return {
        "id": co.id,
        "organisation_id": co.organisation_id,
        "name": co.name,
        "industry": co.industry,
        "website": co.website,
        "contact_name": co.contact_name,
        "contact_email": co.contact_email,
        "contact_phone": co.contact_phone,
        "notes": co.notes,
        "active": co.active,
        "drives_count": drives,
        "openings_count": openings,
        "created_at": c.iso(co.created_at),
    }


def _render(db: Session, actor: Actor, co: Company) -> dict:
    drives, openings = _counts(db, actor, [co.id])
    return company_dict(co, drives.get(co.id, 0), openings.get(co.id, 0))


def list_companies(db: Session, actor: Actor, active: bool | None, text: str | None, cursor, limit: int) -> dict:
    query = c.q(db, Company)
    if active is not None:
        query = query.where(Company.active.is_(active))
    needle = rules.clean(text)
    if needle:
        query = query.where(Company.name_key.contains(rules.name_key(needle), autoescape=True))
    result = c.page(db, query.order_by(Company.name_key, Company.id), cursor, limit, lambda co: co)
    rows = result["items"]
    drives, openings = _counts(db, actor, [co.id for co in rows])
    result["items"] = [company_dict(co, drives.get(co.id, 0), openings.get(co.id, 0)) for co in rows]
    return result


def get_company(db: Session, actor: Actor, company_id: str) -> dict:
    return _render(db, actor, c.get(db, Company, company_id, "company"))


def _values(db: Session, co: Company, body: dict) -> None:
    name = c.rule(rules.company_name, body.get("name"))
    website = c.rule(rules.website, body.get("website"))
    email = c.rule(rules.email, body.get("contact_email"))
    key = rules.name_key(name)
    same = c.q(db, Company).where(Company.name_key == key)
    if co.id:
        same = same.where(Company.id != co.id)
    if db.scalar(same) is not None:
        raise conflict("company_exists", "a company with this name exists in your organisation")
    co.name, co.name_key, co.website, co.contact_email = name, key, website, email
    co.industry = rules.clean(body.get("industry"))
    co.contact_name = rules.clean(body.get("contact_name"))
    co.contact_phone = rules.clean(body.get("contact_phone"))
    co.notes = rules.clean(body.get("notes"))
    co.active = True if body.get("active") is None else bool(body["active"])


@c.duplicate_is_409("company_exists", "a company with this name exists in your organisation")
def create_company(db: Session, actor: Actor, body: dict) -> dict:
    co = Company(organisation_id=actor.organisation_id, created_by=actor.user_id, created_at=c.clock())
    _values(db, co, body)
    db.add(co)
    c.audit(db, actor.user_id, "company.created", "company", co)
    db.commit()
    return _render(db, actor, co)


@c.duplicate_is_409("company_exists", "a company with this name exists in your organisation")
def update_company(db: Session, actor: Actor, company_id: str, body: dict) -> dict:
    """A full replacement of the editable fields; `active` omitted means active, as the contract's default says."""
    co = c.get(db, Company, company_id, "company", lock=True)
    was_active = co.active
    _values(db, co, body)
    action = "company.updated"
    if was_active != co.active:
        action = "company.reactivated" if co.active else "company.deactivated"
    c.audit(db, actor.user_id, action, "company", co)
    db.commit()
    return _render(db, actor, co)
