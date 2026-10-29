"""Messages: accept, send, recover, read.

What this provides, and what it does not (README states the same):
- accept + dispatch are driven by a call (API route or direct service call). Nothing in this module polls.
- `recover_stuck` is a function. NOTHING triggers it automatically yet (scheduler #82 is unbuilt), so a message
  left `queued` or `sending` after a crash waits until someone runs it.
- Delivery is at-least-once at the provider: the provider port has no idempotency key, so a crash after the
  provider accepted a message and before we recorded it can send a duplicate. Exactly-once is not claimed.
- Events are not consumed here. `accept_message(source_event_id=...)` is the dedupe-safe entry a future event
  handler would call.
- Two ways to send. `send_message` owns the transaction (the HTTP route). An in-process caller that already has
  one open, such as tenancy recording a registration, uses `accept_in_transaction` and then, after its own
  commit, `deliver_accepted`. Both go through the same accept and dispatch, so there is one delivery path.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from eos_core import events
from eos_core.db import SessionLocal, scoped
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..domain.errors import NotificationError
from ..domain.models import (
    CATEGORIES,
    CHANNELS,
    DELIVERED,
    FAILED,
    QUEUED,
    SENDING,
    SENT,
    SUPPRESSED,
    TRANSITIONS,
    Message,
)
from ..infrastructure.config import NotificationConfig
from ..infrastructure.templates import DEFAULTS, DefaultTemplate, get_default, render
from ..infrastructure.transport import (
    ERROR_CODES,
    MAX_PROVIDER_MESSAGE_ID,
    OutboundMessage,
    SendResult,
    Transport,
    get_transport,
)
from . import preferences, recipients, templates
from .common import aware, canonical_uuid, organisation_of, utc_now

log = logging.getLogger("eos.notification")

# Rows are always re-read with populate_existing after an UPDATE, so skip the in-Python evaluation of the WHERE
# clause (it cannot compare SQLite's naive datetimes with aware ones).
_NO_SYNC = {"synchronize_session": False}


class StorageError(Exception):
    """Parameter-free stand-in for a database error whose own text would include row values."""


def _describe(error: IntegrityError | DataError) -> str:
    orig = getattr(error, "orig", None)
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)  # psycopg; SQLite has none
    return f"{type(orig).__name__ if orig else type(error).__name__} on constraint {constraint or 'unknown'}"


@dataclass
class Accepted:
    message: Message
    created: bool
    secrets: dict[str, str] = field(default_factory=dict, repr=False)  # in memory only, never stored or logged
    # The transport resolved before the row was written, so delivery uses the one that was checked. None for a
    # replay and for in_app, which is stored rather than sent.
    transport: Transport | None = field(default=None, repr=False)


# --- guarded state changes -------------------------------------------------------------------------------------


def _transition(
    db: Session, message_id: str, organisation_id: str, *, from_statuses, to: str, attempts: int | None = None, **values
) -> bool:
    """One guarded UPDATE: it changes the row only if it is still in an allowed state (and, when `attempts` is
    given, still on that attempt, which fences out a worker that outlived its lease). True if this call won."""
    for f in from_statuses:
        if to not in TRANSITIONS[f]:
            raise ValueError(f"illegal transition {f} -> {to}")
    stmt = update(Message).where(
        Message.id == message_id, Message.organisation_id == organisation_id, Message.status.in_(tuple(from_statuses))
    )
    if attempts is not None:
        stmt = stmt.where(Message.attempts == attempts)
    result = db.execute(stmt.values(status=to, updated_at=utc_now(), **values), execution_options=_NO_SYNC)
    return result.rowcount == 1


def _get(db: Session, organisation_id: str, message_id: str) -> Message | None:
    return db.scalars(
        scoped(db, select(Message), Message)
        .where(Message.id == message_id, Message.organisation_id == organisation_id)
        .execution_options(populate_existing=True)
    ).first()


def _requested_recipient(recipient: dict) -> tuple[str | None, str | None, str]:
    """(user_id, address, recipient_key) exactly as the caller asked, with no identity or preference lookup, so a
    retry is recognised whatever has changed since. recipient_key matches what accept_message stores."""
    user_id = canonical_uuid(recipient.get("user_id"), "recipient.user_id") if recipient.get("user_id") else None
    address = (recipient.get("address") or "").strip().lower() or None
    return user_id, address, (user_id or address or "")


def requested_locale(recipient: dict) -> str | None:
    """The locale the caller asked for; an empty or blank one counts as not given."""
    return (recipient.get("locale") or "").strip() or None


def event_token(source_event_id: str, template: str, channel: str, recipient_key: str) -> str:
    """The client_token an event-linked send derives, instead of being given one: `client_token` is the only
    idempotency key, so a relay does not need a second dedupe mechanism. recipient_key is the recipient AS ASKED
    (never the resolved one, which depends on state that can change between deliveries). 68 characters."""
    blob = "|".join((source_event_id, template, channel, recipient_key))
    return "evt:" + hashlib.sha256(blob.encode()).hexdigest()


def _fingerprint(template: str, channel: str | None, category: str | None, recipient: dict, variables: dict) -> str:
    """Non-secret identity of the request as sent, for client_token reuse. Secret values are never part of it; a
    secret-bearing template carries a non-secret issuance id (`secret_ref`) in `variables`, which is. Nothing
    derived from mutable state (preferences, account status, template wording) is part of it either."""
    user_id, address, _ = _requested_recipient(recipient)
    blob = json.dumps(
        {
            "t": template,
            "c": channel,
            "g": category,
            "r": {"u": user_id, "a": address, "l": requested_locale(recipient)},
            "v": variables,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()


# --- accept ---------------------------------------------------------------------------------------------------


def _choose_channel(
    db: Session,
    org: str,
    default: DefaultTemplate,
    requested: str | None,
    user_id: str | None,
    category: str,
    config: NotificationConfig,
) -> str:
    enabled = [c for c in default.channels if c in config.channels_enabled]
    if requested:
        if requested not in CHANNELS or requested not in enabled:
            raise NotificationError(422, "channel is not available for this template")
        return requested
    if not enabled:
        raise NotificationError(422, "no channel is available for this template")
    if category != "transactional" and user_id:
        allowed = preferences.effective_channels(preferences.get_row(db, org, user_id), config)[category]
        for c in enabled:
            if c in allowed:
                return c
    return enabled[0]  # no preference blocks it; if one does, dispatch records the message as suppressed


def accept_message(
    db: Session,
    *,
    template: str,
    recipient: dict,
    channel: str | None = None,
    category: str | None = None,
    variables: dict | None = None,
    client_token: str | None = None,
    attachments: list | None = None,
    send_after: datetime | None = None,
    source_event_id: str | None = None,
    now: datetime | None = None,
    config: NotificationConfig | None = None,
    before_insert: Callable[[str], None] | None = None,
) -> Accepted:
    """Validate, render once to prove the template works, and record the message as `queued`. Does not send and
    does not commit. A repeat of the same `client_token` or `source_event_id` returns the existing row; that check
    runs BEFORE recipient, preference and template lookups, so a genuine retry gets the original even if the
    user's preferences or account changed in between."""
    config = config or NotificationConfig.from_env()
    now = now or utc_now()
    org = organisation_of(db)
    default = get_default(template)
    if attachments:
        raise NotificationError(422, "attachments are not supported yet")
    if send_after is not None and aware(send_after) > now:
        raise NotificationError(422, "send_after in the future is not supported yet; use the scheduler")
    if category is not None and (category not in CATEGORIES or category != default.category):
        raise NotificationError(422, "category does not match the template")
    category = default.category  # an explicit category may only repeat the template's, so it adds nothing
    if client_token is not None and not (1 <= len(client_token) <= 120):
        raise NotificationError(422, "client_token must be 1 to 120 characters")
    source_event_id = canonical_uuid(source_event_id, "source_event_id")
    if channel is not None and channel not in CHANNELS:
        raise NotificationError(422, "channel is not available for this template")
    recipient = recipient or {}
    user_id, _, requested_key = _requested_recipient(recipient)
    if source_event_id:
        if channel is None:
            # One event may notify one person on several channels. With the channel left to preferences, a
            # redelivery could not tell "the same message again" from "the same event on another channel".
            raise NotificationError(422, "an event-linked message needs an explicit channel")
        derived = event_token(source_event_id, template, channel, requested_key)
        if client_token is not None and client_token != derived:
            # Supplying both keys means the relay believes something the service does not. Refuse rather than
            # silently prefer one of them.
            raise NotificationError(422, "an event-linked message derives its own client_token")
        client_token = derived

    values = templates.clean_variables(default, variables)
    secrets = {k: values.pop(k) for k in default.secret_variables}
    if default.secret_bearing and not client_token:
        raise NotificationError(422, "a secret-bearing template needs a client_token")

    # --- replay check: only the request itself and stored rows, nothing that can change under a retry ---
    # client_token is the only idempotency key. An event-linked send reaches here with its derived token, so one
    # lookup answers both cases; source_event_id is read only by _find_duplicate, after its constraint fires.
    fingerprint = _fingerprint(template, channel, category, recipient, values) if client_token else None
    if client_token:
        existing = db.scalars(
            scoped(db, select(Message), Message).where(
                Message.organisation_id == org, Message.client_token == client_token
            )
        ).first()
        if existing is not None:
            return _replay(existing, fingerprint)

    # --- first time: these read state that may change, and that is fine now ---
    channel = _choose_channel(db, org, default, channel, user_id, category, config)
    who = recipients.resolve(db, org, recipient or {}, channel)

    pref = preferences.get_row(db, org, who.user_id) if who.user_id else None
    locale = (pref.locale if pref and pref.locale else None) or who.locale or config.default_locale
    text, locale_used = templates.resolve_text(db, org, template, channel, locale, config)
    # render once now (with the real secrets, in memory) so a broken template is a 422 here, not a failure later
    subject = render(text.subject, {**values, **secrets}, single_line=True)
    if subject is not None and len(subject) > templates.MAX_SUBJECT:
        # The column is String(300); SQLite would store it, PostgreSQL would raise mid-insert. Applies to the
        # platform wording and an organisation override alike, since both are rendered here.
        raise NotificationError(422, "the rendered subject is too long")
    body = render(text.body, {**values, **secrets})

    if before_insert is not None:
        before_insert(channel)  # last chance to refuse before anything is written (send_message: the transport)
    row = Message(
        organisation_id=org,
        template_key=template,
        channel=channel,
        category=category,
        status=QUEUED,
        recipient_id=who.user_id,
        recipient_key=who.key,
        recipient_address=who.address,
        locale=locale_used,
        subject=subject,
        variables=values,
        body=body if channel == "in_app" else None,
        body_template=text.body,
        client_token=client_token,
        request_hash=fingerprint,
        source_event_id=source_event_id,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except (IntegrityError, DataError) as e:
        # DataError (a value the database refuses, e.g. too long) carries the SQL parameters in its text too.
        existing = _find_duplicate(db, org, client_token, source_event_id, template, channel, who.key)
        if existing is None:
            # The driver's text includes the SQL parameters (address, subject, variables). Keep only what is
            # safe: the error class and constraint name, as the cause; never the original text.
            cause = StorageError(_describe(e))
            log.warning("message insert failed: %s", cause)
            raise NotificationError(500, "the message could not be stored") from cause
        return _replay(existing, fingerprint)
    return Accepted(row, True, secrets)


def _replay(existing: Message, fingerprint: str | None) -> Accepted:
    if fingerprint is not None and existing.request_hash is not None and existing.request_hash != fingerprint:
        raise NotificationError(422, "client_token was already used for a different request")
    return Accepted(existing, False)


def _find_duplicate(db, org, client_token, source_event_id, template, channel, recipient_key) -> Message | None:
    q = scoped(db, select(Message), Message).where(Message.organisation_id == org)
    if client_token:
        found = db.scalars(q.where(Message.client_token == client_token)).first()
        if found:
            return found
    if source_event_id:
        return db.scalars(
            q.where(
                Message.source_event_id == source_event_id,
                Message.template_key == template,
                Message.channel == channel,
                Message.recipient_key == recipient_key,
            )
        ).first()
    return None


# --- send -----------------------------------------------------------------------------------------------------


def accept_in_transaction(
    db: Session,
    *,
    transport: Transport | None = None,
    config: NotificationConfig | None = None,
    now: datetime | None = None,
    **request,
) -> Accepted:
    """Step one for an in-process caller that owns the transaction, such as tenancy recording a registration.

    The calling contract:
    1. Call it inside the caller's open transaction and organisation scope (`organisation_scope(org_id)`), with
       the same fields POST /messages takes (template, recipient, variables, client_token, ...).
    2. It validates, resolves the transport and adds the message row with a flush. It NEVER commits and NEVER
       rolls back, so the row commits, or disappears, together with the caller's own work.
    3. Every refusal is raised as NotificationError BEFORE a row is written. That includes 503 when the channel
       needs a transport and none can be resolved (the memory transport outside dev mode, or no adapter
       installed). The caller's pending work is left exactly as it was; the caller decides whether to roll back.
    4. A replayed client_token returns the original (created=False) and writes nothing.
    5. After its own commit, the caller passes the result to deliver_accepted(). Nothing is sent before that.

    Acceptance is not delivery. The returned message is `queued`: recorded, not sent.

    Secrets, such as a verification token, exist only in the returned object, never in the database. If the
    process stops after the caller's commit and before deliver_accepted(), the row stays `queued`:
    - a message without a secret is sent by the next recover_stuck() sweep, but nothing runs that sweep
      automatically until the scheduler (#82) exists, so until then it waits;
    - a message with a secret can never be sent later, because the secret is gone. The next dispatch or sweep
      marks it `failed` with `secret_unavailable`, and the caller must issue a new secret under a new
      client_token."""
    config = config or NotificationConfig.from_env()
    chosen: dict[str, Transport | None] = {"transport": transport}

    def need_transport(channel: str) -> None:
        # Only something that leaves the process needs a transport; in_app is stored, not sent. Checked before
        # the insert, so a refusal writes nothing (a rollback is not relied on: SQLite's default driver commits
        # a savepoint opened outside a transaction).
        if channel != "in_app" and chosen["transport"] is None:
            chosen["transport"] = get_transport(config)

    _open_transaction(db)
    accepted = accept_message(db, config=config, now=now, before_insert=need_transport, **request)
    accepted.transport = chosen["transport"]
    return accepted


def _open_transaction(db: Session) -> None:
    """Make sure the caller's transaction exists in the database before accept_message takes its savepoint.

    Python's sqlite3 driver opens a transaction only before an INSERT, UPDATE or DELETE. If the caller has not
    written anything yet, the savepoint is not nested in anything: SQLite starts the transaction with it, and
    RELEASE then COMMITS, so the message would survive the caller's rollback. Starting the transaction here makes
    the savepoint nested, as it already is on PostgreSQL, whose driver begins the transaction with the first
    statement. Nothing is begun when one is already open."""
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.dbapi_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")


def deliver_accepted(
    accepted: Accepted,
    *,
    session_factory: sessionmaker | None = None,
    config: NotificationConfig | None = None,
    now: datetime | None = None,
) -> Message:
    """Step two, after the caller has committed. A new message is sent once, through dispatch(), the path every
    send takes. A replay is returned untouched and nothing is sent again.

    It works in a session of its own, in the message's own organisation, never the caller's. That is what makes
    "only after the commit" a guarantee rather than a rule to remember. A row the caller has not committed, or
    has rolled back, is invisible to another session, so a call made too early finds no message, raises
    NotificationError(404) and sends nothing. And dispatch() commits its claim and outcome in that session,
    so it can never commit the caller's unfinished work.

    The returned message says what actually happened, and none of it is "delivered to the inbox":
    - `sent` (shown as `sending` by the API): the provider accepted it. Delivery is not confirmed; receipts
      are not built.
    - `queued` with next_attempt_at set: a retryable failure, retried by recover_stuck().
    - `failed`: permanent, with last_error saying why.
    - `suppressed`: the recipient's preferences blocked it.
    - `delivered`: in_app only, where storing it is delivering it."""
    if not accepted.created:
        return accepted.message
    factory = session_factory or SessionLocal
    with organisation_scope(accepted.message.organisation_id), factory() as db:
        return dispatch(
            db, accepted.message.id, secrets=accepted.secrets, transport=accepted.transport, config=config, now=now
        )


def send_message(
    db: Session,
    *,
    transport: Transport | None = None,
    config: NotificationConfig | None = None,
    now: datetime | None = None,
    **request,
) -> tuple[Message, bool]:
    """accept -> commit -> dispatch, owning the transaction: for the HTTP route and any caller with no transaction
    of its own. A caller that has one open uses accept_in_transaction() and deliver_accepted() instead, because
    this function commits, and on a replay rolls back, whatever the session holds. Returns (message, created). A
    replay returns the original untouched."""
    config = config or NotificationConfig.from_env()
    accepted = accept_in_transaction(db, transport=transport, config=config, now=now, **request)
    if not accepted.created:
        # A replay is read-only, so detach it with its loaded values BEFORE ending the transaction: a rollback
        # expires every attribute, and the caller would then be holding an object that must be re-read. On
        # PostgreSQL that re-read runs under row-level security, so outside the organisation scope it finds
        # nothing and raises ObjectDeletedError for a row that exists. On SQLite it silently succeeds, which is
        # why this never showed up until the suite was run against PostgreSQL.
        if accepted.message in db:
            db.expunge(accepted.message)
        db.rollback()  # nothing was written; end the read transaction
        return accepted.message, False
    db.commit()
    message = dispatch(
        db, accepted.message.id, secrets=accepted.secrets, transport=accepted.transport, config=config, now=now
    )
    return message, True


def _claim(db: Session, org: str, message_id: str, now: datetime, config: NotificationConfig) -> bool:
    """Atomic claim: queued and due, or sending with an expired lease. Exactly one concurrent caller gets True."""
    result = db.execute(
        update(Message)
        .where(
            Message.id == message_id,
            Message.organisation_id == org,
            or_(
                and_(
                    Message.status == QUEUED,
                    or_(Message.next_attempt_at.is_(None), Message.next_attempt_at <= now),
                ),
                and_(Message.status == SENDING, Message.lease_expires_at < now),
            ),
        )
        .values(
            status=SENDING,
            attempts=Message.attempts + 1,
            lease_expires_at=now + timedelta(seconds=config.sending_lease_s),
            next_attempt_at=None,
            updated_at=utc_now(),
        ),
        execution_options=_NO_SYNC,
    )
    return result.rowcount == 1


def _fail(db: Session, msg: Message, from_statuses, code: str, attempts: int | None) -> bool:
    """Terminal failure, recorded once, with the failure event in the same transaction."""
    won = _transition(
        db,
        msg.id,
        msg.organisation_id,
        from_statuses=from_statuses,
        to=FAILED,
        attempts=attempts,
        last_error=code,
        lease_expires_at=None,
        next_attempt_at=None,
    )
    if won:
        _publish_failed(db, msg, attempts if attempts is not None else msg.attempts, code)
    return won


def _publish_failed(db: Session, msg: Message, attempts: int, reported_error: str) -> None:
    """Add the failure event to the outbox. eos_core.events.publish only adds the row to this session; it is
    written by the caller's commit, together with the status change that won the guarded UPDATE."""
    events.publish(
        db,
        "notification.message.failed",
        msg.organisation_id,
        {
            "message_id": msg.id,
            "template": msg.template_key,
            "channel": msg.channel,
            "recipient_id": msg.recipient_id,
            "attempts": attempts,
            "last_error": reported_error,
        },
    )


def dispatch(
    db: Session,
    message_id: str,
    *,
    secrets: dict[str, str] | None = None,
    transport: Transport | None = None,
    config: NotificationConfig | None = None,
    now: datetime | None = None,
) -> Message:
    """Send one queued message once. Safe to call concurrently or twice: only the claim winner calls the provider.
    `secrets` exist only in the call that accepted the message; a later attempt has none, so a secret-bearing
    message that is not sent on that first call is failed (the sender must issue a new secret), not re-rendered."""
    config = config or NotificationConfig.from_env()
    now = now or utc_now()
    org = organisation_of(db)
    msg = _get(db, org, message_id)
    if msg is None:
        raise NotificationError(404, "no such message in this organisation")
    default = get_default(msg.template_key)

    if msg.status == QUEUED and _is_suppressed(db, msg, config):
        if _transition(db, msg.id, org, from_statuses=(QUEUED,), to=SUPPRESSED, last_error=None):
            db.commit()
        return _get(db, org, message_id)

    if msg.channel == "in_app":
        if _transition(db, msg.id, org, from_statuses=(QUEUED,), to=DELIVERED, sent_at=now, last_error=None):
            db.commit()
        return _get(db, org, message_id)

    lease = aware(msg.lease_expires_at)
    if msg.status == SENDING and lease is not None and lease >= now:
        return msg  # another worker holds the lease; leave it alone
    if default.secret_bearing and not secrets and msg.status in (QUEUED, SENDING):
        code = "outcome_unknown" if msg.status == SENDING else "secret_unavailable"
        # fenced on the status and attempt read above: a worker that reclaimed it meanwhile is left alone
        if _fail(db, msg, (msg.status,), code, msg.attempts):
            db.commit()
        return _get(db, org, message_id)

    transport = transport or get_transport(config)
    if not _claim(db, org, message_id, now, config):
        db.rollback()
        return _get(db, org, message_id)
    db.commit()  # the claim is durable before the provider is called
    msg = _get(db, org, message_id)
    attempt = msg.attempts

    result = _call_provider(msg, secrets or {}, transport, config)
    _record(db, msg, default, result, attempt, now, config)
    db.commit()
    return _get(db, org, message_id)


def _call_provider(msg: Message, secrets: dict, transport: Transport, config: NotificationConfig) -> SendResult:
    try:
        outbound = OutboundMessage(
            message_id=msg.id,
            organisation_id=msg.organisation_id,
            channel=msg.channel,
            to=msg.recipient_address or "",
            sender=f"{config.default_from_name} <{config.default_from_email}>",
            subject=msg.subject,  # rendered at acceptance from non-secret values only
            body=render(msg.body_template, {**(msg.variables or {}), **secrets}) or "",
            metadata={},  # echoed on provider receipts: never a secret
            dev_secrets=dict(secrets),  # memory transport only; not part of the provider port
        )
    except NotificationError:
        return SendResult(False, reason="render_error", retryable=False)
    try:
        return transport.send(outbound)
    except Exception:  # noqa: BLE001  a transport bug must not strand the claim; only the class name is logged
        log.warning("transport raised for message %s", msg.id)
        return SendResult(False, reason="transport_error", retryable=True)


def _record(db: Session, msg: Message, default, result: SendResult, attempt: int, now: datetime, config) -> None:
    org = msg.organisation_id
    if result.accepted:
        provider_id = _provider_id(result.provider_message_id)
        won = _transition(
            db,
            msg.id,
            org,
            from_statuses=(SENDING,),
            to=SENT,
            attempts=attempt,
            provider_message_id=provider_id,
            sent_at=utc_now(),
            last_error=None,
            lease_expires_at=None,
        )
        if won:
            events.publish(
                db,
                "notification.message.sent",
                org,
                {
                    "message_id": msg.id,
                    "template": msg.template_key,
                    "channel": msg.channel,
                    "recipient_id": msg.recipient_id,
                    "provider_message_id": provider_id,
                },
            )
        return
    code = result.reason if result.reason in ERROR_CODES else ("transport_error" if result.retryable else "rejected")
    can_retry = result.retryable and attempt < config.max_attempts and not default.secret_bearing
    if can_retry:
        # The exponent is bounded the way recovery_delay() bounds its own: max_attempts has no ceiling, so a
        # high attempt number would otherwise build a pointless big integer that min() immediately discards,
        # and a non-positive attempt would make 2 ** negative a float. retry_backoff_s cannot be negative
        # (NotificationConfig._bound), so the delay cannot be either.
        exponent = min(max(attempt - 1, 0), 30)
        delay = min(
            _retry_after(result.retry_after_s) or config.retry_backoff_s * (2**exponent),
            config.recovery_max_delay_s,
        )
        _transition(
            db,
            msg.id,
            org,
            from_statuses=(SENDING,),
            to=QUEUED,
            attempts=attempt,
            last_error=code,
            lease_expires_at=None,
            next_attempt_at=now + timedelta(seconds=delay),
        )
        return
    _fail(db, msg, (SENDING,), code, attempt)


def _provider_id(value) -> str | None:
    """The persistence boundary for a provider's receipt id: a non-empty string that fits
    Message.provider_message_id (String(200)), else nothing. AdapterTransport applies the same rule, but it is
    not the only Transport and this is the code that writes both the column and the event payload, so the
    invariant has to hold here whichever transport answered. Mirrors _retry_after, which guards its value at
    both layers for the same reason. The send itself still succeeded: an unusable reference is dropped, never
    turned into a failure, because failing here is what makes recovery send the message twice."""
    if not isinstance(value, str) or not value:
        return None
    return value if len(value) <= MAX_PROVIDER_MESSAGE_ID else None


def _retry_after(value) -> int | None:
    """A provider's retry hint, only if it is a positive integer. Anything else means "use the backoff": a
    negative or absurd value must not schedule a retry in the past or overflow the timestamp."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _is_suppressed(db: Session, msg: Message, config: NotificationConfig) -> bool:
    """A recipient's preference stops anything but transactional mail. (A previous hard bounce would stop it
    too, but nothing records bounces until the receipt handler exists.)"""
    if msg.category == "transactional" or not msg.recipient_id:
        return False
    row = preferences.get_row(db, msg.organisation_id, msg.recipient_id)
    return msg.channel not in preferences.effective_channels(row, config)[msg.category]


# --- recovery -------------------------------------------------------------------------------------------------


def recover_stuck(
    *,
    session_factory: sessionmaker | None = None,
    transport: Transport | None = None,
    config: NotificationConfig | None = None,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Re-drive messages nothing is working on: queued rows whose retry is due or that were never dispatched, and
    sending rows whose lease expired. NOT TRIGGERED BY ANYTHING in this release. Secret-bearing messages cannot be
    re-rendered (their secret was never stored), so they are failed: `secret_unavailable` if never sent,
    `outcome_unknown` if a provider call may have succeeded. Attempts are bounded by NOTIFICATION_MAX_ATTEMPTS."""
    config = config or NotificationConfig.from_env()
    now = now or utc_now()
    factory = session_factory or SessionLocal
    stale_before = now - timedelta(seconds=config.sending_lease_s)
    with platform_scope(), factory() as lister:  # only the ids are read across tenants
        rows = lister.execute(
            select(Message.id, Message.organisation_id, Message.status, Message.attempts, Message.recovery_failures)
            .where(
                or_(
                    and_(
                        Message.status == QUEUED,
                        or_(
                            and_(Message.next_attempt_at.is_not(None), Message.next_attempt_at <= now),
                            and_(Message.next_attempt_at.is_(None), Message.created_at < stale_before),
                        ),
                    ),
                    and_(Message.status == SENDING, Message.lease_expires_at < now),
                )
            )
            .order_by(Message.created_at)
            .limit(limit)
        ).all()
    counts = {"found": len(rows), "redriven": 0, "failed": 0, "skipped": 0, "errors": 0, "exhausted": 0}
    for message_id, org, seen_status, seen_attempts, seen_failures in rows:  # each in its own session and scope
        error_class = None
        try:
            with organisation_scope(org), factory() as db:
                outcome = _recover_one(db, org, message_id, transport, config, now)
        except NotificationError as e:
            # 503: no usable transport. Not this message's fault; it is left exactly as it was.
            outcome = "skipped" if e.status == 503 else "errors"
            error_class = type(e).__name__
        except Exception as e:  # noqa: BLE001  one bad row must not stop the sweep
            outcome, error_class = "errors", type(e).__name__
        if outcome == "errors":
            # Class name only: exception text may carry addresses or SQL parameters.
            log.warning("recovery of message %s failed: %s", message_id, error_class)
            seen = _Seen(seen_status, seen_attempts, seen_failures)
            if _defer(factory, org, message_id, seen, error_class, now, config) == "exhausted":
                counts["exhausted"] += 1
        if outcome in counts:
            counts[outcome] += 1
    return counts


