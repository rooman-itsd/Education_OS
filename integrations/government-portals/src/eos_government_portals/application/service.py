"""The regulatory-submission port's operations, against the database and platform/documents.

State changes (a package prepared, a filing recorded) publish their outbox event in the same transaction as the row,
which is also the audit trail (platform/audit consumes events). Nothing here ever talks to a portal.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from eos_core import events
from eos_core.db import new_id, scoped
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.models import FILED_STATUSES, Package, PackageFile, iso
from ..domain.port import Result, fail, ok
from ..infrastructure.config import Settings
from ..infrastructure.documents import DocumentStore, StoredDocument
from . import rules, writers
from .catalogue import AUTHORITIES, FORMS, FormSpec, get_form

KEY_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,100}")
REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._/:#-]{0,99}")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
MAX_LIMIT = 200


class InvalidCursorError(ValueError):
    pass


def _uuid(value: Any) -> str | None:
    """A canonical lowercase UUID string, or None when the value is not one (never raises)."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str) and UUID_RE.fullmatch(value):
        return value.lower()
    return None


# ------------------------------------------------------------------ catalogue


def list_forms(settings: Settings, authority: str | None = None) -> Result:
    if authority is not None and authority not in AUTHORITIES:
        return fail("invalid_request", "authority must be aishe, nirf or naac")
    items = [f.describe(settings) for f in FORMS.values() if authority in (None, f.authority)]
    return ok({"items": items})


def capabilities(settings: Settings) -> dict:
    return {
        "forms": [
            {"form_code": f.form_code, "channel": "manual_entry", "format_version": settings.format_for(f.authority)}
            for f in FORMS.values()
        ]
    }


def _resolve(settings: Settings, form_code: Any, period: Any) -> tuple[FormSpec | None, Result | None]:
    """The form, or the port error saying why this adapter cannot prepare it (unknown form, or a cycle it has no format for)."""
    if not isinstance(form_code, str) or len(form_code) > 64:
        return None, fail("invalid_request", "form_code must be a string")
    spec = get_form(form_code)
    if spec is None:
        return None, fail("unsupported", "no such form in the catalogue")
    if not settings.supported(spec.authority):
        return None, fail("unsupported", f"no {spec.authority.upper()} format for the configured cycle")
    if spec.authority in ("aishe", "nirf") and period != settings.format_for(spec.authority):
        return None, fail("unsupported", f"this release prepares only the {settings.format_for(spec.authority)} cycle")
    if not isinstance(period, str) or len(period) > 40:
        return None, fail("invalid_request", "period must be a short string")
    return spec, None


def validate(settings: Settings, form_code: Any, period: Any, data: Any) -> Result:
    spec, err = _resolve(settings, form_code, period)
    if err:
        return err
    issues = rules.validate_data(spec, period, data)
    return ok({"valid": not any(i["severity"] == "error" for i in issues), "issues": issues})


# ------------------------------------------------------------------ prepare


def _load_evidence(organisation_id: str, documents: DocumentStore, evidence: list[dict]) -> dict[int, StoredDocument]:
    found: dict[int, StoredDocument] = {}
    for i, ev in enumerate(evidence):
        doc = documents.get(organisation_id, ev["document_id"])
        if doc is not None:
            found[i] = doc
    return found


