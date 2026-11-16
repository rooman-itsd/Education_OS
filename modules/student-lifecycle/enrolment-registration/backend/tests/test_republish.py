"""POST /registrations/republish: the backfill for consumers that started after registrations were confirmed
(issue #325). Every registration that is confirmed now is announced again as `course-registration.confirmed`, so a
consumer that missed the original (examinations' candidates, timetable-attendance's section members) reaches the
current state, and one that has it is not disturbed.

The consumers at the end are reference implementations of the rules the events contract gives consumers, written
from the payloads alone (no other module is imported): one keeps a registration's facts, each applied once (as
timetable-attendance does), the other keeps a status ordered by occurred_at (as lms does)."""

from __future__ import annotations

import random
from datetime import date

import yaml
from conftest import (
    BASE,
    CONTRACTS,
    EXAM_STAFF,
    MANAGEMENT,
    NO_ACCESS,
    add_enrolment,
    add_window,
    headers,
    make_actor,
    seed,
)
from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_enrolment_registration.application import service as svc

CONFIRMED = "enrolment-registration.course-registration.confirmed"
WITHDRAWN = "enrolment-registration.course-registration.withdrawn"
MOVED = "enrolment-registration.section-allocation.changed"
PAYLOAD = {e["name"]: set(e["payload"]) for e in yaml.safe_load((CONTRACTS / "events.yaml").read_text())["events"]}


def outbox(db, org) -> list[OutboxEvent]:
    query = db.query(OutboxEvent).filter(OutboxEvent.organisation_id == org)
    return query.order_by(OutboxEvent.occurred_at, OutboxEvent.id).all()


def register(db, actor, enrolment, term, section=None) -> dict:
    return svc.register(
        db,
        actor,
        programme_enrolment_id=enrolment.id,
        course_offering_id=new_id(),
        section_id=section or new_id(),
        academic_period_id=term,
    )


def registrations(db, org) -> dict:
    """Two students: one with a registration that moved section, one withdrawn and one untouched."""
    staff, term = make_actor(org), new_id()
    add_window(db, org, term)
    ana, ben = add_enrolment(db, org, student_name="Ana"), add_enrolment(db, org, student_name="Ben")
    moved, kept, dropped = (
        register(db, staff, ana, term),
        register(db, staff, ben, term),
        register(db, staff, ana, term),
    )
    svc.change_section(db, staff, moved["id"], new_id(), date(2026, 11, 2))
    svc.withdraw_registration(db, staff, dropped["id"], "dropped")
    db.flush()
    return {"staff": staff, "moved": moved["id"], "kept": kept["id"], "dropped": dropped["id"]}


def current(db, actor) -> dict:
    """What a consumer should hold: each confirmed registration's student, offering and section, as listed now."""
    items = svc.list_registrations(db, actor, status="confirmed", page_size=200)["items"]
    return {r["id"]: (r["person_id"], r["course_offering_id"], r["section_id"]) for r in items}


def test_republish_announces_every_confirmed_registration_with_its_current_section(db, org):
    regs = registrations(db, org)
    originals = {e.payload["registration_id"]: e.payload for e in outbox(db, org) if e.name == CONFIRMED}
    before = {e.id for e in outbox(db, org)}
    caller = make_actor(org)

    assert svc.republish_registrations(db, caller) == 2

    new = [e for e in outbox(db, org) if e.id not in before]
    assert [e.name for e in new] == [CONFIRMED, CONFIRMED]
    assert {e.actor for e in new} == {caller.user_id}
    payloads = {e.payload["registration_id"]: e.payload for e in new}
    assert set(payloads) == {regs["moved"], regs["kept"]}  # the withdrawn one is not announced
    for payload in payloads.values():
        assert set(payload) == PAYLOAD[CONFIRMED]  # the same shape as the original
    assert payloads[regs["kept"]] == originals[regs["kept"]]
    moved_to = current(db, caller)[regs["moved"]][2]
    assert payloads[regs["moved"]] == {**originals[regs["moved"]], "section_id": moved_to}  # its current section
    assert moved_to != originals[regs["moved"]]["section_id"]


