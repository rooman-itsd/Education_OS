import pytest
from eos_notification.application import messages, preferences
from eos_notification.domain.errors import NotificationError
from notification_support import NOW, ScriptedTransport, outbox_events, reminder_request


def test_defaults_when_nothing_is_stored(db, org, as_org):
    with as_org(org):
        p = preferences.get_preferences(db, org.member.id)
    assert p["locale"] is None and p["quiet_hours"] is None
    assert p["channels"]["transactional"] == ["email", "in_app"] and p["channels"]["operational"] == ["email", "in_app"]


def test_a_user_of_another_organisation_is_a_404(db, org, other_org, as_org):
    with as_org(org), pytest.raises(NotificationError) as e:
        preferences.get_preferences(db, other_org.member.id)
    assert e.value.status == 404


def test_transactional_cannot_be_switched_off_but_other_categories_can(db, org, as_org):
    with as_org(org):
        p = preferences.set_preferences(db, org.member.id, channels={"transactional": [], "reminder": []})
    assert p["channels"]["transactional"] == ["email", "in_app"] and p["channels"]["reminder"] == []
    (event,) = outbox_events(db, org.id, "notification.preferences.changed")
    assert event.payload["categories_disabled"] == ["reminder"] and event.payload["user_id"] == org.member.id


def test_saving_the_same_preferences_again_publishes_no_second_event(db, org, as_org):
    with as_org(org):
        preferences.set_preferences(db, org.member.id, channels={"reminder": ["email"]})
        preferences.set_preferences(db, org.member.id, channels={"reminder": ["email"]})
    assert len(outbox_events(db, org.id, "notification.preferences.changed")) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"channels": {"nonsense": ["email"]}},
        {"channels": {"reminder": ["carrier-pigeon"]}},
        {"channels": "email"},
        {"channels": {}, "locale": "not a locale!"},
        {"channels": {}, "quiet_hours": {"start": "25:00", "end": "07:00", "timezone": "Asia/Kolkata"}},
        {"channels": {}, "quiet_hours": {"start": "21:00", "end": "07:00", "timezone": "Mars/Olympus"}},
        {"channels": {}, "quiet_hours": {"start": "21:00"}},
    ],
)
def test_invalid_preferences_are_rejected(db, org, as_org, kwargs):
    with as_org(org), pytest.raises(NotificationError) as e:
        preferences.set_preferences(db, org.member.id, **kwargs)
    assert e.value.status == 422


def test_quiet_hours_are_stored_but_not_enforced_in_this_release(db, org, as_org):
    window = {"start": "00:00", "end": "23:59", "timezone": "Asia/Kolkata"}
    with as_org(org):
        stored = preferences.set_preferences(db, org.member.id, channels={}, quiet_hours=window)
        assert stored["quiet_hours"] == window
        t = ScriptedTransport()
        m, _ = messages.send_message(db, transport=t, now=NOW, **reminder_request(user_id=org.member.id))
    assert m.status == "sent" and len(t.sent) == 1  # deferral needs the scheduler; documented, not implemented


def test_inbox_lists_unread_marks_read_and_is_private_to_the_user(db, org, other_org, as_org):
    with as_org(org):
        m, _ = messages.send_message(db, now=NOW, **reminder_request(user_id=org.member.id, channel="in_app"))
        items, unread = messages.list_inbox(db, org.member.id)
        assert [i.id for i in items] == [m.id] and unread == 1
        assert messages.list_inbox(db, org.admin.id) == ([], 0)  # someone else's inbox is empty
        with pytest.raises(NotificationError) as e:
            messages.mark_read(db, org.admin.id, m.id)  # not theirs
        assert e.value.status == 404
        messages.mark_read(db, org.member.id, m.id)
        messages.mark_read(db, org.member.id, m.id)  # idempotent
        assert messages.list_inbox(db, org.member.id)[1] == 0
        assert messages.list_inbox(db, org.member.id, unread_only=True)[0] == []
    with as_org(other_org), pytest.raises(NotificationError):
        messages.mark_read(db, org.member.id, m.id)


def test_the_inbox_organisation_filter_is_load_bearing_not_decoration(db, org, other_org, as_org):
    """A row with the SAME recipient_id but another organisation's id must not appear.

    The HTTP leak test cannot prove this: recipient ids are uuid4, so no two organisations ever share one, and
    filtering by recipient alone already looks correct. This constructs the case that filter actually exists
    for — the one RLS would otherwise be the only defence against — by writing the row directly.
    """
    from eos_notification.domain.models import Message

    with as_org(other_org):
        db.add(
            Message(
                organisation_id=other_org.id,
                template_key="billing.trial.reminder",
                channel="in_app",
                category="reminder",
                status="delivered",
                recipient_id=org.member.id,  # the SAME user id, under the other organisation
                recipient_key=org.member.id,
                body="not yours",
                body_template="not yours",
                variables={},
            )
        )
        db.commit()

    with as_org(org):
        rows, unread = messages.list_inbox(db, org.member.id)
    assert rows == [] and unread == 0, "an inbox returned a row belonging to another organisation"