@dataclass(frozen=True)
class _Seen:
    """A message's state as the sweep listed it. Every recovery write is guarded on all three values."""

    status: str
    attempts: int
    recovery_failures: int


def recovery_delay(failures_before: int, config: NotificationConfig) -> timedelta:
    """Doubling delay for the n-th recovery failure (0-based), capped. Starts at NOTIFICATION_RETRY_BACKOFF_S."""
    base = max(config.retry_backoff_s, 1)
    return timedelta(seconds=min(base * (2 ** min(failures_before, 30)), config.recovery_max_delay_s))


def _defer(factory, org: str, message_id: str, seen: _Seen, error_class: str, now: datetime, config) -> str:
    """Record one recovery failure. Returns deferred | exhausted | unchanged | not_recorded.

    Below the limit: defer the message (queued: next_attempt_at; sending: the lease) by a capped doubling delay.
    At the limit: mark it failed and publish notification.message.failed once. Both are one guarded UPDATE on the
    status, attempts and recovery_failures the sweep saw, so a worker that claimed the message, or another worker
    that already recorded this same failure, makes this a no-op. The delivery last_error is never overwritten."""
    try:
        with organisation_scope(org), factory() as db:
            outcome = _record_recovery_failure(db, org, message_id, seen, error_class[:60], now, config)
            db.commit()  # the status change and, if exhausted, its outbox row: one transaction
            return outcome
    except Exception as e:  # noqa: BLE001  e.g. the database is unavailable; nothing was recorded
        # Not counted, so the message stays eligible and the next sweep logs again. That repetition is bounded
        # by sweep frequency and `limit`, not by the counter; class name only, never the text.
        log.warning("could not record recovery failure for message %s: %s", message_id, type(e).__name__)
        return "not_recorded"


