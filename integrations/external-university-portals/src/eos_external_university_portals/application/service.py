"""The inter-institution-records port's operations, against the database and platform/documents.

State changes publish their outbox event in the same transaction as the row, which is also the audit trail
(platform/audit consumes events). The transcript is read, written and forgotten: only the exchange row survives, with
the file's document id and hash, and what could not be mapped by position and reason.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from eos_core import events
from eos_core.db import new_id, scoped
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.models import Exchange, iso
from ..domain.port import Result, fail, ok
from ..infrastructure.config import Settings
from ..infrastructure.documents import Courier, CourierError, DocumentStore
from . import transcript as tr
from .formats import csvfmt, edc, elmo
from .formats.countries import ALPHA3

KEY_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,100}")
REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._/:#-]{0,99}")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
PROVIDER_FORMATS = {"file": ("pdf", "csv"), "elmo": ("elmo_xml",), "edc": ("edc_jsonld",)}
CHANNELS = ("download", "email", "partner_portal", "api")
MAX_LIMIT = 200
MAX_PDF_BYTES = 52_428_800
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "elmo_xml": "application/xml",
    "edc_jsonld": "application/ld+json",
}
EXTENSIONS = {"pdf": "pdf", "csv": "csv", "elmo_xml": "xml", "edc_jsonld": "jsonld"}


class InvalidCursorError(ValueError):
    pass


@dataclass(frozen=True)
class Partner:
    """A partner institution: one integration-hub connection's non-secret settings."""

    partner_id: str
    country: str
    channel: str
    name: str | None = None
    institution_code: str | None = None
    formats_out: tuple[str, ...] = ()
    formats_in: tuple[str, ...] = ()
    email: str | None = None
    portal_url: str | None = None
    csv_mapping: dict[str, str] = field(default_factory=dict)
    grade_conversion: dict[str, Any] = field(default_factory=dict)
    credit_conversion: dict[str, Any] = field(default_factory=dict)

    def accepts(self, direction: str, fmt: str, provider: str) -> bool:
        wanted = self.formats_out if direction == "out" else self.formats_in
        return fmt in PROVIDER_FORMATS[provider] and (not wanted or fmt in wanted)


def _uuid(value: Any) -> str | None:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str) and UUID_RE.fullmatch(value):
        return value.lower()
    return None


def _detail(prefix: str, issues: list[dict]) -> str:
    shown = ", ".join(f"{i['path']} ({i['code']})" for i in issues[:5])
    more = f" and {len(issues) - 5} more" if len(issues) > 5 else ""
    return f"{prefix}: {shown}{more}"


def _check_common(
    partner: Partner, exchange_key: Any, partner_id: Any, fmt: Any, provider: str, direction: str
) -> Result | None:
    if not isinstance(exchange_key, str) or not KEY_PATTERN.fullmatch(exchange_key):
        return fail("invalid_request", "exchange_key must be 1 to 100 letters, digits or . _ : -")
    if partner_id != partner.partner_id:
        return fail("invalid_request", "partner_id is not the partner of this connection")
    if not isinstance(fmt, str) or fmt not in tr.FORMATS:
        return fail("invalid_request", "format must be pdf, csv, elmo_xml or edc_jsonld")
    if not partner.accepts(direction, fmt, provider):
        return fail("unsupported", f"this connection does not exchange {fmt} in this direction")
    return None


def list_partners(partner: Partner, provider: str) -> Result:
    formats = list(PROVIDER_FORMATS[provider])
    return ok(
        {
            "items": [
                {
                    "partner_id": partner.partner_id,
                    "name": partner.name,
                    "country": partner.country,
                    "formats": {
                        "out": [f for f in formats if partner.accepts("out", f, provider)],
                        "in": [f for f in formats if partner.accepts("in", f, provider)],
                    },
                    "channels": [partner.channel],
                    "grade_conversion": partner.grade_conversion,
                }
            ]
        }
    )


def capabilities(provider: str) -> dict:
    formats = list(PROVIDER_FORMATS[provider])
    return {
        "formats_out": formats,
        "formats_in": [f for f in formats if f != "pdf"],
        "channels": ["download", "email", "partner_portal"],
        "signed_exports": False,
    }


# ------------------------------------------------------------------ export


def _generate(fmt: str, transcript: dict, partner: Partner, credential_id: str, clock: datetime) -> bytes:
    if fmt == "csv":
        return csvfmt.write(transcript, partner.csv_mapping)
    if fmt == "elmo_xml":
        return elmo.write(transcript, clock)
    return edc.write(transcript, credential_id, clock)


