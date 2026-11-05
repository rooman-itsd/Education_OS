"""Permission keys, the Actor and the error type of the application layer."""

from pathlib import Path

import pytest
import yaml
from eos_examinations.application import access
from eos_examinations.application.errors import STATUS_BY_KIND, ExaminationsError, from_domain
from eos_examinations.domain.errors import DomainRuleError

CATALOGUE = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "permissions.yaml").read_text(encoding="utf-8")
)
OPENAPI = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)


def test_the_keys_are_exactly_the_catalogues_keys():
    assert set(access.PERMISSION_KEYS) == {p["key"] for p in CATALOGUE["permissions"]}
    assert len(access.PERMISSION_KEYS) == len(set(access.PERMISSION_KEYS)) == 43


def test_every_key_is_module_resource_action_in_this_module():
    for key in access.PERMISSION_KEYS:
        module, resource, action = key.split(":")
        assert module == access.MODULE == CATALOGUE["module"]
        assert resource and action


def test_every_operations_x_permission_is_a_known_key():
    """The keys the future routes will declare exist, so a typo cannot reach `require()`."""
    named = set()
    for item in OPENAPI["paths"].values():
        for operation in item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                named.add(operation["x-permission"])
    assert named <= set(access.PERMISSION_KEYS)


def test_actor_can_only_what_it_holds_and_a_wider_key_is_a_separate_key():
    actor = access.Actor("u", "o", permissions={access.DUTY_READ_OWN})
    assert actor.can(access.DUTY_READ_OWN)
    assert not actor.can(access.DUTY_READ_ALL) and not actor.can(access.DUTY_READ_DEPARTMENT)


def test_require_is_a_403_with_the_contract_body():
    actor = access.Actor("u", "o", permissions={access.EXAM_CYCLE_READ})
    access.require(actor, access.EXAM_CYCLE_READ)
    with pytest.raises(ExaminationsError) as e:
        access.require(actor, access.EXAM_CYCLE_MANAGE)
    assert e.value.status == 403
    assert e.value.body() == {"code": "forbidden", "message": f"missing permission {access.EXAM_CYCLE_MANAGE}"}


def test_no_department_is_carried_or_assumed():
    assert "department" not in access.Actor.__dataclass_fields__


def test_domain_error_kinds_map_to_the_contracts_statuses():
    assert STATUS_BY_KIND == {"invalid": 400, "not_found": 404, "conflict": 409, "unprocessable": 422}
    err = from_domain(
        DomainRuleError("weightage_not_100", "x", kind="unprocessable", field="components", details={"total": "60"})
    )
    assert (err.status, err.body()) == (
        422,
        {"code": "weightage_not_100", "message": "x", "details": {"total": "60", "field": "components"}},
    )
    assert from_domain(DomainRuleError("c", "m", kind="invalid")).body() == {"code": "c", "message": "m"}
