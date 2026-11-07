"""OAuth (authorization code with PKCE S256) for organisation connections and for people linking their own accounts
(docs/prd.md, "Authorisation"). The hub owns the state, the verifier, the callback URL and the secret store; the
adapter only knows the provider's URLs and parameters (adapter.yaml begin/complete/refresh/revoke_authorisation).

`state` is a random single-use value. Only its SHA-256 is stored, with the PKCE verifier encrypted, bound to the
organisation, the connection or link and the person, and expiring after INTEGRATION_HUB_OAUTH_STATE_TTL_S. The browser
is sent back only to a host in INTEGRATION_HUB_ALLOWED_RETURN_HOSTS. Nobody links an account for someone else: a link is
always the caller's own.

The state is also bound to the browser that started the flow. Starting it sets a short-lived cookie (HttpOnly, Secure,
SameSite=Lax, path the callback's, named after the state) holding a random nonce whose SHA-256 is stored with the
state; the callback is refused unless the browser presents that nonce, and, when the callback carries a token, unless
it is the same person's. So an authorize_url sent to someone else cannot land their tokens on the sender's link or
connection: their browser has no nonce, and the state is spent without exchanging the code."""

from __future__ import annotations

import hmac
import json
import logging
import secrets as pysecrets
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from eos_core.db import scoped
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.errors import HubError, not_found
from ..domain.vocabulary import CREDENTIAL_NAME_RE, MAX_SUBJECT, MAX_URL
from ..infrastructure.config import API_PREFIX, HubConfig
from ..infrastructure.models import AccountLink, Connection, OAuthState
from ..infrastructure.registry import AdapterInfo, ProviderInfo, call, get_registry
from ..infrastructure.secrets import SecretStoreError, get_cipher, ref_for
from . import connections
from .common import (
    Actor,
    as_organisation,
    clock,
    context_for,
    get_connection,
    get_link,
    iso,
    link_secrets,
    page,
    platform_rows,
    provider_of,
    publish,
    record,
    resolve_secrets,
    store_or_503,
)

log = logging.getLogger("eos.integration_hub")

LINK_TOKENS = "tokens"  # one secret per link: the provider's tokens as a JSON object
BINDING_COOKIE_PREFIX = "eos_ih_oauth_"
MAX_BINDING = 200


@dataclass(frozen=True)
class BrowserBinding:
    """The cookie that binds a pending authorisation to the browser that started it. The API layer sets it with
    HttpOnly, Secure and SameSite=Lax (the provider's redirect back is a top-level GET, which Lax lets through)."""

    name: str
    value: str
    max_age: int
    path: str


def binding_cookie_name(state: str) -> str:
    """One cookie per pending state, so two authorisations started in one browser do not overwrite each other."""
    return BINDING_COOKIE_PREFIX + rules.sha256_hex(state)[:16]


def binding_cookie_path(config: HubConfig | None = None) -> str:
    """The callback's path as the browser sees it on the public base URL; the cookie is sent nowhere else."""
    config = config or HubConfig.from_env()
    return urlsplit(config.public_url("/oauth/callback")).path or f"{API_PREFIX}/oauth/callback"


def link_dict(link: AccountLink) -> dict:
    return {
        "id": link.id,
        "person_id": link.person_id,
        "port": link.port,
        "provider": link.provider,
        "status": link.status,
        "purpose": link.purpose,
        "granted_scopes": list(link.granted_scopes or []),
        "linked_at": iso(link.linked_at),
        "expires_at": iso(link.expires_at),
        "last_synced_at": iso(link.last_synced_at),
        "revoked_at": iso(link.revoked_at),
    }


def _return_url(config: HubConfig, url: str | None) -> str:
    if url is None:
        if not config.allowed_return_hosts:
            raise HubError(422, "invalid_return_url", "no return_url and no allowed return host is configured")
        return f"https://{config.allowed_return_hosts[0]}/"
    if len(url) > MAX_URL or not config.return_host_allowed(url):
        raise HubError(422, "invalid_return_url", "return_url must be on an allowed host")
    return url


