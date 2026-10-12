"""Platform stubs: in-memory stand-ins for audit, notification, the event bus, the scheduler and the
signed-in user, so a module's tests pass with only packages/ available (module standard rule 6).

Each fake records what it was asked to do and offers assert_* helpers. Field names follow the platform
contracts (platform/<service>/contracts/openapi.yaml) so a test written against a fake keeps passing
once the real service ships behind packages/sdk.

Nothing here touches the database or settings at import time; the pytest plugin builds the fakes per test.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


def _matches(item: dict, criteria: dict) -> bool:
    return all(item.get(k) == v for k, v in criteria.items())


def _describe(items: list[dict], keys: tuple[str, ...]) -> str:
    if not items:
        return "nothing"
    return ", ".join("{" + ", ".join(f"{k}={i.get(k)!r}" for k in keys if i.get(k) is not None) + "}" for i in items)


class FakeAudit:
    """platform/audit recordAction. Append-only; a repeated client_token returns the original record."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(
        self,
        *,
        module: str,
        action: str,
        entity_type: str,
        entity_id: str,
        organisation_id: str | None = None,
        actor: str | None = None,
        summary: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        context: dict | None = None,
        client_token: str | None = None,
    ) -> dict:
        if client_token is not None:
            for existing in self.records:
                if existing["client_token"] == client_token:
                    return existing
        rec = {
            "id": _new_id(),
            "module": module,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "organisation_id": organisation_id,
            "actor": actor,
            "summary": summary,
            "before": before,
            "after": after,
            "context": context or {},
            "client_token": client_token,
            "occurred_at": _now(),
        }
        self.records.append(rec)
        return rec

    def find(self, **criteria: Any) -> list[dict]:
        return [r for r in self.records if _matches(r, criteria)]

    def history(self, entity_type: str, entity_id: str) -> list[dict]:
        return self.find(entity_type=entity_type, entity_id=entity_id)

    def assert_recorded(self, **criteria: Any) -> dict:
        found = self.find(**criteria)
        assert found, (
            f"no audit record matching {criteria}; recorded: {_describe(self.records, ('module', 'action', 'entity_id'))}"
        )
        return found[-1]

    def assert_not_recorded(self, **criteria: Any) -> None:
        found = self.find(**criteria)
        assert not found, f"unexpected audit record matching {criteria}: {_describe(found, ('action', 'entity_id'))}"

    def clear(self) -> None:
        self.records.clear()


class FakeNotification:
    """platform/notification sendMessage, plus the eos_core.notify email stub the platform uses today.

    `messages` holds sendMessage calls; `emails` reads eos_core.notify.sent, so verification and approval
    mails sent by tenancy are visible too.
    """

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self._emails_before = 0

    def send(
        self,
        *,
        template: str,
        recipient: dict,
        variables: dict | None = None,
        channel: str | None = None,
        category: str = "operational",
        organisation_id: str | None = None,
        client_token: str | None = None,
    ) -> dict:
        if client_token is not None:
            for existing in self.messages:
                if existing["client_token"] == client_token:
                    return existing
        msg = {
            "id": _new_id(),
            "template": template,
            "recipient": dict(recipient),
            "variables": variables or {},
            "channel": channel,
            "category": category,
            "organisation_id": organisation_id,
            "client_token": client_token,
            "status": "sent",
            "sent_at": _now(),
        }
        self.messages.append(msg)
        return msg

    @property
    def emails(self) -> list[dict]:
        from eos_core import notify

        return notify.sent[self._emails_before :]

    def find(self, **criteria: Any) -> list[dict]:
        recipient = criteria.pop("to", None)
        found = [m for m in self.messages if _matches(m, criteria)]
        if recipient is not None:
            found = [m for m in found if recipient in (m["recipient"].get("address"), m["recipient"].get("user_id"))]
        return found

    def assert_sent(self, **criteria: Any) -> dict:
        found = self.find(**dict(criteria))
        assert found, f"no message matching {criteria}; sent: {_describe(self.messages, ('template', 'channel'))}"
        return found[-1]

    def assert_not_sent(self, **criteria: Any) -> None:
        found = self.find(**dict(criteria))
        assert not found, f"unexpected message matching {criteria}: {_describe(found, ('template',))}"

    def assert_emailed(self, to: str, subject_contains: str | None = None) -> dict:
        found = [e for e in self.emails if e.get("to") == to]
        if subject_contains is not None:
            found = [e for e in found if subject_contains in e.get("subject", "")]
        assert found, f"no email to {to!r}" + (f" with {subject_contains!r} in the subject" if subject_contains else "")
        return found[-1]

    def start(self) -> None:
        from eos_core import notify

        self._emails_before = len(notify.sent)

    def clear(self) -> None:
        self.messages.clear()
        self.start()


