"""Unit tests of the caller's permissions and the error a use case raises (application layer)."""

import pytest
from eos_helpdesk.application.access import (
    PERMISSION_KEYS,
    SETTINGS_MANAGE,
    TICKET_READ,
    TICKET_WORK,
    Actor,
    require,
)
from eos_helpdesk.application.errors import STATUS_BY_KIND, HelpdeskError, forbidden, from_domain
from eos_helpdesk.domain.errors import KINDS, DomainRuleError


def agent(*permissions):
    return Actor(user_id="agent-1", organisation_id="org-1", permissions=set(permissions))


# --- require


def test_a_caller_with_the_permission_passes():
    require(agent(TICKET_READ), TICKET_READ)


def test_a_caller_without_the_permission_is_forbidden():
    with pytest.raises(HelpdeskError) as err:
        require(agent(TICKET_WORK), TICKET_READ)
    assert (err.value.status, err.value.code) == (403, "forbidden")
    assert TICKET_READ in err.value.message


def test_any_one_of_several_permissions_is_enough():
    # GET /queues: "Permission helpdesk:ticket:read or helpdesk:settings:manage"
    require(agent(SETTINGS_MANAGE), TICKET_READ, SETTINGS_MANAGE)
    require(agent(TICKET_READ), TICKET_READ, SETTINGS_MANAGE)
    with pytest.raises(HelpdeskError):
        require(agent(TICKET_WORK), TICKET_READ, SETTINGS_MANAGE)


def test_a_caller_with_no_permissions_is_forbidden():
    with pytest.raises(HelpdeskError):
        require(agent(), TICKET_READ)


def test_require_needs_a_permission_to_check():
    with pytest.raises(ValueError):
        require(agent(TICKET_READ))


def test_permission_keys_follow_the_module_naming():
    assert all(key.startswith("helpdesk:") and key.count(":") == 2 for key in PERMISSION_KEYS)
    assert len(set(PERMISSION_KEYS)) == len(PERMISSION_KEYS)


# --- errors


def test_every_domain_kind_has_a_status():
    assert set(STATUS_BY_KIND) == set(KINDS)


@pytest.mark.parametrize(("kind", "status"), [("conflict", 409), ("invalid", 422)])
def test_a_domain_error_keeps_its_code_and_field(kind, status):
    err = from_domain(DomainRuleError("some_rule", "some message", kind=kind, field="status"))
    assert (err.status, err.code, err.message, err.field) == (status, "some_rule", "some message", "status")
    assert err.body() == {"code": "some_rule", "message": "some message", "field": "status"}


def test_a_body_without_a_field_leaves_it_out():
    assert forbidden("no").body() == {"code": "forbidden", "message": "no"}
