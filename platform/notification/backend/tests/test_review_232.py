"""Regressions from the PR #232 review: values the database or a provider could hand back that the code took on
trust (rendered subject length, provider id length, retry hints), a CRLF in a subject override, and the own-
preferences check on a non-canonical id."""

import pathlib

import pytest
from eos_core import config as core_config
from eos_notification.api.router import router
from eos_notification.application import messages, templates
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure.config import NotificationConfig
from eos_notification.infrastructure.templates import render
from eos_notification.infrastructure.transport import AdapterTransport, SendResult
from fastapi import FastAPI
from fastapi.testclient import TestClient
from notification_support import NOW, PREFIX, ScriptedTransport, later, outbox_events, reminder_request
from sqlalchemy import func, select
from sqlalchemy.exc import DataError


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    real = core_config.load_role_grants()
    monkeypatch.setattr(core_config, "load_role_grants", lambda: {**real, "test-sender": {"notification:message:send"}})


class _Provider:
    def __init__(self, **result):
        self.result = type("R", (), result)()

    def send(self, **kwargs):
        return self.result


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(Message)) or 0


# F1 -----------------------------------------------------------------------------------------------------------


def test_a_rendered_subject_longer_than_its_column_is_a_422_and_queues_nothing(db, org, as_org):
    request = reminder_request(
        template="billing.invoice.issued",
        variables={"organisation_name": "x" * 2000, "invoice_number": "1", "amount": "1", "due_on": "d"},
    )
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.send_message(db, transport=ScriptedTransport(), **request)
    assert e.value.status == 422 and "x" not in e.value.detail
    db.rollback()
    with as_org(org):
        # Counted inside the scope on purpose. Outside it, on PostgreSQL, row-level security hides every row,
        # so the assertion would pass whatever was written; and the SELECT would open a transaction with no
        # tenant that the block below would then inherit, because app.organisation_id is written once on
        # after_begin and never re-written -- the write would be refused by the policy.
        assert _count(db) == 0
    # the same bound applies to an organisation's own wording
    with as_org(org):
        templates.upsert_template(
            db,
            key="billing.trial.reminder",
            channel="email",
            locale="en",
            subject="y" * 280 + " ${days_left}",
            body="b",
        )
        with pytest.raises(NotificationError) as e:
            messages.send_message(
                db,
                transport=ScriptedTransport(),
                **reminder_request(variables={"organisation_name": "C", "trial_ends_on": "d", "days_left": "x" * 20}),
            )
    assert e.value.status == 422
    db.rollback()
    with as_org(org):
        assert _count(db) == 0


def test_a_data_error_on_insert_is_a_500_that_exposes_no_row_values(db, org, as_org, monkeypatch, caplog):
    address = "leak-me@college.example.com"

    def refuse(*_a, **_k):
        raise DataError("INSERT ...", {"recipient_address": address}, Exception("value too long"))

    monkeypatch.setattr(db, "flush", refuse)
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.accept_message(db, **reminder_request(recipient={"address": address}))
    assert e.value.status == 500 and address not in e.value.detail
    assert address not in str(e.value.__cause__) and address not in caplog.text


# F2 -----------------------------------------------------------------------------------------------------------


def test_a_provider_message_id_that_does_not_fit_the_column_is_dropped_not_cut():
    long_id = AdapterTransport(lambda ch: _Provider(accepted=True, provider_message_id="p" * 500)).send(_outbound())
    assert long_id.accepted and long_id.provider_message_id is None  # the send succeeded; only the id is gone
    odd = AdapterTransport(lambda ch: _Provider(accepted=True, provider_message_id=12345)).send(_outbound())
    assert odd.accepted and odd.provider_message_id is None
    fits = AdapterTransport(lambda ch: _Provider(accepted=True, provider_message_id="p" * 200)).send(_outbound())
    assert fits.provider_message_id == "p" * 200  # exactly the column width is a valid id, not an edge to trim


def _sent_event(db, org, message_id: str) -> dict:
    """The sent event for exactly this message. outbox_events filters by organisation and name, and conftest's
    _clean empties the outbox between tests, so tuple-unpacking asserts there is one and only one."""
    (event,) = outbox_events(db, org.id, "notification.message.sent")
    assert event.payload["message_id"] == message_id  # the event under test, not a neighbour's
    return event.payload


