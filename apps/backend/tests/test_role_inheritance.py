"""Role inheritance across the whole repo (eos_core.config): a role whose dashboard layout `extends` another holds
that role's grants plus its own, so an academy role (research-scholar, coach, ...) is not refused by every module
whose catalogue only names `student` or `faculty`. This is the host's check over every layout and every catalogue.

1. Every layout with `extends` holds at least what the extended role holds.
2. Every widget on a layout whose module has a catalogue is backed by at least one key that module's catalogue
   declares (`<module>:...`, or a `platform:` key it declares) held by the layout's role, the way the role really
   holds keys: its own grants, its inherited grants and the implicit `member` role every organisation user has, or,
   for the super-admin layout, the super-admin rule. Without one the shell hides the card and the API refuses it.
"""

import uuid
from pathlib import Path

import pytest
import yaml
from eos_core.config import permissions_for
from eos_identity.api.deps import MEMBER_ROLE
from eos_identity.application.service import NOT_A_PERSON_ROLES
from eos_testing import register_and_login
from eos_testing.tenancy import auth

REPO = Path(__file__).resolve().parents[3]
DASHBOARDS = REPO / "platform/identity/config/dashboards"


def _layouts() -> list[dict]:
    return [yaml.safe_load(f.read_text()) for f in sorted(DASHBOARDS.glob("*.yaml"))]


def _catalogue_keys() -> dict[str, set[str]]:
    """Module name (the folder name, which is also the key prefix) -> the keys its contracts/permissions.yaml declares."""
    files = [*REPO.glob("*/*/contracts/permissions.yaml"), *REPO.glob("modules/*/*/contracts/permissions.yaml")]
    out: dict[str, set[str]] = {}
    for f in files:
        data = yaml.safe_load(f.read_text()) or {}
        out[f.parents[1].name] = {p["key"] for p in data.get("permissions") or []}
    return out


def _held(role: str) -> set[str]:
    """The keys a person with this one role holds, as identity's current_principal computes them."""
    if role == "super-admin":
        return permissions_for([role], super_admin=True)
    return permissions_for([role, MEMBER_ROLE])


CATALOGUE_KEYS = _catalogue_keys()
EXTENDING = [(lay["role"], lay["extends"]) for lay in _layouts() if lay.get("extends")]

