"""Reservations and holds, fines, the daily jobs, and fees-accounts.invoice.paid (docs/user-stories.md RE, FI, JO)."""

from datetime import timedelta

from conftest import NOW, events
from eos_core.db import SessionLocal
from eos_library.application import consumers, jobs


def test_reservation_queue_hold_and_collect(lib, tick):
    t, codes = lib.title(copies=1)
    borrower, _ = lib.student()
    lib.issue(codes[0], borrower)
    first_id, first = lib.student()
    second_id, second = lib.student()
    tick(1)
    r1 = lib.post("/me/reservations", {"title_id": t["id"]}, first)
    assert r1.status_code == 201 and r1.json()["position"] == 1 and r1.json()["status"] == "waiting"
    tick(2)
    r2 = lib.post("/me/reservations", {"title_id": t["id"]}, second).json()
    assert r2["position"] == 2
    assert events("library.reservation.placed", lib.org.id)[-1]["position"] == 2
    dup = lib.post("/me/reservations", {"title_id": t["id"]}, first)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "already_reserved"

    held = lib.give_back(codes[0]).json()["held_for_reservation"]
    assert held["person_id"] == first_id and held["status"] == "ready" and held["hold_expires_on"] == "2026-11-01"
    assert events("library.reservation.ready", lib.org.id)[-1]["copy_id"] == held["held_copy_id"]
    assert lib.get("/me/reservations", second).json()[0]["position"] == 1  # moved up the queue
    r = lib.issue(codes[0], second_id)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "held-for-other"
    assert lib.issue(codes[0], first_id).status_code == 201
    assert lib.get("/me/reservations", first).json() == []  # fulfilled


def test_cannot_reserve_an_available_title_or_as_a_non_member(lib):
    t, _ = lib.title(copies=1)
    _, member = lib.student()
    r = lib.post("/me/reservations", {"title_id": t["id"]}, member)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "copy_available"
    _, outsider = lib.org.user("student")
    assert lib.post("/me/reservations", {"title_id": t["id"]}, outsider).json()["detail"]["code"] == "not-a-member"


def test_cancelling_a_ready_hold_passes_the_copy_on(lib, tick):
    t, codes = lib.title(copies=1)
    borrower, _ = lib.student()
    lib.issue(codes[0], borrower)
    first_id, first = lib.student()
    second_id, second = lib.student()
    tick(1)
    r1 = lib.post("/me/reservations", {"title_id": t["id"]}, first).json()
    tick(2)
    lib.post("/me/reservations", {"title_id": t["id"]}, second)
    lib.give_back(codes[0])
    assert lib.post(f"/reservations/{r1['id']}/cancel", None, second).status_code == 404  # not hers
    r = lib.post(f"/reservations/{r1['id']}/cancel", None, first)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert lib.get("/me/reservations", second).json()[0]["status"] == "ready"
    assert lib.post(f"/reservations/{r1['id']}/cancel", None, first).status_code == 409


def test_daily_jobs_flag_overdue_once_and_expire_holds(lib, travel, tick):
    t, codes = lib.title(copies=1)
    borrower, _ = lib.student()
    loan = lib.issue(codes[0], borrower).json()
    first_id, first = lib.student()
    second_id, second = lib.student()
    tick(1)
    lib.post("/me/reservations", {"title_id": t["id"]}, first)
    tick(2)
    lib.post("/me/reservations", {"title_id": t["id"]}, second)
    travel(15)  # due 12 Nov; today 13 Nov
    with SessionLocal() as db:
        jobs.flag_overdue_loans(db)
        jobs.flag_overdue_loans(db)  # a second run the same day publishes nothing new
    flagged = [e for e in events("library.loan.overdue", lib.org.id) if e["loan_id"] == loan["id"]]
    assert len(flagged) == 1 and flagged[0]["due_on"] == "2026-11-12"
    lib.give_back(codes[0])  # held for the first member until 16 Nov
    travel(19)  # 17 Nov: the hold ran out
    with SessionLocal() as db:
        jobs.expire_holds(db)
    assert [e["person_id"] for e in events("library.reservation.expired", lib.org.id)] == [first_id]
    assert lib.get("/me/reservations", first).json() == []
    nxt = lib.get("/me/reservations", second).json()[0]
    assert nxt["status"] == "ready" and nxt["hold_expires_on"] == "2026-11-20"  # held from the day it moved on