def test_the_service_drops_an_oversized_provider_id_whatever_transport_returned_it(db, org, as_org):
    """AdapterTransport screens the id, but it is not the only Transport and the write path cannot assume one.
    A 500-character id would fail the SENT update after the provider had already accepted the message, and
    recovery would then send it again. The delivery must stand; only the unusable reference goes."""
    with as_org(org):
        transport = ScriptedTransport(SendResult(True, provider_message_id="p" * 500))
        message, _ = messages.send_message(db, transport=transport, **reminder_request())
        stored = messages.get_message(db, message.id)  # reloaded from the database, not the in-memory row
        assert stored.status == "sent", "the message was delivered; only its reference was unusable"
        assert stored.provider_message_id is None
        assert _sent_event(db, org, message.id)["provider_message_id"] == stored.provider_message_id


def test_a_provider_id_that_fits_the_column_is_stored_and_published_unchanged(db, org, as_org):
    """The guard must not damage a legitimate id, including one exactly at the column width."""
    exact = "p" * 200
    with as_org(org):
        message, _ = messages.send_message(
            db, transport=ScriptedTransport(SendResult(True, provider_message_id=exact)), **reminder_request()
        )
        stored = messages.get_message(db, message.id)
        assert stored.status == "sent" and stored.provider_message_id == exact
        assert _sent_event(db, org, message.id)["provider_message_id"] == exact


def test_a_non_string_provider_id_is_dropped_rather_than_coerced(db, org, as_org):
    """12345 is not a receipt id. Storing "12345" would invent a reference the provider never issued, which no
    receipt could match and a support engineer would trust."""
    with as_org(org):
        message, _ = messages.send_message(
            db, transport=ScriptedTransport(SendResult(True, provider_message_id=12345)), **reminder_request()
        )
        stored = messages.get_message(db, message.id)
        assert stored.status == "sent" and stored.provider_message_id is None
        assert _sent_event(db, org, message.id)["provider_message_id"] is None


@pytest.mark.parametrize(
    "provider_id",
    [
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
        pytest.param(12345, id="int"),
        pytest.param(b"abc", id="bytes"),
        pytest.param(["x"], id="list"),
        pytest.param("p" * 201, id="one-over-the-column"),
        pytest.param("p" * 500, id="far-over-the-column"),
    ],
)
def test_an_unusable_provider_id_never_reaches_the_row_or_the_event(db, org, as_org, provider_id):
    """Every input class the port can hand back, driven straight into the service through ScriptedTransport so
    AdapterTransport's own screening is not what is being measured. In each case the provider accepted the
    message, so the send must stand: an unusable optional reference may not become a failure or a retry."""
    with as_org(org):
        transport = ScriptedTransport(SendResult(True, provider_message_id=provider_id))
        message, _ = messages.send_message(db, transport=transport, **reminder_request())
        stored = messages.get_message(db, message.id)
    assert stored.status == "sent" and stored.attempts == 1, "delivery succeeded; only the reference was unusable"
    assert stored.provider_message_id is None
    assert _sent_event(db, org, message.id)["provider_message_id"] is None


def test_a_provider_id_one_character_under_the_column_is_kept(db, org, as_org):
    """200 is kept and 201 is dropped, so the boundary is tested from both sides; 199 guards the comparison
    itself against an off-by-one that would reject everything short."""
    almost = "p" * 199
    with as_org(org):
        message, _ = messages.send_message(
            db, transport=ScriptedTransport(SendResult(True, provider_message_id=almost)), **reminder_request()
        )
        stored = messages.get_message(db, message.id)
    assert stored.provider_message_id == almost
    assert _sent_event(db, org, message.id)["provider_message_id"] == almost


# F3 -----------------------------------------------------------------------------------------------------------


