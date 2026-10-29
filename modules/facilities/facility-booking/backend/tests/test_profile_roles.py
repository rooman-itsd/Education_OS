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


# Academy profile roles whose dashboards show this module's widgets (follow-up to #288, part of #331).
# role -> (module role whose grants it gets, extra keys, the widget's endpoint it must be able to read)
PROFILE_ROLES = {
    "actor": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "artist": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "dancer": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "designer": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "engineering-student": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "field-trainee": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "filmmaker": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "hospitality-trainee": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "medical-student": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "musician": ("facility-booking-user", set(), "/bookings?scope=mine"),
    "chef-instructor": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "choreographer": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "clinical-supervisor": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "coach": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "director": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "equipment-manager": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "exhibition-manager": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "farm-supervisor": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "hospital-coordinator": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "lab-in-charge": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "medical-staff": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "music-teacher": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "production-manager": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "stage-manager": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
    "studio-instructor": ("facility-booking-approver", set(), "/bookings?scope=managed&date=today"),
}


def test_each_dashboard_profile_role_has_the_grants_its_prd_names():
    for role, (base, extra, _) in PROFILE_ROLES.items():
        assert _module_grants(role) == _module_grants(base) | extra, role


def test_each_dashboard_profile_role_reads_the_data_behind_its_widget(client, org):
    for role, (_, _, path) in PROFILE_ROLES.items():
        _, headers = org.user(role)
        r = client.get(f"{BASE}{path}", headers=headers)
        assert r.status_code == 200, (role, r.text)