def test_pay_and_waive_fines(lib, travel):
    _, codes = lib.title(copies=2)
    person_id, me = lib.student()
    lib.issue(codes[0], person_id)
    lib.issue(codes[1], person_id)
    travel(15)
    a = lib.give_back(codes[0]).json()["fine"]
    b = lib.give_back(codes[1]).json()["fine"]
    r = lib.post(f"/fines/{a['id']}/pay", {"receipt_ref": "DESK-0001"}, lib.librarian)
    assert r.status_code == 200 and r.json()["status"] == "paid" and r.json()["receipt_ref"] == "DESK-0001"
    assert events("library.fine.paid", lib.org.id)[-1]["receipt_ref"] == "DESK-0001"
    assert lib.post(f"/fines/{a['id']}/pay", {"receipt_ref": "x"}, lib.librarian).status_code == 409
    r = lib.post(f"/fines/{b['id']}/waive", {"reason": "First time"}, lib.librarian)
    assert r.status_code == 200 and r.json()["status"] == "waived" and r.json()["waive_reason"] == "First time"
    assert events("library.fine.waived", lib.org.id)[-1]["waived_by"] == lib.librarian_id
    assert lib.get("/me/fines", me).json() == {"fines": [], "total": "0.00"}
    assert lib.get("/fines?status=paid", lib.librarian).json()["items"][0]["id"] == a["id"]
    _, student = lib.student()
    assert lib.post(f"/fines/{b['id']}/waive", {"reason": "please"}, student).status_code == 403


def test_fees_accounts_invoice_paid_marks_the_fine_paid(lib, travel):
    _, codes = lib.title(copies=1)
    person_id, me = lib.student()
    lib.issue(codes[0], person_id)
    travel(15)
    fine = lib.give_back(codes[0]).json()["fine"]
    payload = {
        "organisation_id": lib.org.id,
        "invoice_id": "11111111-2222-3333-4444-555555555555",
        "person_id": person_id,
        "total": fine["amount"],
        "paid_at": (NOW + timedelta(days=15)).isoformat(),
        "source_module": "library",
        "source_reference": fine["id"],
    }
    with SessionLocal() as db:
        assert consumers.handle(db, "fees-accounts.invoice.paid", payload)["result"] == "applied"
        again = consumers.handle(db, "fees-accounts.invoice.paid", payload)
        assert again["result"] == "ignored" and "already paid" in again["reason"]  # idempotent
        other = consumers.handle(db, "fees-accounts.invoice.paid", {**payload, "source_module": "hostel"})
        assert other["result"] == "ignored"
        assert consumers.handle(db, "hostel.allocation.confirmed", payload)["result"] == "ignored"
        bad = consumers.handle(
            db, "fees-accounts.invoice.paid", {"organisation_id": lib.org.id, "source_module": "library"}
        )
        assert bad["result"] == "ignored" and "malformed" in bad["reason"]
    paid = lib.get(f"/fines?person_id={person_id}", lib.librarian).json()["items"][0]
    assert paid["status"] == "paid" and paid["receipt_ref"] == f"fees-accounts:{payload['invoice_id']}"
    assert lib.get("/me/fines", me).json()["total"] == "0.00"


def test_the_relay_finds_library_s_consumer():
    from importlib.metadata import entry_points

    from eos_library.application.consumers import CONSUMERS

    found = {e.name: e.value for e in entry_points(group="eos.event_consumers")}
    assert found.get("library") == "eos_library.application.consumers:CONSUMERS"
    assert set(CONSUMERS) == {"fees-accounts.invoice.paid"}