def _format_issues(fmt: str, transcript: dict) -> list[dict]:
    if fmt == "elmo_xml" and "url" not in transcript["issuer"]:
        return [{"path": "issuer.url", "code": "required"}]
    if fmt == "edc_jsonld":
        issues = []
        if transcript["issuer"]["country"] not in ALPHA3:
            issues.append({"path": "issuer.country", "code": "unknown_country"})
        if not any(e["status"] == "passed" for e in transcript["entries"]):
            issues.append({"path": "entries", "code": "no_passed_entries"})
        return issues
    return []


def _find(db: Session, key: str, direction: str) -> Exchange | None:
    q = scoped(db, select(Exchange).where(Exchange.exchange_key == key, Exchange.direction == direction), Exchange)
    return db.execute(q.with_for_update()).scalar_one_or_none()


def _publish(db: Session, name: str, ex: Exchange, actor: str | None = None, **extra: Any) -> None:
    events.publish(
        db,
        f"external-university-portals.exchange.{name}",
        ex.organisation_id,
        {
            "organisation_id": ex.organisation_id,
            "exchange_id": ex.id,
            "partner_id": ex.partner_id,
            "direction": ex.direction,
            "format": ex.format,
            "channel": ex.channel,
            "status": ex.status,
            **extra,
        },
        actor=actor,
    )


def export_records(
    db: Session,
    documents: DocumentStore,
    settings: Settings,
    partner: Partner,
    *,
    provider: str,
    organisation_id: str,
    connection_id: str | None,
    exchange_key: Any,
    partner_id: Any,
    format: Any,
    transcript: Any,
    document_id: Any = None,
    clock: datetime,
    secrets: dict | None = None,
    caller: Any = None,
) -> Result:
    if (err := _check_common(partner, exchange_key, partner_id, format, provider, "out")) is not None:
        return err
    if partner.country in settings.restricted_countries:
        return fail("rejected", "delivery to this partner's country is not allowed by configuration")
    if secrets and secrets.get("signing_key"):
        return fail(
            "unsupported",
            "signed exports are not available in this release; remove the signing key from the connection",
        )
    issues = tr.validate(transcript)
    if not issues:
        issues = _format_issues(format, transcript)
    if issues:
        return fail("invalid_request", _detail("the transcript is not valid", issues))

    existing = _find(db, exchange_key, "outbound")
    if existing is not None:
        if existing.partner_id == partner.partner_id and existing.format == format:
            return ok(
                {
                    "exchange_id": existing.id,
                    "document_id": existing.document_id,
                    "format": existing.format,
                    "sha256": existing.sha256,
                }
            )
        return fail("conflict", "this exchange_key was used for another partner or format")

    person_id = _uuid(transcript["learner"].get("person_id"))
    if format == "pdf":
        pdf_id = _uuid(document_id)
        if pdf_id is None:
            return fail("invalid_request", "document_id must be the uuid of the signed PDF")
        doc = documents.get(organisation_id, pdf_id)
        if doc is None or len(doc.content) > MAX_PDF_BYTES or not doc.content.startswith(b"%PDF-"):
            return fail("invalid_request", "document_id is not a PDF this organisation holds")
        content, stored_id = doc.content, pdf_id  # the caller's own file is referenced, not copied
    else:
        credential_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:eos:{organisation_id}:{exchange_key}"))
        content = _generate(format, transcript, partner, credential_id, clock)
        stored_id = None
    sha = hashlib.sha256(content).hexdigest()
    if stored_id is None:
        stored_id = documents.put(
            organisation_id,
            filename=f"transcript-{exchange_key}.{EXTENSIONS[format]}"[:200],
            content_type=CONTENT_TYPES[format],
            content=content,
        )
    ex = Exchange(
        id=new_id(),
        organisation_id=organisation_id,
        connection_id=connection_id,
        exchange_key=exchange_key,
        partner_id=partner.partner_id,
        partner_name=partner.name,
        direction="outbound",
        person_id=person_id,
        format=format,
        channel=partner.channel,
        status="prepared",
        document_id=stored_id,
        sha256=sha,
        unmapped=[],
        caller_module=str(caller["module"])[:60] if isinstance(caller, dict) and caller.get("module") else None,
        caller_reference=str(caller["reference"])[:100]
        if isinstance(caller, dict) and caller.get("reference")
        else exchange_key,
    )
    try:
        db.add(ex)
        _publish(db, "exported", ex)
        db.commit()
    except IntegrityError:
        db.rollback()
        return fail("conflict", "another export for this key was running; try again")
    return ok({"exchange_id": ex.id, "document_id": stored_id, "format": format, "sha256": sha})


# ------------------------------------------------------------------ send and manual delivery


def _get(db: Session, exchange_id: Any, lock: bool = False) -> Exchange | None:
    pid = _uuid(exchange_id)
    if pid is None:
        return None
    q = scoped(db, select(Exchange).where(Exchange.id == pid), Exchange)
    return db.execute(q.with_for_update() if lock else q).scalar_one_or_none()


