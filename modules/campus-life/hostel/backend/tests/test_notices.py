"""Notices and the Student widget's endpoint (docs/user-stories.md NO-1..NO-5, WI-1)."""

from datetime import UTC, datetime

from conftest import at, events
from eos_hostel.application import service
from eos_hostel.infrastructure.models import new_id


def test_publish_withdraw_and_expire(campus):
    c = campus
    body = {"hostel_id": c.hostel["id"], "title": "Water cut", "body": "No water 2-4 pm", "expires_at": at(20)}
    r = c.post("/notices", body, c.warden)
    assert r.status_code == 201 and r.json()["status"] == "current" and r.json()["published_by"] == c.warden_id
    notice = r.json()
    assert events("hostel.notice.published", c.org.id)[-1] == {
        "organisation_id": c.org.id,
        "notice_id": notice["id"],
        "hostel_id": c.hostel["id"],
        "title": "Water cut",
    }
    assert c.post("/notices", {**body, "title": "x" * 121}, c.warden).status_code == 422
    assert c.post("/notices", {**body, "expires_at": at(7)}, c.warden).status_code == 422  # already past
    assert c.post("/notices", {**body, "hostel_id": new_id()}, c.warden).status_code == 404  # no such hostel
    assert c.post("/notices", {**body, "hostel_id": "missing"}, c.warden).status_code == 422  # not a uuid

    r = c.post(f"/notices/{notice['id']}/withdraw", None, c.admin)
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert c.post(f"/notices/{notice['id']}/withdraw", None, c.admin).status_code == 409
    statuses = {n["id"]: n["status"] for n in c.get("/notices", c.warden).json()}
    assert statuses[notice["id"]] == "withdrawn"
    assert c.get("/notices", c.security).status_code == 403
    assert c.post("/notices", body, c.security).status_code == 403


def test_my_notices_show_my_hostel_and_everyone_newest_first(campus, monkeypatch):
    c = campus
    _, me, _ = c.resident()
    _, homeless = c.org.user("hostel-resident")
    other = c.post("/hostels", {"name": "South Block", "occupancy_type": "men"}, c.admin).json()

    def publish(minute: int, body: dict, headers: dict) -> dict:
        monkeypatch.setattr(service, "clock", lambda: datetime(2026, 10, 12, 8, minute, tzinfo=UTC))
        return c.post("/notices", {"body": "x", **body}, headers).json()

    everyone = publish(1, {"title": "Holiday", "hostel_id": None}, c.admin)
    mine = publish(2, {"title": "Ours", "hostel_id": c.hostel["id"]}, c.warden)
    publish(3, {"title": "Theirs", "hostel_id": other["id"]}, c.warden)
    expiring = publish(4, {"title": "Soon gone", "expires_at": at(9)}, c.warden)
    withdrawn = publish(5, {"title": "Oops"}, c.warden)
    c.post(f"/notices/{withdrawn['id']}/withdraw", None, c.warden)

    assert [n["id"] for n in c.get("/me/notices", me).json()] == [expiring["id"], mine["id"], everyone["id"]]
    assert [n["id"] for n in c.get("/me/notices", homeless).json()] == [expiring["id"], everyone["id"]]
    assert [n["id"] for n in c.get("/me/notices?limit=1", me).json()] == [expiring["id"]]

    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 10, 12, 10, 0, tzinfo=UTC))
    assert expiring["id"] not in [n["id"] for n in c.get("/me/notices", me).json()]
    assert c.get("/me/notices", c.viewer).status_code == 403