def test_a_retry_hint_is_a_positive_integer_clamped_to_the_cap_or_ignored(db, org, as_org):
    factory = lambda ch: _Provider(accepted=False, reason="throttled", retryable=True, retry_after_s=10**12)  # noqa: E731
    assert AdapterTransport(factory, max_retry_delay_s=3600).send(_outbound()).retry_after_s == 3600
    for bad in (-5, 0, "60", True, None, 1.5):
        f = lambda ch, bad=bad: _Provider(accepted=False, reason="throttled", retryable=True, retry_after_s=bad)  # noqa: E731
        assert AdapterTransport(f, max_retry_delay_s=3600).send(_outbound()).retry_after_s is None
    # and the service clamps once more, so a transport given directly cannot overflow the timestamp either
    config = NotificationConfig.from_env()
    with as_org(org):
        huge = ScriptedTransport(SendResult(False, reason="throttled", retryable=True, retry_after_s=10**12))
        msg, _ = messages.send_message(db, transport=huge, now=NOW, config=config, **reminder_request())
        assert msg.status == "queued" and messages.aware(msg.next_attempt_at) == later(config.recovery_max_delay_s)
        past = ScriptedTransport(SendResult(False, reason="throttled", retryable=True, retry_after_s=-999999))
        msg, _ = messages.send_message(db, transport=past, now=NOW, config=config, **reminder_request())
        assert messages.aware(msg.next_attempt_at) == later(config.retry_backoff_s)  # the backoff, not the past


# F3 configuration bounds ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "configured,effective",
    [
        ("", 3600),  # unset: the default
        ("3600", 3600),  # the default, set explicitly
        ("1", 1),  # the floor
        ("86399", 86_399),  # just inside the ceiling
        ("86400", 86_400),  # exactly the ceiling, honoured
        ("86401", 86_400),  # just outside: clamped, not rejected
        ("1000000000000", 86_400),  # the value that would overflow next_attempt_at
        ("0", 1),
        ("-5", 1),
        ("not-a-number", 3600),  # unparseable falls back to the default
        ("true", 3600),
    ],
)
def test_the_recovery_delay_is_bounded_however_the_environment_spells_it(monkeypatch, configured, effective):
    monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_DELAY_S", configured)
    value = NotificationConfig.from_env().recovery_max_delay_s
    assert value == effective
    assert isinstance(value, int) and not isinstance(value, bool)


def _base_config() -> dict:
    return {f: getattr(NotificationConfig.from_env(), f) for f in NotificationConfig.__dataclass_fields__}


@pytest.mark.parametrize(
    "field,given,expected",
    [
        ("recovery_max_delay_s", 10**12, 86_400),
        ("recovery_max_delay_s", 86_401, 86_400),
        ("recovery_max_delay_s", 86_400, 86_400),
        ("recovery_max_delay_s", 1, 1),
        ("recovery_max_delay_s", 0, 1),
        ("recovery_max_delay_s", -1, 1),
        ("retry_backoff_s", -30, 0),  # negative would schedule the next attempt in the past
        ("retry_backoff_s", 0, 0),  # zero is legal: retry on the next sweep
        ("retry_backoff_s", 30, 30),
        ("sending_lease_s", 10**12, 86_400),  # goes straight into timestamp arithmetic, so it needs a ceiling
        ("sending_lease_s", 86_400, 86_400),
        ("sending_lease_s", 0, 1),
        ("sending_lease_s", 120, 120),
    ],
)
def test_direct_construction_clamps_an_integer_outside_the_supported_range(field, given, expected):
    """send_message(), dispatch() and recover_stuck() all accept an injected config, and #82 and #83 will
    build one, so a bound enforced only in from_env() would not be a bound."""
    assert getattr(NotificationConfig(**{**_base_config(), field: given}), field) == expected


def test_the_sending_lease_is_bounded_because_it_is_added_to_the_clock_unguarded(monkeypatch):
    """_claim() does `now + timedelta(seconds=sending_lease_s)` and recover_stuck() does `now - timedelta(...)`
    with nothing capping either, unlike a retry delay. The subtraction is the tighter limit: from 2026 it
    underflows above about 63,928,224,000 seconds, where the addition survives to roughly 251,609,673,599."""
    for configured, effective in (("120", 120), ("1", 1), ("0", 1), ("86400", 86_400), ("86401", 86_400),
                                  ("1000000000000", 86_400), ("not-a-number", 120)):  # fmt: skip
        monkeypatch.setenv("NOTIFICATION_SENDING_LEASE_S", configured)
        assert NotificationConfig.from_env().sending_lease_s == effective, configured
    assert NotificationConfig(**{**_base_config(), "sending_lease_s": 10**12}).sending_lease_s == 86_400


