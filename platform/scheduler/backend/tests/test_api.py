"""The scheduler API in contracts/openapi.yaml: who may schedule what, the cross-tenant leak test, run now and
the run history the super admin reads ("did the nightly job run?")."""

from __future__ import annotations

import pytest
from eos_scheduler.api.router import router
from eos_scheduler.application import jobs as jobs_module
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from scheduler_support import JOBS, Clock, Org, add_schedule, super_admin_headers, ticker

PREFIX = "/api/v1/scheduler"


@pytest.fixture(autouse=True)
def _jobs(monkeypatch):
    monkeypatch.setattr(jobs_module, "discover", lambda: dict(JOBS))


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def orgs():
    return Org(), Org()


def test_every_route_names_its_permission():
    for route in router.routes:
        assert isinstance(route, APIRoute)
        keys = {getattr(d.call, "permission", None) for d in route.dependant.dependencies} - {None}
        assert len(keys) == 1, route.path


def test_jobs_are_listed_read_only(client, orgs):
    a, _ = orgs
    body = client.get(f"{PREFIX}/jobs", params={"scope": "platform"}, headers=a.headers(a.admin)).json()
    assert [j["key"] for j in body["items"]] == ["billing.expire-trials"] and body["items"][0]["idempotent"]


def test_an_organisation_admin_schedules_their_own_work_in_their_own_timezone(client, orgs):
    a, _ = orgs
    r = client.post(
        f"{PREFIX}/schedules",
        json={"job": "fees.reminder-sweep", "cron": "0 9 * * 1", "timezone": "Asia/Kolkata"},
        headers=a.headers(a.admin),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["organisation_id"] == a.id and body["scope"] == "organisation" and body["next_run_at"]


@pytest.mark.parametrize(
    ("payload", "status", "words"),
    [
        ({"job": "billing.expire-trials", "cron": "0 0 * * *", "timezone": "UTC"}, 403, "platform job"),
        ({"job": "fees.unsafe", "cron": "0 0 * * *", "timezone": "UTC"}, 422, "idempotent"),
        ({"job": "nobody.declares-this", "cron": "0 0 * * *", "timezone": "UTC"}, 422, "no installed module"),
        ({"job": "fees.reminder-sweep", "cron": "0 0 * * *"}, 422, "timezone"),
        ({"job": "fees.reminder-sweep", "cron": "0 0 * *", "timezone": "UTC"}, 422, "five fields"),
        ({"job": "fees.reminder-sweep"}, 422, "exactly one"),
    ],
)
def test_a_schedule_that_cannot_run_properly_is_refused(client, orgs, payload, status, words):
    a, _ = orgs
    r = client.post(f"{PREFIX}/schedules", json=payload, headers=a.headers(a.admin))
    assert r.status_code == status and words in r.text, r.text


def test_another_organisations_schedules_and_runs_are_not_found(client, orgs):
    a, b = orgs
    theirs = add_schedule("fees.reminder-sweep", b.id)
    ticker(Clock()).tick()
    h = a.headers(a.admin)
    assert client.get(f"{PREFIX}/schedules/{theirs}", headers=h).status_code == 404
    assert client.patch(f"{PREFIX}/schedules/{theirs}", json={"enabled": False}, headers=h).status_code == 404
    assert client.post(f"{PREFIX}/schedules/{theirs}/run", headers=h).status_code == 404
    assert client.delete(f"{PREFIX}/schedules/{theirs}", headers=h).status_code == 404
    assert all(r["organisation_id"] == a.id for r in client.get(f"{PREFIX}/runs", headers=h).json()["items"])
    assert client.get(f"{PREFIX}/runs", params={"organisation_id": b.id}, headers=h).json()["total"] == 0


def test_a_member_has_no_access(client, orgs):
    a, _ = orgs
    assert client.get(f"{PREFIX}/schedules", headers=a.headers(a.member)).status_code == 403
    assert client.get(f"{PREFIX}/runs").status_code == 401


def test_the_super_admin_sees_platform_runs_and_runs_a_platform_job_now(client):
    sa = super_admin_headers()
    sid = add_schedule("billing.expire-trials", allow_overlap=False)
    r = client.post(f"{PREFIX}/schedules/{sid}/run", headers=sa)
    assert r.status_code == 202 and r.json()["trigger"] == "manual" and r.json()["status"] == "running"
    assert client.post(f"{PREFIX}/schedules/{sid}/run", headers=sa).status_code == 409  # still running
    history = client.get(f"{PREFIX}/runs", params={"job": "billing.expire-trials"}, headers=sa).json()
    assert history["total"] == 1 and history["items"][0]["organisation_id"] is None
    assert client.get(f"{PREFIX}/runs/{r.json()['id']}", headers=sa).status_code == 200


def test_retime_disable_and_delete(client, orgs):
    a, _ = orgs
    h = a.headers(a.admin)
    made = client.post(
        f"{PREFIX}/schedules", json={"job": "fees.reminder-sweep", "cron": "0 9 * * *", "timezone": "UTC"}, headers=h
    ).json()
    off = client.patch(f"{PREFIX}/schedules/{made['id']}", json={"enabled": False}, headers=h).json()
    assert off["enabled"] is False and off["next_run_at"] is None
    on = client.patch(
        f"{PREFIX}/schedules/{made['id']}", json={"enabled": True, "cron": "30 6 * * *"}, headers=h
    ).json()
    assert on["cron"] == "30 6 * * *" and on["next_run_at"].endswith("06:30:00+00:00")
    assert client.delete(f"{PREFIX}/schedules/{made['id']}", headers=h).status_code == 204
    assert client.get(f"{PREFIX}/schedules/{made['id']}", headers=h).status_code == 404
