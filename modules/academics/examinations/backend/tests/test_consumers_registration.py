"""The registration consumers (`course-registration.confirmed` and `.withdrawn`, kept as `registration_ref`): the
fields they keep, repeats and the republish backfill, a withdrawal that arrives before its confirmation, a registration
type the module does not know, organisation isolation and malformed events. Delivered through the handlers as in
test_consumers.py, with payloads shaped as enrolment-registration publishes them."""

from datetime import timedelta
from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import NOW, uid  # noqa: E402
from eos_core.db import SessionLocal, init_db  # noqa: E402
from eos_core.tenant import organisation_scope  # noqa: E402
from eos_examinations.application.consumers import (  # noqa: E402
    APPLIED,
    DUPLICATE,
    IGNORED,
    REGISTRATION_CONFIRMED,
    REGISTRATION_WITHDRAWN,
)
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import ProcessedEvent, RegistrationRef  # noqa: E402
from test_consumers import deliver  # noqa: E402

MODULE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


def confirmed(registration_id=None, **over) -> dict:
    payload = {
        "registration_id": registration_id or uid(),
        "person_id": uid(),
        "course_offering_id": uid(),
        "section_id": uid(),
        "academic_period_id": uid(),
        "registration_type": "regular",
        "student_name": "Asha Rao",
        "roll_number": "R-101",
        "confirmed_at": "2026-11-05T08:00:00+00:00",
    }
    return {**payload, **over}


def withdrawn(of: dict, **over) -> dict:
    payload = {
        "registration_id": of["registration_id"],
        "person_id": of["person_id"],
        "course_offering_id": of["course_offering_id"],
        "section_id": of["section_id"],
        "reason": "dropped the course",
        "withdrawn_at": "2026-11-06T08:00:00+00:00",
    }
    return {**payload, **over}


def rows(org_id: str) -> list[RegistrationRef]:
    with organisation_scope(org_id), SessionLocal() as db:
        return list(db.scalars(repo.q(db, RegistrationRef)))


def row_of(org_id: str, registration_id: str) -> RegistrationRef:
    [row] = [r for r in rows(org_id) if r.registration_id == registration_id]
    return row


def test_the_contract_publishes_the_fields_the_handlers_read_to_examinations():
    contract = (
        MODULE.parents[2] / "modules" / "student-lifecycle" / "enrolment-registration" / "contracts" / "events.yaml"
    )
    if not contract.exists():
        pytest.skip("the enrolment-registration contract is not in this checkout")
    events = {e["name"]: e for e in yaml.safe_load(contract.read_text(encoding="utf-8"))["events"]}
    read = {
        REGISTRATION_CONFIRMED: {
            "registration_id",
            "person_id",
            "course_offering_id",
            "academic_period_id",
            "registration_type",
            "confirmed_at",
        },
        REGISTRATION_WITHDRAWN: {"registration_id", "person_id", "course_offering_id", "withdrawn_at"},
    }
    for name, fields in read.items():
        assert "examinations" in events[name]["consumers"], name
        assert fields <= set(events[name]["payload"]), (name, fields - set(events[name]["payload"]))


@pytest.mark.parametrize("kind", ["regular", "supplementary", "backlog"])
def test_a_confirmation_keeps_the_registration_with_its_type(org, kind):
    p = confirmed(registration_type=kind)
    assert deliver(org.id, REGISTRATION_CONFIRMED, p) == APPLIED
    row = row_of(org.id, p["registration_id"])
    assert (row.person_id, row.course_offering_id, row.academic_period_id) == (
        p["person_id"],
        p["course_offering_id"],
        p["academic_period_id"],
    )
    assert (row.registration_type, row.status) == (kind, "confirmed")
    assert row.confirmed_at is not None and row.withdrawn_at is None


def test_a_registration_type_the_module_does_not_know_is_refused_and_writes_nothing(org):
    with pytest.raises(ValueError, match="registration_type"):
        deliver(org.id, REGISTRATION_CONFIRMED, confirmed(registration_type="audit"))
    assert rows(org.id) == []
    with organisation_scope(org.id), SessionLocal() as db:  # the marker rolled back with the row
        assert list(db.scalars(repo.q(db, ProcessedEvent))) == []


def test_a_republished_confirmation_keeps_what_is_known(org):
    p = confirmed()
    deliver(org.id, REGISTRATION_CONFIRMED, p)
    backfill = {**p, "student_name": "Asha R. Rao", "section_id": uid()}  # a new envelope: the republish backfill
    assert deliver(org.id, REGISTRATION_CONFIRMED, backfill) == IGNORED
    assert len(rows(org.id)) == 1


