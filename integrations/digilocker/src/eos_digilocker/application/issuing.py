"""issue, replace, withdraw, get_issuance (port certificate-issuance). The document is always recorded first, so a
student can pull it; pushing to their account is an extra that may fail without losing the issuance. A push that
fails stays pending on the row and is sent again when the hub retries."""

from __future__ import annotations

import hashlib
from datetime import date

from eos_core.db import scoped, utcnow
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.errors import AdapterError
from ..domain.models import IssuanceHistory, IssuedDocument, iso
from ..domain.rules import data_xml, normalise_name, search_key_hash, uri_for
from .runtime import Runtime
from .schemas import (
    ConnectionSettings,
    Context,
    DocTypeSetting,
    GetIssuanceInput,
    IssueInput,
    ReplaceInput,
    WithdrawInput,
)


def _doc_type(settings: ConnectionSettings, doc_kind: str, requested: str | None) -> DocTypeSetting:
    candidates = [d for d in settings.doc_types if d.doc_kind == doc_kind]
    if requested:
        candidates = [d for d in candidates if d.doc_type == requested]
        if not candidates:
            raise AdapterError("invalid_request", "provider_doc_type is not one of the connection's doc types")
    if not candidates:
        raise AdapterError("not_configured", f"the connection maps no DigiLocker doc type for {doc_kind}")
    if len(candidates) > 1:
        raise AdapterError("invalid_request", "several doc types are mapped for this kind: send provider_doc_type")
    return candidates[0]


def _check_search_keys(dt: DocTypeSetting, keys: dict) -> None:
    given = {k.strip().casefold() for k in keys}
    wanted = {f.casefold() for f in dt.search_fields}
    if given != wanted or len(given) != len(keys):
        raise AdapterError("invalid_request", "search_keys must be exactly the doc type's search fields")


def _load_pdf(rt: Runtime, ctx: Context, document_id, sha256: str, max_bytes: int) -> None:
    """The adapter never sends or serves a file whose hash differs from the one the caller signed off."""
    content = rt.documents_for(ctx).get(str(ctx.organisation_id), str(document_id))
    if content is None:
        raise AdapterError("invalid_request", "document_id is not a document of this organisation")
    if len(content) > max_bytes:
        raise AdapterError("invalid_request", "the document is larger than this deployment serves")
    if hashlib.sha256(content).hexdigest() != sha256.lower():
        raise AdapterError("invalid_request", "document_sha256 does not match the stored file")


def _find(db: Session, issuance_key: str) -> IssuedDocument | None:
    return db.scalar(
        scoped(db, select(IssuedDocument).where(IssuedDocument.issuance_key == issuance_key), IssuedDocument)
    )


def _history(db: Session, ctx: Context, row: IssuedDocument, event: str, **detail) -> None:
    db.add(
        IssuanceHistory(
            organisation_id=row.organisation_id,
            issued_document_id=row.id,
            action=event,
            detail=detail,
            delivery_id=str(ctx.delivery_id) if ctx.delivery_id else None,
        )
    )


def _creds(ctx: Context) -> tuple[str, str]:
    client_id, client_secret = ctx.secrets.get("push_client_id"), ctx.secrets.get("push_client_secret")
    if not client_id or not client_secret:
        raise AdapterError("not_configured", "push is enabled but push_client_id / push_client_secret are not set")
    return client_id, client_secret


def _dates(valid_from: date | None, valid_to: date | None) -> None:
    if valid_from and valid_to and valid_to < valid_from:
        raise AdapterError("invalid_request", "valid_to is before valid_from")


def _flush_push(rt: Runtime, ctx: Context, db: Session, row: IssuedDocument, description: str) -> None:
    """Send the push the row still owes DigiLocker. On failure the pending action stays and the error is raised."""
    if not row.push_pending:
        return
    cfg = rt.config()
    client = rt.client(ctx, cfg)
    client_id, client_secret = _creds(ctx)
    rt.trust_mock_client(ctx, client_id, client_secret)
    action = row.push_pending
    try:
        client.push_uri(
            client_id=client_id,
            client_secret=client_secret,
            digilocker_id=row.wallet_account_id or "",
            uri=row.uri,
            doc_type=row.doc_type,
            description=description[:100],
            doc_id=row.document_number,
            issue_date=row.issued_on,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            action=action,
        )
    except AdapterError as e:
        _history(db, ctx, row, "push_failed", push=action, code=e.code, provider_code=e.provider_code)
        db.commit()
        raise
    row.push_pending = None
    if action == "D":
        row.wallet_account_id = None  # nothing left to update or delete
    else:
        row.status, row.pushed_at = "pushed", utcnow()
    _history(db, ctx, row, "pushed", push=action)
    db.commit()


def _resolve_account(rt: Runtime, ctx: Context, row: IssuedDocument, mobile: str | None) -> None:
    """Find the holder's DigiLocker id (known from a link, or by mobile number, used once and not kept) and mark
    the push as owed. No account: the document stays available for pull."""
    if row.wallet_account_id:
        row.push_pending = "A"
        return
    if not mobile:
        return
    cfg = rt.config()
    client_id, client_secret = _creds(ctx)
    rt.trust_mock_client(ctx, client_id, client_secret)
    found = rt.client(ctx, cfg).find_account(client_id=client_id, client_secret=client_secret, mobile=mobile)
    if found:
        row.wallet_account_id, row.push_pending = found, "A"


