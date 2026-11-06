"""The read-only HTTP surface: permissions, pagination, filters, error shapes."""

import base64
import json
import uuid

import pytest
from gp_support import PREFIX, load_case, prepare


def test_forms_catalogue(client, org):
    r = client.get(f"{PREFIX}/forms", headers=org.admin)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 24 and all(i["channel"] == "manual_entry" for i in items)
    only = client.get(f"{PREFIX}/forms?authority=naac", headers=org.admin).json()["items"]
    assert {i["authority"] for i in only} == {"naac"} and len(only) == 4
    assert client.get(f"{PREFIX}/forms?authority=ugc", headers=org.admin).status_code == 422


def test_permissions(client, org):
    for path in ("/forms", "/packages", f"/packages/{uuid.uuid4()}"):
        assert client.get(f"{PREFIX}{path}").status_code == 401
        assert client.get(f"{PREFIX}{path}", headers=org.student).status_code == 403
        assert client.get(f"{PREFIX}{path}", headers={"Authorization": "Bearer junk"}).status_code == 401
        assert client.get(f"{PREFIX}{path}", headers=org.admin).status_code in (200, 404)


def test_list_filters_and_paginates_newest_first(client, adapter, docs, org):
    ids = [prepare(adapter, org, docs, load_case("aishe-dcf-i")).output["package_id"] for _ in range(5)]
    prepare(adapter, org, docs, load_case("nirf-dcs-overall"))
    page1 = client.get(f"{PREFIX}/packages?form_code=aishe.dcf-i&limit=2", headers=org.admin).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    seen = [i["id"] for i in page1["items"]]
    cursor = page1["next_cursor"]
    while cursor:
        page = client.get(f"{PREFIX}/packages?form_code=aishe.dcf-i&limit=2&cursor={cursor}", headers=org.admin).json()
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
    assert sorted(seen) == sorted(ids) and len(set(seen)) == 5
    assert seen == [
        i["id"] for i in client.get(f"{PREFIX}/packages?form_code=aishe.dcf-i", headers=org.admin).json()["items"]
    ]
    assert client.get(f"{PREFIX}/packages?status=invalid", headers=org.admin).json()["items"] == []
    assert (
        client.get(f"{PREFIX}/packages?period=2026", headers=org.admin).json()["items"][0]["form_code"]
        == "nirf.dcs.overall"
    )


def _cursor(payload) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "cursor",
    [
        "garbage",
        "!!!!",
        "",
        "x" * 300,
        _cursor("string"),
        _cursor([1, 2]),
        _cursor(["not-a-date", str(uuid.uuid4())]),
        _cursor(["2026-01-01T00:00:00+00:00", "not-a-uuid"]),
        _cursor([None, None]),
        _cursor({"a": 1}),
    ],
)
def test_a_bad_cursor_is_a_400_never_a_500(client, org, cursor):
    r = client.get(f"{PREFIX}/packages", params={"cursor": cursor}, headers=org.admin)
    assert r.status_code in (200, 400, 422), r.text  # an empty cursor means "no cursor"
    if r.status_code == 400:
        assert r.json() == {"code": "invalid_cursor", "detail": "the cursor is not one this API issued"}
    assert r.status_code != 200 or cursor == ""


def test_bad_query_values_are_422(client, org):
    for q in ("limit=0", "limit=201", "limit=abc", "status=nope", f"form_code={'x' * 65}", f"period={'x' * 41}"):
        assert client.get(f"{PREFIX}/packages?{q}", headers=org.admin).status_code == 422, q


def test_package_detail_has_files_checklist_issues_and_filing(client, adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("naac-aqar")).output["package_id"]
    d = client.get(f"{PREFIX}/packages/{pid}", headers=org.admin).json()
    assert d["id"] == pid and d["status"] == "prepared" and d["form_code"] == "naac.aqar"
    assert {f["role"] for f in d["files"]} == {"keying_sheet", "upload", "evidence", "bundle"}
    assert (
        d["checklist"] and d["issues"] == [] and d["submitted_by"] is None and d["acknowledgement_document_id"] is None
    )


def test_unknown_or_malformed_package_ids_are_404(client, org):
    for pid in (str(uuid.uuid4()), "not-a-uuid", "x" * 500, "%00"):
        r = client.get(f"{PREFIX}/packages/{pid}", headers=org.admin)
        assert r.status_code == 404 and r.json()["code"] == "not_found", pid


def test_the_api_is_read_only(client, org):
    for method in (client.post, client.put, client.delete, client.patch):
        assert method(f"{PREFIX}/packages", headers=org.admin).status_code == 405
