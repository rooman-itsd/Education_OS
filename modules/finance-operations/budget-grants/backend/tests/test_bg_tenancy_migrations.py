"""The cross-tenant leak test, the Alembic chain and drift between code and contract."""

import tempfile
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from bg_support import BASE, TODAY, approved_budget, grant, head
from eos_budget_grants.api.router import router
from eos_budget_grants.application.access import PERMISSION_KEYS
from eos_budget_grants.domain import rules
from eos_budget_grants.infrastructure.models import PREFIX, TABLES
from eos_testing import assert_no_cross_tenant_leak
from sqlalchemy import create_engine, inspect

MODULE = Path(__file__).resolve().parents[2]


def seed(client, org):
    h1, h2 = head(client, org), head(client, org)
    b = approved_budget(client, org, {h1["id"]: "1000", h2["id"]: "500"})
    src, dst = (x["id"] for x in b["lines"])
    client.post(
        f"{BASE}/expenditures",
        json={"line_id": src, "amount": "10", "date": TODAY, "description": "x"},
        headers=org.staff,
    )
    client.post(
        f"{BASE}/reappropriations",
        json={"from_line_id": src, "to_line_id": dst, "amount": "1", "reason": "x"},
        headers=org.staff,
    )
    return b, grant(client, org)


def test_no_cross_tenant_leak(client, org, other_org):
    budget_a, grant_a = seed(client, org)
    seed(client, other_org)
    for path, who in (
        ("/budget-heads", "staff"),
        ("/budgets", "staff"),
        ("/reappropriations", "staff"),
        ("/expenditures", "staff"),
        ("/grants", "research"),
        ("/me/grants", "scholar"),
    ):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", org.token(who), other_org.token(who))
    b = other_org.staff
    line_a = budget_a["lines"][0]["id"]
    assert client.get(f"{BASE}/budgets/{budget_a['id']}", headers=b).status_code == 404
    assert client.get(f"{BASE}/grants/{grant_a['id']}", headers=other_org.research).status_code == 404
    assert client.get(f"{BASE}/availability?line_id={line_a}&amount=1", headers=b).status_code == 404
    assert line_a not in {x["line_id"] for x in client.get(f"{BASE}/lines", headers=b).json()}
    r = client.post(
        f"{BASE}/expenditures", json={"line_id": line_a, "amount": "1", "date": TODAY, "description": "x"}, headers=b
    )
    assert r.status_code == 404


def _config(url: str) -> Config:
    cfg = Config(str(MODULE / "db" / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def test_migrations_match_the_models_and_downgrade():
    url = f"sqlite:///{tempfile.mkdtemp()}/migrations.db"  # a fresh throwaway file, never a real database
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        assert {t.name for t in TABLES} <= tables and f"{PREFIX}alembic_version" in tables
        for t in TABLES:
            assert "organisation_id" in {c["name"] for c in insp.get_columns(t.name)}
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: (
                    type_ != "table" or (name.startswith(PREFIX) and "alembic" not in name)
                ),
                "compare_type": True,
            },
        )
        assert [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)] == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert not [t for t in inspect(conn).get_table_names() if t.startswith(PREFIX) and "alembic" not in t]


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((MODULE / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))


def test_permission_keys_match_the_catalogue():
    catalogue = yaml.safe_load((MODULE / "contracts" / "permissions.yaml").read_text(encoding="utf-8"))
    assert set(PERMISSION_KEYS) == {p["key"] for p in catalogue["permissions"]}


def test_every_contract_operation_is_served_and_nothing_else(openapi):
    contract = {
        (method.upper(), path)
        for path, ops in openapi["paths"].items()
        for method in ops
        if method in ("get", "post", "put", "delete", "patch")
    }
    served = set()
    for route in router.routes:
        path = route.path
        for name in ("head_id", "budget_id", "reappropriation_id", "expenditure_id", "grant_id", "certificate_id"):
            path = path.replace("{" + name + "}", "{id}")
        served |= {(m, path) for m in route.methods}
    assert served == contract


def test_enums_match_the_contract(openapi):
    schemas = openapi["components"]["schemas"]
    assert list(rules.BUDGET_STATUSES) == schemas["BudgetStatus"]["enum"]
    assert list(rules.GRANT_STATUSES) == schemas["GrantStatus"]["enum"]
    assert list(rules.HEAD_KINDS) == schemas["BudgetHead"]["properties"]["kind"]["enum"]
    assert list(rules.UC_FREQUENCIES) == schemas["GrantInput"]["properties"]["uc_frequency"]["enum"]
    assert list(rules.UC_STATUSES) == schemas["UtilisationCertificate"]["properties"]["status"]["enum"]
    assert list(rules.EXPENDITURE_KINDS) == schemas["Expenditure"]["properties"]["kind"]["enum"]