def _record_recovery_failure(
    db: Session, org: str, message_id: str, seen: _Seen, error_class: str, now: datetime, config
) -> str:
    failures = seen.recovery_failures + 1
    guard = (
        Message.id == message_id,
        Message.organisation_id == org,
        Message.status == seen.status,
        Message.attempts == seen.attempts,
        Message.recovery_failures == seen.recovery_failures,
    )
    if failures >= config.recovery_max_failures:
        msg = _get(db, org, message_id)  # for the event payload; the UPDATE below decides whether it is ours
        if msg is None or FAILED not in TRANSITIONS.get(seen.status, frozenset()):
            return "unchanged"
        won = (
            db.execute(
                update(Message)
                .where(*guard)
                .values(
                    status=FAILED,
                    last_error=func.coalesce(Message.last_error, "recovery_exhausted"),  # keep the delivery error
                    recovery_failures=failures,
                    last_recovery_error=error_class,
                    lease_expires_at=None,
                    next_attempt_at=None,
                    updated_at=utc_now(),
                ),
                execution_options=_NO_SYNC,
            ).rowcount
            == 1
        )
        if not won:
            return "unchanged"
        _publish_failed(db, msg, seen.attempts, "recovery_exhausted")
        return "exhausted"

    when = now + recovery_delay(seen.recovery_failures, config)
    if seen.status == QUEUED:
        values = {"next_attempt_at": when}
        still_stuck = or_(Message.next_attempt_at.is_(None), Message.next_attempt_at <= now)
    else:  # SENDING with an expired lease: the lease is what makes it eligible again
        values = {"lease_expires_at": when}
        still_stuck = Message.lease_expires_at < now
    won = (
        db.execute(
            update(Message)
            .where(*guard, still_stuck)
            .values(recovery_failures=failures, last_recovery_error=error_class, updated_at=utc_now(), **values),
            execution_options=_NO_SYNC,
        ).rowcount
        == 1
    )
    return "deferred" if won else "unchanged"


