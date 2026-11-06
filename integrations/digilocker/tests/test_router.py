"""The read-only operator view (contracts/openapi.yaml /issuances): permission, tenancy, paging, bad input."""

from dgl_support import PREFIX, ctx, issue_input, ok
from eos_testing import assert_no_cross_tenant_leak


def seed(adapter, documents, org, n=3):
    for i in range(n):
        ok(adapter.invoke("issue", ctx(org), issue_input(documents, org, key=f"k{i}", number=f"N-{i}")))


def test_listing_needs_the_permission(client, adapter, documents, org):
    seed(adapter, documents, org, 1)
    assert client.get(f"{PREFIX}/issuances").status_code == 401
    assert client.get(f"{PREFIX}/issuances", headers=org.student).status_code == 403
    r = client.get(f"{PREFIX}/issuances", headers=org.admin)
    assert r.status_code == 200
    [item] = r.json()["items"]
    assert item["status"] == "available_for_pull" and item["uri"].endswith("N-0")
    for private in ("holder", "name", "dob", "mobile", "search", "sha256", "document_id", "wallet"):
        assert not any(private in k for k in item), private  # no document content, no contact details


def test_paging_and_filters(client, adapter, documents, org):
    seed(adapter, documents, org, 3)
    ok(adapter.invoke("withdraw", ctx(org), {"issuance_key": "k0", "reason": "x"}))
    page = client.get(f"{PREFIX}/issuances?limit=2", headers=org.admin).json()
    assert len(page["items"]) == 2 and page["next_cursor"] == "2"
    rest = client.get(f"{PREFIX}/issuances?limit=2&cursor=2", headers=org.admin).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    withdrawn = client.get(f"{PREFIX}/issuances?status=withdrawn", headers=org.admin).json()["items"]
    assert [i["issuance_key"] for i in withdrawn] == ["k0"]
    assert client.get(f"{PREFIX}/issuances?doc_kind=marksheet", headers=org.admin).json()["items"] == []


def test_bad_parameters_are_4xx_never_500(client, org):
    for query, status in (
        ("cursor=abc", 400), ("cursor=-1", 400), ("cursor=99999999999", 400), ("cursor=%E0%A4%A", 400),
        ("cursor=" + "9" * 21, 422), ("limit=0", 422), ("limit=201", 422), ("limit=x", 422),
        ("status=bogus", 422), ("person_id=nope", 422), ("doc_kind=" + "x" * 41, 422),
    ):  # fmt: skip
        r = client.get(f"{PREFIX}/issuances?{query}", headers=org.admin)
        assert r.status_code == status, (query, r.status_code)
    assert client.get(f"{PREFIX}/issuances?cursor=abc", headers=org.admin).json()["detail"]["code"] == "invalid_cursor"


def test_no_cross_tenant_leak(client, adapter, documents, org, other_org):
    seed(adapter, documents, org, 2)
    seed(adapter, documents, other_org, 2)
    assert_no_cross_tenant_leak(client, f"{PREFIX}/issuances", org.token("admin"), other_org.token("admin"))
    mine = client.get(f"{PREFIX}/issuances", headers=org.admin).json()["items"]
    assert len(mine) == 2
