"""Schema rules: the constraints themselves. These are NOT evidence of row-level security, which is covered by
test_postgres.py. They run on both SQLite and PostgreSQL."""

import uuid

import pytest
from eos_core.db import TenantMixin
from eos_core.tenant import platform_scope
from eos_notification.domain.models import STATUSES, TRANSITIONS, Message, Preference, TemplateOverride
from sqlalchemy.exc import IntegrityError


@pytest.fixture(autouse=True)
def _as_platform():
    """These tests write rows for several made-up organisations in one transaction on purpose, to prove the
    CONSTRAINTS hold. On PostgreSQL the tenant_isolation policy refuses those writes before any constraint is
    reached, so they run as the platform. On SQLite this only sets a ContextVar and changes nothing."""
    with platform_scope():
        yield


def message(org_id, **kw):
    base = dict(
        organisation_id=org_id,
        template_key="billing.trial.reminder",
        channel="email",
        recipient_key="a@example.com",
        variables={},
        body_template="b",
    )
    base.update(kw)
    return Message(**base)


def test_organisation_id_is_not_null_on_every_table_even_though_the_mixin_allows_null():
    assert TenantMixin.organisation_id.column.nullable is True
    for model in (Message, TemplateOverride, Preference):
        assert model.__table__.c.organisation_id.nullable is False, model


@pytest.mark.parametrize("value", [None, ""])
def test_missing_or_empty_organisation_is_rejected_by_the_database(db, value):
    db.add(message(value))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_client_token_is_unique_per_organisation_only(db):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    db.add_all([message(a, client_token="t1"), message(b, client_token="t1")])
    db.flush()  # same token in two organisations is fine
    db.add(message(a, client_token="t1"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_missing_client_token_is_not_deduplicated(db):
    org = str(uuid.uuid4())
    db.add_all([message(org), message(org)])
    db.flush()
    db.rollback()


def test_event_key_is_per_event_template_channel_and_recipient(db):
    org, event = str(uuid.uuid4()), str(uuid.uuid4())
    db.add_all(
        [message(org, source_event_id=event), message(org, source_event_id=event, recipient_key="b@example.com")]
    )
    db.flush()  # one event may notify two people
    db.add(message(org, source_event_id=event))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_transition_table_covers_every_status_and_only_known_ones():
    assert set(TRANSITIONS) == set(STATUSES)
    assert all(targets <= set(STATUSES) for targets in TRANSITIONS.values())
    assert TRANSITIONS["suppressed"] == frozenset()
    assert "sent" in TRANSITIONS["sending"]