def test_an_absurd_lease_cannot_raise_inside_a_claim_or_a_sweep(db, org, as_org, monkeypatch):
    """The failure this guards is not a silly schedule but an OverflowError raised from inside _claim(), after
    the row has been selected, and from the first statement of recover_stuck()."""
    monkeypatch.setenv("NOTIFICATION_SENDING_LEASE_S", "1000000000000")
    config = NotificationConfig.from_env()
    assert config.sending_lease_s == 86_400
    with as_org(org):
        message, _ = messages.send_message(
            db, transport=ScriptedTransport(), now=NOW, config=config, **reminder_request()
        )
        assert message.status == "sent"  # the claim inside dispatch did not raise
        assert messages.aware(messages.get_message(db, message.id).lease_expires_at) is None
    messages.recover_stuck(transport=ScriptedTransport(), now=NOW, config=config)  # the subtraction, too


@pytest.mark.parametrize("field", ["recovery_max_delay_s", "retry_backoff_s", "sending_lease_s"])
@pytest.mark.parametrize("bad", [True, False, "60", "", 1.5, 0.0, None, [], object()])
def test_direct_construction_rejects_a_non_integer_bound(field, bad):
    """A bool, string, float or None is a bug in the calling code, not operator misconfiguration, and must not
    be absorbed: min(True, 86400) is 1, so a bool would quietly become a one-second delay, and min("60", 86400)
    raises a TypeError about comparison that names neither the field nor the real mistake. False and 0.0 are
    here because both are falsy and would slip past a truthiness check."""
    with pytest.raises(TypeError) as e:
        NotificationConfig(**{**_base_config(), field: bad})
    assert field in str(e.value) and "must be an int" in str(e.value)
    assert type(bad).__name__ in str(e.value)  # the message names what was actually passed


def test_an_out_of_range_value_is_warned_about_once_per_field(monkeypatch, caplog):
    """from_env() runs on request and dispatch paths, so warning on every call would be one line per message.
    The record is keyed on the field, not the value, which bounds it -- and means a later, different
    out-of-range value for the same field is silent. That cost is asserted here, not just documented."""
    from eos_notification.infrastructure import config as config_module

    monkeypatch.setattr(config_module, "_warned_fields", set())  # a fresh process, in effect
    with caplog.at_level("WARNING", logger="eos.notification"):
        monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_DELAY_S", "999999")
        for _ in range(3):
            assert NotificationConfig.from_env().recovery_max_delay_s == 86_400
        lines = [r.message for r in caplog.records if "recovery_max_delay_s" in r.message]
        assert len(lines) == 1
        assert "999999" in lines[0] and "86400" in lines[0]  # names the value given and the value used

        monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_DELAY_S", "123456")
        assert NotificationConfig.from_env().recovery_max_delay_s == 86_400
        assert len([r for r in caplog.records if "recovery_max_delay_s" in r.message]) == 1

        NotificationConfig(**{**_base_config(), "retry_backoff_s": -30})  # a different field: its own line
        assert any("retry_backoff_s" in r.message for r in caplog.records)


def test_concurrent_construction_still_warns_only_once(monkeypatch, caplog):
    """The lock is what makes "once per field" a guarantee rather than best effort."""
    from concurrent.futures import ThreadPoolExecutor

    from eos_notification.infrastructure import config as config_module

    monkeypatch.setattr(config_module, "_warned_fields", set())
    monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_DELAY_S", "999999")
    with caplog.at_level("WARNING", logger="eos.notification"):
        with ThreadPoolExecutor(max_workers=8) as pool:
            built = list(pool.map(lambda _: NotificationConfig.from_env(), range(64)))
    assert all(c.recovery_max_delay_s == 86_400 for c in built)
    assert len([r for r in caplog.records if "recovery_max_delay_s" in r.message]) == 1


def test_an_absurd_ceiling_cannot_let_a_provider_hint_overflow_the_timestamp(db, org, as_org, monkeypatch):
    """The ceiling is the only bound on retry_after_s, so an unbounded one would undo _retry_after however
    carefully it validates: now + timedelta(seconds=1e12) raises, after the claim has been committed."""
    monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_DELAY_S", "1000000000000")
    config = NotificationConfig.from_env()
    assert config.recovery_max_delay_s == 86_400
    with as_org(org):
        hostile = ScriptedTransport(SendResult(False, reason="throttled", retryable=True, retry_after_s=10**12))
        message, _ = messages.send_message(db, transport=hostile, now=NOW, config=config, **reminder_request())
    assert message.status == "queued"
    assert messages.aware(message.next_attempt_at) == later(86_400)


