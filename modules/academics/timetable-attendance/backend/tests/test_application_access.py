"""Permission keys and errors of the application layer."""

from pathlib import Path

import pytest
import yaml
from eos_timetable_attendance.application import access
from eos_timetable_attendance.application.errors import STATUS_BY_KIND, TimetableAttendanceError, from_domain
from eos_timetable_attendance.domain.errors import DomainRuleError

CATALOGUE = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "permissions.yaml").read_text(encoding="utf-8")
)


def test_the_keys_are_exactly_the_catalogues_keys():
    assert set(access.PERMISSION_KEYS) == {p["key"] for p in CATALOGUE["permissions"]}
    assert len(access.PERMISSION_KEYS) == len(set(access.PERMISSION_KEYS))


def test_every_key_is_module_resource_action():
    for key in access.PERMISSION_KEYS:
        module, resource, action = key.split(":")
        assert module == access.MODULE == CATALOGUE["module"]
        assert resource and action


def test_actor_can_only_what_it_holds():
    actor = access.Actor("u", "o", permissions={access.TIMETABLE_READ})
    assert actor.can(access.TIMETABLE_READ)
    assert not actor.can(access.TIMETABLE_WRITE)


def test_require_is_a_403_with_the_contract_body():
    actor = access.Actor("u", "o", permissions={access.TIMETABLE_READ})
    access.require(actor, access.TIMETABLE_READ)
    with pytest.raises(TimetableAttendanceError) as e:
        access.require(actor, access.TIMETABLE_WRITE)
    assert e.value.status == 403
    assert e.value.body() == {"code": "forbidden", "message": f"missing permission {access.TIMETABLE_WRITE}"}


def test_domain_error_kinds_map_to_the_contracts_statuses():
    assert STATUS_BY_KIND == {"invalid": 400, "not_found": 404, "conflict": 409, "unprocessable": 422}
    err = from_domain(DomainRuleError("blocking_conflicts", "x", kind="conflict", field="f", details={"n": 2}))
    assert (err.status, err.body()) == (
        409,
        {"code": "blocking_conflicts", "message": "x", "details": {"n": 2, "field": "f"}},
    )
    assert from_domain(DomainRuleError("c", "m", kind="invalid")).body() == {"code": "c", "message": "m"}