def _valid_authorize_url(value) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    return value if value.startswith("https://") or value.startswith("http://") else None


def _begin(
    db: Session,
    info: AdapterInfo,
    c: Connection,
    *,
    link: AccountLink | None,
    person_id: str,
    return_url: str,
) -> tuple[dict, BrowserBinding]:
    config = HubConfig.from_env()
    state = pysecrets.token_urlsafe(32)
    verifier = pysecrets.token_urlsafe(64)  # 86 characters, within RFC 7636's 43 to 128
    redirect_uri = config.public_url(f"/oauth/callback/{c.adapter}")
    try:
        secrets = resolve_secrets(db, c)
        cipher = get_cipher(config)
    except SecretStoreError as e:
        raise HubError(503, "secret_store_unavailable", str(e)) from e
    ctx = context_for(c, secrets=secrets, link=link, timeout_s=config.sync_timeout_s, operation="begin_authorisation")
    payload = {
        "state": state,
        "code_challenge": rules.pkce_challenge(verifier),
        "code_challenge_method": "S256",
        "redirect_uri": redirect_uri,
        "scope_hint": [],
    }
    out = call(info, "begin_authorisation", ctx, payload, timeout_s=config.sync_timeout_s)
    if not out.ok:
        if out.error_code == "unsupported":
            raise HubError(409, "provider_not_offered", f"{c.provider} does not use an authorization code")
        raise HubError(502, out.error_code, f"the adapter could not start authorisation ({out.error_code})")
    authorize_url = _valid_authorize_url(out.output.get("authorize_url"))
    if authorize_url is None:
        raise HubError(502, "provider_error", "the adapter returned no usable authorize_url")
    state_hash = rules.sha256_hex(state)
    expires_at = clock() + timedelta(seconds=config.oauth_state_ttl_s)
    binding = BrowserBinding(
        name=binding_cookie_name(state),
        value=pysecrets.token_urlsafe(32),
        max_age=config.oauth_state_ttl_s,
        path=binding_cookie_path(config),
    )
    db.add(
        OAuthState(
            organisation_id=c.organisation_id,
            state_hash=state_hash,
            adapter=c.adapter,
            connection_id=c.id,
            account_link_id=link.id if link else None,
            person_id=person_id,
            browser_binding_hash=rules.sha256_hex(binding.value),
            code_verifier_encrypted=cipher.encrypt(verifier.encode(), state_hash),
            return_url=return_url,
            expires_at=expires_at,
            created_at=clock(),
        )
    )
    return {"authorize_url": authorize_url, "expires_at": iso(expires_at)}, binding


def _authorisable(c: Connection, scope: str) -> tuple[AdapterInfo, ProviderInfo]:
    info, provider = provider_of(c)
    if info is None or provider is None:
        raise HubError(409, "adapter_not_installed", f"adapter {c.adapter} is not installed")
    if not provider.uses_authorization_code or provider.link_scope != scope:
        raise HubError(409, "provider_not_offered", f"{c.provider} is not authorised this way")
    return info, provider


def authorise_connection(
    db: Session, actor: Actor, connection_id: str, return_url: str | None
) -> tuple[dict, BrowserBinding]:
    """The response body and the browser-binding cookie the API layer must set on it."""
    c = get_connection(db, connection_id)
    info, _provider = _authorisable(c, "organisation")
    url = _return_url(HubConfig.from_env(), return_url)
    out, binding = _begin(db, info, c, link=None, person_id=actor.user_id, return_url=url)
    record(db, c.organisation_id, actor.user_id, "connection.authorisation-started", "connection", c.id)
    db.commit()
    return out, binding


# ------------------------------------------------------------------ account links


