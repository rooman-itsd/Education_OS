"""The read-only operator view (contracts/openapi.yaml /submissions): permission, tenancy, paging, bad input."""

import uuid

from eos_testing import assert_no_cross_tenant_leak
from nad_support import PREFIX, awards_batch, credits_batch, ctx, ok, record


def seed(adapter, org, n=2):
    for i in range(n):
        ok(adapter.invoke("publish_awards", ctx(org), awards_batch(batch_key=f"b{i}", records=[record(i)])))


def test_listing_needs_the_permission(client, adapter, org):
    seed(adapter, org, 1)
    assert client.get(f"{PREFIX}/submissions").status_code == 401
    assert client.get(f"{PREFIX}/submissions", headers=org.student).status_code == 403
    r = client.get(f"{PREFIX}/submissions", headers=org.admin)
    assert r.status_code == 200
    [item] = r.json()["items"]
    assert (item["kind"], item["depository"], item["channel"], item["status"], item["rows"]) == (
        "awards",
        "nad",
        "manual_upload",
        "manual_action_required",
        1,
    )
    assert item["caller_reference"] == "b0" and item["session"] == "2025-26"
    for private in ("learner", "name", "apaar", "dob", "digest", "reason"):
        assert not any(private in k for k in item), private  # no learner rows


def test_detail_has_files_steps_and_row_errors_but_no_learner_data(client, adapter, org):
    bad = awards_batch(batch_key="bad", records=[record(1, learner={"name": "Secret Name"})])
    rejected = ok(adapter.invoke("publish_awards", ctx(org), bad))["submission_id"]
    good = ok(adapter.invoke("publish_awards", ctx(org), awards_batch(records=[record(2)])))["submission_id"]
    d = client.get(f"{PREFIX}/submissions/{good}", headers=org.admin).json()
    assert (
        len(d["upload_files"]) == 1
        and d["upload_files"][0]["rows"] == 1
        and len(d["steps"]) == 4
        and d["row_errors"] == []
    )
    r = client.get(f"{PREFIX}/submissions/{rejected}", headers=org.admin)
    assert r.json()["status"] == "rejected" and r.json()["row_errors"] and "Secret Name" not in r.text
    assert client.get(f"{PREFIX}/submissions/{good}", headers=org.student).status_code == 403
    assert client.get(f"{PREFIX}/submissions/{uuid.uuid4()}", headers=org.admin).status_code == 404
    assert client.get(f"{PREFIX}/submissions/not-a-uuid", headers=org.admin).status_code == 422


def test_paging_and_filters(client, adapter, org):
    seed(adapter, org, 3)
    ok(adapter.invoke("publish_credits", ctx(org), credits_batch()))
    page = client.get(f"{PREFIX}/submissions?limit=3", headers=org.admin).json()
    assert len(page["items"]) == 3 and page["next_cursor"] == "3"
    assert len(client.get(f"{PREFIX}/submissions?limit=3&cursor=3", headers=org.admin).json()["items"]) == 1
    assert len(client.get(f"{PREFIX}/submissions?kind=credits", headers=org.admin).json()["items"]) == 1
    assert client.get(f"{PREFIX}/submissions?status=rejected", headers=org.admin).json()["items"] == []
    assert len(client.get(f"{PREFIX}/submissions?session=2025-26", headers=org.admin).json()["items"]) == 4


def test_bad_parameters_are_4xx_never_500(client, org):
    for query, status in (
        ("cursor=abc", 400), ("cursor=-1", 400), ("cursor=99999999999", 400), ("cursor=" + "9" * 21, 422),
        ("limit=0", 422), ("limit=201", 422), ("limit=x", 422), ("status=bogus", 422), ("kind=bogus", 422),
        ("session=2025", 422), ("session=" + "9" * 50, 422),
    ):  # fmt: skip
        assert client.get(f"{PREFIX}/submissions?{query}", headers=org.admin).status_code == status, query
    assert (
        client.get(f"{PREFIX}/submissions?cursor=abc", headers=org.admin).json()["detail"]["code"] == "invalid_cursor"
    )


def test_no_cross_tenant_leak(client, adapter, org, other_org):
    seed(adapter, org, 2)
    seed(adapter, other_org, 2)
    assert_no_cross_tenant_leak(client, f"{PREFIX}/submissions", org.token("admin"), other_org.token("admin"))
    assert len(client.get(f"{PREFIX}/submissions", headers=org.admin).json()["items"]) == 2
    theirs = client.get(f"{PREFIX}/submissions", headers=other_org.admin).json()["items"][0]["id"]
    assert client.get(f"{PREFIX}/submissions/{theirs}", headers=org.admin).status_code == 404
