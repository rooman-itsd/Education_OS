"""The ports and the installed adapters (GET /ports, GET /adapters) and the super admin's cross-organisation overview
(GET /platform/overview). The overview reads counts only: no organisation's names, settings or people."""

from __future__ import annotations

import os
import re
from datetime import timedelta

from eos_core.tenant import platform_scope
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..infrastructure.models import Connection, Delivery
from ..infrastructure.ports import load_ports
from ..infrastructure.registry import AdapterInfo, ProviderInfo, get_registry
from .common import clock

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def platform_env_name(adapter: str, name: str) -> str:
    """A platform credential is an environment variable of the adapter: given as one (DIGILOCKER_CLIENT_SECRET), or
    as a short name, prefixed with the adapter's name (client_secret -> DIGILOCKER_CLIENT_SECRET)."""
    if _ENV_NAME.match(name):
        return name
    return f"{adapter.replace('-', '_').upper()}_{name.replace('-', '_').upper()}"


def missing_platform_credentials(adapter: str, provider: ProviderInfo) -> list[str]:
    return [n for n in provider.platform_credential_names if not os.environ.get(platform_env_name(adapter, n))]


def list_ports() -> list[dict]:
    registry = get_registry()
    out = []
    for spec in load_ports().values():
        out.append(
            {
                "id": spec.id,
                "name": spec.name,
                "version": spec.version,
                "operations": [{"name": n, "mode": m} for n, m in spec.operations.items()],
                "implemented_by": sorted(a.adapter for a in registry.adapters.values() if spec.id in dict(a.ports)),
            }
        )
    return out


def _provider_dict(info: AdapterInfo, p: ProviderInfo) -> dict:
    return {
        "provider": p.provider,
        "title": p.title,
        "ports": list(p.ports),
        "modes": list(p.modes),
        "auth": p.auth,
        "link_scope": p.link_scope,
        "inbound": list(p.inbound),
        "settings_schema": p.settings_schema,
        "credential_names": list(p.credential_names),
        "platform_credentials_present": not missing_platform_credentials(info.adapter, p),
    }


def list_adapters(port: str | None) -> list[dict]:
    out = []
    for info in sorted(get_registry().adapters.values(), key=lambda a: a.adapter):
        if port and port not in dict(info.ports):
            continue
        providers = [p for p in info.providers.values() if not port or port in p.ports]
        out.append(
            {
                "adapter": info.adapter,
                "version": info.version,
                "ports": [{"port": p, "version": v} for p, v in info.ports],
                "providers": [_provider_dict(info, p) for p in providers],
            }
        )
    return out


def overview(db: Session) -> dict:
    since = clock() - timedelta(hours=24)
    with platform_scope():
        by_mode = db.execute(
            select(
                Connection.adapter,
                Connection.provider,
                Connection.mode,
                func.count(func.distinct(Connection.organisation_id)),
            ).group_by(Connection.adapter, Connection.provider, Connection.mode)
        ).all()
        by_health = db.execute(
            select(
                Connection.adapter,
                Connection.provider,
                Connection.health_status,
                func.count(func.distinct(Connection.organisation_id)),
            )
            .where(Connection.enabled.is_(True))
            .group_by(Connection.adapter, Connection.provider, Connection.health_status)
        ).all()
        dead = db.execute(
            select(Connection.adapter, Connection.provider, func.count(Delivery.id))
            .join(Delivery, Delivery.connection_id == Connection.id)
            .where(Delivery.status == "dead_lettered", Delivery.completed_at >= since)
            .group_by(Connection.adapter, Connection.provider)
        ).all()
        db.rollback()
    rows: dict[tuple[str, str], dict] = {}

    def row(adapter: str, provider: str) -> dict:
        return rows.setdefault(
            (adapter, provider),
            {
                "adapter": adapter,
                "provider": provider,
                "platform_credentials_missing": [],
                "connections_by_mode": {},
                "connections_by_health": {},
                "dead_lettered_24h": 0,
            },
        )

    for info in get_registry().adapters.values():
        for p in info.providers.values():
            row(info.adapter, p.provider)["platform_credentials_missing"] = missing_platform_credentials(
                info.adapter, p
            )
    for adapter, provider, mode, n in by_mode:
        row(adapter, provider)["connections_by_mode"][mode] = n
    for adapter, provider, status, n in by_health:
        row(adapter, provider)["connections_by_health"][status] = n
    for adapter, provider, n in dead:
        row(adapter, provider)["dead_lettered_24h"] = n
    return {"items": [rows[k] for k in sorted(rows)]}
