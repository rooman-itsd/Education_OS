"""The event-bus entry point: enrolment-registration's three course-registration events reach the roster read model through
`application/consumers.py`. roster.py's own rules (once per envelope id, a withdrawal never undone by a late confirmation,
section capacity) are covered in test_roster.py; here it is the wiring: what is registered, and that a delivered `Event`
(the relay's detached envelope, not a dict) is applied."""

import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, make_course, make_offering, make_term, ok, open_offering  # noqa: E402
from eos_academic_management.application import consumers, roster  # noqa: E402
from eos_core.db import SessionLocal, new_id  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]
NAMES = {
    "enrolment-registration.course-registration.confirmed",
    "enrolment-registration.course-registration.withdrawn",
    "enrolment-registration.section-allocation.changed",
}


@dataclass
class Event:
    """The fields of eos_event_bus.domain.models.Event that a consumer reads."""

    name: str
    organisation_id: str | None
    payload: dict
    id: str = field(default_factory=new_id)
    version: int = 1
    actor: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime(2026, 10, 22, 9, 0, tzinfo=UTC))


def deliver(event: Event) -> str:
    with SessionLocal() as db:
        return consumers.CONSUMERS[event.name](db, event)


@pytest.fixture
def world(client, org):
    _, h = org.user("department-admin")
    _, admin = org.user("org-admin")
    term, course = make_term(client, admin), make_course(client, admin)
    o = make_offering(client, h, course["id"], term["id"], (("A", 2), ("B", 1)))
    teacher, _ = org.user("faculty")
    open_offering(client, h, o["id"], teacher)
    o = ok(client.get(f"{BASE}/offerings/{o['id']}", headers=h))
    a, b = o["sections"]
    return {"h": h, "o": o, "a": a, "b": b, "org": org}


def confirmed(w, **extra) -> dict:
    return {
        "registration_id": new_id(),
        "person_id": new_id(),
        "course_offering_id": w["o"]["id"],
        "section_id": w["a"]["id"],
        "academic_period_id": w["o"]["academic_period_id"],
        "registration_type": "regular",
        "student_name": "Asha Rao",
        "roll_number": "R-101",
        "confirmed_at": "2026-10-22T08:00:00+00:00",
        **extra,
    }


def roster_of(client, w) -> dict:
    return ok(client.get(f"{BASE}/offerings/{w['o']['id']}/roster", headers=w["h"]))


def test_the_entry_point_the_manifest_and_the_handlers_name_the_same_three_events():
    pyproject = tomllib.loads((MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    entry = pyproject["project"]["entry-points"]["eos.event_consumers"]
    assert entry == {"academic-management": "eos_academic_management.application.consumers:CONSUMERS"}
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text(encoding="utf-8"))
    assert set(manifest["consumes_events"]) == NAMES == set(consumers.CONSUMERS)


def test_a_delivered_confirmation_puts_the_learner_on_the_roster_and_a_repeat_changes_nothing(client, world):
    w = world
    p = confirmed(w)
    event = Event(roster.CONFIRMED, w["org"].id, p)
    assert deliver(event) == roster.APPLIED
    items = roster_of(client, w)["items"]
    assert [(i["person_id"], i["student_name"], i["roll_number"], i["section_code"]) for i in items] == [
        (p["person_id"], "Asha Rao", "R-101", "A")
    ]
    assert deliver(event) == roster.DUPLICATE  # the same envelope id again
    assert roster_of(client, w)["total"] == 1


def test_a_delivered_section_change_and_withdrawal_follow_the_registration(client, world):
    w = world
    p = confirmed(w)
    deliver(Event(roster.CONFIRMED, w["org"].id, p))
    move = {
        "registration_id": p["registration_id"],
        "person_id": p["person_id"],
        "course_offering_id": w["o"]["id"],
        "from_section_id": w["a"]["id"],
        "to_section_id": w["b"]["id"],
        "effective_on": "2026-10-25",
        "student_name": "Asha Rao",
    }
    assert deliver(Event(roster.SECTION_CHANGED, w["org"].id, move)) == roster.APPLIED
    assert [i["section_code"] for i in roster_of(client, w)["items"]] == ["B"]
    out = {k: p[k] for k in ("registration_id", "person_id", "course_offering_id")} | {
        "section_id": w["b"]["id"],
        "reason": "dropped",
        "withdrawn_at": "2026-10-30T00:00:00Z",
    }
    assert deliver(Event(roster.WITHDRAWN, w["org"].id, out)) == roster.APPLIED
    assert roster_of(client, w)["total"] == 0


def test_an_event_of_another_version_or_without_an_organisation_is_ignored(client, world):
    w = world
    p = confirmed(w)
    assert deliver(Event(roster.CONFIRMED, w["org"].id, p, version=2)) == roster.IGNORED
    assert deliver(Event(roster.CONFIRMED, None, p)) == roster.IGNORED
    assert roster_of(client, w)["total"] == 0


def test_another_organisations_event_does_not_reach_this_roster(client, world, other_org):
    w = world
    assert deliver(Event(roster.CONFIRMED, other_org.id, confirmed(w))) in (
        roster.REJECTED_UNKNOWN_SECTION,
        roster.IGNORED,
    )
    assert roster_of(client, w)["total"] == 0
