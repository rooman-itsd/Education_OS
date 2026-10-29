"""Profile roles in contracts/permissions.yaml. Tokens carry profile roles such as facility-staff, not the
maintenance-* roles, so facility-staff is granted the same keys as maintenance-manager by hand; this keeps the two lists
from drifting apart and proves the Facility / Inventory Staff dashboard's widget can read its data (#331)."""

from conftest import BASE
from eos_core.config import permissions_for

MODULE = "maintenance:"


def _module_grants(role: str) -> set[str]:
    return {p for p in permissions_for([role]) if p.startswith(MODULE)}


def test_facility_staff_has_exactly_the_manager_grants():
    assert _module_grants("facility-staff") == _module_grants("maintenance-manager")
    assert _module_grants("facility-staff")  # not empty: the profile role is really granted


def test_facility_staff_reads_the_data_behind_the_tickets_widget(client, org):
    _, staff = org.user("facility-staff")
    r = client.get(f"{BASE}/tickets?scope=managed&open=true", headers=staff)
    assert r.status_code == 200, r.text


def test_a_role_without_grants_is_refused(client, org):
    _, student = org.user("student")
    assert client.get(f"{BASE}/tickets?scope=managed&open=true", headers=student).status_code == 403


# Academy profile roles whose dashboards show this module's widgets (follow-up to #288, part of #331).
# role -> (module role whose grants it gets, extra keys, the widget's endpoint it must be able to read)
PROFILE_ROLES = {
    "equipment-manager": ("maintenance-manager", set(), "/tickets?scope=managed&open=true"),
    "lab-in-charge": ("maintenance-manager", set(), "/tickets?scope=managed&open=true"),
}


def test_each_dashboard_profile_role_has_the_grants_its_prd_names():
    for role, (base, extra, _) in PROFILE_ROLES.items():
        assert _module_grants(role) == _module_grants(base) | extra, role


def test_each_dashboard_profile_role_reads_the_data_behind_its_widget(client, org):
    for role, (_, _, path) in PROFILE_ROLES.items():
        _, headers = org.user(role)
        r = client.get(f"{BASE}{path}", headers=headers)
        assert r.status_code == 200, (role, r.text)
