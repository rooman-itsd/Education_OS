"""The requester side: OAuth with PKCE (S256 only) and consented file access. Aadhaar never enters: the token
response's name, date of birth and Aadhaar flag are dropped on arrival, and only the DigiLocker id is kept (as the
account link's provider_subject)."""

from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from urllib.parse import urlparse

from ..domain.errors import AdapterError
from ..domain.models import iso
from ..domain.rules import parse_dob
from .runtime import Runtime
from .schemas import BeginAuthInput, CompleteAuthInput, Context, FetchInput, ListHolderInput

MAX_LISTED = 500
_URI = re.compile(r"^[A-Za-z0-9._:/@~+%=-]{1,300}$")


def _redirect_ok(uri: str, mode: str) -> None:
    parsed = urlparse(uri)
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if (
        not parsed.hostname
        or parsed.fragment
        or not (parsed.scheme == "https" or (parsed.scheme == "http" and local and mode == "mock"))
    ):
        raise AdapterError("invalid_request", "redirect_uri must be an absolute https URL")


def begin_authorisation(rt: Runtime, ctx: Context, inp: BeginAuthInput) -> tuple[dict, str | None]:
    cfg = rt.config()
    rt.require_mode(ctx, cfg)
    client_id, _ = rt.requester(ctx, cfg)
    _redirect_ok(inp.redirect_uri, ctx.mode)
    valid_till = int((rt.clock() + timedelta(days=cfg.consent_days)).timestamp())
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": inp.redirect_uri,
        "state": inp.state,
        "code_challenge": inp.code_challenge,
        "code_challenge_method": "S256",
        "purpose": cfg.requester_purpose,
        "consent_valid_till": str(valid_till),
    }
    if inp.scope_hint:
        params["req_doctype"] = ",".join(inp.scope_hint)
    return {"authorize_url": rt.client(ctx, cfg).authorize_url(params)}, None


def _tokens(body: dict, *, subject_required: bool) -> tuple[dict, str | None, list, str]:
    access = body.get("access_token")
    if not isinstance(access, str) or not access:
        raise AdapterError("provider_error", "DigiLocker answered without an access token")
    secrets_out = {"access_token": access}
    if isinstance(body.get("refresh_token"), str) and body["refresh_token"]:
        secrets_out["refresh_token"] = body["refresh_token"]
    subject = body.get("digilockerid")
    if subject_required and not (isinstance(subject, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,100}", subject)):
        raise AdapterError("provider_error", "DigiLocker answered without a DigiLocker id")
    scope = body.get("scope")
    scopes = scope.split() if isinstance(scope, str) else []
    expires_in = body.get("expires_in")
    seconds = (
        expires_in
        if isinstance(expires_in, int) and not isinstance(expires_in, bool) and 0 < expires_in <= 31_536_000
        else 3600
    )
    return secrets_out, subject if isinstance(subject, str) else None, scopes[:20], str(seconds)


def complete_authorisation(rt: Runtime, ctx: Context, inp: CompleteAuthInput) -> tuple[dict, str | None]:
    cfg = rt.config()
    client = rt.client(ctx, cfg)
    client_id, client_secret = rt.requester(ctx, cfg)
    _redirect_ok(inp.redirect_uri, ctx.mode)
    body = client.token(
        {
            "grant_type": "authorization_code",
            "code": inp.code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": inp.redirect_uri,
            "code_verifier": inp.code_verifier,
        }
    )
    secrets_out, subject, scopes, seconds = _tokens(body, subject_required=True)
    expires = rt.clock() + timedelta(seconds=int(seconds))
    return {
        "secrets": secrets_out,
        "provider_subject": subject,
        "granted_scopes": scopes,
        "expires_at": iso(expires),
    }, subject


def refresh_authorisation(rt: Runtime, ctx: Context) -> tuple[dict, str | None]:
    cfg = rt.config()
    client = rt.client(ctx, cfg)
    refresh = ctx.secrets.get("refresh_token")
    if not refresh:
        raise AdapterError("consent_required", "there is no refresh token: the person must link DigiLocker again")
    client_id, client_secret = rt.requester(ctx, cfg)
    body = client.token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )
    secrets_out, _, _, seconds = _tokens(body, subject_required=False)
    secrets_out.setdefault("refresh_token", refresh)  # DigiLocker may keep the same refresh token
    return {"secrets": secrets_out, "expires_at": iso(rt.clock() + timedelta(seconds=int(seconds)))}, None


