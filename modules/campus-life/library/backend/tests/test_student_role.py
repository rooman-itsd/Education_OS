"""A normal student holds only the profile role `student` (identity's default). The student layout lists
`library-member` in `module_roles`, so that role alone carries the library self-service keys. These tests use real
`student` tokens; `library-member` must keep working for members who are not students."""

from conftest import BASE
from eos_core.config import permissions_for
from eos_library.infrastructure.models import new_id

SELF = {"library:self:read", "library:self:borrow"}


def library_keys(roles: list[str]) -> set[str]:
    return {p for p in permissions_for(roles) if p.startswith("library:")}


def test_student_gets_exactly_the_self_service_keys():
    assert library_keys(["student"]) == SELF
    assert library_keys(["library-member"]) == SELF
    assert library_keys(["student", "library-member"]) == SELF
    assert library_keys(["org-admin"]) == set()
    assert library_keys(["applicant"]) == set()


def test_student_uses_self_service(lib):
    t, codes = lib.title(copies=1)
    person_id, me = lib.student()
    assert lib.get("/titles?q=gray", me).status_code == 200
    assert lib.get(f"/titles/{t['id']}", me).status_code == 200
    assert lib.get("/digital-resources", me).status_code == 200
    assert lib.get("/me/loans", me).json() == []
    assert lib.get("/me/reservations", me).json() == []
    assert lib.get("/me/fines", me).json() == {"fines": [], "total": "0.00"}
    loan = lib.issue(codes[0], person_id).json()
    assert lib.post(f"/loans/{loan['id']}/renew", None, me).status_code == 200
    other_title, _ = lib.title("Only copy is out", copies=1)
    holder, _ = lib.student()
    lib.issue(lib.get(f"/titles/{other_title['id']}", lib.viewer).json()["copies"][0]["barcode"], holder)
    r = lib.post("/me/reservations", {"title_id": other_title["id"]}, me)
    assert r.status_code == 201
    assert lib.post(f"/reservations/{r.json()['id']}/cancel", None, me).json()["status"] == "cancelled"


def test_student_cannot_touch_another_students_records(lib):
    t, codes = lib.title(copies=1)
    a_id, a = lib.student()
    b_id, b = lib.student()
    b_loan = lib.issue(codes[0], b_id).json()
    r = lib.post("/me/reservations", {"title_id": t["id"]}, a)
    assert lib.post(f"/loans/{b_loan['id']}/renew", None, a).status_code == 404
    assert lib.post(f"/reservations/{r.json()['id']}/cancel", None, b).status_code == 404
    assert lib.get("/me/loans", a).json() == []
    assert [x["id"] for x in lib.get("/me/loans", b).json()] == [b_loan["id"]]


def test_student_cannot_use_staff_operations(lib, client):
    _, codes = lib.title(copies=1)
    person_id, me = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    for path in ("/members", f"/members/{person_id}", "/loans", "/reservations", "/fines"):
        assert lib.get(path, me).status_code == 403, path
    posts = [
        ("/titles", {"title": "x", "kind": "book"}),
        ("/members", {"person_id": new_id(), "category": "student"}),
        ("/loans", {"barcode": codes[0], "person_id": person_id}),
        ("/returns", {"barcode": codes[0]}),
        (f"/loans/{loan['id']}/lost", {"replacement_amount": "1"}),
        ("/digital-resources", {"title": "x", "url": "https://x.example.com", "access": "open"}),
    ]
    for path, body in posts:
        assert lib.post(path, body, me).status_code == 403, path
    assert client.put(f"{BASE}/loan-policies", json=[], headers=me).status_code == 403
    assert lib.patch(f"/members/{person_id}", {"blocked": True, "reason": "self"}, me).status_code == 403
