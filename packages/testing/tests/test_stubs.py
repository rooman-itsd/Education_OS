"""The fakes behave like the services they stand in for, and the plugin hands every test a fresh one."""

import pytest
from eos_testing import FakePrincipal, as_user
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_audit_records_and_finds(fake_audit):
    fake_audit.record(
        module="admissions",
        action="application.accepted",
        entity_type="application",
        entity_id="a1",
        organisation_id="org-1",
        after={"status": "accepted"},
    )
    rec = fake_audit.assert_recorded(action="application.accepted", entity_id="a1")
    assert rec["after"] == {"status": "accepted"}
    assert fake_audit.history("application", "a1") == [rec]
    fake_audit.assert_not_recorded(action="application.rejected")


def test_audit_client_token_is_idempotent(fake_audit):
    first = fake_audit.record(module="m", action="x.done", entity_type="x", entity_id="1", client_token="t")
    again = fake_audit.record(module="m", action="x.done", entity_type="x", entity_id="1", client_token="t")
    assert again is first
    assert len(fake_audit.records) == 1


def test_audit_failure_message_lists_what_was_recorded(fake_audit):
    fake_audit.record(module="lms", action="course.created", entity_type="course", entity_id="c1")
    with pytest.raises(AssertionError, match="course.created"):
        fake_audit.assert_recorded(action="course.deleted")


def test_notification_send_and_find_by_recipient(fake_notification):
    fake_notification.send(
        template="admissions.offer",
        recipient={"address": "student@example.com"},
        variables={"programme": "BSc"},
        client_token="offer-1",
    )
    fake_notification.send(
        template="admissions.offer", recipient={"address": "student@example.com"}, client_token="offer-1"
    )
    assert len(fake_notification.messages) == 1
    msg = fake_notification.assert_sent(template="admissions.offer", to="student@example.com")
    assert msg["variables"] == {"programme": "BSc"}
    fake_notification.assert_not_sent(template="admissions.offer", to="someone@example.com")


def test_notification_sees_only_emails_sent_during_the_test(fake_notification):
    from eos_core import notify

    notify.send_email("admin@alpha.example.com", "Verify your email", "body", token="abc")
    mail = fake_notification.assert_emailed("admin@alpha.example.com", subject_contains="Verify")
    assert mail["token"] == "abc"
    fake_notification.clear()
    assert fake_notification.emails == []


def test_events_capture_outbox_publish(fake_events):
    from eos_core.events import publish

    session = Session()
    publish(session, "admissions.application.accepted", "org-1", {"application_id": "a1"}, actor="u1")
    ev = fake_events.assert_published("admissions.application.accepted", application_id="a1")
    assert ev["organisation_id"] == "org-1"
    assert fake_events.find(organisation_id="org-2") == []
    fake_events.assert_not_published("admissions.application.rejected")
    session.close()


def test_events_stop_listening_after_the_test(fake_events):
    fake_events.stop()
    from eos_core.events import publish

    publish(Session(), "x.happened", "org-1", {})
    assert fake_events.published == []


def test_scheduler_schedule_run_and_cancel(fake_scheduler):
    sch = fake_scheduler.schedule(job="tenancy.trial-expiry", cron="0 2 * * *", organisation_id="org-1")
    fake_scheduler.assert_scheduled(job="tenancy.trial-expiry")
    ok = fake_scheduler.run_now(sch["id"], handler=lambda payload: "done")
    assert ok["status"] == "succeeded" and ok["result"] == "done"
    failed = fake_scheduler.run_now(sch["id"], handler=lambda payload: 1 / 0)
    assert failed["status"] == "failed" and "ZeroDivisionError" in failed["error"]
    fake_scheduler.cancel(sch["id"])
    with pytest.raises(AssertionError):
        fake_scheduler.assert_scheduled(job="tenancy.trial-expiry")


def test_scheduler_needs_a_time(fake_scheduler):
    with pytest.raises(AssertionError, match="cron or run_at"):
        fake_scheduler.schedule(job="x")


def test_each_test_gets_a_fresh_fake(fake_audit, fake_scheduler):
    assert fake_audit.records == []
    assert fake_scheduler.schedules == []


# as_user: a tiny app shaped like a real module router, with identity's dependency pattern.


def current_principal():
    raise HTTPException(401, "missing bearer token")


def require(permission: str):
    def dep(p=Depends(current_principal)):
        if not p.can(permission):
            raise HTTPException(403, f"requires {permission}")
        return p

    return dep


app = FastAPI()


@app.get("/courses")
def list_courses(p=Depends(require("lms.course.read"))):
    return {"organisation_id": p.organisation_id}


def test_as_user_grants_permissions_and_restores():
    client = TestClient(app)
    assert client.get("/courses").status_code == 401
    with as_user(app, current_principal, organisation_id="org-1", permissions={"lms.course.read"}):
        r = client.get("/courses")
        assert r.status_code == 200 and r.json() == {"organisation_id": "org-1"}
    assert client.get("/courses").status_code == 401


def test_as_user_without_permission_is_forbidden():
    client = TestClient(app)
    with as_user(app, current_principal, permissions={"lms.course.manage"}):
        assert client.get("/courses").status_code == 403


def test_as_user_super_admin_and_explicit_principal():
    client = TestClient(app)
    # A super admin gets no implicit grant, exactly like platform/identity's Principal.can.
    with as_user(app, current_principal, FakePrincipal(super_admin=True, organisation_id=None)):
        assert client.get("/courses").status_code == 403
    with as_user(
        app, current_principal, FakePrincipal(super_admin=True, organisation_id=None, permissions={"lms.course.read"})
    ):
        assert client.get("/courses").status_code == 200
    with pytest.raises(TypeError):
        with as_user(app, current_principal, FakePrincipal(), roles=["x"]):
            pass