def test_republish_is_limited_to_the_callers_organisation(db, org, other_org):
    registrations(db, org)
    theirs = registrations(db, other_org)
    theirs_before = len(outbox(db, other_org))
    ours_before = len(outbox(db, org))

    assert svc.republish_registrations(db, make_actor(org)) == 2

    assert len(outbox(db, other_org)) == theirs_before
    new = outbox(db, org)[ours_before:]
    assert len(new) == 2 and all(e.organisation_id == org for e in new)
    assert not {theirs["moved"], theirs["kept"]} & {e.payload["registration_id"] for e in new}


def test_republish_changes_nothing_and_can_run_twice(db, org):
    regs = registrations(db, org)
    staff = regs["staff"]
    listed = svc.list_registrations(db, staff, page_size=200)
    assert svc.republish_registrations(db, staff) == svc.republish_registrations(db, staff) == 2
    assert svc.list_registrations(db, staff, page_size=200) == listed
    ids = [e.id for e in outbox(db, org)]
    assert len(ids) == len(set(ids))  # every republished event has its own envelope id


def test_an_organisation_without_registrations_publishes_nothing(db, org):
    assert svc.republish_registrations(db, make_actor(org)) == 0
    assert outbox(db, org) == []


def test_the_endpoint_counts_and_commits(client, org):
    term = new_id()
    seed(add_window, org, term)
    student = seed(add_enrolment, org)
    body = {
        "programme_enrolment_id": student.id,
        "course_offering_id": new_id(),
        "section_id": new_id(),
        "academic_period_id": term,
    }
    assert client.post(f"{BASE}/registrations", json=body, headers=headers(org)).status_code == 201

    res = client.post(f"{BASE}/registrations/republish", headers=headers(org))
    assert res.status_code == 200, res.text
    assert res.json() == {"published": 1}
    assert client.post(f"{BASE}/registrations/republish", headers=headers(org, "org-admin")).json() == {"published": 1}
    with SessionLocal() as db:
        assert [e.name for e in outbox(db, org)].count(CONFIRMED) == 3  # the original and two republished


def test_the_endpoint_needs_registration_manage(client, org):
    with SessionLocal() as db:
        before = len(outbox(db, org))
    for role in (EXAM_STAFF, MANAGEMENT, NO_ACCESS, "department-admin"):
        assert client.post(f"{BASE}/registrations/republish", headers=headers(org, role)).status_code == 403, role
    with SessionLocal() as db:
        assert len(outbox(db, org)) == before


# ---------------------------------------------------------------- consumers fed the republished events


class FactConsumer:
    """Keeps each registration's facts, each applied once and in any order: the confirmation (section, date), the
    section moves and the withdrawal. Its candidates are the registrations confirmed and not withdrawn, each in the
    section of its latest move, or of its confirmation."""

    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.rows: dict[str, dict] = {}

    def apply(self, event: OutboxEvent) -> str:
        if event.id in self.seen:
            return "duplicate"
        self.seen.add(event.id)
        p = event.payload
        row = self.rows.setdefault(p["registration_id"], {"moves": []})
        row.update(person=p["person_id"], offering=p["course_offering_id"])
        if event.name == CONFIRMED:
            if "section" in row:
                return "ignored"  # a registration is confirmed once
            row.update(section=p["section_id"], confirmed_at=p["confirmed_at"])
        elif event.name == MOVED:
            move = (p["effective_on"], p["from_section_id"], p["to_section_id"])
            if move in row["moves"]:
                return "ignored"
            row["moves"].append(move)
        elif event.name == WITHDRAWN:
            if row.get("withdrawn"):
                return "ignored"
            row["withdrawn"] = True
        else:
            return "ignored"
        return "applied"

    def feed(self, stream) -> list[str]:
        return [self.apply(e) for e in stream]

    def candidates(self) -> dict:
        out = {}
        for rid, row in self.rows.items():
            if "section" not in row or row.get("withdrawn"):
                continue
            section = max(row["moves"])[2] if row["moves"] else row["section"]
            out[rid] = (row["person"], row["offering"], section)
        return out


