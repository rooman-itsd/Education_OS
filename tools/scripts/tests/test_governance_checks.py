"""check-manifests.py and check-migrations.py accept good input and catch each kind of mistake."""

import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


manifests = load("check-manifests")
migrations = load("check-migrations")


# ---------- manifests ----------


def manifest(name: str, /, **over) -> dict:
    data = {
        "name": name,
        "kind": "feature",
        "domain": "academics",
        "tier": "common",
        "version": "0.1.0",
        "status": "planned",
        "description": "A module",
        "owners": ["srujanrooman"],
        "depends_on": {"platform": ["identity"], "integrations": []},
        "exposes": {
            "api": "contracts/openapi.yaml",
            "events": "contracts/events.yaml",
            "permissions": "contracts/permissions.yaml",
        },
        "consumes_events": [],
        "config": "config/env.example",
        "portable": False,
    }
    data.update(over)
    return data


def write(root: Path, rel: str, data: dict) -> Path:
    path = root / rel / "module.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path.parent


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "docs/team").mkdir(parents=True)
    (tmp_path / "docs/team/members.yaml").write_text(
        "members:\n  - { name: Srujan, handle: srujanrooman }\n", encoding="utf-8"
    )
    write(
        tmp_path,
        "platform/identity",
        manifest(
            "identity", kind="platform", domain="platform", tier="core", depends_on={"platform": [], "integrations": []}
        ),
    )
    write(
        tmp_path,
        "integrations/wearables",
        manifest(
            "wearables", kind="integration", domain="integrations", depends_on={"platform": [], "integrations": []}
        ),
    )
    write(tmp_path, "modules/_template", {"name": "__MODULE_NAME__"})
    return tmp_path


def test_valid_repo_passes(repo):
    write(repo, "modules/academics/lms", manifest("lms"))
    assert manifests.check(repo) == []


def test_template_is_ignored(repo):
    found = [p.relative_to(repo).as_posix() for p in manifests.manifests(repo)]
    assert found == ["integrations/wearables/module.yaml", "platform/identity/module.yaml"]


@pytest.mark.parametrize(
    ("over", "expected"),
    [
        ({"name": "lmss"}, "must be the folder name"),
        ({"kind": "platform"}, "kind `platform` must be `feature`"),
        ({"domain": "sports"}, "domain `sports` must be `academics`"),
        ({"status": "done"}, "status `done` must be one of"),
        ({"version": "1.0"}, "must look like 1.2.3"),
        ({"tier": "core"}, "tier `core` is for platform services"),
        ({"tier": "specialized"}, "declares its `field`"),
        ({"field": "music"}, "`field` is only for tier `specialized`"),
        ({"owners": ["nobody"]}, "owner `nobody` is not a handle"),
        ({"depends_on": {"platform": ["payments"], "integrations": []}}, "names `payments`"),
        ({"depends_on": {"platform": [], "integrations": ["sms"]}}, "names `sms`"),
        ({"depends_on": {"platform": []}}, "depends_on.integrations must be a list"),
        ({"portable": "yes"}, "`portable` must be a bool"),
        ({"description": " "}, "`description` must be a non-empty str"),
    ],
)
def test_each_mistake_is_caught(repo, over, expected):
    write(repo, "modules/academics/lms", manifest("lms", **over))
    problems = manifests.check(repo)
    assert any(expected in p for p in problems), problems
    assert all(p.startswith("modules/academics/lms/module.yaml") for p in problems)


def test_missing_key_is_caught(repo):
    data = manifest("lms")
    del data["exposes"]
    write(repo, "modules/academics/lms", data)
    assert any("missing `exposes`" in p for p in manifests.check(repo))


def test_specialized_with_field_passes(repo):
    write(repo, "modules/academics/lms", manifest("lms", tier="specialized", field="music"))
    assert manifests.check(repo) == []


def test_platform_must_be_core(repo):
    write(repo, "platform/audit", manifest("audit", kind="platform", domain="platform", tier="common"))
    assert any("platform service has tier `core`" in p for p in manifests.check(repo))


