"""A loan keeps the policy it was issued under; edge inputs answer 422 or 409, never a 500."""

import base64
from types import SimpleNamespace

from conftest import BASE, STUDENT_POLICY
from eos_core.db import SessionLocal
from eos_library.application import consumers
from eos_library.infrastructure import repository


def put_policies(lib, *policies):
    return lib.client.put(f"{BASE}/loan-policies", json=list(policies), headers=lib.admin)


def test_a_new_rate_applies_to_new_loans_not_to_a_loan_already_out(lib, travel):
    _, codes = lib.title(copies=2)
    person_id, me = lib.student()
    lib.issue(codes[0], person_id)
    assert put_policies(lib, {**STUDENT_POLICY, "fine_per_day": "20.00", "max_renewals": 0}).status_code == 200
    travel(24)  # due 12 Nov, back 22 Nov: 10 days late
    mine = lib.get("/me/loans", me).json()[0]
    assert mine["fine_accrued"] == "20.00" and mine["renewals_left"] == 1  # 2.00 a day, one renewal, as issued
    assert lib.give_back(codes[0]).json()["fine"]["amount"] == "20.00"
    lib.post(
        f"/fines/{lib.get(f'/fines?person_id={person_id}', lib.librarian).json()['items'][0]['id']}/waive",
        {"reason": "test"},
        lib.librarian,
    )
    later = lib.issue(codes[1], person_id).json()
    assert later["renewals_left"] == 0


def test_a_loan_still_raises_its_fine_when_the_category_loses_its_policy(lib, travel):
    _, codes = lib.title(copies=1)
    person_id, _ = lib.student()
    lib.issue(codes[0], person_id)
    staff = {**STUDENT_POLICY, "member_category": "staff"}
    assert put_policies(lib, staff).status_code == 200  # the student policy is gone
    travel(17)
    assert lib.give_back(codes[0]).json()["fine"]["amount"] == "6.00"


def test_a_renewal_takes_the_current_rate(lib, travel):
    _, codes = lib.title(copies=1)
    person_id, me = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    put_policies(lib, {**STUDENT_POLICY, "fine_per_day": "5.00"})
    travel(10)
    assert lib.post(f"/loans/{loan['id']}/renew", None, me).status_code == 200  # due 8 Nov + 14 = 22 Nov
    travel(28)  # 26 Nov: 4 days past the new due date
    assert lib.get("/me/loans", me).json()[0]["fine_accrued"] == "20.00"


def test_numbers_past_the_columns_are_refused(lib):
    huge = 2**63
    for key, value in (
        ("hold_days", 10_000_000),
        ("loan_days", 2_147_483_647),
        ("max_loans", huge),
        ("max_renewals", 101),
        ("hold_days", 61),
        ("loan_days", 366),
    ):
        assert put_policies(lib, {**STUDENT_POLICY, key: value}).status_code == 422, key
    for money in ("11111111111.00", "99999999999"):
        assert put_policies(lib, {**STUDENT_POLICY, "fine_per_day": money}).status_code == 422
    assert put_policies(lib, {**STUDENT_POLICY, "fine_per_day": "9999999999.99"}).status_code == 200
    assert lib.post("/titles", {"title": "Old", "kind": "book", "year": huge}, lib.librarian).status_code == 422
    t, _ = lib.title(copies=0)
    assert lib.patch(f"/titles/{t['id']}", {"year": 10000}, lib.librarian).status_code == 422
    assert lib.patch(f"/titles/{t['id']}", {"year": 1999}, lib.librarian).status_code == 200


def test_a_lost_book_too_dear_for_the_column_is_refused(lib):
    _, codes = lib.title(copies=1)
    person_id, _ = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    r = lib.post(f"/loans/{loan['id']}/lost", {"replacement_amount": "11111111111.00"}, lib.librarian)
    assert r.status_code == 422


def test_a_cursor_we_never_handed_out_starts_from_the_top(lib):
    lib.title(copies=1)
    lib.title("Second", copies=1)
    first = lib.get("/titles?limit=1", lib.viewer).json()
    for raw in (b"99999999999999999999", b"9223372036854775808", b"-1"):
        cursor = base64.urlsafe_b64encode(raw).decode()
        r = lib.get(f"/titles?limit=1&cursor={cursor}", lib.viewer)
        assert r.status_code == 200 and r.json() == first


def test_duplicates_that_slip_past_the_check_are_conflicts(lib, monkeypatch):
    """Two requests at once both pass the lookup; the unique constraint catches the second one."""
    t, codes = lib.title(copies=1)
    person_id, me = lib.student()
    monkeypatch.setattr(repository, "copy_by", lambda db, **kw: None)
    r = lib.post(f"/titles/{t['id']}/copies", {"accession_no": "ACC-X", "barcode": codes[0]}, lib.librarian)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "copy_exists"
    real_member = repository.member
    monkeypatch.setattr(repository, "member", lambda db, pid, org=None, lock=False: None)
    r = lib.post("/members", {"person_id": person_id, "category": "student"}, lib.librarian)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_member"
    monkeypatch.setattr(repository, "member", real_member)
    lib.issue(codes[0], person_id)  # no copy left, so the title can be reserved
    other_id, other = lib.student()
    assert lib.post("/me/reservations", {"title_id": t["id"]}, other).status_code == 201
    monkeypatch.setattr(repository, "active_reservation", lambda db, pid, tid: None)
    r = lib.post("/me/reservations", {"title_id": t["id"]}, other)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_reserved"
    assert len(lib.get("/me/reservations", other).json()) == 1


def test_the_consumer_scopes_by_the_envelope_and_ignores_odd_references(lib, travel):
    _, codes = lib.title(copies=1)
    person_id, _ = lib.student()
    lib.issue(codes[0], person_id)
    travel(15)
    fine = lib.give_back(codes[0]).json()["fine"]
    payload = {
        "invoice_id": "11111111-2222-3333-4444-555555555555",
        "source_module": "library",
        "source_reference": 12345,
    }
    with SessionLocal() as db:
        odd = consumers.handle(db, "fees-accounts.invoice.paid", payload, lib.org.id)
        assert odd["result"] == "ignored" and "strings" in odd["reason"]
        event = SimpleNamespace(
            name="fees-accounts.invoice.paid",
            organisation_id=lib.org.id,
            payload={**payload, "source_reference": fine["id"]},  # no organisation_id in the payload
        )
        consumers.CONSUMERS["fees-accounts.invoice.paid"](db, event)
    assert lib.get(f"/fines?person_id={person_id}", lib.librarian).json()["items"][0]["status"] == "paid"
