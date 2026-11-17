"""POST /offerings/republish: the backfill for consumers that started after offerings were created (issue #325).

Every offering and section of the caller's organisation is announced again with the normal events, so a consumer
that missed the originals reaches the current state, and one that has them is not disturbed. The consumer at the end
is a reference implementation of the rules contracts/events.yaml and the event-bus envelope give consumers (apply an
envelope id once, a creation once, a status by occurred_at); it imports no other module."""

import random
from datetime import datetime
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, make_course, make_offering, make_term, ok, open_offering  # noqa: E402
from eos_core.db import SessionLocal  # noqa: E402
from eos_core.events import OutboxEvent  # noqa: E402
from sqlalchemy import select  # noqa: E402

EVENTS = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts" / "events.yaml").read_text(encoding="utf-8"))
DECLARED = {e["name"]: e for e in EVENTS["events"]}
AM = "academic-management."
REPUBLISHED = {"offering.created", "offering.status-changed", "section.created", "section.updated"}


def events(organisation_id: str) -> list[OutboxEvent]:
    """The organisation's outbox rows, in the order they were written."""
    with SessionLocal() as db:
        query = select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)
        return list(db.scalars(query.order_by(OutboxEvent.occurred_at, OutboxEvent.id)))


def republish(client, h) -> dict:
    return ok(client.post(f"{BASE}/offerings/republish", headers=h))


def catalogue(client, org):
    """Two offerings: one open with an open and a closed section, renamed course; one planned with one section."""
    _, admin = org.user("org-admin")
    teacher, _ = org.user("faculty")
    term = make_term(client, admin)
    first, second = make_course(client, admin, "CS101"), make_course(client, admin, "CS102", credits=3)
    o1 = make_offering(client, admin, first["id"], term["id"], (("A", 30), ("B", 25)))
    open_offering(client, admin, o1["id"], teacher)
    closed = o1["sections"][1]["id"]
    ok(client.patch(f"{BASE}/sections/{closed}", json={"status": "closed"}, headers=admin))
    ok(client.patch(f"{BASE}/courses/{first['id']}", json={"title": "Algorithms"}, headers=admin))
    o2 = make_offering(client, admin, second["id"], term["id"])
    return admin, o1, o2


def test_republish_announces_every_offering_and_section_with_its_current_state(client, org):
    admin, o1, o2 = catalogue(client, org)
    before = {e.id: e for e in events(org.id)}

    caller, h = org.user("department-admin")  # offering:write, like org-admin
    assert republish(client, h) == {"offerings": 2, "sections": 3, "published": 10}

    new = [e for e in events(org.id) if e.id not in before]
    assert len(new) == 10
    assert all(e.name.startswith(AM) and e.name[len(AM) :] in REPUBLISHED for e in new)
    assert {e.actor for e in new} == {caller}
    for e in new:  # the payload of each is the declared one, field for field
        assert set(e.payload) == set(DECLARED[e.name]["payload"]), e.name

    created = {e.payload["course_offering_id"]: e.payload for e in new if e.name == f"{AM}offering.created"}
    originals = {
        e.payload["course_offering_id"]: e.payload for e in before.values() if e.name == f"{AM}offering.created"
    }
    assert created.keys() == originals.keys() == {o1["id"], o2["id"]}
    assert created[o2["id"]] == originals[o2["id"]]
    assert created[o1["id"]] == {**originals[o1["id"]], "course_title": "Algorithms"}  # the course as it is now

    statuses = {
        e.payload["course_offering_id"]: (e.payload["from_status"], e.payload["to_status"])
        for e in new
        if e.name == f"{AM}offering.status-changed"
    }
    assert statuses == {o1["id"]: ("open", "open"), o2["id"]: ("planned", "planned")}

    section_codes = {e.payload["section_id"]: e.payload["code"] for e in new if e.name == f"{AM}section.created"}
    sections = {
        e.payload["section_id"]: (e.payload["course_offering_id"], e.payload["capacity"], e.payload["status"])
        for e in new
        if e.name == f"{AM}section.updated"
    }
    a, b = o1["sections"]
    (c,) = o2["sections"]
    assert section_codes == {a["id"]: "A", b["id"]: "B", c["id"]: "A"}
    assert sections == {
        a["id"]: (o1["id"], 30, "open"),
        b["id"]: (o1["id"], 25, "closed"),
        c["id"]: (o2["id"], 2, "open"),
    }