class StatusConsumer:
    """Keeps each registration's status and section, replaced only by an event that occurred at or after the one that
    set them."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def apply(self, event: OutboxEvent) -> None:
        p, at = event.payload, event.occurred_at.replace(tzinfo=None)
        row = self.rows.setdefault(p["registration_id"], {})
        if row.get("as_of") and at < row["as_of"]:
            return
        if event.name == CONFIRMED:
            row.update(status="active", section=p["section_id"], as_of=at)
        elif event.name == MOVED:
            row.update(status=row.get("status", "active"), section=p["to_section_id"], as_of=at)
        elif event.name == WITHDRAWN:
            row.update(status="withdrawn", as_of=at)

    def active(self) -> dict:
        return {rid: row["section"] for rid, row in self.rows.items() if row.get("status") == "active"}


def test_a_consumer_that_starts_late_finds_every_candidate_from_the_republish_alone(db, org):
    regs = registrations(db, org)
    before = {e.id for e in outbox(db, org)}
    svc.republish_registrations(db, regs["staff"])
    stream = [e for e in outbox(db, org) if e.id not in before]
    want = current(db, regs["staff"])
    assert set(want) == {regs["moved"], regs["kept"]}

    for order in (stream, list(reversed(stream)), random.Random(325).sample(stream, len(stream))):
        facts, status = FactConsumer(), StatusConsumer()
        assert set(facts.feed(order)) == {"applied"}
        for event in order:
            status.apply(event)
        assert facts.candidates() == want
        assert status.active() == {rid: section for rid, (_, _, section) in want.items()}
        assert set(facts.feed(order)) == {"duplicate"}  # a redelivery changes nothing


def test_a_consumer_that_has_the_originals_is_not_disturbed(db, org):
    regs = registrations(db, org)
    originals = outbox(db, org)
    facts, status = FactConsumer(), StatusConsumer()
    facts.feed(originals)
    for event in originals:
        status.apply(event)
    rows_before = {rid: dict(row, moves=list(row["moves"])) for rid, row in facts.rows.items()}

    svc.republish_registrations(db, regs["staff"])
    republished = outbox(db, org)[len(originals) :]
    assert set(facts.feed(republished)) == {"ignored"}
    for event in republished:
        status.apply(event)

    assert facts.rows == rows_before  # the original section and the move are kept
    want = current(db, regs["staff"])
    assert facts.candidates() == want
    assert status.active() == {rid: section for rid, (_, _, section) in want.items()}
    assert status.rows[regs["dropped"]]["status"] == "withdrawn"


def test_a_withdrawal_after_the_republish_is_not_undone_by_it(db, org):
    """The republished confirmation is stamped when it was published; a later withdrawal occurred later, so whichever
    arrives first, the consumer ends withdrawn."""
    regs = registrations(db, org)
    before = len(outbox(db, org))
    svc.republish_registrations(db, regs["staff"])
    svc.withdraw_registration(db, regs["staff"], regs["kept"], "left")
    later = outbox(db, org)[before:]
    assert [e.name for e in later] == [CONFIRMED, CONFIRMED, WITHDRAWN]

    facts, status = FactConsumer(), StatusConsumer()
    for event in reversed(later):  # the withdrawal first, then the older republish
        facts.apply(event)
        status.apply(event)
    assert regs["kept"] not in facts.candidates()
    assert status.rows[regs["kept"]]["status"] == "withdrawn"
    assert set(status.active()) == {regs["moved"]}
