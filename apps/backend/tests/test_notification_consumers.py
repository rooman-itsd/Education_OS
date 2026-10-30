"""#316's actual promise, end to end with the installed modules and no stand-ins: a trial that is ending makes
billing raise an event, the relay delivers it to notification, and the organisation's admin really gets the mail.

Every link here is the deployment's own wiring — the jobs, consumers and organisation directory each module
declares on its entry points — so this fails if any of them is missing, which is how it was missing before."""

import uuid
from datetime import UTC, datetime, timedelta

from eos_billing.domain.models import Subscription
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope, platform_scope
from eos_event_bus.application.consumers import discover as discover_consumers
from eos_event_bus.application.relay import Relay
from eos_event_bus.application.transport import InProcessTransport
from eos_event_bus.infrastructure.config import EventBusConfig
from eos_identity.application.service import create_user
from eos_notification.application import organisations
from eos_notification.infrastructure import transport as mail
from eos_scheduler.application.jobs import discover as discover_jobs
from eos_scheduler.application.ticker import Ticker
from eos_scheduler.domain.models import Schedule
from eos_scheduler.infrastructure.config import SchedulerConfig
from eos_tenancy.domain.models import Organisation
from sqlalchemy import select

ACADEMY = "Harmony School of Music"


def _organisation_with_admin() -> tuple[str, str]:
    """A real tenancy organisation and a real identity admin, as registration would leave them."""
    with platform_scope(), SessionLocal() as db:
        org = Organisation(
            name=ACADEMY, slug=f"chain-{uuid.uuid4().hex[:8]}", academy_type="music-academy", status="active"
        )
        db.add(org)
        db.commit()
        organisation_id = org.id
    with organisation_scope(organisation_id), SessionLocal() as db:
        admin = create_user(
            db,
            organisation_id=organisation_id,
            email=f"admin-{uuid.uuid4().hex[:8]}@harmony.example.com",
            name="Admin",
            password="Passw0rd!x",
            roles=["org-admin"],
        )
        db.commit()
        return organisation_id, admin.email


def _drain(relay: Relay) -> None:
    for _ in range(20):
        if relay.run_once().claimed == 0:
            return
    raise AssertionError("the outbox did not drain")


def test_the_organisation_directory_is_wired_so_the_relays_process_can_resolve_a_name(client):
    """Not the API's startup: the relay runs as its own process and finds this on the entry point."""
    organisations.reset_cache()
    organisation_id, _ = _organisation_with_admin()
    with SessionLocal() as db:
        assert organisations.hooks.name(db, organisation_id) == ACADEMY


def test_a_trial_ending_in_three_days_really_mails_the_admin(client):
    organisations.reset_cache()
    organisation_id, address = _organisation_with_admin()
    now = datetime.now(UTC)
    with organisation_scope(organisation_id), SessionLocal() as db:
        db.add(
            Subscription(
                organisation_id=organisation_id,
                plan_id="trial",
                status="trialing",
                trial_ends_at=now + timedelta(days=3, hours=1),
            )
        )
        db.commit()

    jobs = discover_jobs()
    ticker = Ticker(jobs, SchedulerConfig(), clock=lambda: now)
    ticker.seed_platform_defaults()
    with platform_scope(), SessionLocal() as db:
        schedule = db.scalar(select(Schedule).where(Schedule.job == "billing.trial-reminders"))
        schedule.next_run_at = now - timedelta(seconds=1)
        db.commit()
    assert ticker.tick().fired >= 1

    mail.sent.clear()
    _drain(Relay(InProcessTransport(discover_consumers()), EventBusConfig()))

    ours = [m for m in mail.sent if m.get("to") == address]
    assert len(ours) == 1, f"the admin was not mailed; sent={[m.get('to') for m in mail.sent]}"
    assert "3 day(s)" in ours[0]["subject"] and ACADEMY in ours[0]["body"]

    # A second run on the same day (catch-up, run-now, or job firing twice) must not mail the admin twice:
    with platform_scope(), SessionLocal() as db:
        schedule = db.scalar(select(Schedule).where(Schedule.job == "billing.trial-reminders"))
        schedule.next_run_at = now - timedelta(seconds=1)
        db.commit()
    assert ticker.tick().fired >= 1
    _drain(Relay(InProcessTransport(discover_consumers()), EventBusConfig()))
    ours = [m for m in mail.sent if m.get("to") == address]
    assert len(ours) == 1, "repeated reminder run on the same day mailed the admin twice"


def test_every_module_that_publishes_a_consumed_event_is_matched_by_a_consumer(client):
    """The gap this test exists for: notification declared the events in its contract but registered no
    consumer, so the relay delivered them to nobody and marked them published."""
    consumers = discover_consumers()
    for name in ("billing.trial.expiring", "billing.trial.expired", "tenancy.organisation.approved"):
        assert any(module == "notification" for module, _ in consumers.for_event(name)), name