class FakeEvents:
    """Captures every event a module publishes through eos_core.events.publish (the transactional outbox).

    It listens for OutboxEvent rows being added to any SQLAlchemy session, so it works however the module
    imported publish and whether or not the transaction commits.
    """

    def __init__(self) -> None:
        self.published: list[dict] = []
        self._listening = False

    def _on_add(self, session, instance) -> None:
        from eos_core.events import OutboxEvent

        if isinstance(instance, OutboxEvent):
            self.published.append(
                {
                    "name": instance.name,
                    "organisation_id": instance.organisation_id,
                    "payload": dict(instance.payload or {}),
                    "actor": instance.actor,
                }
            )

    def start(self) -> None:
        from sqlalchemy import event
        from sqlalchemy.orm import Session

        if not self._listening:
            event.listen(Session, "transient_to_pending", self._on_add)
            self._listening = True

    def stop(self) -> None:
        from sqlalchemy import event
        from sqlalchemy.orm import Session

        if self._listening:
            event.remove(Session, "transient_to_pending", self._on_add)
            self._listening = False

    def record(self, name: str, organisation_id: str | None, payload: dict, actor: str | None = None) -> dict:
        """Publish without a database, for unit tests of code that takes a publisher as a parameter."""
        ev = {"name": name, "organisation_id": organisation_id, "payload": dict(payload), "actor": actor}
        self.published.append(ev)
        return ev

    def find(self, name: str | None = None, **payload: Any) -> list[dict]:
        found = self.published if name is None else [e for e in self.published if e["name"] == name]
        organisation_id = payload.pop("organisation_id", None)
        if organisation_id is not None:
            found = [e for e in found if e["organisation_id"] == organisation_id]
        return [e for e in found if _matches(e["payload"], payload)]

    def assert_published(self, name: str, **payload: Any) -> dict:
        found = self.find(name, **dict(payload))
        assert found, f"event {name!r} {payload or ''} not published; published: {[e['name'] for e in self.published]}"
        return found[-1]

    def assert_not_published(self, name: str, **payload: Any) -> None:
        assert not self.find(name, **dict(payload)), f"event {name!r} {payload or ''} was published"

    def clear(self) -> None:
        self.published.clear()


class FakeScheduler:
    """platform/scheduler createSchedule and runScheduleNow. Schedules never fire on their own; a test
    calls run_now (optionally with a handler) to simulate the run."""

    def __init__(self) -> None:
        self.schedules: list[dict] = []
        self.runs: list[dict] = []

    def schedule(
        self,
        *,
        job: str,
        organisation_id: str | None = None,
        cron: str | None = None,
        run_at: datetime | None = None,
        payload: dict | None = None,
        name: str | None = None,
    ) -> dict:
        assert cron or run_at, "a schedule needs cron or run_at"
        sch = {
            "id": _new_id(),
            "name": name or job,
            "job": job,
            "organisation_id": organisation_id,
            "cron": cron,
            "run_at": run_at,
            "payload": payload or {},
            "enabled": True,
        }
        self.schedules.append(sch)
        return sch

    def cancel(self, schedule_id: str) -> None:
        for s in self.schedules:
            if s["id"] == schedule_id:
                s["enabled"] = False
                return
        raise KeyError(schedule_id)

    def run_now(self, schedule_id: str, handler: Callable[[dict], Any] | None = None) -> dict:
        sch = next((s for s in self.schedules if s["id"] == schedule_id), None)
        if sch is None:
            raise KeyError(schedule_id)
        run = {"id": _new_id(), "schedule_id": schedule_id, "job": sch["job"], "status": "succeeded", "error": None}
        if handler is not None:
            try:
                run["result"] = handler(dict(sch["payload"]))
            except Exception as e:  # noqa: BLE001  a failed run is recorded, as the real scheduler does
                run["status"], run["error"] = "failed", repr(e)
        self.runs.append(run)
        return run

    def find(self, **criteria: Any) -> list[dict]:
        return [s for s in self.schedules if _matches(s, criteria)]

    def assert_scheduled(self, **criteria: Any) -> dict:
        found = [s for s in self.find(**criteria) if s["enabled"]]
        assert found, f"no active schedule matching {criteria}; scheduled: {_describe(self.schedules, ('job', 'cron'))}"
        return found[-1]

    def clear(self) -> None:
        self.schedules.clear()
        self.runs.clear()


@dataclass
class FakePrincipal:
    """Same shape as platform/identity's Principal, so routers that depend on it accept this one."""

    user_id: str = field(default_factory=_new_id)
    organisation_id: str | None = field(default_factory=_new_id)
    roles: list[str] = field(default_factory=list)
    super_admin: bool = False
    impersonated_by: str | None = None
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        # Same rule as platform/identity: a super admin is not granted every permission implicitly.
        return permission in self.permissions


@contextmanager
def as_user(
    app, dependency: Callable, principal: FakePrincipal | None = None, **fields: Any
) -> Iterator[FakePrincipal]:
    """Sign a fake user in for the duration of the block by overriding the identity dependency.

    `dependency` is the module's current_principal (passed in, because packages/ may not import platform/).
    Permission checks built on it, such as require("lms.course.manage"), then see this principal.

        with as_user(app, current_principal, permissions={"lms.course.read"}, organisation_id=org) as p:
            client.get("/api/v1/lms/courses")
    """
    if principal is None:
        if "permissions" in fields:
            fields["permissions"] = set(fields["permissions"])
        principal = FakePrincipal(**fields)
    elif fields:
        raise TypeError("pass either a principal or its fields, not both")
    previous = app.dependency_overrides.get(dependency)
    app.dependency_overrides[dependency] = lambda: principal
    try:
        yield principal
    finally:
        if previous is None:
            app.dependency_overrides.pop(dependency, None)
        else:
            app.dependency_overrides[dependency] = previous
