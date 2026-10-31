"""Profile roles in contracts/permissions.yaml. Tokens carry the sports-college profile roles (facility-staff, coach,
athlete, org-admin), not the sports-facilities-* roles, so each is granted the keys of the module role the PRD names
for its users by hand; this keeps each list equal to its module role and proves the role can really use the API."""

from conftest import BASE
from eos_core.config import permissions_for

MODULE = "sports-facilities:"

# profile role -> (module role whose grants it gets, an endpoint it must be able to read)
PROFILE_ROLES = {
    "facility-staff": ("sports-facilities-admin", "/usage"),
    "org-admin": ("sports-facilities-admin", "/usage"),
    "coach": ("sports-facilities-coach", "/usage"),
    "athlete": ("sports-facilities-viewer", "/facilities"),
}


def _module_grants(role: str) -> set[str]:
    return {p for p in permissions_for([role]) if p.startswith(MODULE)}


def test_each_profile_role_has_exactly_the_grants_of_its_module_role():
    for role, (base, _) in PROFILE_ROLES.items():
        assert _module_grants(role) == _module_grants(base), role
        assert _module_grants(role), role  # not empty: the profile role is really granted


def test_each_profile_role_reads_its_data(client, org):
    for role, (_, path) in PROFILE_ROLES.items():
        _, headers = org.user(role)
        r = client.get(f"{BASE}{path}", headers=headers)
        assert r.status_code == 200, (role, r.text)


def test_facility_staff_registers_and_coach_records(client, org):
    _, staff = org.user("facility-staff")
    body = {"name": "Gym", "facility_type": "gym", "sports": ["Strength"], "indoor": True}
    f = client.post(f"{BASE}/facilities", json=body, headers=staff)
    assert f.status_code == 201, f.text
    _, coach = org.user("coach")
    usage = {
        "facility_id": f.json()["id"],
        "used_from": "2026-10-28T06:00:00+05:30",
        "used_to": "2026-10-28T07:00:00+05:30",
        "purpose": "training",
    }
    assert client.post(f"{BASE}/usage", json=usage, headers=coach).status_code == 201
    assert client.post(f"{BASE}/facilities", json=body | {"name": "Gym 2"}, headers=coach).status_code == 403


def test_athlete_only_reads_and_a_role_without_grants_is_refused(client, org):
    _, athlete = org.user("athlete")
    assert client.get(f"{BASE}/usage", headers=athlete).status_code == 403
    _, student = org.user("student")
    assert client.get(f"{BASE}/facilities", headers=student).status_code == 403
