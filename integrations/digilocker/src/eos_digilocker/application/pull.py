"""The Pull Issuer API: DigiLocker calls us (through the hub's provider-request route) with a Pull URI Request when
a student searches for a document, and a Pull Doc Request when they open it. XML over HTTPS POST, the format of the
Pull API Specification v1.3 (field names to be confirmed against the spec DigiLocker sends at onboarding).

Both answer from our own records within DigiLocker's timeout. A request is accepted only with the right issuer id, a
valid keyhash (when the connection has an issuer API key) and a timestamp inside the tolerance. Matching never uses
Aadhaar: the UID element is not read."""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from xml.etree import ElementTree

from eos_core.db import scoped, utcnow
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.errors import AdapterError
from ..domain.models import SERVED_STATUSES, IssuedDocument, PullRequestLog
from ..domain.rules import IST, keyhash_ok, normalise_name, parse_dob, parse_ts, parse_xml, search_key_hash
from .runtime import Runtime
from .schemas import ConnectionSettings, Context, DocTypeSetting

CHANNELS = ("pull-uri", "pull-doc")
TXN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
KNOWN = {"doctype", "digilockerid", "uid", "fullname", "dob", "photo", "trackingid", "mobile", "email", "gender", "uri"}
UDF = re.compile(r"^udf([1-9][0-9]?)$")


def _plain(status: int, text: str) -> dict:
    return {"status": status, "content_type": "text/plain", "body": text.encode(), "notifications": []}


def _text(el: ElementTree.Element | None, tag: str) -> str:
    if el is None:
        return ""
    for child in el:
        if child.tag.split("}")[-1].casefold() == tag.casefold():
            return (child.text or "").strip()
    return ""


def _response(root_tag: str, txn: str, ts: str, status: str, details: dict[str, str] | None = None) -> bytes:
    root = ElementTree.Element(root_tag, {"ver": "1.0", "ts": ts, "txn": txn})
    ElementTree.SubElement(root, "ResponseStatus", {"Status": status, "ts": ts, "txn": txn})
    if details:
        box = ElementTree.SubElement(root, "DocDetails")
        for key, value in details.items():
            ElementTree.SubElement(box, key).text = value
    return b'<?xml version="1.0" encoding="UTF-8"?>' + ElementTree.tostring(root, encoding="utf-8")


