# packages/testing

Python package `eos_testing`: platform stubs, factories and the **cross-tenant leak check** that every
module's test suite runs (module standard rule 11).

```python
from eos_testing import register_and_login, assert_no_cross_tenant_leak

a = register_and_login(client, slug="alpha")
b = register_and_login(client, slug="beta", academy_type="music-academy")
assert_no_cross_tenant_leak(client, "/api/v1/identity/users", a["token"], b["token"])
```

## Platform stubs

In-memory fakes so a module's tests pass with only `packages/` available (module standard rule 6).
They are pytest fixtures, loaded automatically wherever `eos-testing` is installed; every test gets a
fresh one. Field names follow the platform contracts, so tests keep passing when the real services ship.

| Fixture | Stands in for | Checks |
|---|---|---|
| `fake_audit` | `platform/audit` recordAction | `assert_recorded(action=..., entity_id=...)`, `assert_not_recorded`, `history(type, id)` |
| `fake_notification` | `platform/notification` sendMessage and the `eos_core.notify` email stub | `assert_sent(template=..., to=...)`, `assert_not_sent`, `assert_emailed(to, subject_contains=...)` |
| `fake_events` | the event bus: captures every `eos_core.events.publish` | `assert_published(name, **payload)`, `assert_not_published` |
| `fake_scheduler` | `platform/scheduler` createSchedule and runScheduleNow | `assert_scheduled(job=...)`, `run_now(id, handler)` |

```python
def test_accept_application(client, fake_audit, fake_events, fake_notification):
    client.post(f"/api/v1/admissions/applications/{app_id}/accept", headers=auth(token))
    fake_events.assert_published("admissions.application.accepted", application_id=app_id)
    fake_audit.assert_recorded(action="application.accepted", entity_id=app_id)
    fake_notification.assert_sent(template="admissions.offer", to="student@example.com")
```

`fake_events` sees real publishes, because it listens for outbox rows on any session. Audit,
notification and scheduler have no SDK client yet; until `packages/sdk` ships, code that takes the
service as a parameter can be handed the fake directly.

### Signing in a fake user

`as_user` overrides the "who is calling" dependency your router uses, for the length of a `with` block,
so permission checks such as `require("lms.course.read")` see the fake user. Pass that dependency in,
because `packages/` may not import `platform/`.

```python
from eos_testing import as_user

# current_principal: the dependency your module's routers depend on

with as_user(app, current_principal, organisation_id=org_id, permissions={"lms.course.read"}):
    assert client.get("/api/v1/lms/courses").status_code == 200
```

Not stubbed yet: documents, search and workflow, which have no contract to follow.

## Tests

```
pytest packages/testing
```