def send_records(
    db: Session,
    settings: Settings,
    partner: Partner,
    courier: Courier | None,
    *,
    mode: str,
    exchange_id: Any,
    message: Any = None,
    clock: datetime,
) -> Result:
    if _uuid(exchange_id) is None:
        return fail("invalid_request", "exchange_id must be a uuid")
    if message is not None and (not isinstance(message, str) or len(message) > 2000):
        return fail("invalid_request", "message must be text of at most 2000 characters")
    ex = _get(db, exchange_id, lock=True)
    if ex is None or ex.direction != "outbound" or ex.partner_id != partner.partner_id:
        return fail("not_found", "no such outbound exchange for this partner")
    if ex.status not in ("prepared", "manual_action_required"):
        return fail("conflict", f"an exchange that is {ex.status} cannot be sent")
    if partner.country in settings.restricted_countries:
        return fail("rejected", "delivery to this partner's country is not allowed by configuration")
    channel = partner.channel
    if channel == "api":
        return fail("unsupported", "no API channel exists for partners in this release")
    if channel in ("download", "partner_portal"):
        ex.status, ex.channel = "manual_action_required", channel
        db.commit()
        where = "the partner's portal" if channel == "partner_portal" else "the partner"
        return fail(
            "manual_action_required",
            f"download document {ex.document_id} and send or upload it to {where}, then record the delivery",
        )
    # email: a time-limited link, never an attachment
    if not partner.email:
        return fail("not_configured", "the partner has no email address")
    if mode != "live":
        return ok(
            {
                "exchange_id": ex.id,
                "status": ex.status,
                "channel": "email",
                "provider_reference": f"{mode}-not-delivered",
            }
        )
    if courier is None:
        return fail("not_configured", "no platform/notification client")
    try:
        reference = courier.send_email_with_link(
            ex.organisation_id,
            to=partner.email,
            subject="Academic records transfer",
            message=message or "",
            document_id=ex.document_id,
            expires_in_hours=settings.link_ttl_hours,
        )
    except CourierError as e:
        return fail("transport_unavailable" if e.retryable else "rejected", "notification could not send the message")
    ex.status, ex.channel = "sent", "email"
    ex.link_expires_at = clock + timedelta(hours=settings.link_ttl_hours)
    _publish(db, "sent", ex, reference=str(reference)[:100])
    db.commit()
    return ok(
        {"exchange_id": ex.id, "status": "sent", "channel": "email", "provider_reference": str(reference)[:100]},
        provider_reference=str(reference)[:100],
    )


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


def record_manual_delivery(
    db: Session,
    *,
    organisation_id: str,
    partner: Partner,
    exchange_id: Any,
    delivered_on: Any,
    delivered_by: Any,
    partner_reference: Any,
    today: date,
) -> Result:
    if _uuid(exchange_id) is None:
        return fail("invalid_request", "exchange_id must be a uuid")
    by = _uuid(delivered_by)
    on = _as_date(delivered_on)
    if by is None:
        return fail("invalid_request", "delivered_by must be a uuid")
    if on is None or on < date(2000, 1, 1) or on > today + timedelta(days=1):
        return fail("invalid_request", "delivered_on must be a date between 2000-01-01 and today")
    if not isinstance(partner_reference, str) or not REFERENCE_PATTERN.fullmatch(partner_reference.strip()):
        return fail("invalid_request", "partner_reference must be 1 to 100 letters, digits or . _ / : # - and spaces")
    ex = _get(db, exchange_id, lock=True)
    if ex is None or ex.partner_id != partner.partner_id:
        return fail("not_found", "no such exchange for this partner")
    if ex.direction != "outbound" or ex.status not in ("prepared", "manual_action_required"):
        return fail("conflict", f"an exchange that is {ex.status} ({ex.direction}) cannot be recorded as delivered")
    ex.status, ex.delivered_on, ex.delivered_by, ex.partner_reference = (
        "delivered_manually",
        on,
        by,
        partner_reference.strip(),
    )
    _publish(db, "delivered", ex, actor=by, delivered_on=on.isoformat(), partner_reference=ex.partner_reference)
    db.commit()
    return ok({"exchange_id": ex.id, "status": ex.status}, provider_reference=ex.partner_reference)


# ------------------------------------------------------------------ import