def _output(row: IssuedDocument) -> dict:
    return {"issuance_id": row.id, "status": row.status, "provider_uri": row.uri}


def issue(rt: Runtime, ctx: Context, inp: IssueInput) -> tuple[dict, str | None]:
    settings = rt.settings(ctx)
    cfg = rt.config()
    rt.require_mode(ctx, cfg)
    dt = _doc_type(settings, inp.doc_kind, inp.provider_doc_type)
    _check_search_keys(dt, inp.holder.search_keys)
    _dates(inp.valid_from, inp.valid_to)
    org = str(ctx.organisation_id)
    pepper = rt.pepper(ctx, cfg)
    with rt.db(ctx) as db:
        row = _find(db, inp.issuance_key)
        if row is not None:
            if row.sha256 != inp.document_sha256.lower() or row.document_number != inp.document_number:
                raise AdapterError("conflict", "this issuance_key was used for a different document")
            if row.status == "withdrawn":
                raise AdapterError("conflict", "this issuance was withdrawn")
        else:
            _load_pdf(rt, ctx, inp.document_id, inp.document_sha256, cfg.max_document_bytes)
            clash = db.scalar(
                scoped(
                    db,
                    select(IssuedDocument.id).where(
                        IssuedDocument.doc_kind == inp.doc_kind, IssuedDocument.document_number == inp.document_number
                    ),
                    IssuedDocument,
                )
            )
            if clash:
                raise AdapterError("conflict", "document_number is already issued for this document kind")
            row = IssuedDocument(
                organisation_id=org,
                issuance_key=inp.issuance_key,
                doc_kind=inp.doc_kind,
                doc_type=dt.doc_type,
                uri=uri_for(settings.issuer_id, dt.doc_type, inp.document_number),
                document_id=str(inp.document_id),
                sha256=inp.document_sha256.lower(),
                document_number=inp.document_number,
                person_id=str(inp.holder.person_id),
                title=inp.title,
                holder_name_normalised=normalise_name(inp.holder.name),
                holder_dob=inp.holder.date_of_birth,
                search_key_hash=search_key_hash(pepper, org, dt.doc_type, inp.holder.search_keys),
                wallet_account_id=inp.holder.wallet_account_id,
                data_xml=data_xml(dt.doc_type, inp.data) if inp.data and dt.has_xml else None,
                status="available_for_pull",
                issued_on=inp.issued_on,
                valid_from=inp.valid_from,
                valid_to=inp.valid_to,
            )
            db.add(row)
            try:
                db.flush()
            except IntegrityError as e:
                db.rollback()
                raise AdapterError("conflict", "this document was issued at the same moment by another call") from e
            _history(db, ctx, row, "issued", doc_kind=row.doc_kind, doc_type=row.doc_type)
            db.commit()
        if settings.push_enabled and row.pushed_at is None and not row.push_pending:
            _resolve_account(rt, ctx, row, inp.holder.mobile)
            db.commit()
        if settings.push_enabled:
            _flush_push(rt, ctx, db, row, inp.title)
        return _output(row), row.uri


def replace(rt: Runtime, ctx: Context, inp: ReplaceInput) -> tuple[dict, str | None]:
    settings = rt.settings(ctx)
    cfg = rt.config()
    rt.require_mode(ctx, cfg)
    with rt.db(ctx) as db:
        row = _find(db, inp.issuance_key)
        if row is None or row.status == "withdrawn":
            raise AdapterError("not_found", "no live issuance has this issuance_key")
        if row.sha256 != inp.document_sha256.lower():
            _load_pdf(rt, ctx, inp.document_id, inp.document_sha256, cfg.max_document_bytes)
            row.document_id, row.sha256 = str(inp.document_id), inp.document_sha256.lower()
            dt = next((d for d in settings.doc_types if d.doc_type == row.doc_type), None)
            # A corrected document must not keep serving the old data copy.
            row.data_xml = data_xml(row.doc_type, inp.data) if inp.data and dt and dt.has_xml else None
            if row.wallet_account_id:
                row.push_pending = "U"
            _history(db, ctx, row, "replaced")
            db.commit()
        if settings.push_enabled:
            _flush_push(rt, ctx, db, row, row.title)
        return _output(row), row.uri


def withdraw(rt: Runtime, ctx: Context, inp: WithdrawInput) -> tuple[dict, str | None]:
    settings = rt.settings(ctx)
    rt.require_mode(ctx, rt.config())
    with rt.db(ctx) as db:
        row = _find(db, inp.issuance_key)
        if row is None:
            raise AdapterError("not_found", "no issuance has this issuance_key")
        if row.status != "withdrawn":
            was_pushed = row.pushed_at is not None and row.wallet_account_id
            row.status, row.withdrawn_at = "withdrawn", utcnow()  # the pull lookup stops at once
            row.push_pending = "D" if was_pushed else None
            _history(db, ctx, row, "withdrawn")
            db.commit()
        if settings.push_enabled:
            _flush_push(rt, ctx, db, row, row.title)
        return {"issuance_id": row.id, "status": row.status}, row.uri


def get_issuance(rt: Runtime, ctx: Context, inp: GetIssuanceInput) -> tuple[dict, str | None]:
    with rt.db(ctx) as db:
        row = _find(db, inp.issuance_key)
        if row is None:
            raise AdapterError("not_found", "no issuance has this issuance_key")
        out = _output(row)
        out.update(issued_at=iso(row.created_at), last_pulled_at=iso(row.last_pulled_at))
        return out, row.uri
