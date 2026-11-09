"""Connections, credentials, modes and health (contracts/openapi.yaml, /connections). Every call arrives with the
caller's organisation pinned on the session (eos_identity's current_principal) and every query is scoped, so another
organisation's connection answers 404 exactly like one that does not exist. Every state change writes an audit record
and publishes its event in the same transaction, and the use case commits.

Credentials are write-only: the value goes to the secret store and is never stored in the database, logged, audited,
put on an event or returned. The database keeps the name, a reference, a fingerprint and dates."""

from __future__ import annotations

import secrets as pysecrets
from datetime import datetime, timedelta

from eos_core.db import scoped
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.errors import HubError, not_found
from ..domain.vocabulary import CHECK_STATUSES, CREATE_MODES, MAX_DETAIL, MODES
from ..infrastructure.config import HubConfig
from ..infrastructure.models import Connection, ConnectionCredential
from ..infrastructure.registry import ProviderInfo, call
from ..infrastructure.secrets import SecretStore, SecretStoreError, get_store, ref_for
from .common import (
    Actor,
    adapter_or_409,
    aware,
    clock,
    context_for,
    credentials_of,
    get_connection,
    iso,
    missing_credentials,
    provider_of,
    publish,
    record,
    resolve_secrets,
    store_or_503,
)

CONNECTION_KEY = "_connection_key"  # the inbound URL's key; never a credential name (those start with a letter)


def parse_dt(value) -> datetime | None:
    """A datetime an adapter returned, as an aware UTC datetime; anything unparseable is None."""
    if isinstance(value, datetime):
        return aware(value)
    if isinstance(value, str) and len(value) <= 40:
        try:
            return aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


# ------------------------------------------------------------------ rendering


def _inbound_urls(connection: Connection, provider: ProviderInfo | None, store: SecretStore | None) -> list[str]:
    if provider is None or not provider.inbound or store is None:
        return []
    try:
        key = store.get(ref_for(connection.organisation_id, connection.id, CONNECTION_KEY))
    except SecretStoreError:
        return []
    if not key:
        return []
    config = HubConfig.from_env()
    base = f"/inbound/{connection.adapter}/{key}"
    urls = []
    if "webhook" in provider.inbound:
        urls.append(config.public_url(base))
    if "provider_request" in provider.inbound:
        urls.append(config.public_url(base + "/{channel}"))
    return urls


def health_dict(c: Connection) -> dict:
    return {
        "status": c.health_status,
        "detail": c.health_detail,
        "checked_at": iso(c.health_checked_at),
        "expires_at": iso(c.expires_at),
    }


def connection_dict(db: Session, c: Connection, store: SecretStore | None = None) -> dict:
    _info, provider = provider_of(c)
    complete = provider is not None and not missing_credentials(db, c, provider)
    return {
        "id": c.id,
        "adapter": c.adapter,
        "provider": c.provider,
        "port": c.port,
        "mode": c.mode,
        "enabled": c.enabled,
        "display_name": c.display_name,
        "settings": dict(c.settings or {}),
        "credentials_complete": complete,
        "authorised": c.authorised,
        "inbound_urls": _inbound_urls(c, provider, store),
        "health": health_dict(c),
        "created_at": iso(c.created_at),
        "updated_at": iso(c.updated_at),
    }


def _store_quietly() -> SecretStore | None:
    try:
        return get_store()
    except SecretStoreError:
        return None


def render(db: Session, c: Connection) -> dict:
    return connection_dict(db, c, _store_quietly())


# ------------------------------------------------------------------ reads


def list_connections(db: Session, *, port: str | None, adapter: str | None, enabled: bool | None) -> list[dict]:
    q = scoped(db, select(Connection), Connection)
    if port:
        q = q.where(Connection.port == port)
    if adapter:
        q = q.where(Connection.adapter == adapter)
    if enabled is not None:
        q = q.where(Connection.enabled.is_(enabled))
    store = _store_quietly()
    return [connection_dict(db, c, store) for c in db.scalars(q.order_by(Connection.created_at, Connection.id))]