def import_records(
    db: Session,
    documents: DocumentStore,
    settings: Settings,
    partner: Partner,
    *,
    provider: str,
    organisation_id: str,
    connection_id: str | None,
    exchange_key: Any,
    partner_id: Any,
    format: Any,
    document_id: Any,
    caller: Any = None,
) -> Result:
    if (err := _check_common(partner, exchange_key, partner_id, format, provider, "in")) is not None:
        return err
    if format == "pdf":
        return fail("unsupported", "a PDF transcript is kept and keyed in by a person, not parsed")
    doc_id = _uuid(document_id)
    if doc_id is None:
        return fail("invalid_request", "document_id must be a uuid")
    doc = documents.get(organisation_id, doc_id)
    if doc is None:
        return fail("invalid_request", "document_id is not a document this organisation holds")
    if len(doc.content) > settings.max_import_bytes:
        return fail("invalid_request", "the file is larger than the import limit")
    sha = hashlib.sha256(doc.content).hexdigest()

    existing = _find(db, exchange_key, "inbound")
    if existing is not None and (
        existing.partner_id != partner.partner_id
        or existing.format != format
        or (existing.status == "parsed" and existing.sha256 != sha)
    ):
        return fail("conflict", "this exchange_key was used for another partner, format or file")

    reason: str | None = None
    result: tuple[dict, list[dict], str] | None = None
    try:
        if format == "elmo_xml":
            result = elmo.read(doc.content)
        elif format == "edc_jsonld":
            result = edc.read(doc.content)
        else:
            result = csvfmt.read(doc.content, partner.csv_mapping)
    except (elmo.ElmoError, edc.EdcError, csvfmt.CsvError) as e:
        reason = str(e)
    except (ValueError, RecursionError):
        reason = "the file could not be read"

    ex = existing or Exchange(
        id=new_id(), organisation_id=organisation_id, connection_id=connection_id, exchange_key=exchange_key,
        partner_id=partner.partner_id, partner_name=partner.name, direction="inbound", format=format,
        caller_module=str(caller["module"])[:60] if isinstance(caller, dict) and caller.get("module") else None,
        caller_reference=str(caller["reference"])[:100] if isinstance(caller, dict) and caller.get("reference") else exchange_key,
        status="received", unmapped=[],
    )  # fmt: skip
    ex.document_id, ex.sha256 = doc_id, sha
    if result is None:
        ex.status, ex.integrity, ex.unmapped = "rejected", None, [{"position": "$", "reason": "unreadable"}]
    else:
        transcript, unmapped, integrity = result
        if not transcript.get("issuer", {}).get("institution_name"):
            transcript["issuer"] = {
                "institution_name": partner.name or "",
                "institution_code": partner.institution_code or "",
                "country": partner.country,
            }
        ex.status, ex.integrity, ex.unmapped = "parsed", integrity, unmapped[:500]
    try:
        if existing is None:
            db.add(ex)
        _publish(db, "imported" if result else "rejected", ex, integrity=ex.integrity, unmapped_count=len(ex.unmapped))
        db.commit()
    except IntegrityError:
        db.rollback()
        return fail("conflict", "another import for this key was running; try again")
    if result is None:
        return fail("invalid_request", f"the file could not be read: {reason}")
    return ok({"exchange_id": ex.id, "transcript": transcript, "unmapped": ex.unmapped, "integrity": ex.integrity})


# ------------------------------------------------------------------ reads


def get_detail(db: Session, exchange_id: str) -> dict | None:
    ex = _get(db, exchange_id)
    return ex.detail() if ex else None


def _encode_cursor(ex: Exchange) -> str:
    return base64.urlsafe_b64encode(json.dumps([iso(ex.created_at), ex.id]).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        if len(cursor) > 200:
            raise ValueError
        stamp, eid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        when = datetime.fromisoformat(stamp)
        if not isinstance(eid, str) or _uuid(eid) is None:
            raise ValueError
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError) as e:
        raise InvalidCursorError("invalid cursor") from e
    return (when.astimezone(UTC) if when.tzinfo else when), eid


def list_exchanges(
    db: Session,
    *,
    partner_id: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    person_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict:
    limit = max(1, min(int(limit), MAX_LIMIT))
    q = scoped(db, select(Exchange), Exchange)
    for column, value in (
        (Exchange.partner_id, partner_id),
        (Exchange.direction, direction),
        (Exchange.status, status),
        (Exchange.person_id, person_id),
    ):
        if value:
            q = q.where(column == value)
    if cursor:
        when, eid = _decode_cursor(cursor)
        if db.get_bind().dialect.name == "sqlite":
            when = when.replace(tzinfo=None)
        q = q.where(or_(Exchange.created_at < when, and_(Exchange.created_at == when, Exchange.id < eid)))
    rows = list(db.execute(q.order_by(Exchange.created_at.desc(), Exchange.id.desc()).limit(limit + 1)).scalars())
    page = rows[:limit]
    return {
        "items": [e.summary() for e in page],
        "next_cursor": _encode_cursor(page[-1]) if len(rows) > limit else None,
    }
