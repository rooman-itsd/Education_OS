"""Catalogue, copies, digital resources, members and loan policies (docs/user-stories.md CA, ME, PO, DR)."""

from conftest import BASE, STUDENT_POLICY, events
from eos_library.infrastructure.models import new_id


def test_catalogue_titles_and_copies(lib):
    t, codes = lib.title(
        "Harrison's Principles", copies=2, isbn="9781264268504", authors=["J. Loscalzo"], subjects=["medicine"]
    )
    assert t["copies_total"] == 0 and t["organisation_id"] == lib.org.id  # counted before copies were added
    detail = lib.get(f"/titles/{t['id']}", lib.viewer).json()
    assert detail["copies_total"] == 2 and detail["copies_available"] == 2 and len(detail["copies"]) == 2
    dup = lib.post("/titles", {"title": "Again", "kind": "book", "isbn": "9781264268504"}, lib.librarian)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "isbn_exists"
    copy = lib.post(f"/titles/{t['id']}/copies", {"accession_no": "ACC-X", "barcode": codes[0]}, lib.librarian)
    assert copy.status_code == 409 and copy.json()["detail"]["code"] == "copy_exists"
    r = lib.patch(f"/titles/{t['id']}", {"publisher": "McGraw Hill"}, lib.librarian)
    assert (
        r.status_code == 200 and r.json()["publisher"] == "McGraw Hill" and r.json()["title"] == "Harrison's Principles"
    )


def test_search_and_available_filter(lib):
    lib.title("Robbins Pathology", copies=1, authors=["Kumar"], subjects=["pathology"])
    lib.title("Netter Atlas", copies=0, subjects=["anatomy"])
    titles = lambda q: [t["title"] for t in lib.get(f"/titles?{q}", lib.viewer).json()["items"]]  # noqa: E731
    assert titles("q=kumar") == ["Robbins Pathology"]
    assert titles("q=ANATOMY") == ["Netter Atlas"]
    assert "Netter Atlas" in titles("available=false") and "Netter Atlas" not in titles("available=true")
    page = lib.get("/titles?limit=1", lib.viewer).json()
    assert len(page["items"]) == 1 and page["next_cursor"]


def test_withdraw_and_restore_a_copy(lib):
    t, codes = lib.title(copies=1)
    copy_id = lib.get(f"/titles/{t['id']}", lib.viewer).json()["copies"][0]["id"]
    person_id, _ = lib.student()
    lib.issue(codes[0], person_id)
    r = lib.patch(f"/copies/{copy_id}", {"withdrawn": True, "reason": "Damaged"}, lib.librarian)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "copy_on_loan"
    lib.give_back(codes[0])
    assert (
        lib.patch(f"/copies/{copy_id}", {"withdrawn": True, "reason": "Damaged"}, lib.librarian).json()["status"]
        == "withdrawn"
    )
    assert lib.issue(codes[0], person_id).json()["detail"]["code"] == "copy-unavailable"
    r = lib.patch(f"/copies/{copy_id}", {"withdrawn": False, "location": "Shelf B2"}, lib.librarian)
    assert r.json()["status"] == "available" and r.json()["location"] == "Shelf B2"


def test_members_and_blocking(lib):
    person_id, _ = lib.student()
    again = lib.post("/members", {"person_id": person_id, "category": "student"}, lib.librarian)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "already_member"
    assert lib.post("/members", {"person_id": "not-a-uuid", "category": "student"}, lib.librarian).status_code == 422
    assert lib.patch(f"/members/{person_id}", {"blocked": True}, lib.librarian).status_code == 422  # reason needed
    r = lib.patch(f"/members/{person_id}", {"blocked": True, "reason": "Unreturned books"}, lib.librarian)
    assert r.status_code == 200 and r.json()["blocked"] is True
    assert events("library.member.blocked", lib.org.id)[-1] == {
        "organisation_id": lib.org.id,
        "person_id": person_id,
        "reason": "Unreturned books",
    }
    assert [m["person_id"] for m in lib.get("/members?blocked=true", lib.librarian).json()["items"]] == [person_id]
    detail = lib.get(f"/members/{person_id}", lib.librarian).json()
    assert detail["loans"] == [] and detail["open_fines_total"] == "0.00"
    assert lib.get(f"/members/{new_id()}", lib.librarian).status_code == 404
    assert lib.patch(f"/members/{person_id}", {"blocked": False}, lib.librarian).json()["block_reason"] is None


def test_loan_policies_replace_all(lib):
    staff = {**STUDENT_POLICY, "member_category": "faculty", "max_loans": 10, "fine_per_day": "0"}
    r = lib.client.put(f"{BASE}/loan-policies", json=[STUDENT_POLICY, staff], headers=lib.admin)
    assert r.status_code == 200 and [p["member_category"] for p in r.json()] == ["faculty", "student"]
    assert r.json()[0]["fine_per_day"] == "0.00"
    r = lib.client.put(f"{BASE}/loan-policies", json=[staff], headers=lib.admin)
    assert [p["member_category"] for p in r.json()] == ["faculty"]  # replaced, not merged
    assert lib.client.put(f"{BASE}/loan-policies", json=[staff, staff], headers=lib.admin).status_code == 422
    bad = {**staff, "fine_per_day": "1.234"}
    assert lib.client.put(f"{BASE}/loan-policies", json=[bad], headers=lib.admin).status_code == 422
    assert lib.client.put(f"{BASE}/loan-policies", json=[staff], headers=lib.librarian).status_code == 403
    assert lib.get("/loan-policies", lib.viewer).status_code == 200


def test_digital_resources(lib):
    body = {
        "title": "PubMed",
        "provider": "NLM",
        "kind": "database",
        "url": "https://pubmed.ncbi.nlm.nih.gov",
        "access": "open",
    }
    d = lib.post("/digital-resources", body, lib.librarian)
    assert d.status_code == 201 and d.json()["active"] is True
    old = lib.post(
        "/digital-resources", {**body, "title": "Old DB", "url": "https://old.example.com"}, lib.librarian
    ).json()
    lib.patch(f"/digital-resources/{old['id']}", {"active": False}, lib.librarian)
    assert lib.post("/digital-resources", {**body, "url": "ftp://x"}, lib.librarian).status_code == 422
    _, student = lib.student()
    assert [x["title"] for x in lib.get("/digital-resources", student).json()] == ["PubMed"]  # members: active only
    assert {x["title"] for x in lib.get("/digital-resources", lib.viewer).json()} == {"PubMed", "Old DB"}


def test_staff_permissions(lib):
    _, student = lib.student()
    for path in ("/members", "/loans", "/reservations", "/fines"):
        assert lib.get(path, student).status_code == 403, path
    assert lib.post("/titles", {"title": "x", "kind": "book"}, student).status_code == 403
    assert lib.post("/titles", {"title": "x", "kind": "book"}, lib.viewer).status_code == 403
    assert lib.get("/titles", lib.viewer).status_code == 200
    assert lib.get("/titles", {}).status_code == 401
