"""Per-organisation export and deletion with retention (DPDP). Runs with the module alone on SQLite."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from conftest import organisation
from eos_billing.application import service as billing
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_tenancy.application import service as tenancy
from eos_tenancy.application import tables
from eos_testing import assert_no_cross_tenant_leak
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

BASE = "/api/v1/tenancy/admin/organisations"


def upgrade_to_paid(organisation_id: str) -> None:
    with SessionLocal() as db:
        billing.upgrade(db, organisation_id=organisation_id, plan_id="standard")


def rows_left(organisation_id: str) -> dict[str, int]:
    """Rows of the organisation in every table that carries organisation_id, plus its own row."""
    with SessionLocal() as db, platform_scope():
        every = [tables.organisation_row_table(), *tables.organisation_tables(db)]
        return {t.name: n for t in every if (n := tables.count_rows(db, t, organisation_id))}


def login(client, org: dict):
    return client.post(
        "/api/v1/identity/auth/login",
        json={"email": org["email"], "password": org["password"], "organisation_slug": org["org"]["slug"]},
    )


def test_export_holds_the_organisation_and_only_its_rows(client, super_admin, fake_events):
    a = organisation(client, "export-a")
    b = organisation(client, "export-b", academy_type="law-college")
    upgrade_to_paid(a["org"]["id"])
    client.post(
        "/api/v1/identity/users",
        json={"email": "teacher@export-a.example.com", "name": "T", "password": "Passw0rd!x", "roles": ["teacher"]},
        headers=a["headers"],
    )
    with SessionLocal() as db, platform_scope():  # a document reference on the invoice, as billing will write
        from eos_billing.domain.models import Invoice

        db.execute(update(Invoice).where(Invoice.organisation_id == a["org"]["id"]).values(document_id="doc-inv-1"))
        db.commit()
    assert_no_cross_tenant_leak(client, "/api/v1/tenancy/organisation", a["token"], b["token"], id_field="id")

    r = client.get(f"{BASE}/{a['org']['id']}/export", headers=super_admin)
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].startswith('attachment; filename="export-a-export-')
    doc = r.json()
    assert doc["schema_version"] == 1 and doc["exported_at"] and doc["organisation"]["slug"] == "export-a"
    assert doc["tables"]["tenancy_organisation"][0]["id"] == a["org"]["id"]
    users = doc["tables"]["identity_user"]
    assert {u["email"] for u in users} == {"admin@export-a.example.com", "teacher@export-a.example.com"}
    assert all(u["password_hash"] == "[redacted]" for u in users)
    assert all(
        r["organisation_id"] == a["org"]["id"]
        for name, rows in doc["tables"].items()
        for r in rows
        if name != "tenancy_organisation"
    )
    invoice = doc["tables"]["billing_invoice"][0]
    assert invoice["status"] == "paid" and invoice["amount"] == "24999.00" and "T" in invoice["issued_at"]
    assert doc["tables"]["billing_subscription"][0]["plan_id"] == "standard"
    assert doc["row_counts"]["identity_user"] == 2 and doc["row_counts"]["billing_invoice"] == 1
    assert doc["files"]["references"] == [
        {"table": "billing_invoice", "row_id": invoice["id"], "column": "document_id", "document_id": "doc-inv-1"}
    ]
    assert "not built yet" in doc["files"]["note"]
    text = json.dumps(doc)
    assert b["org"]["id"] not in text and "export-b" not in text
    fake_events.assert_published("tenancy.organisation.exported", organisation_id=a["org"]["id"])
    ev = fake_events.find("tenancy.organisation.exported", organisation_id=a["org"]["id"])[-1]
    assert ev["actor"] and ev["payload"]["actor"] == ev["actor"]


def test_export_values_are_json_safe():
    moment = datetime(2026, 10, 29, 9, 30, tzinfo=UTC)
    from decimal import Decimal

    assert tables.json_safe(moment) == "2026-10-29T09:30:00+00:00"
    assert tables.json_safe(Decimal("12.50")) == "12.50"
    assert tables.json_safe(b"\x00\x01") == "AAE="
    assert tables.json_safe({"a": [moment, Decimal("1")]}) == {"a": ["2026-10-29T09:30:00+00:00", "1"]}


def test_organisation_admin_cannot_export_or_delete(client):
    a = organisation(client, "perm-a")
    url = f"{BASE}/{a['org']['id']}"
    assert client.get(f"{url}/export", headers=a["headers"]).status_code == 403
    assert client.request("DELETE", url, json={}, headers=a["headers"]).status_code == 403
    assert client.post(f"{url}/restore", headers=a["headers"]).status_code == 403
    assert client.post(f"{url}/purge", json={"force": True}, headers=a["headers"]).status_code == 403
    assert client.get(f"{url}/export").status_code == 401


def test_deletion_of_a_paying_organisation_needs_the_slug_and_blocks_login(client, super_admin, fake_events):
    a = organisation(client, "paying-a")
    upgrade_to_paid(a["org"]["id"])
    url = f"{BASE}/{a['org']['id']}"
    r = client.request("DELETE", url, json={"reason": "closing"}, headers=super_admin)
    assert r.status_code == 409 and "confirm_slug" in r.json()["detail"]
    r = client.request("DELETE", url, json={"reason": "closing", "confirm_slug": "wrong"}, headers=super_admin)
    assert r.status_code == 409
    assert login(client, a).status_code == 200  # nothing changed
    before = datetime.now(UTC)
    r = client.request("DELETE", url, json={"reason": "closing", "confirm_slug": "paying-a"}, headers=super_admin)
    assert r.status_code == 200, r.text
    org = r.json()
    assert org["status"] == "archived" and org["status_reason"] == "closing"
    delete_after = datetime.fromisoformat(org["delete_after"])
    assert timedelta(days=30) - timedelta(minutes=1) < delete_after - before < timedelta(days=30, minutes=1)
    assert org["deletion_requested_by"] and org["deletion_requested_at"]
    r = login(client, a)
    assert r.status_code == 401 and "archived" in r.json()["detail"]
    fake_events.assert_published("tenancy.organisation.deletion_requested", organisation_id=a["org"]["id"])
    fake_events.assert_published("tenancy.organisation.archived", organisation_id=a["org"]["id"])
    # asking twice is refused
    assert client.request("DELETE", url, json={"confirm_slug": "paying-a"}, headers=super_admin).status_code == 409


def test_trial_organisation_is_archived_without_confirmation_and_retention_is_configurable(
    client, super_admin, monkeypatch
):
    monkeypatch.setenv("EOS_ORGANISATION_RETENTION_DAYS", "7")
    a = organisation(client, "trial-a")
    r = client.request("DELETE", f"{BASE}/{a['org']['id']}", headers=super_admin)
    assert r.status_code == 200, r.text
    delete_after = datetime.fromisoformat(r.json()["delete_after"])
    assert abs((delete_after - datetime.now(UTC)) - timedelta(days=7)) < timedelta(minutes=1)


def test_restore_puts_the_organisation_back(client, super_admin, fake_events):
    a = organisation(client, "restore-a")
    url = f"{BASE}/{a['org']['id']}"
    assert client.post(f"{url}/restore", headers=super_admin).status_code == 409  # nothing pending
    assert client.request("DELETE", url, headers=super_admin).status_code == 200
    assert login(client, a).status_code == 401
    r = client.post(f"{url}/restore", headers=super_admin)
    assert r.status_code == 200, r.text
    org = r.json()
    assert org["status"] == "active" and org["delete_after"] is None and org["deletion_requested_by"] is None
    assert login(client, a).status_code == 200
    fake_events.assert_published("tenancy.organisation.restored", organisation_id=a["org"]["id"])
    fake_events.assert_published("tenancy.organisation.activated", organisation_id=a["org"]["id"])


def test_purge_waits_for_retention_then_removes_every_row(client, super_admin, monkeypatch, fake_events):
    a = organisation(client, "purge-a")
    b = organisation(client, "purge-b", academy_type="law-college")
    for org in (a, b):
        upgrade_to_paid(org["org"]["id"])
    url = f"{BASE}/{a['org']['id']}"
    assert client.post(f"{url}/purge", headers=super_admin).status_code == 409  # not requested
    r = client.request("DELETE", url, json={"confirm_slug": "purge-a"}, headers=super_admin)
    assert r.status_code == 200
    requested = r.json()
    r = client.post(f"{url}/purge", headers=super_admin)
    assert r.status_code == 409 and "retention runs until" in r.json()["detail"]
    left_a, left_b = rows_left(a["org"]["id"]), rows_left(b["org"]["id"])
    assert left_a["identity_user"] == 1 and left_a["billing_invoice"] == 1 and left_a["tenancy_organisation"] == 1

    monkeypatch.setattr(tenancy, "clock", lambda: datetime.now(UTC) + timedelta(days=31))
    r = client.post(f"{url}/purge", headers=super_admin)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["organisation_id"] == a["org"]["id"] and out["slug"] == "purge-a" and out["forced"] is False
    assert out["rows_deleted"]["identity_user"] == 1 and out["rows_deleted"]["billing_invoice"] == 1
    assert rows_left(a["org"]["id"]) == {}
    assert rows_left(b["org"]["id"]) == left_b
    assert client.get(url, headers=super_admin).status_code == 404
    assert login(client, b).status_code == 200
    ev = fake_events.assert_published("tenancy.organisation.purged", slug="purge-a")
    assert ev["organisation_id"] is None, "the tenant is gone: the record is the platform's"
    assert ev["payload"]["organisation_id"] == a["org"]["id"] and ev["payload"]["rows_deleted"] == out["rows_deleted"]
    assert ev["payload"]["requested_by"] and ev["payload"]["requested_at"] == requested["deletion_requested_at"]
    assert ev["payload"]["requested_by"] == requested["deletion_requested_by"]
    # the slug is free again
    assert organisation(client, "purge-a")["org"]["slug"] == "purge-a"


def test_force_purges_before_retention(client, super_admin):
    a = organisation(client, "force-a")
    url = f"{BASE}/{a['org']['id']}"
    assert client.request("DELETE", url, headers=super_admin).status_code == 200
    r = client.post(f"{url}/purge", json={"force": True}, headers=super_admin)
    assert r.status_code == 200 and r.json()["forced"] is True
    assert rows_left(a["org"]["id"]) == {}


def test_delete_rows_retries_tables_a_foreign_key_blocks(monkeypatch):
    """Children first by metadata order; a table that still fails is retried after the others, and a set that
    never unblocks is an error rather than a half-deleted organisation."""

    class Session:
        dialect = type("D", (), {"name": "sqlite"})()

        def __init__(self, fail_once: set[str], fail_always: set[str] = frozenset()):
            self.fail_once, self.fail_always, self.deleted = set(fail_once), set(fail_always), []

        def get_bind(self):
            return type("B", (), {"dialect": self.dialect})()

        def begin_nested(self):
            from contextlib import nullcontext

            return nullcontext()

        def execute(self, stmt):
            name = stmt.table.name
            if name in self.fail_always or name in self.fail_once:
                self.fail_once.discard(name)
                raise IntegrityError("delete", {}, Exception("fk"))
            self.deleted.append(name)
            return type("R", (), {"rowcount": 2})()

    parent, child = (tables.Base.metadata.tables[n] for n in ("billing_subscription", "billing_invoice"))
    db = Session(fail_once={parent.name})
    counts = tables.delete_rows(db, [parent, child], "org")
    assert db.deleted == [child.name, parent.name] and counts == {parent.name: 2, child.name: 2}
    with pytest.raises(RuntimeError, match="foreign keys block"):
        tables.delete_rows(Session(set(), fail_always={child.name}), [child], "org")


def test_tables_are_found_from_the_database_without_module_code(client):
    with SessionLocal() as db, platform_scope():
        names = [t.name for t in tables.organisation_tables(db)]
    assert {
        "identity_user",
        "billing_subscription",
        "billing_invoice",
        "tenancy_organisation_module",
        "outbox_event",
    } <= set(names)
    assert "tenancy_organisation" not in names and "billing_plan" not in names  # no organisation_id column
    with SessionLocal() as db, platform_scope():
        assert db.scalar(select(tables.organisation_row_table().c.id).limit(1)) is not None


def test_reflected_table_is_exported_and_purged_for_its_organisation_only(client, super_admin):
    """A table no model knows (created with SQL, with organisation_id and a foreign key to a tenant table) takes
    part through reflection: exported for the exported organisation only, purged for the purged one only."""
    from eos_identity.domain.models import User
    from sqlalchemy import text

    a = organisation(client, "raw-a")
    b = organisation(client, "raw-b", academy_type="law-college")
    with SessionLocal() as db, platform_scope():
        user = {
            o: db.scalar(select(User.id).where(User.organisation_id == o)) for o in (a["org"]["id"], b["org"]["id"])
        }
        db.execute(
            text(
                "CREATE TABLE raw_extra (id TEXT PRIMARY KEY, organisation_id TEXT NOT NULL, "
                "user_id TEXT REFERENCES identity_user(id), note TEXT, session_token TEXT)"
            )
        )
        for i, (o, uid) in enumerate(user.items()):
            db.execute(
                text("INSERT INTO raw_extra VALUES (:id, :o, :u, :n, :t)"),
                {"id": f"raw-{i}", "o": o, "u": uid, "n": f"note of {o}", "t": "s3cr3t"},
            )
        db.commit()
    try:
        r = client.get(f"{BASE}/{a['org']['id']}/export", headers=super_admin)
        assert r.status_code == 200, r.text
        rows = r.json()["tables"]["raw_extra"]
        assert [x["organisation_id"] for x in rows] == [a["org"]["id"]] and rows[0]["user_id"] == user[a["org"]["id"]]
        assert rows[0]["session_token"] == "[redacted]" and rows[0]["note"] == f"note of {a['org']['id']}"
        assert "raw-b" not in r.text and b["org"]["id"] not in r.text

        url = f"{BASE}/{a['org']['id']}"
        assert client.request("DELETE", url, headers=super_admin).status_code == 200
        r = client.post(f"{url}/purge", json={"force": True}, headers=super_admin)
        assert r.status_code == 200, r.text
        assert r.json()["rows_deleted"]["raw_extra"] == 1
        assert rows_left(a["org"]["id"]) == {}
        assert rows_left(b["org"]["id"])["raw_extra"] == 1
    finally:
        with SessionLocal() as db:
            db.execute(text("DROP TABLE raw_extra"))
            db.commit()


def test_redaction_covers_secret_like_suffixes():
    assert all(tables.is_redacted(c) for c in ("password_hash", "api_key", "reset_token", "otp_hash", "webhook_secret"))
    assert not any(tables.is_redacted(c) for c in ("email", "token_count", "hash_algorithm", "secretary"))


def test_a_blocked_purge_is_a_409_naming_the_table(monkeypatch):
    """The foreign-key error is not a 500: the purge is refused, rolled back, and says which table blocks."""
    org = type(
        "O",
        (),
        {
            "id": "o1",
            "slug": "s",
            "delete_after": datetime(2020, 1, 1, tzinfo=UTC),
            "deletion_requested_by": "u",
            "deletion_requested_at": datetime(2020, 1, 1, tzinfo=UTC),
        },
    )()

    class Session:
        rolled_back = False

        def rollback(self):
            self.rolled_back = True

    db = Session()
    monkeypatch.setattr(tenancy, "get_organisation", lambda *_: org)
    monkeypatch.setattr(tables, "organisation_tables", lambda _db: [])

    def blocked(*_):
        raise tables.PurgeBlockedError(["billing_invoice"])

    monkeypatch.setattr(tables, "delete_rows", blocked)
    with pytest.raises(tenancy.TenancyError, match="purge_blocked.*billing_invoice") as e:
        tenancy.purge_organisation(db, "o1", actor="a")
    assert e.value.status == 409 and db.rolled_back

    def refused(*_):
        raise IntegrityError("delete", {}, Exception("fk"))

    db.rolled_back = False
    monkeypatch.setattr(tables, "delete_rows", refused)
    with pytest.raises(tenancy.TenancyError, match="purge_blocked") as e:
        tenancy.purge_organisation(db, "o1", actor="a")
    assert e.value.status == 409 and db.rolled_back
