import pytest
from eos_notification.application import templates
from eos_notification.domain.errors import NotificationError
from eos_notification.infrastructure.config import NotificationConfig
from eos_notification.infrastructure.templates import DEFAULTS, check_syntax, render

CONFIG = NotificationConfig.from_env()


def override(db, **kw):
    args = dict(
        key="billing.trial.reminder", channel="email", locale="en", subject="S ${days_left}", body="B ${trial_ends_on}"
    )
    args.update(kw)
    return templates.upsert_template(db, **args)


def test_every_builtin_template_is_consistent():
    """The import-time guard already ran; this pins the security rules it enforces."""
    verify = DEFAULTS["tenancy.organisation.verify"]
    assert verify.secret_bearing and not verify.overridable and not verify.in_app_allowed
    assert verify.secret_ref in verify.variables and verify.secret_ref not in verify.secret_variables
    for d in DEFAULTS.values():
        for (channel, _), text in d.texts.items():
            assert channel in d.channels
            assert "token" not in (text.subject or "")


@pytest.mark.parametrize("text", ["cost $ here", "${", "$1abc"])
def test_malformed_placeholders_are_rejected(text):
    with pytest.raises(NotificationError) as e:
        check_syntax(text, {"a"}, "body")
    assert e.value.status == 422


def test_render_never_leaves_a_blank_for_a_missing_variable():
    with pytest.raises(NotificationError):
        render("Hello ${name}", {})
    assert render("Hello ${name}", {"name": "A"}) == "Hello A"


def test_subject_values_cannot_inject_a_second_header_line():
    assert render("Hi ${n}", {"n": "a\r\nBcc: x@evil"}, single_line=True) == "Hi a Bcc: x@evil"


def test_an_organisation_can_override_wording_for_an_existing_template(db, org, as_org):
    with as_org(org):
        item = override(db)
        assert item["scope"] == "organisation" and item["category"] == "reminder"
        listed = templates.list_templates(db, channel="email")["items"]
    scopes = {(i["key"], i["scope"]) for i in listed}
    assert ("billing.trial.reminder", "platform") in scopes and ("billing.trial.reminder", "organisation") in scopes


def test_another_organisation_never_sees_an_override(db, org, other_org, as_org):
    with as_org(org):
        override(db)
    with as_org(other_org):
        assert all(i["scope"] == "platform" for i in templates.list_templates(db)["items"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"key": "made.up.template"},  # only existing platform templates can be overridden
        {"key": "tenancy.organisation.verify", "body": "x ${token}"},  # secret-bearing: never overridable
        {"body": "x ${not_declared}"},
        {"subject": "x ${not_declared}"},
        {"category": "transactional"},  # an override cannot change the category
        {"variables": ["days_left", "extra"]},
        {"channel": "sms"},
        {"locale": "EN_us!"},
        {"channel": "in_app", "subject": "no subject for in_app"},
        {"body": ""},
    ],
)
def test_invalid_overrides_are_rejected(db, org, as_org, kwargs):
    with as_org(org), pytest.raises(NotificationError) as e:
        override(db, **kwargs)
    assert e.value.status == 422


def test_fallback_chain_org_locale_then_org_default_then_platform(db, org, as_org):
    with as_org(org):
        text, loc = templates.resolve_text(db, org.id, "billing.trial.reminder", "email", "kn", CONFIG)
        assert loc == "en" and text.subject.startswith("Your trial ends")  # platform default for the default locale
        override(db, body="ORG-EN ${trial_ends_on}")
        text, loc = templates.resolve_text(db, org.id, "billing.trial.reminder", "email", "kn", CONFIG)
        assert text.body.startswith("ORG-EN") and loc == "en"  # org wording for the default locale
        override(db, locale="kn", body="ORG-KN ${trial_ends_on}")
        text, loc = templates.resolve_text(db, org.id, "billing.trial.reminder", "email", "kn", CONFIG)
        assert text.body.startswith("ORG-KN") and loc == "kn"  # org wording for the locale wins


def test_no_template_for_the_channel_is_a_422(db, org, as_org):
    with as_org(org), pytest.raises(NotificationError) as e:
        templates.resolve_text(db, org.id, "tenancy.organisation.verify", "in_app", "en", CONFIG)
    assert e.value.status == 422


def test_preview_masks_secrets_whatever_the_caller_sends(db, org, as_org):
    with as_org(org):
        out = templates.preview(
            db, key="tenancy.organisation.verify", variables={"organisation_name": "C", "token": "REAL-SECRET"}
        )
    assert "REAL-SECRET" not in out["body"] and "[secret]" in out["body"]


def test_preview_missing_variable_is_a_422_naming_the_variable_only(db, org, as_org):
    with as_org(org), pytest.raises(NotificationError) as e:
        templates.preview(db, key="billing.trial.reminder", variables={"organisation_name": "SECRET-CORP"})
    assert e.value.status == 422 and "trial_ends_on" in e.value.detail and "SECRET-CORP" not in e.value.detail


def test_undeclared_variables_are_dropped_not_kept():
    d = DEFAULTS["billing.trial.expired"]
    assert templates.clean_variables(d, {"organisation_name": "C", "api_key": "leak"}) == {"organisation_name": "C"}
