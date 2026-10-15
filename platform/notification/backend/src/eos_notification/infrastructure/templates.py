"""Trusted platform templates. They live in code, never in the database: a template's category, placeholders and
secret handling decide what may be stored and what may be overridden, so an organisation cannot edit them.
Rendering uses string.Template (${name}); Jinja is not on the approved stack and a placeholder is never code."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from string import Template

from ..domain.errors import NotificationError

MAX_VALUE_LENGTH = 2000
MAX_VARIABLES = 30
SECRET_MASK = "[secret]"
LOCALE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
_NAMESPACE = uuid.UUID("6f1c2f0e-6a52-4b7e-9d52-0b3c5b0b6d11")


@dataclass(frozen=True)
class TemplateText:
    subject: str | None
    body: str


@dataclass(frozen=True)
class DefaultTemplate:
    key: str
    category: str
    channels: tuple[str, ...]
    variables: tuple[str, ...]
    texts: dict[tuple[str, str], TemplateText] = field(default_factory=dict)  # (channel, locale) -> text
    secret_variables: tuple[str, ...] = ()
    secret_ref: str | None = None  # non-secret id of the secret issuance; makes idempotency safe
    overridable: bool = True
    in_app_allowed: bool = False

    @property
    def secret_bearing(self) -> bool:
        return bool(self.secret_variables)

    def platform_id(self, channel: str, locale: str) -> str:
        return str(uuid.uuid5(_NAMESPACE, f"{self.key}|{channel}|{locale}"))


def identifiers(text: str | None) -> set[str]:
    return set(Template(text).get_identifiers()) if text else set()


def check_syntax(text: str | None, allowed: set[str], what: str) -> None:
    """Reject a malformed placeholder or one the template does not declare. Raises NotificationError(422)."""
    if not text:
        return
    t = Template(text)
    if not t.is_valid():
        raise NotificationError(422, f"{what} has an invalid placeholder")
    unknown = sorted(set(t.get_identifiers()) - allowed)
    if unknown:
        raise NotificationError(422, f"{what} uses undeclared variable(s): {', '.join(unknown)}")


def render(text: str | None, values: dict[str, str], *, single_line: bool = False) -> str | None:
    if text is None:
        return None
    if single_line:
        values = {k: re.sub(r"[\r\n]+", " ", v) for k, v in values.items()}
    try:
        return Template(text).substitute(values)
    except (KeyError, ValueError) as e:
        raise NotificationError(422, "template could not be rendered") from e


def _t(key, category, channels, variables, texts, **kw) -> DefaultTemplate:
    return DefaultTemplate(
        key=key,
        category=category,
        channels=tuple(channels),
        variables=tuple(variables),
        texts={k: TemplateText(*v) for k, v in texts.items()},
        **kw,
    )


_FOOTER = "\n\nThis message was sent by Education OS."

DEFAULTS: dict[str, DefaultTemplate] = {
    d.key: d
    for d in (
        _t(
            "tenancy.organisation.verify",
            "transactional",
            ["email"],
            ["organisation_name", "token", "token_id"],
            {
                ("email", "en"): (
                    "Verify your Education OS organisation",
                    "Welcome to ${organisation_name}. Verify with token ${token}" + _FOOTER,
                )
            },
            secret_variables=("token",),
            secret_ref="token_id",
            overridable=False,
        ),
        _t(
            "tenancy.organisation.verified",
            "operational",
            ["email"],
            ["organisation_name"],
            {
                ("email", "en"): (
                    "Your email is verified",
                    "Thank you. ${organisation_name} is now waiting for approval by the platform operator." + _FOOTER,
                )
            },
        ),
        _t(
            "tenancy.organisation.approved",
            "operational",
            ["email", "in_app"],
            ["organisation_name"],
            {
                ("email", "en"): (
                    "Your academy is live",
                    "${organisation_name} is approved and live. Sign in to get started." + _FOOTER,
                ),
                ("in_app", "en"): (None, "${organisation_name} is approved and live."),
            },
            in_app_allowed=True,
        ),
        _t(
            "billing.trial.reminder",
            "reminder",
            ["email", "in_app"],
            ["organisation_name", "trial_ends_on", "days_left"],
            {
                ("email", "en"): (
                    "Your trial ends in ${days_left} day(s)",
                    "The trial for ${organisation_name} ends on ${trial_ends_on}. Upgrade to keep your data "
                    "editable." + _FOOTER,
                ),
                ("in_app", "en"): (None, "Your trial ends on ${trial_ends_on}."),
            },
            in_app_allowed=True,
        ),
        _t(
            "billing.trial.expired",
            "operational",
            ["email", "in_app"],
            ["organisation_name"],
            {
                ("email", "en"): (
                    "Your trial has ended",
                    "The trial for ${organisation_name} has ended. Upgrade to continue." + _FOOTER,
                ),
                ("in_app", "en"): (None, "Your trial has ended. Upgrade to continue."),
            },
            in_app_allowed=True,
        ),
        _t(
            "billing.invoice.issued",
            "operational",
            ["email", "in_app"],
            ["organisation_name", "invoice_number", "amount", "due_on"],
            {
                ("email", "en"): (
                    "Invoice ${invoice_number} for ${organisation_name}",
                    "Invoice ${invoice_number} for ${amount} is due on ${due_on}." + _FOOTER,
                ),
                ("in_app", "en"): (None, "Invoice ${invoice_number} for ${amount} is due on ${due_on}."),
            },
            in_app_allowed=True,
        ),
    )
}


def _validate_defaults() -> None:
    """Import-time guard: a bad built-in template fails the module's own tests, never a send."""
    for d in DEFAULTS.values():
        declared = set(d.variables)
        assert set(d.secret_variables) <= declared, d.key
        assert not d.secret_variables or d.secret_ref in declared - set(d.secret_variables), d.key
        assert not d.secret_bearing or (not d.overridable and not d.in_app_allowed), d.key
        for (channel, _locale), text in d.texts.items():
            assert channel in d.channels, d.key
            assert (channel != "in_app") or d.in_app_allowed, d.key
            for part in (text.subject, text.body):
                assert part is None or Template(part).is_valid(), d.key
                assert identifiers(part) <= declared, d.key
            assert not (identifiers(text.subject) & set(d.secret_variables)), d.key
            assert channel != "in_app" or not (identifiers(text.body) & set(d.secret_variables)), d.key


_validate_defaults()


def get_default(key: str) -> DefaultTemplate:
    try:
        return DEFAULTS[key]
    except KeyError:
        raise NotificationError(422, "unknown template") from None
