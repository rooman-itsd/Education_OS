"""Profile roles in contracts/permissions.yaml. A token carries an academy profile role (actor, director,
stage-manager, ...), not the productions-* module roles, so each profile role whose dashboard shows one of this
module's widgets is granted by hand there. The role-reach test in #369 found 34 placements on 29 layouts
answering 403 because nothing was granted; these tests keep the two lists from drifting apart again and prove
each role can really read the endpoint behind its widget (#318)."""

from pathlib import Path

import yaml
from conftest import BASE
from eos_core.config import permissions_for

MODULE = "productions:"
DASHBOARDS = Path(__file__).resolve().parents[5] / "platform/identity/config/dashboards"

#: profile role -> (the module role whose grants it gets, the widget endpoint it must be able to read)
PROFILE_ROLES = {
    "actor": ("productions-member", "/my-roles"),
    "artist": ("productions-member", "/upcoming"),
    "dancer": ("productions-member", "/my-roles"),
    "designer": ("productions-member", "/upcoming"),
    "engineering-student": ("productions-member", "/upcoming"),
    "filmmaker": ("productions-member", "/upcoming"),
    "hospitality-trainee": ("productions-member", "/upcoming"),
    "law-student": ("productions-member", "/upcoming"),
    "management": ("productions-member", "/upcoming"),
    "management-student": ("productions-member", "/upcoming"),
    "musician": ("productions-member", "/upcoming"),
    "research-lead": ("productions-member", "/upcoming"),
    "research-scholar": ("productions-member", "/upcoming"),
    "chef-instructor": ("productions-lead", "/in-preparation"),
    "choreographer": ("productions-lead", "/in-preparation"),
    "corporate-mentor": ("productions-lead", "/in-preparation"),
    "director": ("productions-lead", "/in-preparation"),
    "legal-mentor": ("productions-lead", "/in-preparation"),
    "production-supervisor": ("productions-lead", "/in-preparation"),
    "studio-instructor": ("productions-lead", "/in-preparation"),
    "ensemble-director": ("productions-coordinator", "/calendar"),
    "exhibition-manager": ("productions-coordinator", "/calendar"),
    "industry-coordinator": ("productions-coordinator", "/calendar"),
    "industry-liaison": ("productions-coordinator", "/calendar"),
    "moot-court-coordinator": ("productions-coordinator", "/calendar"),
    "placement-officer": ("productions-coordinator", "/calendar"),
    "production-manager": ("productions-coordinator", "/calendar"),
    "research-office": ("productions-coordinator", "/calendar"),
    "stage-manager": ("productions-coordinator", "/calendar"),
}

#: which endpoint backs each widget id.
WIDGET_ENDPOINT = {
    "productions.calendar": "/calendar",
    "productions.upcoming": "/upcoming",
    "productions.my-roles": "/my-roles",
    "productions.in-preparation": "/in-preparation",
}


def _module_grants(role: str) -> set[str]:
    return {p for p in permissions_for([role]) if p.startswith(MODULE)}


def _layouts() -> dict[str, dict]:
    return {p.stem: (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) for p in DASHBOARDS.glob("*.yaml")}


def test_each_dashboard_profile_role_has_the_grants_its_widget_needs():
    for role, (module_role, _) in PROFILE_ROLES.items():
        assert _module_grants(role) == _module_grants(module_role), role
        assert _module_grants(role), role  # not empty: the profile role really is granted


def test_every_layout_showing_a_productions_widget_is_covered(client):
    """The list above is the whole of it: no dashboard may show a widget whose role was never granted."""
    uncovered = {}
    for role, layout in _layouts().items():
        widgets = [w for w in (layout.get("widgets") or []) if w in WIDGET_ENDPOINT]
        if widgets and role not in PROFILE_ROLES:
            uncovered[role] = widgets
    assert uncovered == {}


def test_each_layout_role_can_read_every_productions_widget_it_shows(client, org):
    for role, layout in _layouts().items():
        for widget in layout.get("widgets") or []:
            if widget not in WIDGET_ENDPOINT:
                continue
            _, headers = org.user(role)
            r = client.get(f"{BASE}{WIDGET_ENDPOINT[widget]}", headers=headers)
            assert r.status_code == 200, (role, widget, r.text)


def test_each_profile_role_reads_the_endpoint_behind_its_widget(client, org):
    for role, (_, path) in PROFILE_ROLES.items():
        _, headers = org.user(role)
        r = client.get(f"{BASE}{path}", headers=headers)
        assert r.status_code == 200, (role, r.text)


def test_a_role_with_no_grants_is_still_refused(client, org):
    _, student = org.user("student")
    for path in WIDGET_ENDPOINT.values():
        assert client.get(f"{BASE}{path}", headers=student).status_code == 403


def test_no_profile_role_is_quietly_given_the_right_to_run_the_calendar(client, org):
    """A performer or a lead must not be able to create, schedule or cancel a production."""
    for role, (module_role, _) in PROFILE_ROLES.items():
        can_manage = "productions:production:manage" in _module_grants(role)
        assert can_manage == (module_role == "productions-coordinator"), role
