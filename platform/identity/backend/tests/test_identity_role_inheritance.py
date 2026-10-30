"""An academy role holds the grants of the role its dashboard layout extends (eos_core.config.permissions_for), and
current_principal, which /auth/me and every `require(...)` guard read, carries them. The keys checked belong to
module catalogues; each case is skipped when that catalogue is not in the repo, so the suite still runs alone."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from eos_core.security import create_token
from eos_identity.api import deps

REPO = Path(__file__).resolve().parents[4]
FEES = REPO / "modules/finance-operations/fees-accounts/contracts/permissions.yaml"
ACADEMIC = REPO / "modules/academics/academic-management/contracts/permissions.yaml"


class _Db:
    """Enough of a Session for current_principal once get_user is replaced: it rolls back and carries info."""

    def __init__(self):
        self.info: dict = {}

    def rollback(self) -> None:
        pass


def _principal(monkeypatch, roles: list[str]) -> deps.Principal:
    monkeypatch.setattr(deps, "get_user", lambda db, user_id: SimpleNamespace(id=user_id, status="active"))
    token = create_token(user_id="u-1", organisation_id="org-1", roles=roles)
    return deps.current_principal(authorization=f"Bearer {token}", db=_Db())


@pytest.mark.skipif(not FEES.exists(), reason="fees-accounts catalogue not in this repo")
def test_a_research_scholar_holds_what_a_student_holds(monkeypatch):
    p = _principal(monkeypatch, ["research-scholar"])
    assert p.roles == ["research-scholar"]  # the token's roles are reported as they are; only the keys widen
    assert p.can("fees-accounts:self:read")


@pytest.mark.skipif(not ACADEMIC.exists(), reason="academic-management catalogue not in this repo")
def test_a_research_supervisor_holds_what_a_faculty_member_holds(monkeypatch):
    p = _principal(monkeypatch, ["research-supervisor"])
    assert p.can("academic-management:roster:read")
    assert not p.can("academic-management:roster:read-all")  # inheritance gives faculty's keys, not an admin's


PROJECTS = REPO / "modules/practice/projects/contracts/permissions.yaml"


@pytest.mark.skipif(not PROJECTS.exists(), reason="projects catalogue not in this repo")
def test_a_research_scholar_holds_the_module_roles_its_layout_lists(monkeypatch):
    p = _principal(monkeypatch, ["research-scholar"])
    assert p.can("projects:self:propose")  # projects-member, from `module_roles`
    assert not p.can("projects:project:manage")  # a learner layout never lists a coordinator role
