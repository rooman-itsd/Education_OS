"""Unit tests of permission checks (application layer): keys match contracts/permissions.yaml, and a caller without
the operation's key is refused with 403."""

from pathlib import Path

import pytest
import yaml
from eos_academic_management.application.access import FACULTY_LOAD_READ, PERMISSION_KEYS, Actor, require
from eos_academic_management.application.errors import AcademicManagementError

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def test_permission_keys_are_exactly_the_contract_catalogue():
    catalogue = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
    assert sorted(PERMISSION_KEYS) == sorted(p["key"] for p in catalogue["permissions"])


def test_every_x_permission_in_the_api_contract_is_a_known_key():
    api = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
    ops = [op for path in api["paths"].values() for op in path.values() if "x-permission" in op]
    used = {op["x-permission"] for op in ops} | {k for op in ops for k in op.get("x-permission-any", [])}
    assert used <= set(PERMISSION_KEYS)


def test_a_caller_with_the_key_passes():
    require(Actor("u1", "org1", permissions={FACULTY_LOAD_READ}), FACULTY_LOAD_READ)


@pytest.mark.parametrize("permissions", [set(), {"academic-management:offering:read"}, {"faculty-load:read"}])
def test_a_caller_without_the_key_is_forbidden(permissions):
    with pytest.raises(AcademicManagementError) as err:
        require(Actor("u1", "org1", roles=["department-admin"], permissions=permissions), FACULTY_LOAD_READ)
    assert (err.value.status, err.value.code) == (403, "forbidden")


def test_roles_alone_grant_nothing():
    # Role-to-key mapping is pending (issue #100); only resolved keys count.
    assert not Actor("u1", "org1", roles=["org-admin"]).can(FACULTY_LOAD_READ)
