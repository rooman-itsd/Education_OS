"""The cross-tenant leak test, the super admin's overview, the Alembic chain against the models, and drift between the
code and contracts/ (routes, permissions, enums, error codes, event names and payloads, entry points)."""

import re
import tempfile
import tomllib
from pathlib import Path

import yaml
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_integration_hub.api.router import router
from eos_integration_hub.application import access, deliveries
from eos_integration_hub.application.invoke import invoke
from eos_integration_hub.domain import vocabulary
from eos_integration_hub.infrastructure.models import PREFIX, TABLES
from fastapi.routing import APIRoute
from hub_support import (
    BASE,
    authorised_meet,
    create,
    enabled_cert,
    link_account,
    put_credential,
    wear_connection,
)
from sqlalchemy import create_engine, inspect, select

MODULE = Path(__file__).resolve().parents[2]
BACKEND = MODULE / "backend"


def _contract(name: str) -> dict:
    return yaml.safe_load((MODULE / "contracts" / name).read_text(encoding="utf-8"))


def _ids(client, path: str, headers: dict) -> set[str]:
    r = client.get(f"{BASE}{path}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    return {row["id"] for row in (body["items"] if isinstance(body, dict) else body)}


def _seed(client, org, adapter):
    c = enabled_cert(client, org)
    meet = authorised_meet(client, org, adapter)
    wear_connection(client, org)
    link = link_account(client, org)
    r = invoke(
        port="certificate-issuance",
        operation="issue",
        input={"issuance_key": "k", "holder": {}},
        idempotency_key="exam:k",
        caller_module="examinations",
        organisation_id=org.id,
    )
    return c, meet, link, r["delivery_id"]


def test_no_cross_tenant_leak(client, org, other_org, adapter):
    a = _seed(client, org, adapter)
    _seed(client, other_org, adapter)
    for path in ("/connections", "/account-links", "/deliveries", "/me/account-links"):
        who = "member" if path.startswith("/me") else "admin"
        ids_a, ids_b = _ids(client, path, org.headers[who]), _ids(client, path, other_org.headers[who])
        assert ids_a and ids_b and not (ids_a & ids_b), path
    c_a, meet_a, link_a, delivery_a = a
    # reads across organisations are 404
    for path in (
        f"/connections/{c_a['id']}",
        f"/connections/{c_a['id']}/credentials",
        f"/connections/{c_a['id']}/health",
        f"/deliveries/{delivery_a}",
    ):
        r = client.get(f"{BASE}{path}", headers=other_org.admin)
        assert r.status_code == 404 and r.json()["code"] == "not_found", path
    # writes across organisations are 404 and change nothing
    attempts = [
        ("patch", f"/connections/{c_a['id']}", {"display_name": "stolen"}),
        ("put", f"/connections/{c_a['id']}/credentials/api_key", {"value": "stolen"}),
        ("delete", f"/connections/{c_a['id']}/credentials/api_key", None),
        ("post", f"/connections/{meet_a['id']}/authorise", {"return_url": "https://app.example.test/"}),
        ("post", f"/connections/{c_a['id']}/mode", {"mode": "mock"}),
        ("post", f"/connections/{c_a['id']}/enable", None),
        ("post", f"/connections/{c_a['id']}/disable", None),
        ("post", f"/connections/{c_a['id']}/health", None),
        ("post", f"/account-links/{link_a['id']}/revoke", {"reason": "stolen"}),
        ("post", f"/deliveries/{delivery_a}/retry", None),
    ]
    for method, path, body in attempts:
        r = client.request(method.upper(), f"{BASE}{path}", json=body, headers=other_org.admin)
        assert r.status_code == 404 and r.json()["code"] == "not_found", (path, r.text)
    r = client.delete(f"{BASE}/me/account-links/{link_a['id']}", headers=other_org.member)
    assert r.status_code == 404
    got = client.get(f"{BASE}/connections/{c_a['id']}", headers=org.admin).json()
    assert got["enabled"] is True and got["display_name"] is None
    assert client.get(f"{BASE}/me/account-links", headers=org.member).json()["items"][0]["status"] == "active"
    # a port call runs on the caller's organisation's connection only
    assert (
        invoke(
            port="certificate-issuance",
            operation="get_issuance",
            input={"issuance_key": "k"},
            idempotency_key="x:1",
            caller_module="examinations",
            organisation_id="00000000-0000-0000-0000-000000000000",
        )["error"]["code"]
        == "not_configured"
    )


def test_super_admin_overview_counts_without_organisation_data(
    client, org, other_org, adapter, super_admin, monkeypatch
):
    monkeypatch.delenv("FAKE_ADAPTER_APP_KEY")
    enabled_cert(client, org)
    enabled_cert(client, other_org)
    r = client.get(f"{BASE}/platform/overview", headers=super_admin.headers)
    assert r.status_code == 200
    rows = {(x["adapter"], x["provider"]): x for x in r.json()["items"]}
    cert = rows[("fake-adapter", "fakecert")]
    assert cert["connections_by_mode"]["sandbox"] >= 2 and cert["connections_by_health"]["healthy"] >= 2
    meet = rows[("fake-adapter", "fakemeet")]
    assert meet["platform_credentials_missing"] == ["FAKE_ADAPTER_APP_KEY"]
    assert rows[("fake-adapter", "fakewear")]["platform_credentials_missing"] == ["client_secret"]
    assert org.id not in r.text and other_org.id not in r.text
    assert client.get(f"{BASE}/platform/overview", headers=org.admin).status_code == 403
    # the super admin has no organisation: organisation routes refuse
    assert client.get(f"{BASE}/connections", headers=super_admin.headers).status_code == 403
    assert client.get(f"{BASE}/adapters", headers=super_admin.headers).status_code == 200


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
            assert t.name.startswith(PREFIX)
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


def test_permission_keys_match_the_catalogue():
    assert set(access.PERMISSION_KEYS) == {p["key"] for p in _contract("permissions.yaml")["permissions"]}


def test_every_contract_operation_is_served_with_its_permission_and_status():
    openapi = _contract("openapi.yaml")
    contract = {}
    for path, ops in openapi["paths"].items():
        for method, op in ops.items():
            if method in ("get", "post", "put", "delete", "patch"):
                contract[(method.upper(), path)] = op
    served = {}
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        perms = [d.call.permission for d in route.dependant.dependencies if hasattr(d.call, "permission")]
        for m in route.methods:
            served[(m, route.path)] = (perms, route.status_code or 200)
    assert set(served) == set(contract)
    for key, (perms, status) in served.items():
        op = contract[key]
        named = re.findall(
            r"Permission (platform:integration-hub:[a-z-]+|integration-hub:[a-z-]+:[a-z-]+)",
            " ".join(op["summary"].split()),
        )
        if op.get("security") == []:
            assert perms == [] and named == [], key  # public by necessity
        elif key == ("POST", "/connections/{id}/mode"):
            # go-live to go live, manage otherwise: the guard admits either and the handler checks the exact key
            assert named == [access.CONNECTION_GO_LIVE] and perms == [access.CONNECTION_MANAGE], (key, named)
        else:
            assert perms == named, (key, perms, named)
        success = sorted(int(c) for c in op["responses"] if str(c)[0] in "23")
        assert status in success, (key, success, status)


def test_enums_match_the_contract():
    schemas = _contract("openapi.yaml")["components"]["schemas"]
    assert list(vocabulary.PORTS) == schemas["PortId"]["enum"]
    assert list(vocabulary.MODES) == schemas["Mode"]["enum"]
    assert list(vocabulary.HEALTH_STATUSES) == schemas["HealthStatus"]["enum"]
    assert list(vocabulary.LINK_STATUSES) == schemas["LinkStatus"]["enum"]
    assert list(vocabulary.DELIVERY_STATUSES) == schemas["DeliveryStatus"]["enum"]
    provider = schemas["Adapter"]["properties"]["providers"]["items"]["properties"]
    assert list(vocabulary.AUTH_KINDS) == provider["auth"]["enum"]
    assert list(vocabulary.LINK_SCOPES) == provider["link_scope"]["enum"]
    adapter = yaml.safe_load((MODULE / "contracts" / "ports" / "adapter.yaml").read_text(encoding="utf-8"))
    assert vocabulary.ERROR_CODES == {k: v["retryable"] for k, v in adapter["error_codes"].items()}
    assert adapter["registration"]["entry_point_group"] == "eos.integration_adapters"


# Codes the backend may answer that the draft contract does not list yet; each is named in the PR as a deviation.
EXTRA_CODES = {"secret_store_unavailable", "too_many_requests", "invalid_status", "provider_error"}


def test_every_error_code_the_backend_raises_is_in_the_contract():
    src = BACKEND / "src" / "eos_integration_hub"
    code = "\n".join(p.read_text(encoding="utf-8") for p in src.rglob("*.py"))
    codes = set(re.findall(r'HubError\(\s*\d+,\s*"([a-z_]+)"', code))
    contract = (MODULE / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    missing = sorted(c for c in codes - EXTRA_CODES if c not in contract)
    assert missing == [], missing
    assert EXTRA_CODES <= codes


def test_every_published_event_is_in_events_yaml_with_its_payload(client, org, adapter):
    """Run one of everything, then compare every integration-hub.* event in the outbox with events.yaml."""
    declared = {e["name"]: e for e in _contract("events.yaml")["events"]}
    from test_hub_inbound import test_a_signed_webhook_is_acknowledged_then_processed_into_port_events as webhook

    webhook(client, org, adapter)
    c = enabled_cert(client, org)
    put_credential(client, org, c["id"], "api_key", "rotated")
    client.post(f"{BASE}/connections/{c['id']}/disable", headers=org.admin)
    create(client, org, display_name="x")
    deliveries.process_due()
    with SessionLocal() as db, platform_scope():
        published = list(db.scalars(select(OutboxEvent).where(OutboxEvent.name.like("integration-hub.%"))))
    assert len({e.name for e in published}) >= 8
    for ev in published:
        assert ev.name in declared, ev.name
        keys = set(declared[ev.name]["payload"])
        assert set(ev.payload) == keys, (ev.name, set(ev.payload) ^ keys)
        text = str(ev.payload)
        for value in (
            "@",
            "meet-client-secret",
            "cert-api-key-value",
            "cert-webhook-secret",
            "rt-secret-value",
            "at-good-code",
            "rotated",
            "Riya",
        ):
            assert value not in text, (ev.name, value)


def test_entry_points_are_declared():
    project = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    points = project["entry-points"]
    assert points["eos.integration_hub"]["invoke"] == "eos_integration_hub.application.invoke:invoke"
    assert points["eos.scheduler_jobs"]["integration-hub"] == "eos_integration_hub.application.jobs:JOBS"
    assert points["eos.event_consumers"]["integration-hub"] == "eos_integration_hub.application.consumers:CONSUMERS"
    assert "eos-sdk" not in project["dependencies"]  # not installable yet


def test_scheduled_jobs_report_back_to_the_scheduler(client):
    from eos_integration_hub.application import consumers
    from eos_integration_hub.application.jobs import JOBS

    assert set(JOBS) == set(consumers.RUNS) and all(k.startswith("integration-hub.") for k in JOBS)
    event = type("E", (), {"payload": {"job": "integration-hub.purge", "run_id": "r-1"}, "organisation_id": None})()
    with SessionLocal() as db, platform_scope():
        future = consumers.on_job_due(db, event)
        db.commit()
    future.result(timeout=30)  # the job runs in the hub's worker, not in the relay's session
    with SessionLocal() as db, platform_scope():
        done = [
            e
            for e in db.scalars(select(OutboxEvent).where(OutboxEvent.name == "integration-hub.job.finished"))
            if e.payload["run_id"] == "r-1"
        ]
    assert len(done) == 1 and done[0].payload["outcome"] == "succeeded"
    declared = {e["name"] for e in _contract("events.yaml")["events"]}
    assert "integration-hub.job.finished" in declared