def _log(db: Session, org: str, txn: str, channel: str, doc_type: str | None, row: IssuedDocument | None) -> None:
    """One log row per (channel, txn): DigiLocker may redeliver. No search values, no Aadhaar."""
    exists = db.scalar(
        scoped(
            db,
            select(PullRequestLog.id).where(PullRequestLog.txn == txn, PullRequestLog.channel == channel),
            PullRequestLog,
        )
    )
    if exists:
        return
    db.add(
        PullRequestLog(
            organisation_id=org,
            txn=txn,
            channel=channel,
            doc_type=doc_type,
            matched=row is not None,
            issued_document_id=row.id if row else None,
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()


def _pdf(rt: Runtime, ctx: Context, row: IssuedDocument, max_bytes: int) -> bytes | None:
    """The stored file, only if it is still the exact file that was issued."""
    content = rt.documents_for(ctx).get(str(ctx.organisation_id), row.document_id)
    if content is None or len(content) > max_bytes or hashlib.sha256(content).hexdigest() != row.sha256:
        return None
    return content


def _search_values(details: ElementTree.Element, dt: DocTypeSetting) -> dict[str, str] | None:
    """The doc type's search fields from the request: an element named like the field, or UDF1..n in the order the
    fields are configured. None when one is missing."""
    udfs: dict[int, str] = {}
    for child in details:
        m = UDF.match(child.tag.split("}")[-1].casefold())
        if m:
            udfs[int(m.group(1))] = (child.text or "").strip()
    values = {}
    for i, field in enumerate(dt.search_fields, start=1):
        value = _text(details, field) or udfs.get(i, "")
        if not value or len(value) > 100:
            return None
        values[field] = value
    return values


def _pull_uri(
    rt: Runtime, ctx: Context, db: Session, settings: ConnectionSettings, root, txn: str, fmt: str, now_ts: str
) -> tuple[bytes, IssuedDocument | None]:
    cfg = rt.config()
    details = next((c for c in root if c.tag.split("}")[-1] == "DocDetails"), None)
    doc_type = _text(details, "DocType")[:40]
    dt = next((d for d in settings.doc_types if d.doc_type == doc_type), None)
    no_match = _response("PullURIResponse", txn, now_ts, "0")
    if details is None or dt is None:
        return no_match, None
    values = _search_values(details, dt)
    name, dob_text = _text(details, "FullName"), _text(details, "DOB")
    if values is None or not name:
        return no_match, None
    dob = parse_dob(dob_text)
    if dob_text and dob is None:
        return no_match, None
    org = str(ctx.organisation_id)
    h = search_key_hash(rt.pepper(ctx, cfg), org, dt.doc_type, values)
    candidates = db.scalars(
        scoped(
            db,
            select(IssuedDocument).where(
                IssuedDocument.doc_type == dt.doc_type,
                IssuedDocument.search_key_hash == h,
                IssuedDocument.status.in_(SERVED_STATUSES),
            ),
            IssuedDocument,
        ).limit(10)
    )
    matches = [
        r
        for r in candidates
        if r.holder_name_normalised == normalise_name(name)
        and (r.holder_dob is None or (dob is not None and r.holder_dob == dob))
    ]
    if len(matches) != 1:  # none or several: never guess
        return no_match, None
    row = matches[0]
    out = {"URI": row.uri}
    if dt.send_pdf_on_uri_request and fmt in ("pdf", "both"):
        pdf = _pdf(rt, ctx, row, cfg.max_document_bytes)
        if pdf is None:
            return no_match, None
        out["DocContent"] = base64.b64encode(pdf).decode()
    if row.data_xml and fmt in ("xml", "both"):
        out["DataContent"] = base64.b64encode(row.data_xml.encode()).decode()
    return _response("PullURIResponse", txn, now_ts, "1", out), row


def _pull_doc(
    rt: Runtime, ctx: Context, db: Session, root, txn: str, fmt: str, now_ts: str
) -> tuple[bytes, IssuedDocument | None]:
    cfg = rt.config()
    details = next((c for c in root if c.tag.split("}")[-1] == "DocDetails"), None)
    uri = _text(details, "URI")[:200]
    row = (
        db.scalar(scoped(db, select(IssuedDocument).where(IssuedDocument.uri == uri), IssuedDocument)) if uri else None
    )
    if row is None or row.status not in SERVED_STATUSES:  # a withdrawn document is gone
        return _response("PullDocResponse", txn, now_ts, "0"), None
    pdf = _pdf(rt, ctx, row, cfg.max_document_bytes)
    if pdf is None:
        return _response("PullDocResponse", txn, now_ts, "0"), None
    out = {}
    if fmt in ("pdf", "both"):
        out["DocContent"] = base64.b64encode(pdf).decode()
    if row.data_xml and fmt in ("xml", "both"):
        out["DataContent"] = base64.b64encode(row.data_xml.encode()).decode()
    return _response("PullDocResponse", txn, now_ts, "1", out), row


def handle_provider_request(rt: Runtime, ctx: Context, channel: str, raw_body: bytes) -> dict:
    """Never raises: every outcome is an HTTP answer DigiLocker can read. Adds `notifications` (the port's
    document_pulled) to the contract's {status, content_type, body}, for the hub to publish."""
    if channel not in CHANNELS:
        return _plain(404, "unknown channel")
    cfg = rt.config()
    try:
        settings = rt.settings(ctx)
        rt.require_mode(ctx, cfg)
        api_key = ctx.secrets.get("issuer_api_key", "")
        if not api_key and ctx.mode != "mock":
            return _plain(503, "connection is not configured")
        expected_root = "PullURIRequest" if channel == "pull-uri" else "PullDocRequest"
        try:
            root = parse_xml(raw_body)
        except ValueError:
            return _plain(400, "malformed request")
        if root.tag.split("}")[-1] != expected_root:
            return _plain(400, "malformed request")
        ts, txn = root.get("ts", ""), root.get("txn", "")
        fmt = (root.get("format") or "both").lower()
        if fmt not in ("xml", "pdf", "both") or not TXN.match(txn):
            return _plain(400, "malformed request")
        now = rt.clock()
        sent = parse_ts(ts)
        if (
            root.get("orgId") != settings.issuer_id
            or sent is None
            or abs((now - sent).total_seconds()) > cfg.pull_tolerance_s
            or (api_key and not keyhash_ok(api_key, ts, root.get("keyhash")))
        ):
            return _plain(401, "unauthorised")
        now_ts = now.astimezone(IST).strftime("%Y-%m-%dT%H:%M:%S+05:30")
        with rt.db(ctx) as db:
            if channel == "pull-uri":
                body, row = _pull_uri(rt, ctx, db, settings, root, txn, fmt, now_ts)
                doc_type = _text(next((c for c in root if c.tag.split("}")[-1] == "DocDetails"), None), "DocType")[:40]
            else:
                body, row = _pull_doc(rt, ctx, db, root, txn, fmt, now_ts)
                doc_type = row.doc_type if row else None
            notifications = []
            if channel == "pull-doc" and row is not None:
                pulled = utcnow()
                row.last_pulled_at = pulled
                notifications.append(
                    {
                        "port": "certificate-issuance",
                        "kind": "document_pulled",
                        "data": {
                            "issuance_key": row.issuance_key,
                            "provider_uri": row.uri,
                            "pulled_at": pulled.isoformat(),
                        },
                    }
                )
            _log(db, str(ctx.organisation_id), txn, channel, doc_type, row)
            db.commit()
        return {"status": 200, "content_type": "application/xml", "body": body, "notifications": notifications}
    except AdapterError as e:  # not configured: DigiLocker may retry later
        return _plain(503, e.code)
    except Exception:  # a provider request must always get an answer; the hub logs the failed delivery
        logging.getLogger("eos.digilocker").exception("pull request failed")
        return _plain(500, "temporarily unavailable")
