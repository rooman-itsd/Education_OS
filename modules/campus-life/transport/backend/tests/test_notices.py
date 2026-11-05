"""Notices and the Student widget's endpoint (docs/user-stories.md NO, WI-1)."""

from datetime import UTC, datetime

from conftest import at, events
from eos_transport.application import service
from eos_transport.infrastructure.models import new_id


def test_publish_withdraw_and_expire(campus):
    c = campus
    body = {
        "route_id": c.route["id"],
        "kind": "delay",
        "title": "Late today",
        "body": "15 min late",
        "expires_at": at(20),
    }
    r = c.post("/notices", body, c.admin)
    assert r.status_code == 201
    notice = r.json()
    assert notice["status"] == "current" and notice["route_code"] == "R1"
    assert events("transport.notice.published", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "notice_id": notice["id"],
        "route_id": c.route["id"],
        "kind": "delay",
        "title": "Late today",
    }
    assert c.post("/notices", {**body, "kind": "rumour"}, c.admin).status_code == 422
    assert c.post("/notices", {**body, "title": "x" * 121}, c.admin).status_code == 422
    assert c.post("/notices", {**body, "expires_at": at(7)}, c.admin).status_code == 422
    assert c.post("/notices", {**body, "route_id": new_id()}, c.admin).status_code == 404

    r = c.post(f"/notices/{notice['id']}/withdraw", None, c.admin)
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert c.post(f"/notices/{notice['id']}/withdraw", None, c.admin).status_code == 409
    assert {n["id"]: n["status"] for n in c.get("/notices", c.admin).json()}[notice["id"]] == "withdrawn"
    assert c.get("/notices", c.viewer).status_code == 403


def test_driver_publishes_only_to_own_route(campus):
    c = campus
    other = c.new_route("R2")
    body = {"kind": "delay", "title": "Puncture", "body": "Running late"}
    assert c.post("/notices", {**body, "route_id": c.route["id"]}, c.driver).status_code == 201
    assert c.post("/notices", {**body, "route_id": other["id"]}, c.driver).status_code == 403
    assert c.post("/notices", body, c.driver).status_code == 403  # all routes is for the office
    notice = c.get("/notices", c.admin).json()[0]
    assert c.post(f"/notices/{notice['id']}/withdraw", None, c.driver).status_code == 403


def test_my_notices_show_my_routes_and_all_routes_newest_first(campus, monkeypatch):
    c = campus
    _, me, _ = c.rider()
    _, no_pass = c.org.user("transport-rider")
    other = c.new_route("R2")

    def publish(minute: int, body: dict) -> dict:
        monkeypatch.setattr(service, "clock", lambda: datetime(2026, 10, 27, 8, minute, tzinfo=UTC))
        return c.post("/notices", {"kind": "general", "body": "x", **body}, c.admin).json()

    everyone = publish(1, {"title": "Holiday", "route_id": None})
    mine = publish(2, {"title": "Ours", "route_id": c.route["id"]})
    publish(3, {"title": "Theirs", "route_id": other["id"]})
    expiring = publish(4, {"title": "Soon gone", "expires_at": at(9)})
    withdrawn = publish(5, {"title": "Oops"})
    c.post(f"/notices/{withdrawn['id']}/withdraw", None, c.admin)

    assert [n["id"] for n in c.get("/me/notices", me).json()] == [expiring["id"], mine["id"], everyone["id"]]
    assert [n["id"] for n in c.get("/me/notices", no_pass).json()] == [expiring["id"], everyone["id"]]
    assert [n["id"] for n in c.get("/me/notices?limit=1", me).json()] == [expiring["id"]]
    assert c.get("/me/notices?limit=0", me).status_code == 422

    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 10, 27, 10, 0, tzinfo=UTC))
    assert expiring["id"] not in [n["id"] for n in c.get("/me/notices", me).json()]
    assert c.get("/me/notices", c.viewer).status_code == 403


def test_a_requested_pass_does_not_bring_route_notices(campus):
    c = campus
    _, me = c.org.user("transport-rider")
    c.post(
        "/me/passes",
        {"route_id": c.route["id"], "stop_id": c.stops[0]["id"], "valid_from": "2026-10-27", "valid_to": "2027-01-31"},
        me,
    )
    c.post("/notices", {"kind": "general", "title": "Ours", "body": "x", "route_id": c.route["id"]}, c.admin)
    assert c.get("/me/notices", me).json() == []