def _recover_one(
    db: Session, org: str, message_id: str, transport: Transport | None, config: NotificationConfig, now: datetime
) -> str:
    """Handle one stuck message. Returns redriven | failed | unchanged. Every state change is a guarded UPDATE, so
    a message another worker picked up in the meantime is left alone."""
    msg = _get(db, org, message_id)
    if msg is None or msg.status not in (QUEUED, SENDING):
        return "unchanged"
    fence = msg.attempts if msg.status == SENDING else None
    default = DEFAULTS.get(msg.template_key)
    if default is None:  # the template was retired after the message was accepted
        failed = _fail(db, msg, (msg.status,), "template_unavailable", fence)
    elif msg.status == SENDING and (msg.attempts >= config.max_attempts or default.secret_bearing):
        failed = _fail(db, msg, (SENDING,), "outcome_unknown" if default.secret_bearing else "abandoned", fence)
    elif msg.status == QUEUED and default.secret_bearing:
        failed = _fail(db, msg, (QUEUED,), "secret_unavailable", None)
    else:
        before = msg.attempts
        after = dispatch(db, message_id, transport=transport, config=config, now=now)
        moved = after.attempts > before or after.status in (SUPPRESSED, DELIVERED)
        return "redriven" if moved else "unchanged"
    db.commit()
    return "failed" if failed else "unchanged"