def get(db: Session, connection_id: str) -> dict:
    return render(db, get_connection(db, connection_id))


# ------------------------------------------------------------------ create and update


def _validated_settings(provider: ProviderInfo, settings: dict | None) -> dict:
    value = dict(settings or {})
    try:
        rules.check_json(value, what="settings")
        rules.validate_schema(value, provider.settings_schema)
    except rules.RuleError as e:
        raise HubError(422, e.code, e.message) from e
    return value


def _require_mock_allowed(mode: str) -> None:
    if mode == "mock" and not HubConfig.from_env().allow_mock:
        raise HubError(422, "mock_not_allowed", "mock mode is not allowed on this deployment")


def create_connection(db: Session, actor: Actor, body: dict) -> dict:
    info = adapter_or_409(body["adapter"])
    provider = info.provider(body["provider"])
    if provider is None or body["port"] not in provider.ports:
        raise HubError(
            409, "provider_not_offered", f"{body['adapter']} does not offer {body['provider']} for that port"
        )
    mode = body["mode"]
    if mode not in CREATE_MODES or mode not in provider.modes:
        raise HubError(422, "invalid_mode", "a connection starts in a mode the provider supports, mock or sandbox")
    _require_mock_allowed(mode)
    settings = _validated_settings(provider, body.get("settings"))
    name = (body.get("display_name") or "").strip() or None
    org = actor.organisation_id
    if name:
        clash = db.scalar(
            scoped(db, select(Connection.id), Connection).where(
                Connection.adapter == info.adapter,
                Connection.provider == provider.provider,
                Connection.port == body["port"],
                func.lower(Connection.display_name) == name.lower(),
            )
        )
        if clash:
            raise HubError(409, "connection_exists", "a connection with that name already exists for the provider")
    store = store_or_503()
    if store.read_only:
        raise HubError(503, "secret_store_unavailable", "the secret store is read only")
    now = clock()
    c = Connection(
        organisation_id=org,
        adapter=info.adapter,
        provider=provider.provider,
        port=body["port"],
        mode=mode,
        enabled=False,
        display_name=name,
        settings=settings,
        connection_key_hash="",
        created_by=actor.user_id,
        created_at=now,
        updated_at=now,
        changed_at=now,
    )
    db.add(c)
    db.flush()
    _new_connection_key(c, store)
    publish(
        db,
        org,
        "connection.created",
        {"connection_id": c.id, "adapter": c.adapter, "provider": c.provider, "port": c.port, "mode": c.mode},
        actor.user_id,
    )
    record(
        db,
        org,
        actor.user_id,
        "connection.created",
        "connection",
        c.id,
        after={"adapter": c.adapter, "provider": c.provider, "port": c.port, "mode": c.mode},
    )
    db.commit()
    return connection_dict(db, c, store)


def _new_connection_key(c: Connection, store: SecretStore) -> None:
    key = pysecrets.token_urlsafe(32)  # 43 characters, the ConnectionKey pattern
    try:
        store.put(ref_for(c.organisation_id, c.id, CONNECTION_KEY), key)
    except SecretStoreError as e:
        raise HubError(503, "secret_store_unavailable", str(e)) from e
    c.connection_key_hash = rules.sha256_hex(key)


def update_connection(db: Session, actor: Actor, connection_id: str, body: dict) -> dict:
    c = get_connection(db, connection_id, lock=True)
    changed: list[str] = []
    if "display_name" in body:
        name = (body.get("display_name") or "").strip() or None
        if name != c.display_name:
            c.display_name = name
            changed.append("display_name")
    if body.get("settings") is not None:
        _info, provider = provider_of(c)
        if provider is None:
            raise HubError(409, "adapter_not_installed", f"adapter {c.adapter} is not installed")
        new = _validated_settings(provider, body["settings"])
        old = dict(c.settings or {})
        keys = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        if keys:
            c.settings = new
            c.changed_at = clock()
            changed.extend(keys)
    if changed:
        c.updated_at = clock()
        setting_names = [k for k in changed if k != "display_name"]
        publish(
            db,
            c.organisation_id,
            "connection.updated",
            {"connection_id": c.id, "changed_settings": setting_names},
            actor.user_id,
        )
        record(
            db, c.organisation_id, actor.user_id, "connection.updated", "connection", c.id, after={"changed": changed}
        )
        db.commit()
    return render(db, c)


