"""The scheduled healthcheck: every enabled connection whose last check is older than
INTEGRATION_HUB_HEALTH_INTERVAL_MIN. A transition publishes integration-hub.connection.health-changed once.

Due connections are listed across organisations; each is then checked as its own organisation (as_organisation: no
platform scope, row-level security on), in its own transaction."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..infrastructure.config import HubConfig
from ..infrastructure.models import Connection
from . import connections
from .common import as_organisation, clock, get_connection, platform_rows

log = logging.getLogger("eos.integration_hub")

BUDGET_S = 50  # stop starting checks after this long; the next run (every 15 minutes) takes the rest


def _check_one(db: Session, connection_id: str) -> int:
    c = get_connection(db, connection_id)
    connections.apply_health(db, c, *connections.check_health(db, c))
    db.commit()
    return 1


def check_due(*, budget_s: float = BUDGET_S) -> int:
    config = HubConfig.from_env()
    cutoff = clock() - timedelta(minutes=config.health_interval_min)
    due = platform_rows(
        select(Connection.id, Connection.organisation_id).where(
            Connection.enabled.is_(True),
            or_(Connection.health_checked_at.is_(None), Connection.health_checked_at <= cutoff),
        )
    )
    deadline = time.monotonic() + budget_s
    checked = 0
    for connection_id, org in due:
        if checked and time.monotonic() > deadline:
            break
        try:
            checked += as_organisation(org, _check_one, connection_id)
        except Exception as e:  # noqa: BLE001 - one connection must not stop the others
            log.warning("healthcheck of %s failed: %s", connection_id, type(e).__name__)
    return checked
