"""A role holds its own catalogue grants plus those of the role its dashboard layout extends (eos_core.config)."""

from pathlib import Path

import pytest
from eos_core import config


def _write(root: Path, rel: str, text: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repo root with one module catalogue and a few layouts; the loader caches are cleared around it."""
    _write(
        tmp_path,
        "modules/finance/fees/contracts/permissions.yaml",
        "roles:\n"
        "  - name: student\n    grants: [fees:self:read]\n"
        "  - name: faculty\n    grants: [fees:roster:read]\n"
        "  - name: athlete\n    grants: [fees:athlete:extra]\n"
        "  - name: fees-learner\n    grants: [fees:learner:read]\n"
        "  - name: fees-reviewer\n    grants: [fees:review:read]\n"
        "permissions:\n  - key: fees:self:read\n",
    )
    _write(
        tmp_path,
        "platform/tenancy/contracts/permissions.yaml",
        "permissions:\n  - key: platform:x\n  - key: platform:ungranted:read\n"
        "roles:\n  - name: org-admin\n    grants: [platform:x]\n",
    )
    dash = "platform/identity/config/dashboards"
    _write(tmp_path, f"{dash}/student.yaml", "role: student\nwidgets: []\n")
    _write(tmp_path, f"{dash}/athlete.yaml", "role: athlete\nextends: student\nwidgets: []\n")
    _write(tmp_path, f"{dash}/coach.yaml", "role: coach\nextends: faculty\nwidgets: []\n")
    _write(tmp_path, f"{dash}/head-coach.yaml", "role: head-coach\nextends: coach\nwidgets: []\n")
    _write(tmp_path, f"{dash}/loop-a.yaml", "role: loop-a\nextends: loop-b\n")
    _write(tmp_path, f"{dash}/loop-b.yaml", "role: loop-b\nextends: loop-a\n")
    _write(
        tmp_path,
        f"{dash}/scholar.yaml",
        "role: scholar\nextends: student\nmodule_roles: [fees-learner, scholar]\nwidgets: []\n",
    )
    _write(
        tmp_path,
        f"{dash}/senior-scholar.yaml",
        "role: senior-scholar\nextends: scholar\nmodule_roles: [fees-reviewer]\n",
    )
    _write(tmp_path, f"{dash}/mod-a.yaml", "role: mod-a\nmodule_roles: [mod-b]\n")
    _write(tmp_path, f"{dash}/mod-b.yaml", "role: mod-b\nmodule_roles: [mod-a, fees-learner]\n")
    _write(tmp_path, f"{dash}/README.md", "not a layout\n")
    monkeypatch.setattr(config, "_root", lambda: tmp_path)
    config.load_role_grants.cache_clear()
    for loader in (config.load_role_grants, config.load_role_parents, config.load_platform_keys):
        loader.cache_clear()
    yield tmp_path
    for loader in (config.load_role_grants, config.load_role_parents, config.load_platform_keys):
        loader.cache_clear()


def test_a_role_holds_the_grants_of_the_role_its_layout_extends_plus_its_own(repo):
    assert config.permissions_for(["athlete"]) == {"fees:self:read", "fees:athlete:extra"}
    assert config.permissions_for(["coach"]) == {"fees:roster:read"}


def test_inheritance_is_transitive(repo):
    assert config.load_role_parents()["head-coach"] == ["coach"]
    assert config.permissions_for(["head-coach"]) == {"fees:roster:read"}


def test_inheritance_only_adds_and_never_flows_back_to_the_parent(repo):
    assert config.permissions_for(["student"]) == {"fees:self:read"}
    assert config.permissions_for(["faculty"]) == {"fees:roster:read"}


def test_a_cycle_terminates_and_grants_nothing_it_was_not_given(repo):
    assert config.expand_roles(["loop-a"]) == ["loop-a", "loop-b"]
    assert config.permissions_for(["loop-a"]) == set()


def test_expand_roles_lists_each_role_once_in_first_seen_order(repo):
    assert config.expand_roles(["athlete", "student", "head-coach"]) == [
        "athlete",
        "student",
        "head-coach",
        "coach",
        "faculty",
    ]
    assert config.expand_roles([]) == []
    assert config.expand_roles(["nobody"]) == ["nobody"]


def test_super_admin_holds_every_declared_platform_key_granted_or_not(repo):
    assert config.permissions_for([], super_admin=True) == {"platform:x", "platform:ungranted:read"}
    assert config.permissions_for(["athlete"], super_admin=True) == {
        "fees:self:read",
        "fees:athlete:extra",
        "platform:x",
        "platform:ungranted:read",
    }
    assert "platform:ungranted:read" not in config.permissions_for(["athlete"])


def test_module_roles_are_parents_of_the_layouts_role(repo):
    assert config.load_role_parents()["scholar"] == ["student", "fees-learner"]  # itself is dropped
    assert config.permissions_for(["scholar"]) == {"fees:self:read", "fees:learner:read"}


def test_module_roles_of_an_extended_layout_are_inherited_but_not_back(repo):
    assert config.permissions_for(["senior-scholar"]) == {"fees:self:read", "fees:learner:read", "fees:review:read"}
    assert config.permissions_for(["scholar"]) == {"fees:self:read", "fees:learner:read"}
    assert config.permissions_for(["athlete"]) == {"fees:self:read", "fees:athlete:extra"}


def test_module_roles_cycle_terminates(repo):
    assert config.expand_roles(["mod-a"]) == ["mod-a", "mod-b", "fees-learner"]
    assert config.permissions_for(["mod-a"]) == {"fees:learner:read"}


def test_a_missing_dashboards_folder_means_no_inheritance(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_root", lambda: tmp_path)
    config.load_role_parents.cache_clear()
    try:
        assert config.load_role_parents() == {}
    finally:
        config.load_role_parents.cache_clear()