# ------------------------------------------------------------------ credentials


def credential_status(name: str, cred: ConnectionCredential | None) -> dict:
    return {
        "name": name,
        "set": cred is not None,
        "fingerprint": cred.fingerprint if cred else None,
        "set_at": iso(cred.set_at) if cred else None,
        "set_by": cred.set_by if cred else None,
        "expires_at": iso(cred.expires_at) if cred else None,
        "source": cred.source if cred else "admin",
    }


def list_credentials(db: Session, connection_id: str) -> list[dict]:
    c = get_connection(db, connection_id)
    _info, provider = provider_of(c)
    have = {cred.name: cred for cred in credentials_of(db, c)}
    names = list(provider.credential_names) if provider else []
    names += sorted(n for n in have if n not in names)
    return [credential_status(n, have.get(n)) for n in names]


def write_credential(
    db: Session,
    c: Connection,
    name: str,
    value: str,
    *,
    source: str,
    set_by: str | None,
    expires_at: datetime | None,
    store: SecretStore,
) -> ConnectionCredential:
    """Put one value in the store and upsert its row. No event or audit: the callers add theirs."""
    ref = ref_for(c.organisation_id, c.id, name)
    try:
        store.put(ref, value)
    except SecretStoreError as e:
        raise HubError(503, "secret_store_unavailable", str(e)) from e
    cred = db.scalar(
        select(ConnectionCredential).where(
            ConnectionCredential.connection_id == c.id,
            ConnectionCredential.organisation_id == c.organisation_id,
            ConnectionCredential.name == name,
        )
    )
    if cred is None:
        cred = ConnectionCredential(
            organisation_id=c.organisation_id,
            connection_id=c.id,
            name=name,
            secret_ref=ref,
            fingerprint="",
            source=source,
            set_at=clock(),
        )
        db.add(cred)
    cred.secret_ref = ref
    cred.fingerprint = rules.fingerprint(value)
    cred.source = source
    cred.set_by = set_by
    cred.set_at = clock()
    cred.expires_at = aware(expires_at)
    c.changed_at = c.updated_at = clock()
    return cred


def set_credential(db: Session, actor: Actor, connection_id: str, name: str, value: str, expires_at) -> dict:
    c = get_connection(db, connection_id, lock=True)
    _info, provider = provider_of(c)
    if provider is None:
        raise HubError(409, "adapter_not_installed", f"adapter {c.adapter} is not installed")
    if name not in provider.credential_names:
        raise HubError(422, "unknown_credential", f"{c.provider} does not use a credential named {name}")
    store = store_or_503()
    if store.read_only:
        raise HubError(503, "secret_store_unavailable", "the secret store is read only")
    cred = write_credential(
        db, c, name, value, source="admin", set_by=actor.user_id, expires_at=expires_at, store=store
    )
    if "webhook" in name and provider.inbound:
        _new_connection_key(c, store)  # the inbound URL rotates with the webhook secret (docs/prd.md)
    publish(
        db,
        c.organisation_id,
        "connection.credentials-rotated",
        {"connection_id": c.id, "name": name, "fingerprint": cred.fingerprint, "removed": False},
        actor.user_id,
    )
    record(
        db,
        c.organisation_id,
        actor.user_id,
        "connection.credential-set",
        "connection",
        c.id,
        after={"name": name, "fingerprint": cred.fingerprint},
    )
    db.commit()
    return credential_status(name, cred)