# Widgets the layout's role cannot use yet, by module. Each is a gap in that module's catalogue (or in the mapping of
# profile roles onto it), not in the platform rule, and is closed by a PR to that module, one module per PR. The
# test fails on an entry that has become backed, so this list only shrinks. Tracked under #315.
EMPTY = "the catalogue grants no role yet (#315)"
UNMAPPED = (
    "the catalogue grants only its own generic roles (<module>-learner, -reviewer, ...); no profile role is mapped "
    "onto them yet, and the layout's role (or the student/faculty role it extends) is not named (#315)"
)
NAMED = "the catalogue names profile roles, but not this one (#315)"
SUPER = (
    "the super-admin rule grants only platform: keys that some role is granted, and no role is granted "
    "platform:audit:read (#315)"
)
KNOWN_UNBACKED: dict[str, tuple[str, list[str]]] = {
    "admissions": (
        NAMED,
        [
            "applicant admissions.application-status",
            "applicant admissions.pending-documents",
        ],
    ),
    "alumni": (
        EMPTY,
        [
            "management-student alumni.mentoring",
        ],
    ),
    "amc-vendor-support": (
        UNMAPPED,
        [
            "support-staff amc-vendor-support.contracts-expiring",
        ],
    ),
    "athlete-performance": (
        NAMED,
        [
            "nutritionist athlete-performance.body-composition-trend",
        ],
    ),
    "audit": (
        SUPER,
        [
            "super-admin audit.super-admin-actions",
        ],
    ),
    "examinations": (
        UNMAPPED,
        [
            "department-admin examinations.results-summary",
            "examination-staff examinations.schedule",
            "examination-staff examinations.hall-tickets-issued",
            "examination-staff examinations.results-pending",
            "faculty examinations.exam-duties",
            "student examinations.upcoming-assessments",
        ],
    ),
    "field-training": (
        UNMAPPED,
        [
            "clinical-supervisor field-training.trainees-to-assess",
            "clinical-supervisor field-training.placements-open",
            "corporate-mentor field-training.trainees-to-assess",
            "design-mentor field-training.trainees-to-assess",
            "designer field-training.my-placement",
            "engineering-student field-training.my-placement",
            "farm-supervisor field-training.trainees-to-assess",
            "field-trainee field-training.my-placement",
            "field-trainee field-training.hours-logged",
            "hospital-coordinator field-training.active-placements",
            "hospital-coordinator field-training.placements-open",
            "hospitality-trainee field-training.my-placement",
            "industry-coordinator field-training.placements-open",
            "industry-coordinator field-training.active-placements",
            "industry-liaison field-training.placements-open",
            "law-student field-training.my-placement",
            "law-student field-training.hours-logged",
            "legal-mentor field-training.trainees-to-assess",
            "management-student field-training.my-placement",
            "medical-student field-training.my-placement",
            "medical-student field-training.hours-logged",
            "mentor-teacher field-training.trainees-to-assess",
            "moot-court-coordinator field-training.placements-open",
            "placement-officer field-training.placements-open",
            "practicum-coordinator field-training.placements-open",
            "practicum-coordinator field-training.active-placements",
            "project-guide field-training.trainees-to-assess",
            "research-lead field-training.placements-open",
            "teacher-trainee field-training.my-placement",
            "teacher-trainee field-training.hours-logged",
        ],
    ),
    "grievance": (
        UNMAPPED,
        [
            "governance grievance.open-by-committee",
            "management grievance.open",
        ],
    ),
    "incident-management": (
        UNMAPPED,
        [
            "support-staff incident-management.open",
        ],
    ),
    "iqac-accreditation": (
        UNMAPPED,
        [
            "governance iqac-accreditation.action-items",
        ],
    ),
    "knowledge-base": (
        UNMAPPED,
        [
            "support-staff knowledge-base.top-articles",
        ],
    ),
    "library": (
        UNMAPPED,
        [
            "student library.loans",
        ],
    ),
    "lms": (
        UNMAPPED,
        [
            "faculty lms.assignments-to-grade",
            "management-student lms.course-materials",
            "medical-student lms.course-materials",
            "student lms.course-materials",
        ],
    ),
    "placement-career": (
        EMPTY,
        [
            "engineering-student placement-career.openings",
            "hospitality-trainee placement-career.openings",
            "industry-coordinator placement-career.openings",
            "industry-liaison placement-career.openings",
            "law-student placement-career.openings",
            "management-student placement-career.openings",
            "placement-officer placement-career.openings",
            "placement-officer placement-career.drives",
            "practicum-coordinator placement-career.openings",
        ],
    ),
    "portfolio": (
        UNMAPPED,
        [
            "actor portfolio.my-portfolio",
            "artist portfolio.my-portfolio",
            "design-mentor portfolio.reviews-pending",
            "designer portfolio.my-portfolio",
            "filmmaker portfolio.my-portfolio",
            "mentor-teacher portfolio.reviews-pending",
            "music-teacher portfolio.reviews-pending",
            "musician portfolio.my-portfolio",
            "research-scholar portfolio.my-portfolio",
            "research-supervisor portfolio.reviews-pending",
            "studio-instructor portfolio.reviews-pending",
            "teacher-trainee portfolio.my-portfolio",
        ],
    ),
    "productions": (
        EMPTY,
        [
            "actor productions.my-roles",
            "artist productions.upcoming",
            "chef-instructor productions.in-preparation",
            "choreographer productions.in-preparation",
            "corporate-mentor productions.in-preparation",
            "dancer productions.my-roles",
            "designer productions.upcoming",
            "director productions.in-preparation",
            "engineering-student productions.upcoming",
            "ensemble-director productions.in-preparation",
            "ensemble-director productions.calendar",
            "exhibition-manager productions.calendar",
            "exhibition-manager productions.upcoming",
            "filmmaker productions.upcoming",
            "hospitality-trainee productions.upcoming",
            "industry-coordinator productions.calendar",
            "industry-liaison productions.calendar",
            "law-student productions.upcoming",
            "legal-mentor productions.in-preparation",
            "management-student productions.upcoming",
            "management productions.upcoming",
            "moot-court-coordinator productions.calendar",
            "moot-court-coordinator productions.upcoming",
            "musician productions.upcoming",
            "placement-officer productions.calendar",
            "production-manager productions.calendar",
            "production-manager productions.upcoming",
            "production-supervisor productions.in-preparation",
            "research-lead productions.upcoming",
            "research-office productions.calendar",
            "research-scholar productions.upcoming",
            "stage-manager productions.calendar",
            "stage-manager productions.upcoming",
            "studio-instructor productions.in-preparation",
        ],
    ),
    "projects": (
        UNMAPPED,
        [
            "artist projects.my-projects",
            "corporate-mentor projects.to-review",
            "design-mentor projects.to-review",
            "designer projects.my-projects",
            "director projects.to-review",
            "engineering-student projects.my-projects",
            "engineering-student projects.milestones-due",
            "farm-supervisor projects.active",
            "field-trainee projects.my-projects",
            "filmmaker projects.my-projects",
            "filmmaker projects.milestones-due",
            "industry-liaison projects.active",
            "law-student projects.my-projects",
            "legal-mentor projects.to-review",
            "management-student projects.my-projects",
            "medical-student projects.my-projects",
            "mentor-teacher projects.to-review",
            "production-supervisor projects.to-review",
            "production-supervisor projects.active",
            "project-guide projects.to-review",
            "project-guide projects.active",
            "research-lead projects.active",
            "research-lead projects.to-review",
            "research-office projects.active",
            "research-scholar projects.my-projects",
            "research-scholar projects.milestones-due",
            "research-supervisor projects.to-review",
            "research-supervisor projects.active",
            "studio-instructor projects.to-review",
            "teacher-trainee projects.my-projects",
        ],
    ),
    "regulatory-reports": (
        UNMAPPED,
        [
            "governance regulatory-reports.due",
            "hospital-coordinator regulatory-reports.due",
            "management regulatory-reports.compliance-calendar",
            "research-office regulatory-reports.due",
        ],
    ),
    "reporting": (
        EMPTY,
        [
            "department-admin reporting.department-reports",
            "management reporting.attendance-and-results-by-department",
        ],
    ),
    "rti": (
        UNMAPPED,
        [
            "governance rti.nearing-deadline",
        ],
    ),
    "selection-process": (
        UNMAPPED,
        [
            "actor selection-process.upcoming",
            "artist selection-process.upcoming",
            "choreographer selection-process.to-judge",
            "corporate-mentor selection-process.to-judge",
            "dancer selection-process.upcoming",
            "design-mentor selection-process.to-judge",
            "designer selection-process.upcoming",
            "director selection-process.to-judge",
            "ensemble-director selection-process.open-calls",
            "law-student selection-process.upcoming",
            "legal-mentor selection-process.to-judge",
            "moot-court-coordinator selection-process.open-calls",
            "music-teacher selection-process.to-judge",
            "musician selection-process.upcoming",
            "production-supervisor selection-process.to-judge",
            "research-office selection-process.open-calls",
            "research-scholar selection-process.my-applications",
            "research-supervisor selection-process.to-judge",
            "studio-instructor selection-process.to-judge",
        ],
    ),
    "skill-progress": (
        UNMAPPED,
        [
            "chef-instructor skill-progress.assessments-due",
            "choreographer skill-progress.assessments-due",
            "clinical-supervisor skill-progress.assessments-due",
            "dancer skill-progress.my-progress",
            "field-trainee skill-progress.my-progress",
            "hospitality-trainee skill-progress.my-progress",
            "medical-student skill-progress.my-progress",
            "mentor-teacher skill-progress.assessments-due",
            "music-teacher skill-progress.assessments-due",
            "musician skill-progress.my-progress",
            "practicum-coordinator skill-progress.cohort-overview",
            "project-guide skill-progress.assessments-due",
            "teacher-trainee skill-progress.my-progress",
        ],
    ),
    "sla-management": (
        UNMAPPED,
        [
            "support-staff sla-management.breaches",
        ],
    ),
    "sports-nutrition-health": (
        UNMAPPED,
        [
            "athlete sports-nutrition-health.nutrition-plan",
            "medical-staff sports-nutrition-health.injured-athletes",
            "medical-staff sports-nutrition-health.appointments-today",
            "nutritionist sports-nutrition-health.athletes-on-plans",
            "nutritionist sports-nutrition-health.plan-reviews-due",
        ],
    ),
    "timetable-attendance": (
        UNMAPPED,
        [
            "dancer timetable-attendance.today",
            "department-admin timetable-attendance.department-attendance",
            "faculty timetable-attendance.today-classes",
            "faculty timetable-attendance.attendance-to-mark",
            "student timetable-attendance.today",
            "student timetable-attendance.attendance-summary",
        ],
    ),
    "tournament-events": (
        UNMAPPED,
        [
            "athlete tournament-events.upcoming",
            "coach tournament-events.calendar",
        ],
    ),
    "training-video-analysis": (
        UNMAPPED,
        [
            "coach training-video-analysis.reviews-pending",
        ],
    ),
    "transport": (
        UNMAPPED,
        [
            "student transport.notices",
        ],
    ),
    "workflow": (
        EMPTY,
        [
            "department-admin workflow.approvals-pending",
        ],
    ),
}
KNOWN_UNBACKED_WIDGETS: dict[tuple[str, str], str] = {
    tuple(pair.split(" ")): f"{module}: {reason}"
    for module, (reason, pairs) in KNOWN_UNBACKED.items()
    for pair in pairs
}


