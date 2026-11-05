"""The read-only HTTP surface: permissions, filters, pagination, error shapes, and that no transcript content shows."""

import base64
import json
import uuid

import pytest
from eup_support import PREFIX, export, put, transcript


def test_permissions(client, org):
    for path in ("/exchanges", f"/exchanges/{uuid.uuid4()}"):
        assert client.get(f"{PREFIX}{path}").status_code == 401
        assert client.get(f"{PREFIX}{path}", headers=org.student).status_code == 403
        assert client.get(f"{PREFIX}{path}", headers={"Authorization": "Bearer junk"}).status_code == 401
        assert client.get(f"{PREFIX}{path}", headers=org.admin).status_code in (200, 404)


def test_list_filters_and_paginates_newest_first(client, adapter, docs, org):
    ids = [export(adapter, org, "csv").output["exchange_id"] for _ in range(5)]
    export(adapter, org, "elmo_xml")
    adapter.import_records(
        org.ctx(),
        exchange_key="in",
        partner_id="uni-oslo",
        format="csv",
        document_id=put(docs, org.id, b"course_code,title,credits,status\nC,T,1,passed\n"),
    )
    seen, cursor = [], None
    while True:
        params = {"direction": "outbound", "limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get(f"{PREFIX}/exchanges", params=params, headers=org.admin).json()
        seen += [i["id"] for i in page["items"] if i["format"] == "csv"]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert sorted(seen) == sorted(ids)
    inbound = client.get(f"{PREFIX}/exchanges?direction=inbound", headers=org.admin).json()["items"]
    assert [i["status"] for i in inbound] == ["parsed"]
    assert client.get(f"{PREFIX}/exchanges?status=sent", headers=org.admin).json()["items"] == []
    assert len(client.get(f"{PREFIX}/exchanges?partner_id=uni-oslo&limit=200", headers=org.admin).json()["items"]) == 7
    pid = transcript()["learner"]["person_id"]
    assert (
        len(client.get(f"{PREFIX}/exchanges?person_id={pid.upper()}&limit=200", headers=org.admin).json()["items"]) == 6
    )


def _cursor(payload) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "cursor",
    [
        "garbage",
        "!!!!",
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
    r = client.get(f"{PREFIX}/exchanges", params={"cursor": cursor}, headers=org.admin)
    assert r.status_code in (400, 422), r.text
    if r.status_code == 400:
        assert r.json() == {"code": "invalid_cursor", "detail": "the cursor is not one this API issued"}


def test_bad_query_values_are_422(client, org):
    for q in (
        "limit=0",
        "limit=201",
        "limit=abc",
        "status=nope",
        "direction=sideways",
        f"partner_id={'x' * 61}",
        "person_id=nope",
    ):
        assert client.get(f"{PREFIX}/exchanges?{q}", headers=org.admin).status_code == 422, q


def test_detail_shows_the_file_integrity_and_unmapped_lines_but_no_content(client, adapter, docs, org):
    doc = put(docs, org.id, b"course_code,title,credits,status\nC1,Secret Course Title,1,passed\nC2,Bad,x,passed\n")
    ex = adapter.import_records(
        org.ctx(), exchange_key="d1", partner_id="uni-oslo", format="csv", document_id=doc
    ).output["exchange_id"]
    r = client.get(f"{PREFIX}/exchanges/{ex}", headers=org.admin)
    d = r.json()
    assert (
        d["direction"] == "inbound"
        and d["status"] == "parsed"
        and d["integrity"] == "unsigned"
        and d["document_id"] == doc
    )
    assert d["unmapped"] == [{"position": "row 3", "reason": "bad_credit_value"}] and len(d["sha256"]) == 64
    assert "Secret Course Title" not in r.text and "transcript" not in d
    out = export(adapter, org, "csv").output
    d = client.get(f"{PREFIX}/exchanges/{out['exchange_id']}", headers=org.admin).json()
    assert (
        d["document_id"] == out["document_id"]
        and d["sha256"] == out["sha256"]
        and d["partner_reference"] is None
        and d["delivered_by"] is None
    )


def test_unknown_or_malformed_ids_are_404(client, org):
    for eid in (str(uuid.uuid4()), "not-a-uuid", "x" * 500, "%00"):
        r = client.get(f"{PREFIX}/exchanges/{eid}", headers=org.admin)
        assert r.status_code == 404 and r.json()["code"] == "not_found", eid


def test_the_api_is_read_only(client, org):
    for method in (client.post, client.put, client.delete, client.patch):
        assert method(f"{PREFIX}/exchanges", headers=org.admin).status_code == 405