def delete_credential(db: Session, actor: Actor, connection_id: str, name: str) -> None:
    c = get_connection(db, connection_id, lock=True)
    cred = next((x for x in credentials_of(db, c) if x.name == name), None)
    if cred is None:
        raise not_found("credential")
    store = store_or_503()
    try:
        store.delete(cred.secret_ref)
    except SecretStoreError as e:
        raise HubError(503, "secret_store_unavailable", str(e)) from e
    db.delete(cred)
    c.changed_at = c.updated_at = clock()
    _info, provider = provider_of(c)
    if c.enabled and (provider is None or name in provider.credential_names):
        _disable(db, c, "credential_removed", actor.user_id)
    publish(
        db,
        c.organisation_id,
        "connection.credentials-rotated",
        {"connection_id": c.id, "name": name, "fingerprint": None, "removed": True},
        actor.user_id,
    )
    record(
        db, c.organisation_id, actor.user_id, "connection.credential-removed", "connection", c.id, after={"name": name}
    )
    db.commit()


# ------------------------------------------------------------------ health


def check_health(db: Session, c: Connection, *, mode: str | None = None) -> tuple[str, str | None, datetime | None]:
    """Run the adapter's healthcheck: (status, detail, expires_at). Never raises for what the adapter does."""
    info, provider = provider_of(c)
    if info is None or provider is None:
        return "unreachable", "adapter not installed", None
    config = HubConfig.from_env()
    try:
        secrets = resolve_secrets(db, c)
    except SecretStoreError:
        return "unreachable", "secret store unavailable", None
    ctx = context_for(c, secrets=secrets, timeout_s=config.sync_timeout_s, operation="healthcheck", mode=mode)
    out = call(info, "healthcheck", ctx, timeout_s=config.sync_timeout_s)
    if not out.ok:
        return ("auth_failed" if out.error_code == "auth_failed" else "unreachable"), out.error_code, None
    status = out.output.get("status")
    detail = out.output.get("detail")
    detail = detail[:MAX_DETAIL] if isinstance(detail, str) else None
    return (status if status in CHECK_STATUSES else "degraded"), detail, parse_dt(out.output.get("expires_at"))


def apply_health(db: Session, c: Connection, status: str, detail: str | None, expires_at: datetime | None) -> None:
    """Store a result; publish health-changed once per transition, not per check."""
    before = c.health_status
    c.health_status = status
    c.health_detail = detail
    c.health_checked_at = clock()
    if expires_at is not None:
        c.expires_at = expires_at
    if before != status:
        publish(
            db,
            c.organisation_id,
            "connection.health-changed",
            {
                "connection_id": c.id,
                "port": c.port,
                "provider": c.provider,
                "from_status": before,
                "to_status": status,
                "expires_at": iso(c.expires_at),
            },
        )


def run_health(db: Session, connection_id: str) -> dict:
    """On demand, limited to INTEGRATION_HUB_HEALTH_RUNS_PER_HOUR per connection."""
    c = get_connection(db, connection_id, lock=True)
    limit = HubConfig.from_env().health_runs_per_hour
    now = clock()
    start = aware(c.health_window_start)
    if start is None or now - start >= timedelta(hours=1):
        c.health_window_start, c.health_window_runs = now, 0
    if c.health_window_runs >= limit:
        raise HubError(429, "too_many_requests", f"at most {limit} health checks per hour for a connection")
    c.health_window_runs += 1
    apply_health(db, c, *check_health(db, c))
    db.commit()
    return health_dict(c)


def get_health(db: Session, connection_id: str) -> dict:
    return health_dict(get_connection(db, connection_id))


# ------------------------------------------------------------------ enable, disable, mode


def _require_credentials(db: Session, c: Connection, provider: ProviderInfo) -> None:
    missing = missing_credentials(db, c, provider)
    if missing:
        raise HubError(409, "credentials_missing", f"missing credentials: {', '.join(missing)}")
    if provider.uses_authorization_code and provider.link_scope == "organisation" and not c.authorised:
        raise HubError(409, "credentials_missing", "the provider has not been authorised yet")