def test_a_negative_backoff_cannot_schedule_the_next_attempt_in_the_past(db, org, as_org):
    """min(backoff * 2**n, cap) picks the left operand when it is negative, whatever the cap is."""
    config = NotificationConfig(**{**_base_config(), "retry_backoff_s": -30})
    with as_org(org):
        refused = ScriptedTransport(SendResult(False, reason="throttled", retryable=True))
        message, _ = messages.send_message(db, transport=refused, now=NOW, config=config, **reminder_request())
    assert message.status == "queued"
    assert messages.aware(message.next_attempt_at) == later(0)  # the clamped floor, never earlier than now


def test_the_backoff_exponent_is_bounded_so_a_high_attempt_cannot_run_away(db, org, as_org, monkeypatch):
    """max_attempts has no ceiling. Without the capped exponent a high attempt number would build an enormous
    integer before min() discarded it, and the scheduled time must stay inside the cap at every attempt. Each
    sweep has to run after whatever the previous one scheduled, because _claim only takes a queued message
    once next_attempt_at has passed."""
    monkeypatch.setenv("NOTIFICATION_MAX_ATTEMPTS", "500")
    config = NotificationConfig.from_env()
    cap = config.recovery_max_delay_s
    with as_org(org):
        refused = ScriptedTransport(SendResult(False, reason="throttled", retryable=True))
        message, _ = messages.send_message(db, transport=refused, now=NOW, config=config, **reminder_request())
        assert message.status == "queued" and message.attempts == 1
        for attempt in range(2, 10):
            at = later(cap * (attempt - 1))  # past anything the previous attempt could have scheduled
            messages.dispatch(db, message.id, transport=refused, config=config, now=at)
            message = messages.get_message(db, message.id)
            assert message.attempts == attempt, f"attempt {attempt} was not claimed"
            scheduled = messages.aware(message.next_attempt_at)
            assert at <= scheduled <= later(cap, base=at), f"attempt {attempt} scheduled outside the cap"


# F4 -----------------------------------------------------------------------------------------------------------


def test_a_subject_override_with_a_line_break_is_refused_and_render_never_emits_one(db, org, as_org):
    with as_org(org):
        for subject in ("Trial\r\nBcc: attacker@evil.example", "Trial\nBcc: x", "Trial\rBcc: x"):
            with pytest.raises(NotificationError) as e:
                templates.upsert_template(
                    db, key="billing.trial.reminder", channel="email", locale="en", subject=subject, body="b"
                )
            assert e.value.status == 422
    assert render("a\r\nb ${n}", {"n": "c\nd"}, single_line=True) == "a b c d"
    assert render("a\r\nb", {}) == "a\r\nb"  # bodies keep their lines


# F6 -----------------------------------------------------------------------------------------------------------


def test_own_preferences_are_reachable_with_any_spelling_of_own_id(org):
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    client = TestClient(app)
    me, other = org.member, org.admin
    for spelling in (me.id, me.id.upper(), "{" + me.id + "}"):
        r = client.get(f"{PREFIX}/preferences/{spelling}", headers=org.headers(me))
        assert r.status_code == 200 and r.json()["user_id"] == me.id, spelling
        r = client.put(f"{PREFIX}/preferences/{spelling}", json={"channels": {"reminder": []}}, headers=org.headers(me))
        assert r.status_code == 200 and r.json()["channels"]["reminder"] == [], spelling
    assert client.get(f"{PREFIX}/preferences/{other.id.upper()}", headers=org.headers(me)).status_code == 403
    assert client.get(f"{PREFIX}/preferences/not-an-id", headers=org.headers(me)).status_code == 422


# POST /templates: the 422s the contract now documents ------------------------------------------------------