def _widget_pairs() -> list[tuple[str, str, str]]:
    """(role, widget, module) for every widget on every layout whose module has a catalogue; the rest are skipped."""
    out = []
    for lay in _layouts():
        for w in lay.get("widgets") or []:
            module = w.split(".", 1)[0]  # <module>.<widget>
            if module in CATALOGUE_KEYS:
                out.append((lay["role"], w, module))
    return out


WIDGET_PAIRS = _widget_pairs()


def test_layouts_exist_and_some_extend():
    assert EXTENDING, "no layout extends another: the inheritance tests below would prove nothing"


@pytest.mark.parametrize(("role", "parent"), EXTENDING, ids=[r for r, _ in EXTENDING])
def test_a_role_holds_everything_the_role_its_layout_extends_holds(role, parent):
    assert permissions_for([role]) >= permissions_for([parent])


@pytest.mark.parametrize(("role", "parent"), EXTENDING, ids=[r for r, _ in EXTENDING])
def test_no_layout_inherits_from_a_privileged_or_non_person_role(role, parent):
    """Inheritance hands over every key of the parent, so a layout may only extend an ordinary person's role.
    Extending org-admin, super-admin or a role no person may hold would be an escalation by dashboard edit."""
    assert parent not in {"org-admin", "super-admin", *NOT_A_PERSON_ROLES}


