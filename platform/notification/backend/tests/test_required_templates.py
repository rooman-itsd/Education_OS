"""The four templates issue #79 names by hand: verification, approval, trial reminder, invoice.

The other template tests check structure (placeholders declared, secrets handled, overrides scoped). These
send each required template end to end and assert on what actually reaches the transport, because a template
can be structurally valid and still never produce a sendable message.
"""

from __future__ import annotations

import uuid

import pytest
from eos_notification.application import messages
from eos_notification.domain.errors import NotificationError
from eos_notification.infrastructure.templates import DEFAULTS
from notification_support import NOW, ScriptedTransport

# (issue wording, template key, the variables a caller must supply)
REQUIRED = [
    ("verification", "tenancy.organisation.verify",
     {"organisation_name": "Rooman College", "token": "s3cr3t-token-value", "token_id": str(uuid.uuid4())}),
    ("approval", "tenancy.organisation.approved", {"organisation_name": "Rooman College"}),
    ("trial reminder", "billing.trial.reminder",
     {"organisation_name": "Rooman College", "trial_ends_on": "2026-10-20", "days_left": "3"}),
    ("invoice", "billing.invoice.issued",
     {"organisation_name": "Rooman College", "invoice_number": "INV-2026-0042",
      "amount": "12,500.00", "due_on": "2026-11-01"}),
]  # fmt: skip
IDS = [r[0] for r in REQUIRED]


def send(db, org, as_org, key, variables, **over):
    request = {
        "template": key,
        "recipient": {"address": "finance@college.example.com"},
        "variables": variables,
        "client_token": f"{key}-{uuid.uuid4()}",
        "channel": "email",
    }
    request.update(over)
    transport = ScriptedTransport()
    with as_org(org):
        message, created = messages.send_message(db, transport=transport, now=NOW, **request)
    return message, created, transport


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_every_required_template_exists_and_supports_email(_label, key, variables):
    assert key in DEFAULTS, "issue #79 names this template; it is not defined"
    assert "email" in DEFAULTS[key].channels


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_every_required_template_sends_and_renders_its_values(_label, key, variables, db, org, as_org):
    message, created, transport = send(db, org, as_org, key, variables)
    assert created and message.status == "sent"
    (outbound,) = transport.sent
    assert outbound.subject and outbound.body
    # every non-secret value the caller supplied appears in the rendered mail
    secret_names = set(DEFAULTS[key].secret_variables)
    for name, value in variables.items():
        if name not in secret_names and name != DEFAULTS[key].secret_ref:
            assert str(value) in (outbound.subject + outbound.body), f"{name} did not reach the message"
    assert "${" not in outbound.body and "${" not in outbound.subject  # nothing left unrendered


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_every_required_template_refuses_a_missing_variable(_label, key, variables, db, org, as_org):
    for name in variables:
        incomplete = {k: v for k, v in variables.items() if k != name}
        with pytest.raises(NotificationError) as e:
            send(db, org, as_org, key, incomplete)
        assert e.value.status == 422, f"{key} accepted a request missing {name}"
        assert name in e.value.detail  # names the variable, so a caller can fix it


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_every_required_template_drops_undeclared_variables(_label, key, variables, db, org, as_org):
    """An extra value a caller invents must never be stored or rendered."""
    message, _, transport = send(db, org, as_org, key, {**variables, "api_key": "leak-me", "admin": "true"})
    assert "api_key" not in message.variables and "admin" not in message.variables
    assert "leak-me" not in transport.sent[0].body


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_every_required_template_refuses_an_oversized_value(_label, key, variables, db, org, as_org):
    name = next(iter(variables))
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, key, {**variables, name: "x" * 2001})
    assert e.value.status == 422


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_every_required_template_refuses_a_non_scalar_value(_label, key, variables, db, org, as_org):
    name = next(iter(variables))
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, key, {**variables, name: {"nested": "object"}})
    assert e.value.status == 422


@pytest.mark.parametrize("_label, key, variables", REQUIRED, ids=IDS)
def test_a_value_cannot_inject_a_second_header_line(_label, key, variables, db, org, as_org):
    """A newline in a value must not split the subject into an extra header."""
    name = next(iter(variables))
    _, _, transport = send(db, org, as_org, key, {**variables, name: "Acme\r\nBcc: attacker@evil.example"})
    subject = transport.sent[0].subject or ""
    assert "\r" not in subject and "\n" not in subject


def test_only_the_verification_template_carries_a_secret():
    """The other three take no secret, so nothing of theirs needs secret handling at all."""
    secret_bearing = {k for k, d in DEFAULTS.items() if d.secret_bearing}
    assert secret_bearing == {"tenancy.organisation.verify"}


def test_the_verification_secret_is_rendered_but_never_stored(db, org, as_org):
    key, variables = REQUIRED[0][1], REQUIRED[0][2]
    message, _, transport = send(db, org, as_org, key, variables)
    token = variables["token"]
    assert token in transport.sent[0].body  # the recipient must receive it
    assert token not in str(message.variables)  # but it is never stored
    assert token not in (message.body or "") and token not in (message.body_template or "")
    assert token not in str(transport.sent[0].metadata)  # nor echoed on provider receipts