@pytest.mark.parametrize(
    "subject,body,why",
    [
        ("Trial ${unclosed", "B ${days_left}", "malformed placeholder in the subject"),
        ("S ${days_left}", "B ${unclosed", "malformed placeholder in the body"),
        ("Trial ${nonsense}", "B ${days_left}", "undeclared placeholder in the subject"),
        ("S ${days_left}", "B ${nonsense}", "undeclared placeholder in the body"),
    ],
)
def test_a_bad_placeholder_in_an_override_is_refused(db, org, as_org, subject, body, why):
    """check_syntax() guards the subject and body TEXT. It is a different check from the one on the request's
    `variables` list: these requests send no variables list at all and are still refused."""
    with as_org(org), pytest.raises(NotificationError) as e:
        templates.upsert_template(
            db, key="billing.trial.reminder", channel="email", locale="en", subject=subject, body=body
        )
    assert e.value.status == 422, why
    assert "placeholder" in e.value.detail or "undeclared" in e.value.detail


def test_a_valid_variables_list_does_not_excuse_a_bad_placeholder(db, org, as_org):
    """The two checks are independent, which is what the contract text now has to say."""
    with as_org(org), pytest.raises(NotificationError) as e:
        templates.upsert_template(
            db,
            key="billing.trial.reminder",
            channel="email",
            locale="en",
            subject="S ${days_left}",
            body="B ${nonsense}",
            variables=["days_left"],  # a legal list ...
        )
    assert e.value.status == 422 and "undeclared" in e.value.detail  # ... and still refused for the body


def test_an_invalid_variables_list_is_refused_even_with_clean_placeholders(db, org, as_org):
    with as_org(org), pytest.raises(NotificationError) as e:
        templates.upsert_template(
            db,
            key="billing.trial.reminder",
            channel="email",
            locale="en",
            subject="S",
            body="B",
            variables=["not_a_template_variable"],
        )
    assert e.value.status == 422 and "does not have" in e.value.detail


def _contract() -> dict:
    import yaml

    path = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
    return yaml.safe_load(path.read_text())


def test_the_contract_describes_both_shapes_a_422_can_take():
    """This module raises {"detail": "<sentence>"}; the framework answers a bad request body or query with
    {"detail": [ {...} ]} before the handler runs, and no handler rewrites it. A contract that named only one
    of those would be wrong about the other, so every 422 has to say which shapes it can be."""
    contract = _contract()
    schemas = contract["components"]["schemas"]
    assert schemas["Error"]["properties"]["detail"]["type"] == "string"
    assert schemas["ValidationError"]["properties"]["detail"]["type"] == "array"
    assert set(schemas["ValidationIssue"]["required"]) == {"loc", "msg", "type"}

    seen = {}
    for path, operations in contract["paths"].items():
        for verb, operation in operations.items():
            response = (operation.get("responses") or {}).get("422")
            if response:
                seen[(verb, path)] = response["content"]["application/json"]["schema"]

    # Operations with a request body can produce either shape; the list endpoints validate only query
    # parameters, so the handler is never reached and only the framework shape is possible.
    for key in [("post", "/messages"), ("post", "/templates"), ("post", "/templates/{key}/preview"),
                ("put", "/preferences/{user_id}")]:  # fmt: skip
        refs = {option["$ref"].rsplit("/", 1)[-1] for option in seen[key]["oneOf"]}
        assert refs == {"Error", "ValidationError"}, key
    for key in [("get", "/messages"), ("get", "/templates"), ("get", "/inbox")]:
        assert seen[key]["$ref"].endswith("/ValidationError"), key
    # GET /preferences/{user_id} takes no body and no query parameters, so only this module can refuse it.
    assert seen[("get", "/preferences/{user_id}")]["$ref"].endswith("/Error")


def test_the_uuid_422_documents_that_it_precedes_the_permission_check():
    """router._own_or_manage parses the id before comparing permissions, so a malformed id from a caller
    without preference:manage is a 422, not a 403. The contract must not imply the opposite."""
    contract = _contract()
    for verb in ("get", "put"):
        text = contract["paths"]["/preferences/{user_id}"][verb]["responses"]["422"]["description"]
        assert "before the permission comparison" in text and "422" in text


def _outbound():
    from eos_notification.infrastructure.transport import OutboundMessage

    return OutboundMessage(
        message_id="m", organisation_id="o", channel="email", to="a@b.c", sender="s", subject="s", body="b"
    )
