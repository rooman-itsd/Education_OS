"""D14: notification history past NOTIFICATION_HISTORY_RETENTION_DAYS is deleted, per organisation, and nothing
that still has to be sent is touched."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_notification.application import consumers, jobs, retention
from eos_notification.domain.models import STATUSES, Message
from eos_notification.infrastructure.config import NotificationConfig
from sqlalchemy import func, select
from test_consumers import finished_reports, job_due, run_job

NOW = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=120)
RECENT = NOW - timedelta(days=10)


def _add(org_id, status, when, **over) -> str:
    with organisation_scope(org_id), SessionLocal() as db:
        m = Message(
            organisation_id=org_id,
            template_key="billing.trial.expired",
            channel="email",
            recipient_key="private.person@college.example.com",
            recipient_address="private.person@college.example.com",
            variables={"organisation_name": "C"},
            body_template="Trial over",
            status=status,
            created_at=when,
            updated_at=when,
            **over,
        )
        db.add(m)
        db.commit()
        return m.id


def _ids(org_id) -> set[str]:
    with organisation_scope(org_id), SessionLocal() as db:
        return set(db.scalars(select(Message.id).where(Message.organisation_id == org_id)).all())


def test_finished_messages_past_retention_are_deleted_and_recent_ones_kept(org):
    old = {s: _add(org.id, s, OLD) for s in ("sent", "delivered", "failed", "bounced", "suppressed")}
    recent = _add(org.id, "sent", RECENT)
    counts = retention.prune_history(now=NOW)
    assert counts == {"organisations": 1, "deleted": 5, "errors": 0}
    assert _ids(org.id) == {recent} and not set(old.values()) & _ids(org.id)


def test_messages_not_yet_sent_are_kept_however_old(org):
    queued = _add(org.id, "queued", OLD, next_attempt_at=NOW)
    sending = _add(org.id, "sending", OLD, lease_expires_at=NOW)
    done = _add(org.id, "sent", OLD)
    retention.prune_history(now=NOW)
    assert _ids(org.id) == {queued, sending}
    assert done not in _ids(org.id)


def test_every_status_is_either_kept_as_pending_or_purged_when_old(org):
    assert set(retention.FINISHED) | {"queued", "sending"} == set(STATUSES)


def test_only_the_organisations_with_old_history_are_purged_and_each_in_its_own_scope(org, other_org):
    mine, theirs = _add(org.id, "sent", OLD), _add(other_org.id, "sent", RECENT)
    other_old = _add(other_org.id, "failed", OLD)
    counts = retention.prune_history(now=NOW, organisation_id=org.id)
    assert counts["organisations"] == 1 and counts["deleted"] == 1
    assert _ids(org.id) == set() and _ids(other_org.id) == {theirs, other_old}  # other org untouched when not named
    counts = retention.prune_history(now=NOW)
    assert counts == {"organisations": 1, "deleted": 1, "errors": 0}
    assert _ids(other_org.id) == {theirs} and mine not in _ids(org.id)


def test_a_second_run_finds_nothing(org):
    _add(org.id, "sent", OLD)
    assert retention.prune_history(now=NOW)["deleted"] == 1
    assert retention.prune_history(now=NOW) == {"organisations": 0, "deleted": 0, "errors": 0}


def test_the_setting_is_honoured(org, monkeypatch):
    twenty_days = _add(org.id, "sent", NOW - timedelta(days=20))
    forty_days = _add(org.id, "sent", NOW - timedelta(days=40))
    monkeypatch.setenv("NOTIFICATION_HISTORY_RETENTION_DAYS", "30")
    retention.prune_history(now=NOW)
    assert _ids(org.id) == {twenty_days}
    monkeypatch.setenv("NOTIFICATION_HISTORY_RETENTION_DAYS", "7")
    retention.prune_history(now=NOW)
    assert _ids(org.id) == set() and forty_days not in _ids(org.id)


def test_the_default_is_ninety_days(org):
    inside, outside = _add(org.id, "sent", NOW - timedelta(days=89)), _add(org.id, "sent", NOW - timedelta(days=91))
    retention.prune_history(now=NOW)
    assert _ids(org.id) == {inside} and outside not in _ids(org.id)


@pytest.mark.parametrize(
    "configured,expected",
    [("90", 90), ("0", 1), ("-5", 1), ("1", 1), ("not-a-number", 90), ("", 90), ("99999999999", 36_500)],
)
def test_the_retention_setting_is_clamped_to_one_day_and_a_ceiling(monkeypatch, configured, expected):
    monkeypatch.setenv("NOTIFICATION_HISTORY_RETENTION_DAYS", configured)
    assert NotificationConfig.from_env().history_retention_days == expected


def test_a_retention_of_zero_never_deletes_todays_history(org, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_HISTORY_RETENTION_DAYS", "0")
    today = _add(org.id, "sent", NOW - timedelta(hours=2))
    retention.prune_history(now=NOW)
    assert _ids(org.id) == {today}


def test_a_failing_organisation_does_not_stop_the_others(org, other_org, monkeypatch):
    _add(org.id, "sent", OLD)
    _add(other_org.id, "sent", OLD)
    real = retention._prune_organisation

    def flaky(factory, o, stale):
        if o == org.id:
            raise RuntimeError("boom private.person@college.example.com")
        return real(factory, o, stale)

    monkeypatch.setattr(retention, "_prune_organisation", flaky)
    counts = retention.prune_history(now=NOW)
    assert counts["errors"] == 1 and counts["deleted"] == 1 and _ids(other_org.id) == set()


def test_a_large_backlog_is_deleted_in_batches(org, monkeypatch):
    monkeypatch.setattr(retention, "BATCH", 3)
    for _ in range(8):
        _add(org.id, "sent", OLD)
    assert retention.prune_history(now=NOW)["deleted"] == 8 and _ids(org.id) == set()


# the scheduled job -------------------------------------------------------------------------------------------


def test_the_job_is_declared_for_the_scheduler():
    spec = jobs.JOBS["notification.prune-history"]
    assert spec["scope"] == "platform" and spec["idempotent"] is True and spec["default_cron"] == "45 2 * * *"


def test_the_due_event_runs_the_purge_and_reports_job_finished(org):
    _add(org.id, "sent", datetime.now(UTC) - timedelta(days=200))
    keep = _add(org.id, "queued", datetime.now(UTC) - timedelta(days=200))
    run_id = str(uuid.uuid4())
    run_job(job_due("notification.prune-history", run_id))
    assert _ids(org.id) == {keep}
    (report,) = finished_reports(run_id)
    assert report["outcome"] == "succeeded" and "deleted 1" in report["detail"]


def test_a_partial_failure_is_reported_as_failed(org, monkeypatch):
    monkeypatch.setattr(retention, "prune_history", lambda: {"organisations": 1, "deleted": 0, "errors": 1})
    run_id = str(uuid.uuid4())
    run_job(job_due("notification.prune-history", run_id))
    (report,) = finished_reports(run_id)
    assert report["outcome"] == "failed"


def test_the_recovery_job_does_not_purge(org):
    old = _add(org.id, "sent", datetime.now(UTC) - timedelta(days=200))
    run_job(job_due("notification.recover-stuck"))
    assert old in _ids(org.id)
    assert consumers.CONSUMERS["scheduler.job.due"] is consumers.on_job_due
    with platform_scope(), SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) >= 1