def prepare_package(
    db: Session,
    documents: DocumentStore,
    settings: Settings,
    *,
    organisation_id: str,
    package_key: Any,
    form_code: Any,
    period: Any,
    data: Any,
    evidence: Any = None,
    caller: Any = None,
    actor: str | None = None,
) -> Result:
    if not isinstance(package_key, str) or not KEY_PATTERN.fullmatch(package_key):
        return fail("invalid_request", "package_key must be 1 to 100 letters, digits or . _ : -")
    spec, err = _resolve(settings, form_code, period)
    if err:
        return err
    if not isinstance(data, dict):
        return fail("invalid_request", "data must be an object")
    evidence = [] if evidence is None else evidence
    shape = rules.evidence_shape_issues(evidence)
    if shape:
        return fail("invalid_request", f"evidence is malformed at {shape[0]['path']}")
    caller_module = caller_reference = None
    if isinstance(caller, dict):
        caller_module = str(caller.get("module"))[:60] if caller.get("module") else None
        caller_reference = str(caller.get("reference"))[:100] if caller.get("reference") else None

    issues = rules.validate_data(spec, period, data)
    docs = _load_evidence(organisation_id, documents, evidence)
    issues += rules.validate_evidence(
        spec, data, evidence, docs, (settings.max_evidence_file_bytes, settings.max_package_bytes)
    )
    invalid = any(i["severity"] == "error" for i in issues)

    live = db.execute(
        scoped(
            db,
            select(Package).where(Package.package_key == package_key, Package.status != "superseded"),
            Package,
        ).with_for_update()
    ).scalar_one_or_none()
    if live is not None and live.status in FILED_STATUSES:
        return fail("conflict", "this package was already filed and is read-only")

    new = Package(
        id=new_id(),
        organisation_id=organisation_id,
        package_key=package_key,
        form_code=spec.form_code,
        format_version=settings.format_for(spec.authority),
        period=period,
        status="invalid" if invalid else "prepared",
        issues=issues,
        checklist=[] if invalid else writers.checklist_for(spec),
        caller_module=caller_module,
        caller_reference=caller_reference or package_key,
    )
    out_files: list[dict] = []
    rows: list[PackageFile] = []
    if not invalid:
        for f in writers.build_files(spec, period, data, evidence, docs):
            if f.role == "evidence":
                document_id = f.document_id  # the original document, referenced and not copied
            else:
                document_id = documents.put(
                    organisation_id, filename=f.filename, content_type=f.content_type, content=f.content
                )
            rows.append(
                PackageFile(
                    organisation_id=organisation_id,
                    package_id=new.id,
                    document_id=document_id,
                    filename=f.filename,
                    role=f.role,
                    metric=f.metric,
                )
            )
            out_files.append({"document_id": document_id, "filename": f.filename, "role": f.role})
    try:
        if live is not None:
            live.status = "superseded"
            live.superseded_by = new.id
            db.flush()  # the live-key index must see the old one gone before the new one arrives
        db.add(new)
        db.add_all(rows)
        events.publish(
            db,
            "government-portals.package.prepared",
            organisation_id,
            {
                "organisation_id": organisation_id,
                "package_id": new.id,
                "package_key": package_key,
                "form_code": spec.form_code,
                "period": period,
                "status": new.status,
                "superseded_package_id": live.id if live is not None else None,
            },
            actor=actor,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        return fail("conflict", "another package for this key was being prepared; try again")
    return ok(
        {
            "package_id": new.id,
            "status": new.status,
            "files": out_files,
            "checklist": new.checklist,
            "issues": issues,
        }
    )


# ------------------------------------------------------------------ filing


def _get(db: Session, package_id: str, lock: bool = False) -> Package | None:
    q = scoped(db, select(Package).where(Package.id == package_id), Package)
    return db.execute(q.with_for_update() if lock else q).scalar_one_or_none()


def _files(db: Session, package_id: str) -> list[PackageFile]:
    q = scoped(db, select(PackageFile).where(PackageFile.package_id == package_id), PackageFile)
    return list(db.execute(q.order_by(PackageFile.filename)).scalars())


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def record_manual_submission(
    db: Session,
    documents: DocumentStore,
    *,
    organisation_id: str,
    package_id: Any,
    submitted_on: Any,
    submitted_by: Any,
    portal_reference: Any,
    acknowledgement_document_id: Any = None,
    actor: str | None = None,
) -> Result:
    pid = _uuid(package_id)
    if pid is None:
        return fail("invalid_request", "package_id must be a uuid")
    by = _uuid(submitted_by)
    on = _as_date(submitted_on)
    if by is None:
        return fail("invalid_request", "submitted_by must be a uuid")
    if on is None or on < date(2000, 1, 1) or on > datetime.now(UTC).date() + timedelta(days=1):
        return fail("invalid_request", "submitted_on must be a date between 2000-01-01 and today")
    if not isinstance(portal_reference, str) or not REFERENCE_PATTERN.fullmatch(portal_reference.strip()):
        return fail("invalid_request", "portal_reference must be 1 to 100 letters, digits or . _ / : # - and spaces")
    ack = None
    if acknowledgement_document_id is not None:
        ack = _uuid(acknowledgement_document_id)
        if ack is None:
            return fail("invalid_request", "acknowledgement_document_id must be a uuid")
        if documents.get(organisation_id, ack) is None:
            return fail("invalid_request", "the acknowledgement document does not exist")
    pkg = _get(db, pid, lock=True)
    if pkg is None:
        return fail("not_found", "no such package")
    if pkg.status != "prepared":
        return fail("conflict", f"a package that is {pkg.status} cannot be recorded as filed")
    pkg.status = "acknowledged" if ack else "uploaded_manually"
    pkg.submitted_on = on
    pkg.submitted_by = by
    pkg.portal_reference = portal_reference.strip()
    pkg.acknowledgement_document_id = ack
    events.publish(
        db,
        "government-portals.package.filed",
        organisation_id,
        {
            "organisation_id": organisation_id,
            "package_id": pkg.id,
            "form_code": pkg.form_code,
            "period": pkg.period,
            "status": pkg.status,
            "portal_reference": pkg.portal_reference,
            "submitted_on": on.isoformat(),
            "submitted_by": by,
        },
        actor=actor or by,
    )
    db.commit()
    return ok({"package_id": pkg.id, "status": pkg.status}, provider_reference=pkg.portal_reference)


def submit(db: Session, *, package_id: Any) -> Result:
    """No portal has an API, so every form answers manual_action_required once the package exists (the checklist is
    on get_package). The day a portal opens one, its form gets channel api and a client here."""
    pid = _uuid(package_id)
    if pid is None:
        return fail("invalid_request", "package_id must be a uuid")
    pkg = _get(db, pid)
    if pkg is None:
        return fail("not_found", "no such package")
    return fail("manual_action_required", "no API for this portal: a person files the package; see its checklist")


# ------------------------------------------------------------------ reads


def detail(db: Session, pkg: Package) -> dict:
    return {
        **pkg.summary(),
        "files": [f.to_dict() for f in _files(db, pkg.id)],
        "checklist": pkg.checklist,
        "issues": pkg.issues,
        "submitted_by": pkg.submitted_by,
        "acknowledgement_document_id": pkg.acknowledgement_document_id,
    }


def get_package(db: Session, package_id: Any) -> Result:
    pid = _uuid(package_id)
    if pid is None:
        return fail("invalid_request", "package_id must be a uuid")
    pkg = _get(db, pid)
    if pkg is None:
        return fail("not_found", "no such package")
    d = detail(db, pkg)
    return ok(
        {k: d[k] for k in ("form_code", "period", "status", "files", "checklist", "portal_reference", "submitted_on")}
        | {"package_id": pkg.id}
    )


def get_detail(db: Session, package_id: str) -> dict | None:
    pid = _uuid(package_id)
    pkg = _get(db, pid) if pid else None
    return detail(db, pkg) if pkg else None


def _encode_cursor(pkg: Package) -> str:
    raw = json.dumps([iso(pkg.created_at), pkg.id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        if len(cursor) > 200:
            raise ValueError
        stamp, pid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        when = datetime.fromisoformat(stamp)
        if not isinstance(pid, str) or _uuid(pid) is None:
            raise ValueError
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError) as e:
        raise InvalidCursorError("invalid cursor") from e
    when = when.astimezone(UTC) if when.tzinfo else when
    return when, pid


def list_packages(
    db: Session,
    *,
    form_code: str | None = None,
    period: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict:
    limit = max(1, min(int(limit), MAX_LIMIT))
    q = scoped(db, select(Package), Package)
    if form_code:
        q = q.where(Package.form_code == form_code)
    if period:
        q = q.where(Package.period == period)
    if status:
        q = q.where(Package.status == status)
    if cursor:
        when, pid = _decode_cursor(cursor)
        if db.get_bind().dialect.name == "sqlite":
            when = when.replace(tzinfo=None)
        q = q.where(or_(Package.created_at < when, and_(Package.created_at == when, Package.id < pid)))
    rows = list(db.execute(q.order_by(Package.created_at.desc(), Package.id.desc()).limit(limit + 1)).scalars())
    page = rows[:limit]
    return {
        "items": [p.summary() for p in page],
        "next_cursor": _encode_cursor(page[-1]) if len(rows) > limit else None,
    }
