from pathlib import Path

import pytest
import yaml
from eos_core.security import hash_password, verify_password
from eos_identity.application.service import NOT_A_PERSON_ROLES, RoleNotAssignableError, create_user

PROFILES = Path(__file__).resolve().parents[2] / "config" / "profiles"


def test_password_roundtrip():
    h = hash_password("Secret123!")
    assert verify_password("Secret123!", h) and not verify_password("nope", h)


@pytest.mark.parametrize("roles", [["service"], ["student", "service"], ["service", "org-admin"]])
def test_create_user_refuses_a_role_no_person_may_hold_before_writing_anything(roles):
    """Every role assignment passes through create_user (the users route, tenancy's registration, the super-admin
    seed), so the refusal holds for each of them. It comes first: db=None proves nothing is touched."""
    with pytest.raises(RoleNotAssignableError, match="service"):
        create_user(None, organisation_id="org-1", email="p@example.com", name="P", password="Passw0rd!x", roles=roles)


def test_no_profile_role_is_one_a_person_may_not_hold():
    """The refused set must never catch a role an institution actually hands out to people."""
    assigned = {
        r["id"] for f in PROFILES.glob("*.yaml") for r in (yaml.safe_load(f.read_text()) or {}).get("roles", [])
    }
    assert assigned and not (assigned & NOT_A_PERSON_ROLES)