def test_republish_changes_nothing_and_can_run_twice(client, org):
    admin, o1, o2 = catalogue(client, org)
    offerings = ok(client.get(f"{BASE}/offerings", headers=admin))
    first, second = republish(client, admin), republish(client, admin)
    assert first == second == {"offerings": 2, "sections": 3, "published": 10}
    assert ok(client.get(f"{BASE}/offerings", headers=admin)) == offerings
    ids = [e.id for e in events(org.id)]
    assert len(ids) == len(set(ids))  # every republished event has its own envelope id


def test_republish_is_limited_to_the_callers_organisation(client, org, other_org):
    catalogue(client, org)
    _, theirs = other_org.user("org-admin")
    term = make_term(client, theirs)
    make_offering(client, theirs, make_course(client, theirs)["id"], term["id"])
    theirs_before = len(events(other_org.id))
    ours_before = len(events(org.id))

    _, h = org.user("org-admin")
    assert republish(client, h) == {"offerings": 2, "sections": 3, "published": 10}

    assert len(events(other_org.id)) == theirs_before
    assert len(events(org.id)) == ours_before + 10
    assert republish(client, theirs) == {"offerings": 1, "sections": 1, "published": 4}


def test_an_organisation_without_offerings_publishes_nothing(client, org):
    _, h = org.user("org-admin")
    assert republish(client, h) == {"offerings": 0, "sections": 0, "published": 0}
    assert events(org.id) == []


@pytest.mark.parametrize("role", ["faculty", "student", "examination-staff"])
def test_republish_needs_offering_write(client, org, role):
    catalogue(client, org)
    count = len(events(org.id))
    _, h = org.user(role)
    r = client.post(f"{BASE}/offerings/republish", headers=h)
    assert r.status_code == 403
    assert len(events(org.id)) == count


def test_republish_needs_a_signed_in_caller(client):
    assert client.post(f"{BASE}/offerings/republish").status_code in (401, 403)


# ---------------------------------------------------------------- a consumer fed the republished events


def _instant(value: datetime) -> datetime:
    return value.replace(tzinfo=None)  # SQLite hands back naive UTC; compare like with like


class ReferenceConsumer:
    """The consumer rules of contracts/events.yaml and the event-bus envelope: an envelope id is applied once; a
    creation fills a row once and never overwrites what a later event set (an update may arrive first); a status is
    replaced only by an event that occurred at or after the one that set it."""

    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.offerings: dict[str, dict] = {}
        self.sections: dict[str, dict] = {}

    def apply(self, event: OutboxEvent) -> str:
        if event.id in self.seen:
            return "duplicate"
        self.seen.add(event.id)
        p, at, kind = event.payload, _instant(event.occurred_at), event.name[len(AM) :]
        if kind == "offering.created":
            row = self.offerings.setdefault(p["course_offering_id"], {})
            if "academic_period_id" in row:
                return "ignored"
            row.update(academic_period_id=p["academic_period_id"], code=p["course_code"], title=p["course_title"])
        elif kind == "offering.status-changed":
            row = self.offerings.setdefault(p["course_offering_id"], {})
            if row.get("status_as_of") and at < row["status_as_of"]:
                return "stale"
            row.update(status=p["to_status"], status_as_of=at)
        elif kind == "section.created":
            row = self.sections.setdefault(p["section_id"], {"offering": p["course_offering_id"]})
            if "code" in row:
                return "ignored"
            row["code"] = p["code"]
        elif kind == "section.updated":
            row = self.sections.setdefault(p["section_id"], {"offering": p["course_offering_id"]})
            if row.get("status_as_of") and at < row["status_as_of"]:
                return "stale"
            row.update(status=p["status"], capacity=p["capacity"], status_as_of=at)
        else:
            return "ignored"
        return "applied"

    def feed(self, stream) -> list[str]:
        return [self.apply(e) for e in stream]

    def state(self) -> tuple[dict, dict]:
        offerings = {k: {f: v for f, v in r.items() if f != "status_as_of"} for k, r in self.offerings.items()}
        sections = {k: {f: v for f, v in r.items() if f != "status_as_of"} for k, r in self.sections.items()}
        return offerings, sections