def test_contract_files_required_once_past_planned(repo):
    mod = write(repo, "modules/academics/lms", manifest("lms", status="in-progress"))
    problems = manifests.check(repo)
    assert any("exposes.api points to contracts/openapi.yaml" in p for p in problems)
    for rel in ("contracts/openapi.yaml", "contracts/events.yaml", "contracts/permissions.yaml", "config/env.example"):
        (mod / rel).parent.mkdir(parents=True, exist_ok=True)
        (mod / rel).write_text("x", encoding="utf-8")
    assert manifests.check(repo) == []


def test_invalid_yaml_is_reported(repo):
    path = repo / "modules/academics/lms/module.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("name: [unclosed", encoding="utf-8")
    assert any("not valid YAML" in p for p in manifests.check(repo))


def test_the_real_repository_passes():
    assert manifests.check(manifests.ROOT) == []


# ---------- migrations ----------

GOOD_PY = '''
def upgrade():
    op.create_table(
        "course",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        schema="lms",
    )
    op.execute("ALTER TABLE lms.course ENABLE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON lms.course
        USING (organisation_id::text = current_setting('app.organisation_id', true))""")
'''

GOOD_SQL = """
CREATE TABLE IF NOT EXISTS hostel.room (
  id uuid PRIMARY KEY,
  organisation_id uuid NOT NULL
);
ALTER TABLE hostel.room ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON hostel.room
  USING (organisation_id::text = current_setting('app.organisation_id', true));
"""


def mig(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_migrations_passes(tmp_path):
    assert migrations.check(tmp_path) == []


def test_good_alembic_and_sql_pass(tmp_path):
    mig(tmp_path, "modules/academics/lms/db/migrations/versions/0001_course.py", GOOD_PY)
    mig(tmp_path, "modules/campus-life/hostel/db/migrations/0001_room.sql", GOOD_SQL)
    assert migrations.check(tmp_path) == []


def test_missing_organisation_id_is_caught(tmp_path):
    mig(tmp_path, "platform/audit/db/migrations/0001.py", GOOD_PY.replace('"organisation_id"', '"tenant"'))
    problems = migrations.check(tmp_path)
    assert problems == ["platform/audit/db/migrations/0001.py: table `course` has no organisation_id column"]


def test_missing_rls_is_caught(tmp_path):
    text = GOOD_SQL.replace("ALTER TABLE hostel.room ENABLE ROW LEVEL SECURITY;", "")
    mig(tmp_path, "modules/campus-life/hostel/db/migrations/0001.sql", text)
    assert any("does not enable row level security" in p for p in migrations.check(tmp_path))


def test_policy_must_use_app_organisation_id(tmp_path):
    text = GOOD_SQL.replace("current_setting('app.organisation_id', true)", "'x'")
    mig(tmp_path, "modules/campus-life/hostel/db/migrations/0001.sql", text)
    assert any("no policy on app.organisation_id" in p for p in migrations.check(tmp_path))


def test_rls_on_another_table_does_not_count(tmp_path):
    text = GOOD_PY + '\n    op.create_table("lesson", sa.Column("organisation_id", sa.String(36)))\n'
    mig(tmp_path, "modules/academics/lms/db/migrations/0002.py", text)
    problems = migrations.check(tmp_path)
    assert any("`lesson` does not enable row level security" in p for p in problems)
    assert not any("`course`" in p for p in problems)


def test_rls_helper_call_counts(tmp_path):
    text = 'op.create_table("course", sa.Column("organisation_id", sa.String(36)))\nenable_rls(op, "course")\n'
    mig(tmp_path, "modules/academics/lms/db/migrations/0001.py", text)
    assert migrations.check(tmp_path) == []


def test_reviewed_exemption(tmp_path):
    text = '# rls-exempt: academy_type: reference data shared by every organisation\nop.create_table("academy_type", sa.Column("id", sa.String(36)))\n'
    mig(tmp_path, "platform/tenancy/db/migrations/0001.py", text)
    assert migrations.check(tmp_path) == []


def test_files_outside_migrations_are_ignored(tmp_path):
    mig(tmp_path, "modules/academics/lms/backend/src/models.py", 'op.create_table("x")')
    assert migrations.check(tmp_path) == []