def start_link(db: Session, actor: Actor, body: dict) -> tuple[dict, BrowserBinding]:
    """The response body and the browser-binding cookie the API layer must set on it."""
    c = db.scalar(
        scoped(db, select(Connection), Connection).where(
            Connection.port == body["port"], Connection.provider == body["provider"], Connection.enabled.is_(True)
        )
    )
    if c is None:
        raise HubError(409, "connection_disabled", "the organisation has no enabled connection for that provider")
    info, _provider = _authorisable(c, "person")
    q = scoped(db, select(AccountLink), AccountLink).where(
        AccountLink.connection_id == c.id, AccountLink.person_id == actor.user_id
    )
    if db.scalar(q.where(AccountLink.status == "active")):
        raise HubError(409, "link_exists", "you already linked an account at that provider")
    url = _return_url(HubConfig.from_env(), body.get("return_url"))
    link = db.scalar(q.where(AccountLink.status == "pending"))
    if link is None:
        link = AccountLink(
            organisation_id=c.organisation_id,
            connection_id=c.id,
            person_id=actor.user_id,
            port=c.port,
            provider=c.provider,
            status="pending",
            created_at=clock(),
        )
        db.add(link)
    link.purpose = (body.get("purpose") or "").strip() or None
    db.flush()
    out, binding = _begin(db, info, c, link=link, person_id=actor.user_id, return_url=url)
    db.commit()
    return {"account_link": link_dict(link), "authorize_url": out["authorize_url"]}, binding


def my_links(db: Session, actor: Actor) -> list[dict]:
    q = scoped(db, select(AccountLink), AccountLink).where(AccountLink.person_id == actor.user_id)
    return [link_dict(x) for x in db.scalars(q.order_by(AccountLink.created_at.desc(), AccountLink.id))]


def list_links(db: Session, *, port, provider, status, person_id, cursor, limit) -> dict:
    q = scoped(db, select(AccountLink), AccountLink)
    if port:
        q = q.where(AccountLink.port == port)
    if provider:
        q = q.where(AccountLink.provider == provider)
    if status:
        q = q.where(AccountLink.status == status)
    if person_id:
        q = q.where(AccountLink.person_id == person_id)
    return page(db, q.order_by(AccountLink.created_at.desc(), AccountLink.id), cursor, limit, link_dict)


def end_link(db: Session, link: AccountLink, *, cause: str, actor: str | None, reason: str | None = None) -> None:
    """Revoke at the provider (best effort), delete the tokens, mark the link and tell the adapter through
    integration-hub.account-link.revoked, on which it deletes the data collected under the link."""
    if link.status == "revoked":
        return
    c = db.get(Connection, link.connection_id)
    store = store_or_503()
    info = get_registry().get(c.adapter) if c else None
    if info is not None and link.status == "active":
        try:
            secrets = link_secrets(link, store)
        except SecretStoreError:
            secrets = {}
        config = HubConfig.from_env()
        ctx = context_for(
            c, secrets=secrets, link=link, timeout_s=config.sync_timeout_s, operation="revoke_authorisation"
        )
        out = call(info, "revoke_authorisation", ctx, timeout_s=config.sync_timeout_s)
        if not out.ok and out.error_code != "unsupported":
            log.warning(
                "revoke at %s failed with %s for link %s; tokens deleted anyway", link.provider, out.error_code, link.id
            )
    if link.secret_ref:
        try:
            store.delete(link.secret_ref)
        except SecretStoreError as e:
            raise HubError(503, "secret_store_unavailable", str(e)) from e
    link.secret_ref = None
    link.status = "revoked"
    link.revoked_at = clock()
    link.revoke_cause = cause[:40]
    publish(
        db,
        link.organisation_id,
        "account-link.revoked",
        {
            "account_link_id": link.id,
            "person_id": link.person_id,
            "port": link.port,
            "provider": link.provider,
            "cause": cause,
        },
        actor,
    )
    record(
        db,
        link.organisation_id,
        actor,
        "account-link.revoked",
        "account_link",
        link.id,
        after={"cause": cause},
        context={"reason": reason} if reason else None,
    )