def _disable(db: Session, c: Connection, reason: str, actor: str | None) -> None:
    c.enabled = False
    c.disabled_reason = reason[:500]
    c.updated_at = clock()
    publish(
        db,
        c.organisation_id,
        "connection.disabled",
        {"connection_id": c.id, "port": c.port, "provider": c.provider, "reason": reason[:500]},
        actor,
    )
    record(db, c.organisation_id, actor, "connection.disabled", "connection", c.id, after={"reason": reason[:500]})


def enable(db: Session, actor: Actor, connection_id: str) -> dict:
    c = get_connection(db, connection_id, lock=True)
    if c.enabled:
        return render(db, c)
    _info, provider = provider_of(c)
    if provider is None:
        raise HubError(409, "adapter_not_installed", f"adapter {c.adapter} is not installed")
    _require_mock_allowed(c.mode)
    if c.mode != "mock":  # a mock connection answers from recordings and needs no credentials
        _require_credentials(db, c, provider)
    status, detail, expires_at = check_health(db, c)
    apply_health(db, c, status, detail, expires_at)
    if status == "auth_failed":
        db.commit()  # keep the result the admin needs to see, then refuse
        raise HubError(409, "health_check_failed", "the provider refused the credentials")
    others = db.scalars(
        scoped(db, select(Connection), Connection).where(
            Connection.port == c.port,
            Connection.provider == c.provider,
            Connection.enabled.is_(True),
            Connection.id != c.id,
        )
    )
    for other in others:
        _disable(db, other, f"replaced by connection {c.id}", actor.user_id)
    c.enabled = True
    c.disabled_reason = None
    c.updated_at = clock()
    publish(
        db,
        c.organisation_id,
        "connection.enabled",
        {"connection_id": c.id, "port": c.port, "provider": c.provider, "mode": c.mode},
        actor.user_id,
    )
    record(db, c.organisation_id, actor.user_id, "connection.enabled", "connection", c.id, after={"mode": c.mode})
    db.commit()
    return render(db, c)


def disable(db: Session, actor: Actor, connection_id: str, reason: str | None) -> dict:
    c = get_connection(db, connection_id, lock=True)
    if c.enabled:
        _disable(db, c, (reason or "").strip() or "disabled by an administrator", actor.user_id)
        db.commit()
    return render(db, c)


def set_mode(db: Session, actor: Actor, connection_id: str, mode: str, confirm_live: bool) -> dict:
    c = get_connection(db, connection_id, lock=True)
    if mode not in MODES:
        raise HubError(422, "invalid_mode", "mode must be mock, sandbox or live")
    if mode == c.mode:
        return render(db, c)
    _info, provider = provider_of(c)
    if provider is None:
        raise HubError(409, "adapter_not_installed", f"adapter {c.adapter} is not installed")
    _require_mock_allowed(mode)
    if mode not in provider.modes:
        if mode == "live":
            raise HubError(409, "live_not_allowed", f"{c.provider} has no live mode in this adapter")
        raise HubError(422, "invalid_mode", f"{c.provider} does not support {mode} mode")
    if mode == "live":
        if not confirm_live:
            raise HubError(422, "invalid_mode", "confirm_live must be true to go live")
        _require_credentials(db, c, provider)
        status, _detail, _exp = check_health(db, c, mode="live")
        if status != "healthy":
            raise HubError(409, "health_check_failed", f"the live healthcheck answered {status}")
    before = c.mode
    c.mode = mode
    c.changed_at = c.updated_at = clock()
    publish(
        db,
        c.organisation_id,
        "connection.mode-changed",
        {"connection_id": c.id, "port": c.port, "provider": c.provider, "from_mode": before, "to_mode": mode},
        actor.user_id,
    )
    record(
        db,
        c.organisation_id,
        actor.user_id,
        "connection.mode-changed",
        "connection",
        c.id,
        after={"from_mode": before, "to_mode": mode},
    )
    db.commit()
    return render(db, c)