def revoke_authorisation(rt: Runtime, ctx: Context) -> tuple[dict, str | None]:
    cfg = rt.config()
    client = rt.client(ctx, cfg)
    token = ctx.secrets.get("refresh_token") or ctx.secrets.get("access_token")
    if not token:
        return {"revoked": False}, None  # nothing was ever granted here
    client_id, client_secret = rt.requester(ctx, cfg)
    client.revoke({"token": token, "client_id": client_id, "client_secret": client_secret})
    return {"revoked": True}, None


def _linked(ctx: Context, account_link_id) -> str:
    """The person's access token, only for the account link they authorised for this call."""
    if ctx.account_link is None or ctx.account_link.id != account_link_id:
        raise AdapterError("consent_required", "the person has not linked DigiLocker for this request")
    token = ctx.secrets.get("access_token")
    if not token:
        raise AdapterError("consent_required", "the person's DigiLocker link has no usable token")
    return token


def _issued_on(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    head = value.strip().split(" ")[0]
    parsed = parse_dob(head)
    return parsed.isoformat() if parsed else None


def list_holder_documents(rt: Runtime, ctx: Context, inp: ListHolderInput) -> tuple[dict, str | None]:
    token = _linked(ctx, inp.account_link_id)
    cfg = rt.config()
    client = rt.client(ctx, cfg)
    rt.requester(ctx, cfg)
    items = []
    for f in client.files_issued(token)[:MAX_LISTED]:
        uri = f.get("uri")
        if not isinstance(uri, str) or not _URI.match(uri):
            continue
        items.append(
            {
                "provider_uri": uri,
                "issuer": str(f.get("issuer") or f.get("issuerid") or "")[:200],
                "doc_type": str(f.get("doctype") or "")[:40],
                "title": str(f.get("description") or f.get("name") or "")[:200],
                "issued_on": _issued_on(f.get("date")),
            }
        )
    return {"items": items}, None


def fetch_holder_document(rt: Runtime, ctx: Context, inp: FetchInput) -> tuple[dict, str | None]:
    token = _linked(ctx, inp.account_link_id)
    if bool(inp.provider_uri) == bool(inp.lookup):
        raise AdapterError("invalid_request", "send exactly one of provider_uri and lookup")
    cfg = rt.config()
    client = rt.client(ctx, cfg)
    _, client_secret = rt.requester(ctx, cfg)
    uri = inp.provider_uri
    if inp.lookup:
        issuer_id, doc_type = inp.lookup.get("issuer_id"), inp.lookup.get("doc_type")
        if not issuer_id or not doc_type:
            raise AdapterError("invalid_request", "lookup needs issuer_id and doc_type")
        params = {k: v for k, v in inp.lookup.items() if k not in ("issuer_id", "doc_type") and len(v) <= 200}
        uri = client.pull_document(token, {"orgid": issuer_id, "doctype": doc_type, **params})
    if not uri or not _URI.match(uri):
        raise AdapterError("invalid_request", "provider_uri is not a DigiLocker URI")
    content, verified = client.file(token, uri, client_secret, cfg.max_document_bytes)
    org = str(ctx.organisation_id)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", uri)[:120]
    document_id = rt.documents_for(ctx).put(
        org, filename=f"{safe}.pdf", content_type="application/pdf", content=content
    )
    parts = uri.split("-", 2)
    return {
        "document_id": document_id,
        "sha256": hashlib.sha256(content).hexdigest(),
        "issuer": parts[0] if len(parts) == 3 else "unknown",
        "doc_type": parts[1] if len(parts) == 3 else "unknown",
        "integrity_verified": verified,
    }, uri