def delete_my_link(db: Session, actor: Actor, link_id: str) -> None:
    link = get_link(db, link_id)
    if link.person_id != actor.user_id:
        raise not_found("account link")
    end_link(db, link, cause="disconnected", actor=actor.user_id)
    db.commit()


def revoke_link(db: Session, actor: Actor, link_id: str, reason: str) -> dict:
    link = get_link(db, link_id)
    end_link(db, link, cause="revoked_by_admin", actor=actor.user_id, reason=reason)
    db.commit()
    return link_dict(link)


# ------------------------------------------------------------------ the callback


def _redirect(url: str, **params: str) -> str:
    return url + ("&" if "?" in url else "?") + urlencode(params)


def _bounded_secrets(value) -> dict[str, str] | None:
    if not isinstance(value, dict) or not value or len(value) > 20:
        return None
    out = {}
    for k, v in value.items():
        if not isinstance(k, str) or not isinstance(v, str) or not v or len(v) > 16384:
            return None
        if not CREDENTIAL_NAME_RE.match(k):
            return None
        out[k] = v
    return out


def claim_state(db: Session, state_hash: str, adapter: str, now) -> int:
    """Redeem a state in one statement; returns how many rows it claimed (1 or 0). Of two requests racing with the
    same state exactly one updates the row: the other waits on its lock, then finds used_at set and matches nothing.
    Single use, whatever happens next. Not committed: the caller's transaction holds the claim."""
    return db.execute(
        update(OAuthState)
        .where(
            OAuthState.state_hash == state_hash,
            OAuthState.adapter == adapter,
            OAuthState.used_at.is_(None),
            OAuthState.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount


def _same_browser(row: OAuthState, binding: str | None) -> bool:
    if not isinstance(binding, str) or not binding or len(binding) > MAX_BINDING:
        return False
    return hmac.compare_digest(rules.sha256_hex(binding), row.browser_binding_hash or "")


def callback(
    db: Session,
    adapter: str,
    code: str | None,
    state: str | None,
    error: str | None,
    *,
    binding: str | None,
    caller_id: str | None = None,
) -> str:
    """The provider sent the browser back. Returns the URL to redirect to; raises 401 state_invalid when the state is
    not one this hub issued, unexpired and unused (then nobody is redirected anywhere).

    `binding` is the nonce from the browser's binding cookie; `caller_id` the person the request is authenticated as,
    when it carries a token (None when it does not, "" when the token did not verify). A state presented by another
    browser, or by another person, is refused and spent: the code is never exchanged."""
    if not state or len(state) > 200:
        raise HubError(401, "state_invalid", "unknown or expired state")
    state_hash = rules.sha256_hex(state)
    with platform_scope():
        now = clock()
        if claim_state(db, state_hash, adapter, now) != 1:
            db.rollback()
            raise HubError(401, "state_invalid", "unknown or expired state")
        row = db.scalar(select(OAuthState).where(OAuthState.state_hash == state_hash))
        if not _same_browser(row, binding) or (caller_id is not None and caller_id != row.person_id):
            record(
                db,
                row.organisation_id,
                None,
                "authorisation.failed",
                "connection",
                row.connection_id,
                after={"code": "session_mismatch"},
            )
            db.commit()
            raise HubError(401, "state_invalid", "unknown or expired state")
        snapshot = {
            "organisation_id": row.organisation_id,
            "connection_id": row.connection_id,
            "account_link_id": row.account_link_id,
            "person_id": row.person_id,
            "return_url": row.return_url,
            "verifier": row.code_verifier_encrypted,
            "state_hash": row.state_hash,
        }
        db.commit()
    with organisation_scope(snapshot["organisation_id"]):
        try:
            return _complete(db, adapter, code, error, snapshot)
        except HubError as e:
            db.rollback()
            return _redirect(snapshot["return_url"], status="failed", code=e.code)


def _complete(db: Session, adapter: str, code: str | None, error: str | None, s: dict) -> str:
    c = get_connection(db, s["connection_id"])
    link = get_link(db, s["account_link_id"]) if s["account_link_id"] else None

    def fail(reason: str) -> str:
        if link is not None and link.status == "pending":
            link.status = "error"
        record(
            db, c.organisation_id, s["person_id"], "authorisation.failed", "connection", c.id, after={"code": reason}
        )
        db.commit()
        return _redirect(s["return_url"], status="failed", code=reason)

    if error or not code or len(code) > 4096:
        return fail("consent_required" if error == "access_denied" else "auth_failed")
    info, provider = provider_of(c)
    if info is None or provider is None:
        return fail("not_configured")
    config = HubConfig.from_env()
    try:
        verifier = get_cipher(config).decrypt(s["verifier"], s["state_hash"]).decode()
        secrets = resolve_secrets(db, c)
    except SecretStoreError:
        return fail("not_configured")
    ctx = context_for(
        c, secrets=secrets, link=link, timeout_s=config.sync_timeout_s, operation="complete_authorisation"
    )
    payload = {"code": code, "code_verifier": verifier, "redirect_uri": config.public_url(f"/oauth/callback/{adapter}")}
    out = call(info, "complete_authorisation", ctx, payload, timeout_s=config.sync_timeout_s)
    if not out.ok:
        return fail(out.error_code)
    tokens = _bounded_secrets(out.output.get("secrets"))
    if tokens is None:
        return fail("provider_error")
    scopes = [x for x in out.output.get("granted_scopes") or [] if isinstance(x, str) and len(x) <= 200][:50]
    expires_at = connections.parse_dt(out.output.get("expires_at"))
    subject = out.output.get("provider_subject")
    subject = subject[:MAX_SUBJECT] if isinstance(subject, str) and subject else None
    store = store_or_503()
    if link is not None:
        ref = ref_for(link.organisation_id, "links", link.id, LINK_TOKENS)
        try:
            store.put(ref, json.dumps(tokens))
        except SecretStoreError:
            return fail("not_configured")
        link.secret_ref = ref
        link.status = "active"
        link.provider_subject = subject
        link.granted_scopes = scopes
        link.linked_at = clock()
        link.expires_at = expires_at
        link.revoked_at = None
        link.revoke_cause = None
        publish(
            db,
            link.organisation_id,
            "account-link.connected",
            {"account_link_id": link.id, "person_id": link.person_id, "port": link.port, "provider": link.provider},
            s["person_id"],
        )
        record(
            db,
            link.organisation_id,
            s["person_id"],
            "account-link.connected",
            "account_link",
            link.id,
            after={"provider": link.provider, "granted_scopes": scopes},
        )
    else:
        for name, value in tokens.items():
            connections.write_credential(
                db, c, name, value, source="oauth", set_by=s["person_id"], expires_at=expires_at, store=store
            )
        c.authorised = True
        if expires_at is not None:
            c.expires_at = expires_at
        publish(
            db,
            c.organisation_id,
            "connection.authorised",
            {"connection_id": c.id, "provider": c.provider, "granted_scopes": scopes},
            s["person_id"],
        )
        record(
            db,
            c.organisation_id,
            s["person_id"],
            "connection.authorised",
            "connection",
            c.id,
            after={"granted_scopes": scopes, "credentials": sorted(tokens)},
        )
    db.commit()
    return _redirect(s["return_url"], status="connected")


# ------------------------------------------------------------------ token refresh (scheduled)


def refresh_due(*, budget_s: float = 50) -> int:
    """Refresh OAuth tokens that expire within INTEGRATION_HUB_TOKEN_REFRESH_LEAD_S. A refresh that answers auth_failed
    marks the connection unauthorised (health auth_failed) or the link expired, and tells the owner by event. Each
    refresh runs as its own organisation (as_organisation: no platform scope), in its own transaction; after
    `budget_s` no new refresh starts and the next run (every 5 minutes) takes the rest."""
    config = HubConfig.from_env()
    horizon = clock() + timedelta(seconds=config.token_refresh_lead_s)
    links = platform_rows(
        select(AccountLink.id, AccountLink.organisation_id).where(
            AccountLink.status == "active",
            AccountLink.expires_at.is_not(None),
            AccountLink.expires_at <= horizon,
        )
    )
    conns = platform_rows(
        select(Connection.id, Connection.organisation_id).where(
            Connection.authorised.is_(True),
            Connection.expires_at.is_not(None),
            Connection.expires_at <= horizon,
        )
    )
    work = [(_refresh_link, i, org) for i, org in links] + [(_refresh_connection, i, org) for i, org in conns]
    deadline = time.monotonic() + budget_s
    refreshed = done = 0
    for fn, row_id, org in work:
        if done and time.monotonic() > deadline:
            break
        done += 1
        try:
            refreshed += as_organisation(org, fn, row_id, config)
        except Exception as e:  # noqa: BLE001 - one row must not stop the others
            log.warning("token refresh of %s failed: %s", row_id, type(e).__name__)
    return refreshed


def _refresh_link(db: Session, link_id: str, config: HubConfig) -> int:
    try:
        link = get_link(db, link_id)
        c = get_connection(db, link.connection_id)
        info = get_registry().get(c.adapter)
        if info is None:
            return 0
        store = store_or_503(config)
        ctx = context_for(
            c,
            secrets=link_secrets(link, store),
            link=link,
            timeout_s=config.sync_timeout_s,
            operation="refresh_authorisation",
        )
        out = call(info, "refresh_authorisation", ctx, timeout_s=config.sync_timeout_s)
        if out.ok and (tokens := _bounded_secrets(out.output.get("secrets"))):
            store.put(
                link.secret_ref or ref_for(link.organisation_id, "links", link.id, LINK_TOKENS), json.dumps(tokens)
            )
            link.expires_at = connections.parse_dt(out.output.get("expires_at"))
            db.commit()
            return 1
        if out.error_code == "auth_failed":
            end_link(db, link, cause="token_expired", actor=None)
            link.status = "expired"
            db.commit()
        else:
            db.rollback()
        return 0
    except (HubError, SecretStoreError) as e:
        log.warning("token refresh for link %s failed: %s", link_id, type(e).__name__)
        db.rollback()
        return 0


def _refresh_connection(db: Session, conn_id: str, config: HubConfig) -> int:
    try:
        c = get_connection(db, conn_id)
        info = get_registry().get(c.adapter)
        if info is None:
            return 0
        store = store_or_503(config)
        ctx = context_for(
            c, secrets=resolve_secrets(db, c, store), timeout_s=config.sync_timeout_s, operation="refresh_authorisation"
        )
        out = call(info, "refresh_authorisation", ctx, timeout_s=config.sync_timeout_s)
        if out.ok and (tokens := _bounded_secrets(out.output.get("secrets"))):
            expires_at = connections.parse_dt(out.output.get("expires_at"))
            for name, value in tokens.items():
                connections.write_credential(
                    db, c, name, value, source="oauth", set_by=None, expires_at=expires_at, store=store
                )
            c.expires_at = expires_at
            db.commit()
            return 1
        if out.error_code == "auth_failed":
            c.authorised = False
            connections.apply_health(db, c, "auth_failed", "token refresh refused", None)
            db.commit()
        else:
            db.rollback()
        return 0
    except (HubError, SecretStoreError) as e:
        log.warning("token refresh for connection %s failed: %s", conn_id, type(e).__name__)
        db.rollback()
        return 0
