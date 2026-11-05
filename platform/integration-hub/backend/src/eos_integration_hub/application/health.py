"""The scheduled healthcheck: every enabled connection whose last check is older than
INTEGRATION_HUB_HEALTH_INTERVAL_MIN. A transition publishes integration-hub.connection.health-changed once."""

from __future__ import annotations

import logging
from datetime import timedelta

from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..infrastructure.config import HubConfig
from ..infrastructure.models import Connection
from . import connections
from .common import clock, get_connection

log = logging.getLogger("eos.integration_hub")


def check_due(db: Session) -> int:
    config = HubConfig.from_env()
    cutoff = clock() - timedelta(minutes=config.health_interval_min)
    with platform_scope():
        due = db.execute(
            select(Connection.id, Connection.organisation_id).where(
                Connection.enabled.is_(True),
                or_(Connection.health_checked_at.is_(None), Connection.health_checked_at <= cutoff),
            )
        ).all()
        db.rollback()
    checked = 0
    for connection_id, org in due:
        with organisation_scope(org):
            try:
                c = get_connection(db, connection_id)
                connections.apply_health(db, c, *connections.check_health(db, c))
                db.commit()
                checked += 1
            except Exception as e:  # noqa: BLE001 - one connection must not stop the others
                db.rollback()
                log.warning("healthcheck of %s failed: %s", connection_id, type(e).__name__)
    return checked
