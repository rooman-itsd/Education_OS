"""Issue, return, renew and lost (docs/user-stories.md CI-1..CI-6), with the student's own views."""

from conftest import events
from eos_library.infrastructure.models import new_id


def test_issue_and_return_on_time(lib):
    t, codes = lib.title(copies=1)
    person_id, me = lib.student()
    r = lib.issue(codes[0], person_id)
    assert r.status_code == 201, r.text
    loan = r.json()
    assert loan["due_on"] == "2026-11-12" and loan["status"] == "active" and loan["renewals_left"] == 1
    assert loan["title"] == "Gray's Anatomy" and loan["overdue"] is False and loan["fine_accrued"] == "0.00"
    assert events("library.loan.issued", lib.org.id)[-1]["due_on"] == "2026-11-12"
    assert lib.get(f"/titles/{t['id']}", lib.viewer).json()["copies_available"] == 0
    assert [x["id"] for x in lib.get("/me/loans", me).json()] == [loan["id"]]

    back = lib.give_back(codes[0])
    assert back.status_code == 200
    body = back.json()
    assert body["loan"]["status"] == "returned" and body["fine"] is None and body["held_for_reservation"] is None
    assert events("library.loan.returned", lib.org.id)[-1]["days_late"] == 0
    assert lib.give_back(codes[0]).status_code == 409  # not on loan any more
    assert lib.get("/me/loans", me).json() == []


def test_issue_refusals(lib):
    _, codes = lib.title(copies=3)
    outsider, _ = lib.org.user("student")
    r = lib.issue(codes[0], outsider)
    assert r.status_code == 409 and r.json()["detail"] == {
        "code": "not-a-member",
        "message": "the person is not a library member",
    }
    person_id, _ = lib.student()
    lib.issue(codes[0], person_id)
    lib.issue(codes[1], person_id)
    assert lib.issue(codes[2], person_id).json()["detail"]["code"] == "loan-limit"
    other, _ = lib.student()
    assert lib.issue(codes[0], other).json()["detail"]["code"] == "copy-unavailable"
    lib.patch(f"/members/{other}", {"blocked": True, "reason": "Rules"}, lib.librarian)
    assert lib.issue(codes[2], other).json()["detail"]["code"] == "member-blocked"
    nobody_policy, _ = lib.student(category="faculty")  # no faculty policy exists
    assert lib.issue(codes[2], nobody_policy).json()["detail"]["code"] == "loan-limit"
    assert lib.issue("NO-SUCH-BARCODE", person_id).status_code == 404


def test_late_return_raises_an_exact_overdue_fine(lib, travel):
    _, codes = lib.title(copies=1)
    person_id, me = lib.student()
    lib.issue(codes[0], person_id)
    travel(17)  # due 12 Nov, back 15 Nov: 3 days late
    mine = lib.get("/me/loans", me).json()[0]
    assert mine["overdue"] is True and mine["fine_accrued"] == "6.00"
    body = lib.give_back(codes[0], damage_note="Cover torn").json()
    assert body["fine"]["amount"] == "6.00" and body["fine"]["reason"] == "overdue" and body["fine"]["status"] == "open"
    assert events("library.fine.raised", lib.org.id)[-1]["amount"] == "6.00"
    assert events("library.loan.returned", lib.org.id)[-1]["days_late"] == 3
    my = lib.get("/me/fines", me).json()
    assert my["total"] == "6.00" and len(my["fines"]) == 1


def test_unpaid_fines_over_the_limit_block_issue(lib, travel):
    _, codes = lib.title(copies=2)
    person_id, _ = lib.student()
    lib.issue(codes[0], person_id)
    travel(20)  # 6 days late at 2.00 = 12.00, over the 10.00 limit
    lib.give_back(codes[0])
    assert lib.issue(codes[1], person_id).json()["detail"]["code"] == "unpaid-fines"


def test_renew_own_loan(lib, travel):
    t, codes = lib.title(copies=1)
    person_id, me = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    travel(10)
    r = lib.post(f"/loans/{loan['id']}/renew", None, me)
    assert r.status_code == 200 and r.json()["renewals"] == 1 and r.json()["renewals_left"] == 0
    assert r.json()["due_on"] == "2026-11-22"  # 14 days from the renewal day, never earlier than before
    assert events("library.loan.renewed", lib.org.id)[-1]["renewals"] == 1
    again = lib.post(f"/loans/{loan['id']}/renew", None, me)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no-renewals-left"
    _, stranger = lib.student()
    assert lib.post(f"/loans/{loan['id']}/renew", None, stranger).status_code == 404


def test_cannot_renew_when_someone_is_waiting(lib):
    t, codes = lib.title(copies=1)
    person_id, _ = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    _, waiting = lib.student()
    assert lib.post("/me/reservations", {"title_id": t["id"]}, waiting).status_code == 201
    r = lib.post(f"/loans/{loan['id']}/renew", None, lib.librarian)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "title-reserved"


def test_renewing_late_keeps_the_fine(lib, travel):
    _, codes = lib.title(copies=1)
    person_id, me = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    travel(16)  # 2 days late
    r = lib.post(f"/loans/{loan['id']}/renew", None, me)
    assert r.status_code == 200 and r.json()["overdue"] is False
    assert lib.get("/me/fines", me).json()["total"] == "4.00"


def test_mark_lost_raises_a_replacement_fine(lib):
    t, codes = lib.title(copies=1)
    person_id, me = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    assert lib.post(f"/loans/{loan['id']}/lost", {"replacement_amount": "12.5"}, lib.librarian).status_code == 200
    assert lib.get(f"/titles/{t['id']}", lib.viewer).json()["copies"][0]["status"] == "lost"
    fines = lib.get("/me/fines", me).json()
    assert fines["total"] == "12.50" and fines["fines"][0]["reason"] == "lost"
    assert events("library.loan.lost", lib.org.id)[-1]["loan_id"] == loan["id"]
    assert lib.post(f"/loans/{loan['id']}/lost", {"replacement_amount": "1"}, lib.librarian).status_code == 409
    assert lib.post(f"/loans/{new_id()}/lost", {"replacement_amount": "1"}, lib.librarian).status_code == 404
    assert lib.post(f"/loans/{loan['id']}/lost", {"replacement_amount": "-1"}, lib.librarian).status_code == 422


def test_staff_loan_list(lib, travel):
    _, codes = lib.title(copies=2)
    a, _ = lib.student()
    b, _ = lib.student()
    lib.issue(codes[0], a)
    lib.issue(codes[1], b)
    travel(15)
    assert len(lib.get("/loans?overdue=true", lib.librarian).json()["items"]) == 2
    assert [x["person_id"] for x in lib.get(f"/loans?person_id={a}", lib.librarian).json()["items"]] == [a]
    assert lib.get("/loans?status=returned", lib.librarian).json()["items"] == []
