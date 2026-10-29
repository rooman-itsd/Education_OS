"""Profile roles in contracts/permissions.yaml. Tokens carry profile roles such as facility-staff, not the
facility-booking-* roles, so facility-staff is granted the same keys as facility-booking-manager by hand; this keeps the two lists
from drifting apart and proves the Facility / Inventory Staff dashboard's widget can read its data (#331)."""

from conftest import BASE
from eos_core.config import permissions_for

MODULE = "facility-booking:"


def _module_grants(role: str) -> set[str]:
    return {p for p in permissions_for([role]) if p.startswith(MODULE)}


def test_facility_staff_has_exactly_the_manager_grants():
    assert _module_grants("facility-staff") == _module_grants("facility-booking-manager")
    assert _module_grants("facility-staff")  # not empty: the profile role is really granted


def test_facility_staff_reads_the_data_behind_the_bookings_today_widget(client, org):
    _, staff = org.user("facility-staff")
    r = client.get(f"{BASE}/summary", headers=staff)
    assert r.status_code == 200, r.text


def test_a_role_without_grants_is_refused(client, org):
    _, student = org.user("student")
    assert client.get(f"{BASE}/summary", headers=student).status_code == 403