def test_the_same_envelope_twice_applies_once(org):
    p = confirmed()
    first = deliver(org.id, REGISTRATION_CONFIRMED, p, event_id=uid())
    again = deliver(org.id, REGISTRATION_CONFIRMED, p, event_id="11111111-1111-4111-8111-111111111111")
    assert (first, again) == (APPLIED, IGNORED)
    envelope = uid()
    w = withdrawn(p)
    assert deliver(org.id, REGISTRATION_WITHDRAWN, w, event_id=envelope) == APPLIED
    assert deliver(org.id, REGISTRATION_WITHDRAWN, w, event_id=envelope) == DUPLICATE


def test_a_withdrawal_ends_the_registration_and_is_kept(org):
    p = confirmed()
    deliver(org.id, REGISTRATION_CONFIRMED, p)
    assert deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(p)) == APPLIED
    row = row_of(org.id, p["registration_id"])
    assert row.status == "withdrawn" and row.withdrawn_at is not None
    assert row.registration_type == "regular"  # the row stays, as enrolment-registration keeps withdrawn registrations
    assert deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(p)) == IGNORED  # another withdrawal event changes nothing


def test_a_confirmation_that_arrives_after_its_withdrawal_does_not_undo_it(org):
    p = confirmed(registration_type="backlog")
    assert deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(p)) == APPLIED  # delivery is unordered
    partial = row_of(org.id, p["registration_id"])
    assert (partial.status, partial.registration_type, partial.academic_period_id) == ("withdrawn", None, None)
    assert deliver(org.id, REGISTRATION_CONFIRMED, p, occurred_at=NOW - timedelta(days=1)) == APPLIED
    row = row_of(org.id, p["registration_id"])
    assert row.status == "withdrawn"  # the withdrawal stands
    assert (row.registration_type, row.academic_period_id) == (
        "backlog",
        p["academic_period_id"],
    )  # and the rest is filled


def test_each_registration_gets_its_own_row_and_each_organisation_its_own(org, other_org):
    a, b = confirmed(), confirmed()
    deliver(org.id, REGISTRATION_CONFIRMED, a)
    deliver(org.id, REGISTRATION_CONFIRMED, b)
    deliver(other_org.id, REGISTRATION_CONFIRMED, a)  # the same registration id in another organisation
    assert len(rows(org.id)) == 2 and len(rows(other_org.id)) == 1
    deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(a))
    assert (
        row_of(other_org.id, a["registration_id"]).status == "confirmed"
    )  # a withdrawal reaches only its own organisation


def test_an_event_for_an_unscoped_session_is_refused_not_written_elsewhere(org, other_org):
    from conftest import uid as new_id
    from eos_examinations.application.consumers import CONSUMERS
    from test_consumers import FakeEvent

    with organisation_scope(other_org.id), SessionLocal() as db:
        with pytest.raises(RuntimeError):
            CONSUMERS[REGISTRATION_CONFIRMED](db, FakeEvent(REGISTRATION_CONFIRMED, org.id, confirmed(new_id())))
    assert rows(org.id) == [] and rows(other_org.id) == []


@pytest.mark.parametrize(
    "change",
    [
        {"registration_id": None},
        {"person_id": "not-a-uuid"},
        {"course_offering_id": None},
        {"academic_period_id": None},
        {"registration_type": None},
        {"confirmed_at": "yesterday"},
    ],
)
def test_a_malformed_confirmation_is_refused_and_writes_nothing(org, change):
    p = {k: v for k, v in confirmed().items() if k not in change or change[k] is not None}
    p.update({k: v for k, v in change.items() if v is not None})
    with pytest.raises(ValueError):
        deliver(org.id, REGISTRATION_CONFIRMED, p)
    assert rows(org.id) == []


@pytest.mark.parametrize("change", [{"registration_id": None}, {"withdrawn_at": "yesterday"}, {"person_id": None}])
def test_a_malformed_withdrawal_is_refused_and_writes_nothing(org, change):
    w = withdrawn(confirmed())
    w = {k: v for k, v in w.items() if k not in change or change[k] is not None}
    w.update({k: v for k, v in change.items() if v is not None})
    with pytest.raises(ValueError):
        deliver(org.id, REGISTRATION_WITHDRAWN, w)
    assert rows(org.id) == []
