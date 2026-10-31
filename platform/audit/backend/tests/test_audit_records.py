"""The write path, the read path and retention, through the service layer that a module's SDK call will use."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from audit_support import Org
from eos_audit.application import service
from eos_audit.application.service import AuditError
from eos_audit.domain.models import AuditRecord
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import func, select, update


def _write(audit_db, org: str | None = None, **over):
    fields = {
        "organisation_id": org,
        "actor": None,
        "module": "admissions",
        "action": "application.accepted",
        "entity_type": "application",
        "entity_id": str(uuid.uuid4()),
    }
    fields.update(over)
    rec, created = service.record(audit_db, **fields)
    audit_db.commit()
    return rec, created


def _count(audit_db) -> int:
    with platform_scope():
        return audit_db.scalar(select(func.count()).select_from(AuditRecord))


# --- writing ---------------------------------------------------------------------------------------------


def test_a_record_is_appended_with_what_it_was_given(audit_db):
    org = str(uuid.uuid4())
    rec, created = _write(
        audit_db, org, summary="Accepted", before={"status": "submitted"}, after={"status": "accepted"}
    )
    assert created and rec.organisation_id == org
    assert rec.before == {"status": "submitted"} and rec.after == {"status": "accepted"}
    assert rec.context == {} and rec.redacted is False and rec.occurred_at is not None


def test_record_rides_the_callers_transaction_so_a_rolled_back_change_leaves_no_record(audit_db):
    """A module records a change in the same transaction that makes it: if the change is rolled back, so is the
    record. That is why record() flushes but never commits."""
    service.record(audit_db, organisation_id=str(uuid.uuid4()), actor=None, module="admissions",
                   action="application.accepted", entity_type="application", entity_id="a1")  # fmt: skip
    audit_db.rollback()
    assert _count(audit_db) == 0


def test_a_replayed_client_token_returns_the_original_and_appends_nothing(audit_db):
    org = str(uuid.uuid4())
    first, created = _write(audit_db, org, client_token="t-1", summary="first")
    again, created_again = _write(audit_db, org, client_token="t-1", summary="second")
    assert created and not created_again and again.id == first.id and again.summary == "first"
    assert _count(audit_db) == 1


def test_a_replayed_token_is_idempotent_for_platform_records_too(audit_db):
    """Platform records have a null organisation. A unique index on the raw columns would let both through,
    because NULLs are distinct; the index is on coalesce(organisation_id, '') for exactly this case."""
    first, _ = _write(audit_db, None, client_token="platform-1")
    again, created = _write(audit_db, None, client_token="platform-1")
    assert not created and again.id == first.id and _count(audit_db) == 1


def test_the_same_token_in_two_organisations_is_two_records(audit_db):
    a, _ = _write(audit_db, str(uuid.uuid4()), client_token="shared")
    b, created = _write(audit_db, str(uuid.uuid4()), client_token="shared")
    assert created and a.id != b.id and _count(audit_db) == 2


@pytest.mark.parametrize(
    "over, message",
    [
        ({"module": ""}, "module is required"),
        ({"action": "Accepted"}, "action must be"),
        ({"action": "accepted"}, "action must be"),
        ({"entity_id": "x" * 121}, "entity_id is longer"),
        ({"summary": "x" * 301}, "summary is longer"),
        ({"before": ["not", "an", "object"]}, "before must be an object"),
        ({"after": {"when": datetime(2026, 1, 1)}}, "after must be plain JSON"),
    ],
)
def test_an_invalid_record_is_refused_and_nothing_is_written(audit_db, over, message):
    with pytest.raises(AuditError, match=message) as e:
        _write(audit_db, str(uuid.uuid4()), **over)
    assert e.value.status == 422 and _count(audit_db) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "hunter2"},
        {"user": {"password_hash": "x"}},
        {"items": [{"api_key": "k"}]},
        {"refresh_token": "r"},
        {"client_secret": "s"},
    ],
)
def test_a_payload_carrying_a_secret_is_refused(audit_db, payload):
    """The contract: before/after are never secrets, passwords or tokens. Record that it changed, not the value."""
    with pytest.raises(AuditError, match="looks like a secret"):
        _write(audit_db, str(uuid.uuid4()), after=payload)
    assert _count(audit_db) == 0


def test_an_identifier_that_merely_mentions_a_token_is_allowed(audit_db):
    rec, created = _write(audit_db, str(uuid.uuid4()), after={"token_id": "issuance-7"})
    assert created and rec.after == {"token_id": "issuance-7"}


def test_an_oversized_payload_is_refused_rather_than_truncated(audit_db, monkeypatch):
    monkeypatch.setenv("AUDIT_MAX_PAYLOAD_BYTES", "40")
    with pytest.raises(AuditError, match="the limit is 40"):
        _write(audit_db, str(uuid.uuid4()), after={"note": "x" * 50})
    assert _count(audit_db) == 0


# --- reading ---------------------------------------------------------------------------------------------


def _at(audit_db, rec, when: datetime):
    """Set occurred_at directly. Fine on SQLite, which has no immutability trigger; never possible on PostgreSQL."""
    with platform_scope():
        audit_db.execute(update(AuditRecord).where(AuditRecord.id == rec.id).values(occurred_at=when))
        audit_db.commit()


def test_an_organisation_never_sees_another_organisations_records(audit_db):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    mine, _ = _write(audit_db, a)
    theirs, _ = _write(audit_db, b)
    page = service.search(audit_db, organisation_id=a)
    assert [r["id"] for r in page["items"]] == [mine.id] and page["total"] == 1
    with pytest.raises(AuditError) as e:
        service.get_record(audit_db, organisation_id=a, record_id=theirs.id, any_organisation=False)
    assert e.value.status == 404  # never a 403: the record's existence is not disclosed


def test_platform_records_and_organisation_records_never_mix(audit_db):
    org = str(uuid.uuid4())
    platform, _ = _write(audit_db, None, module="tenancy", action="organisation.approved")
    _write(audit_db, org)
    assert [r["id"] for r in service.search(audit_db, organisation_id=None)["items"]] == [platform.id]
    assert platform.id not in {r["id"] for r in service.search(audit_db, organisation_id=org)["items"]}


def test_search_is_newest_first_and_pages(audit_db):
    org = str(uuid.uuid4())
    base = datetime(2026, 10, 1, tzinfo=UTC)
    recs = [_write(audit_db, org)[0] for _ in range(3)]
    for i, rec in enumerate(recs):
        _at(audit_db, rec, base + timedelta(days=i))
    page = service.search(audit_db, organisation_id=org, limit=2)
    assert [r["id"] for r in page["items"]] == [recs[2].id, recs[1].id] and page["total"] == 3
    assert [r["id"] for r in service.search(audit_db, organisation_id=org, limit=2, offset=2)["items"]] == [recs[0].id]


def test_search_filters(audit_db):
    org = str(uuid.uuid4())
    actor = str(uuid.uuid4())
    accepted, _ = _write(
        audit_db, org, action="application.accepted", actor=actor, entity_type="application", entity_id="e1"
    )
    rejected, _ = _write(audit_db, org, action="application.rejected")
    other, _ = _write(audit_db, org, module="hostel", action="leave.overdue", entity_type="leave")

    def ids(**f):
        return {r["id"] for r in service.search(audit_db, organisation_id=org, **f)["items"]}

    assert ids(module="hostel") == {other.id}
    assert ids(action="application.rejected") == {rejected.id}
    assert ids(action="application.*") == {accepted.id, rejected.id}
    assert ids(actor=actor) == {accepted.id}
    assert ids(entity_type="application", entity_id="e1") == {accepted.id}


def test_an_action_prefix_is_literal_so_a_wildcard_character_matches_nothing_extra(audit_db):
    org = str(uuid.uuid4())
    _write(audit_db, org, action="application.accepted")
    assert service.search(audit_db, organisation_id=org, action="appl%*")["total"] == 0
    assert service.search(audit_db, organisation_id=org, action="appl_cation.*")["total"] == 0


def test_search_by_time_window(audit_db):
    org = str(uuid.uuid4())
    old, _ = _write(audit_db, org)
    new, _ = _write(audit_db, org)
    _at(audit_db, old, datetime(2026, 1, 1, tzinfo=UTC))
    _at(audit_db, new, datetime(2026, 6, 1, tzinfo=UTC))
    window = service.search(
        audit_db, organisation_id=org, occurred_from=datetime(2026, 3, 1), occurred_to=datetime(2026, 9, 1)
    )
    assert [r["id"] for r in window["items"]] == [new.id]


def test_the_page_size_is_capped_by_configuration(audit_db, monkeypatch):
    org = str(uuid.uuid4())
    for _ in range(3):
        _write(audit_db, org)
    monkeypatch.setenv("AUDIT_MAX_PAGE_SIZE", "2")
    assert len(service.search(audit_db, organisation_id=org, limit=200)["items"]) == 2


def test_history_is_the_whole_story_of_one_entity_oldest_first(audit_db):
    org = str(uuid.uuid4())
    created, _ = _write(audit_db, org, action="application.created", entity_id="app-9")
    accepted, _ = _write(audit_db, org, action="application.accepted", entity_id="app-9")
    _write(audit_db, org, entity_id="someone-else")
    _at(audit_db, created, datetime(2026, 1, 1, tzinfo=UTC))
    _at(audit_db, accepted, datetime(2026, 2, 1, tzinfo=UTC))
    story = service.history(audit_db, organisation_id=org, entity_type="application", entity_id="app-9")
    assert [r["action"] for r in story["items"]] == ["application.created", "application.accepted"]


def test_the_actor_name_is_resolved_at_read_time(audit_db):
    org = Org(audit_db)
    rec, _ = _write(audit_db, org.id, actor=org.admin.id)
    assert service.view(audit_db, rec)["actor_name"] == "admin"
    with organisation_scope(org.id):
        org.admin.name = "Renamed Admin"
        audit_db.commit()
    assert service.view(audit_db, rec)["actor_name"] == "Renamed Admin"


# --- retention ---------------------------------------------------------------------------------------------


def _pruned_events(audit_db) -> list[dict]:
    with platform_scope():
        return [
            e.payload for e in audit_db.scalars(select(OutboxEvent).where(OutboxEvent.name == "audit.retention.pruned"))
        ]


def test_prune_removes_only_the_window_past_retention_and_says_so(audit_db, monkeypatch):
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "3000")
    now = datetime(2026, 10, 24, tzinfo=UTC)
    old, _ = _write(audit_db, str(uuid.uuid4()))
    kept, _ = _write(audit_db, str(uuid.uuid4()))
    _at(audit_db, old, now - timedelta(days=3001))
    _at(audit_db, kept, now - timedelta(days=2999))
    assert service.prune(audit_db, now=now) == 1
    with platform_scope():
        assert set(audit_db.scalars(select(AuditRecord.id))) == {kept.id}
    assert [e["removed_count"] for e in _pruned_events(audit_db)] == [1]


def test_every_prune_run_is_accounted_for_even_when_nothing_was_old_enough(audit_db):
    _write(audit_db, str(uuid.uuid4()))
    assert service.prune(audit_db) == 0
    assert [e["removed_count"] for e in _pruned_events(audit_db)] == [0]


def test_retention_below_the_floor_is_raised_to_it_not_honoured(audit_db, monkeypatch):
    """Deleting cannot be undone, so a mistaken low setting keeps records rather than losing them."""
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "30")
    now = datetime(2026, 10, 24, tzinfo=UTC)
    rec, _ = _write(audit_db, str(uuid.uuid4()))
    _at(audit_db, rec, now - timedelta(days=100))
    assert service.prune(audit_db, now=now) == 0 and _count(audit_db) == 1


def test_retention_can_be_turned_off(audit_db, monkeypatch):
    monkeypatch.setenv("AUDIT_RETENTION_ENABLED", "false")
    rec, _ = _write(audit_db, str(uuid.uuid4()))
    _at(audit_db, rec, datetime(2000, 1, 1, tzinfo=UTC))
    assert service.prune(audit_db) == 0 and _count(audit_db) == 1 and _pruned_events(audit_db) == []