# --- reading --------------------------------------------------------------------------------------------------


def get_message(db: Session, message_id: str) -> Message:
    org = organisation_of(db)
    msg = _get(db, org, canonical_uuid(message_id, "message id") or "")
    if msg is None:
        raise NotificationError(404, "no such message in this organisation")  # 404, never 403: do not confirm
    return msg  # another organisation's id exists


def list_messages(
    db: Session,
    *,
    recipient_id: str | None = None,
    template: str | None = None,
    channel: str | None = None,
    statuses: tuple[str, ...] | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Message], int]:
    org = organisation_of(db)
    q = scoped(db, select(Message), Message).where(Message.organisation_id == org)
    if recipient_id:
        q = q.where(Message.recipient_id == canonical_uuid(recipient_id, "recipient_id"))
    if template:
        q = q.where(Message.template_key == template)
    if channel:
        q = q.where(Message.channel == channel)
    if statuses:
        q = q.where(Message.status.in_(statuses))
    if sent_from:
        q = q.where(Message.sent_at >= sent_from)
    if sent_to:
        q = q.where(Message.sent_at <= sent_to)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(Message.created_at.desc(), Message.id).limit(min(max(limit, 1), 200)).offset(max(offset, 0))
    )
    return list(rows), total


def list_inbox(db: Session, user_id: str, *, unread_only: bool = False, limit: int = 20) -> tuple[list[Message], int]:
    org = organisation_of(db)
    base = scoped(db, select(Message), Message).where(
        Message.organisation_id == org,
        Message.recipient_id == user_id,
        Message.channel == "in_app",
        Message.status == DELIVERED,
    )
    unread = db.scalar(select(func.count()).select_from(base.where(Message.read_at.is_(None)).subquery())) or 0
    q = base.where(Message.read_at.is_(None)) if unread_only else base
    rows = db.scalars(q.order_by(Message.created_at.desc(), Message.id).limit(min(max(limit, 1), 100)))
    return list(rows), unread


def mark_read(db: Session, user_id: str, message_id: str) -> None:
    org = organisation_of(db)
    mid = canonical_uuid(message_id, "message id") or ""
    msg = db.scalars(
        scoped(db, select(Message), Message).where(
            Message.id == mid,
            Message.organisation_id == org,
            Message.recipient_id == user_id,
            Message.channel == "in_app",
        )
    ).first()
    if msg is None:
        raise NotificationError(404, "no such notification")
    if msg.read_at is None:
        db.execute(
            update(Message)
            .where(Message.id == mid, Message.organisation_id == org, Message.read_at.is_(None))
            .values(read_at=utc_now(), updated_at=utc_now()),
            execution_options=_NO_SYNC,
        )
        db.commit()


__all__ = [
    "Accepted",
    "accept_message",
    "dispatch",
    "get_message",
    "list_inbox",
    "list_messages",
    "mark_read",
    "recover_stuck",
    "send_message",
]
