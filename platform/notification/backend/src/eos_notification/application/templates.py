"""Template lookup, organisation overrides and preview."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.errors import NotificationError
from ..domain.models import TemplateOverride
from ..infrastructure.config import NotificationConfig
from ..infrastructure.templates import (
    DEFAULTS,
    LOCALE_RE,
    MAX_VALUE_LENGTH,
    MAX_VARIABLES,
    SECRET_MASK,
    DefaultTemplate,
    TemplateText,
    check_syntax,
    get_default,
    render,
)
from .common import aware, organisation_of

MAX_BODY = 20000
MAX_SUBJECT = 300


def resolve_text(
    db: Session, organisation_id: str, key: str, channel: str, locale: str, config: NotificationConfig
) -> tuple[TemplateText, str]:
    """Fallback chain: the organisation's wording for the locale, then for the default locale, then the platform
    default for the locale, then the platform default for the default locale. 422 if none exists."""
    default = get_default(key)
    chain = [locale] if locale == config.default_locale else [locale, config.default_locale]
    overrides = {
        o.locale: o
        for o in db.scalars(
            scoped(db, select(TemplateOverride), TemplateOverride).where(
                TemplateOverride.organisation_id == organisation_id,
                TemplateOverride.key == key,
                TemplateOverride.channel == channel,
                TemplateOverride.locale.in_(chain),
            )
        )
    }
    for loc in chain:
        if default.overridable and loc in overrides:
            o = overrides[loc]
            return TemplateText(o.subject, o.body), loc
    for loc in chain:
        if (channel, loc) in default.texts:
            return default.texts[(channel, loc)], loc
    raise NotificationError(422, "no template for this channel and locale")


def clean_variables(default: DefaultTemplate, supplied: dict | None, *, require_all: bool = True) -> dict[str, str]:
    """Only declared variables are kept, as short scalar strings. Undeclared ones are dropped, never stored."""
    supplied = supplied or {}
    if not isinstance(supplied, dict) or len(supplied) > MAX_VARIABLES:
        raise NotificationError(422, "variables must be an object with at most 30 entries")
    out: dict[str, str] = {}
    for name in default.variables:
        value = supplied.get(name)
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            raise NotificationError(422, f"variable {name} must be a scalar")
        text = str(value)
        if len(text) > MAX_VALUE_LENGTH:
            raise NotificationError(422, f"variable {name} is too long")
        out[name] = text
    missing = [n for n in default.variables if n not in out]
    if require_all and missing:
        raise NotificationError(422, f"missing variable(s): {', '.join(missing)}")
    return out


def _item(default: DefaultTemplate, channel: str, locale: str, text: TemplateText) -> dict:
    return {
        "id": default.platform_id(channel, locale),
        "scope": "platform",
        "key": default.key,
        "channel": channel,
        "locale": locale,
        "category": default.category,
        "subject": text.subject,
        "body": text.body,
        "variables": list(default.variables),
        "updated_at": None,
    }


def _override_item(o: TemplateOverride, default: DefaultTemplate) -> dict:
    return {
        "id": o.id,
        "scope": "organisation",
        "key": o.key,
        "channel": o.channel,
        "locale": o.locale,
        "category": default.category,
        "subject": o.subject,
        "body": o.body,
        "variables": list(default.variables),
        "updated_at": aware(o.updated_at).isoformat() if o.updated_at else None,
    }


def list_templates(db: Session, channel: str | None = None, locale: str | None = None) -> dict:
    org = organisation_of(db)
    items = [
        _item(d, ch, loc, text)
        for d in DEFAULTS.values()
        for (ch, loc), text in sorted(d.texts.items())
        if (channel is None or ch == channel) and (locale is None or loc == locale)
    ]
    q = scoped(db, select(TemplateOverride), TemplateOverride).where(TemplateOverride.organisation_id == org)
    if channel:
        q = q.where(TemplateOverride.channel == channel)
    if locale:
        q = q.where(TemplateOverride.locale == locale)
    for o in db.scalars(q.order_by(TemplateOverride.key, TemplateOverride.channel, TemplateOverride.locale)):
        if o.key in DEFAULTS:
            items.append(_override_item(o, DEFAULTS[o.key]))
    return {"items": items, "total": len(items)}


def upsert_template(
    db: Session,
    *,
    key: str,
    channel: str,
    locale: str,
    body: str,
    subject: str | None = None,
    category: str | None = None,
    variables: list[str] | None = None,
) -> dict:
    org = organisation_of(db)
    default = DEFAULTS.get(key)
    if default is None:
        raise NotificationError(422, "an organisation may only override an existing platform template")
    if not default.overridable:
        raise NotificationError(422, "this template cannot be overridden")
    if channel not in default.channels:
        raise NotificationError(422, "channel is not supported by this template")
    if not LOCALE_RE.match(locale or ""):
        raise NotificationError(422, "locale is not valid")
    if category is not None and category != default.category:
        raise NotificationError(422, "an override cannot change the template category")
    allowed = set(default.variables)
    if variables is not None and not set(variables) <= allowed:
        raise NotificationError(422, "an override cannot declare variables the template does not have")
    if channel != "email" and subject:
        raise NotificationError(422, "subject is for email only")
    if not body or len(body) > MAX_BODY or (subject and len(subject) > MAX_SUBJECT):
        raise NotificationError(422, "body or subject length is not valid")
    check_syntax(subject, allowed, "subject")
    check_syntax(body, allowed, "body")

    row = db.scalars(
        scoped(db, select(TemplateOverride), TemplateOverride).where(
            TemplateOverride.organisation_id == org,
            TemplateOverride.key == key,
            TemplateOverride.channel == channel,
            TemplateOverride.locale == locale,
        )
    ).first()
    if row is None:
        row = TemplateOverride(organisation_id=org, key=key, channel=channel, locale=locale, body=body, subject=subject)
        db.add(row)
    else:
        row.body, row.subject = body, subject
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise NotificationError(409, "the template was changed at the same time; try again") from None
    return _override_item(row, default)


def preview(
    db: Session,
    *,
    key: str,
    variables: dict,
    channel: str | None = None,
    locale: str | None = None,
    config: NotificationConfig | None = None,
) -> dict:
    """Render without sending. Secret variables are always shown as a fixed marker, whatever the caller sent,
    so a preview can never be used to see or pass a real secret."""
    config = config or NotificationConfig.from_env()
    org = organisation_of(db)
    default = get_default(key)
    channel = channel or default.channels[0]
    if channel not in default.channels:
        raise NotificationError(422, "channel is not supported by this template")
    masked = {s: SECRET_MASK for s in default.secret_variables}
    if default.secret_ref:
        masked[default.secret_ref] = "preview"
    values = clean_variables(default, {**(variables or {}), **masked})
    text, _ = resolve_text(db, org, key, channel, locale or config.default_locale, config)
    return {
        "subject": render(text.subject, values, single_line=True),
        "body": render(text.body, values),
    }
