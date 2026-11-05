"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Library
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org, travel) -> tuple[Library, dict]:
    lib = Library(client, org)
    t, codes = lib.title(copies=2)
    person_id, me = lib.student()
    loan = lib.issue(codes[0], person_id).json()
    holder, _ = lib.student()
    lib.issue(codes[1], holder)
    other_title, other_codes = lib.title("Reserved title", copies=1)
    lib.issue(other_codes[0], holder)
    res = lib.post("/me/reservations", {"title_id": other_title["id"]}, me).json()
    lib.post(
        "/digital-resources", {"title": "PubMed", "url": "https://pubmed.example.com", "access": "open"}, lib.librarian
    )
    return lib, {"me": me, "person_id": person_id, "title": t, "loan": loan, "reservation": res, "barcode": codes[0]}


def test_no_cross_tenant_leak(client, org, other_org, travel):
    a, ia = seed(client, org, travel)
    b, ib = seed(client, other_org, travel)
    travel(15)
    a.give_back(ia["barcode"])  # raises a fine in A
    b.give_back(ib["barcode"])
    for path, ha, hb in [
        ("/titles", a.viewer, b.viewer),
        ("/loans", a.librarian, b.librarian),
        ("/reservations", a.librarian, b.librarian),
        ("/fines", a.librarian, b.librarian),
        ("/digital-resources", a.librarian, b.librarian),
        ("/me/loans", ia["me"], ib["me"]),
        ("/me/reservations", ia["me"], ib["me"]),
    ]:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))
    assert a.get("/me/fines", ia["me"]).json()["fines"][0]["organisation_id"] == org.id
    # Members have no id in the contract (person_id is the key), so they are compared by person_id.
    ma = a.get("/members", a.librarian).json()["items"]
    mb = b.get("/members", b.librarian).json()["items"]
    assert {m["organisation_id"] for m in ma} == {org.id} and {m["organisation_id"] for m in mb} == {other_org.id}
    assert not ({m["person_id"] for m in ma} & {m["person_id"] for m in mb})


def test_another_organisations_records_are_not_found(client, org, other_org, travel):
    a, ia = seed(client, org, travel)
    b = Library(client, other_org)
    assert b.get(f"/titles/{ia['title']['id']}", b.viewer).status_code == 404
    assert b.get(f"/members/{ia['person_id']}", b.librarian).status_code == 404
    assert b.give_back(ia["barcode"]).status_code == 404  # A's barcode is unknown in B
    assert b.issue(ia["barcode"], ia["person_id"]).status_code == 404
    assert b.post(f"/loans/{ia['loan']['id']}/renew", None, b.librarian).status_code == 404
    assert b.post(f"/loans/{ia['loan']['id']}/lost", {"replacement_amount": "1"}, b.librarian).status_code == 404
    assert b.post(f"/reservations/{ia['reservation']['id']}/cancel", None, b.librarian).status_code == 404
    assert (
        b.post(f"/titles/{ia['title']['id']}/copies", {"accession_no": "Z", "barcode": "Z"}, b.librarian).status_code
        == 404
    )
    assert b.patch(f"/titles/{ia['title']['id']}", {"title": "stolen"}, b.librarian).status_code == 404
    assert b.patch(f"/members/{ia['person_id']}", {"blocked": True, "reason": "nope"}, b.librarian).status_code == 404
    # A's data is untouched
    assert a.get(f"/titles/{ia['title']['id']}", a.viewer).json()["title"] == "Gray's Anatomy"