@pytest.mark.parametrize(("role", "widget", "module"), WIDGET_PAIRS, ids=[f"{r}:{w}" for r, w, _ in WIDGET_PAIRS])
def test_every_widget_is_backed_by_a_key_of_its_module(role, widget, module):
    held = _held(role) & CATALOGUE_KEYS[module]
    if (role, widget) in KNOWN_UNBACKED_WIDGETS:
        assert not held, f"{role}/{widget} is backed now; drop it from KNOWN_UNBACKED_WIDGETS"
        pytest.xfail(KNOWN_UNBACKED_WIDGETS[(role, widget)])
    assert held, f"{role} sees widget {widget} but holds no key of {module}'s catalogue"


def test_known_exceptions_name_real_layout_widgets():
    assert set(KNOWN_UNBACKED_WIDGETS) <= {(r, w) for r, w, _ in WIDGET_PAIRS}


def _person(client, admin, slug: str, roles: list[str]) -> dict:
    body = {
        "email": f"p-{uuid.uuid4().hex[:8]}@{slug}.example.com",
        "name": "P",
        "password": "Passw0rd!x",
        "roles": roles,
    }
    assert client.post("/api/v1/identity/users", json=body, headers=admin).status_code == 201
    login = client.post(
        "/api/v1/identity/auth/login",
        json={"email": body["email"], "password": body["password"], "organisation_slug": slug},
    )
    assert login.status_code == 200, login.text
    return client.get("/api/v1/identity/auth/me", headers=auth(login.json()["token"])).json()


def test_auth_me_reports_the_inherited_keys(client):
    slug = "roles-inherit"
    a = register_and_login(client, slug=slug, academy_type="research-university")
    admin = auth(a["token"])
    scholar = _person(client, admin, slug, ["research-scholar"])
    assert scholar["roles"] == ["research-scholar"]
    assert "fees-accounts:self:read" in scholar["permissions"]
    supervisor = _person(client, admin, slug, ["research-supervisor"])
    assert "academic-management:roster:read" in supervisor["permissions"]