def expected(client, h) -> tuple[dict, dict]:
    """What a consumer should hold: the offerings and sections as the API returns them now."""
    offerings, sections = {}, {}
    for o in ok(client.get(f"{BASE}/offerings", headers=h))["items"]:
        offerings[o["id"]] = {
            "academic_period_id": o["academic_period_id"],
            "code": o["course"]["code"],
            "title": o["course"]["title"],
            "status": o["status"],
        }
        for s in o["sections"]:
            sections[s["id"]] = {
                "offering": o["id"],
                "code": s["code"],
                "status": s["status"],
                "capacity": s["capacity"],
            }
    return offerings, sections


def test_a_consumer_that_starts_late_reaches_the_current_state_from_the_republish_alone(client, org):
    admin, _, _ = catalogue(client, org)
    before = {e.id for e in events(org.id)}
    republish(client, admin)
    stream = [e for e in events(org.id) if e.id not in before]

    for order in (stream, list(reversed(stream)), random.Random(325).sample(stream, len(stream))):
        consumer = ReferenceConsumer()
        assert set(consumer.feed(order)) == {"applied"}
        assert consumer.state() == expected(client, admin)
        assert set(consumer.feed(order)) == {"duplicate"}  # a redelivery changes nothing


def test_a_consumer_that_has_the_originals_is_not_disturbed(client, org):
    admin, _, o2 = catalogue(client, org)
    consumer = ReferenceConsumer()
    consumer.feed(events(org.id))
    before_state = consumer.state()
    before = {e.id for e in events(org.id)}

    republish(client, admin)
    republish(client, admin)
    consumer.feed([e for e in events(org.id) if e.id not in before])

    after_state = consumer.state()
    created = ("academic_period_id", "code", "title")
    for key, row in before_state[0].items():  # creation facts are kept (the course rename is not re-applied)
        assert {f: after_state[0][key][f] for f in created} == {f: row[f] for f in created}
    assert {k: r["code"] for k, r in after_state[1].items()} == {k: r["code"] for k, r in before_state[1].items()}
    # Statuses are the current ones: the planned offering and the never-changed section now have theirs too.
    assert "status" not in before_state[0][o2["id"]] and "status" not in before_state[1][o2["sections"][0]["id"]]
    offerings, sections = expected(client, admin)
    assert {k: r["status"] for k, r in consumer.state()[0].items()} == {k: r["status"] for k, r in offerings.items()}
    assert {k: r["status"] for k, r in consumer.state()[1].items()} == {k: r["status"] for k, r in sections.items()}


def test_a_change_after_the_republish_is_not_overridden_by_it(client, org):
    """The republished status is stamped when it was published; a later change occurred later, so whichever arrives
    first, the consumer ends on the later change."""
    admin, o1, _ = catalogue(client, org)
    before = {e.id for e in events(org.id)}
    republish(client, admin)
    ok(client.post(f"{BASE}/offerings/{o1['id']}/status", json={"status": "in_progress"}, headers=admin))
    later = [e for e in events(org.id) if e.id not in before]

    consumer = ReferenceConsumer()
    consumer.feed(list(reversed(later)))  # the real change first, then the older republish
    assert consumer.offerings[o1["id"]]["status"] == "in_progress"
    assert consumer.state() == expected(client, admin)
