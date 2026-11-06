"""Bad input is a 4xx, never a 500: every string, number, date, enum, id and cursor is bounded, and NUL characters
(which Postgres text cannot hold, though SQLite can) never reach the database."""

import base64

import pytest
from conftest import BASE
from eos_core.db import new_id
from eos_iqac_accreditation.api import schemas as s
from pydantic import ValidationError

UUID = new_id()


def raw(client, method: str, path: str, content: str, headers: dict):
    return client.request(method, BASE + path, content=content, headers={**headers, "Content-Type": "application/json"})


@pytest.fixture
def ids(desk):
    c = desk.collecting()
    return {
        "desk": desk,
        "framework": c["framework"]["id"],
        "metric": c["q"]["metric_id"],
        "cycle": c["cycle"]["id"],
        "response": c["q"]["id"],
        "item": desk.action_item()["id"],
    }


def bodies(ids):
    """(method, path, body, who) of requests that each break one bound or rule of the schema."""
    f, c, r, i, m = ids["framework"], ids["cycle"], ids["response"], ids["item"], ids["metric"]
    ok_cycle = {"framework_id": f, "name": "X", "period_start": "2025-04-01", "period_end": "2026-03-31"}
    ok_evidence = {"title": "X", "kind": "link", "url": "https://example.edu"}
    ok_item = {"title": "X", "owner_id": UUID, "due_on": "2026-12-01"}
    ok_assign = {"metric_id": m, "owner_id": UUID, "due_on": "2026-12-01"}
    return [
        ("POST", "/frameworks", {"code": "C" * 41, "name": "X"}, "coordinator"),
        ("POST", "/frameworks", {"code": " ", "name": "X"}, "coordinator"),
        ("POST", "/frameworks", {"code": "", "name": "X"}, "coordinator"),
        ("POST", "/frameworks", {"code": "X", "name": "N" * 201}, "coordinator"),
        ("POST", "/frameworks", {"code": "X", "name": "X", "description": "D" * 10_001}, "coordinator"),
        ("POST", "/frameworks", {"code": "X", "name": "X", "active": "maybe"}, "coordinator"),
        ("POST", "/frameworks", {"code": "X", "name": "X", "extra": 1}, "coordinator"),
        ("POST", "/frameworks", {"code": "X\u0000Y", "name": "X"}, "coordinator"),
        ("POST", "/frameworks", {"code": "X", "name": "a\u0000b"}, "coordinator"),
        ("POST", "/frameworks", {"code": "X", "name": None}, "coordinator"),
        ("POST", "/frameworks", [], "coordinator"),
        ("PATCH", f"/frameworks/{f}", {"code": "C" * 41}, "coordinator"),
        ("PATCH", f"/frameworks/{f}", {"description": "D\u0000"}, "coordinator"),
        ("POST", f"/frameworks/{f}/metrics", {"code": "X", "title": "T", "kind": "numeric"}, "coordinator"),
        ("POST", f"/frameworks/{f}/metrics", {"code": "X", "title": "T" * 501, "kind": "qualitative"}, "coordinator"),
        (
            "POST",
            f"/frameworks/{f}/metrics",
            {"code": "X", "title": "T", "kind": "qualitative", "unit": "u" * 41},
            "coordinator",
        ),
        (
            "POST",
            f"/frameworks/{f}/metrics",
            {"code": "X", "title": "T", "kind": "qualitative", "criterion": "c" * 201},
            "coordinator",
        ),
        (
            "POST",
            f"/frameworks/{f}/metrics",
            {"code": "X", "title": "T", "kind": "qualitative", "guidance": "g" * 10_001},
            "coordinator",
        ),
        ("PATCH", f"/metrics/{m}", {"kind": "qualitative"}, "coordinator"),  # the kind does not change
        ("PATCH", f"/metrics/{m}", {"title": "T" * 501}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "framework_id": "nope"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "framework_id": UUID.upper() + "x"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "name": "N" * 201}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "period_start": "1899-12-31"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "period_end": "2200-01-01"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "period_end": "9999-12-31"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "period_start": "0001-01-01"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "period_start": "2026-02-30"}, "coordinator"),
        ("POST", "/cycles", {**ok_cycle, "period_start": 20250401}, "coordinator"),
        ("PATCH", f"/cycles/{c}", {"period_end": "2200-01-01"}, "coordinator"),
        ("POST", f"/cycles/{c}/status", {"status": "planning"}, "coordinator"),
        ("POST", f"/cycles/{c}/status", {"status": "bogus"}, "coordinator"),
        ("POST", f"/cycles/{c}/status", {"status": "submitted", "submitted_on": "9999-12-31"}, "coordinator"),
        ("POST", f"/cycles/{c}/status", {}, "coordinator"),
        ("POST", f"/cycles/{c}/assignments", {"assignments": []}, "coordinator"),
        ("POST", f"/cycles/{c}/assignments", {"assignments": [ok_assign] * 201}, "coordinator"),
        ("POST", f"/cycles/{c}/assignments", {"assignments": [{**ok_assign, "owner_id": "me"}]}, "coordinator"),
        ("POST", f"/cycles/{c}/assignments", {"assignments": [{**ok_assign, "metric_id": "x"}]}, "coordinator"),
        ("POST", f"/cycles/{c}/assignments", {"assignments": [{**ok_assign, "due_on": "9999-01-01"}]}, "coordinator"),
        ("POST", f"/cycles/{c}/assignments", {"assignments": [{"metric_id": m}]}, "coordinator"),
        ("PUT", f"/responses/{r}", {"value": 1e16}, "alice"),
        ("PUT", f"/responses/{r}", {"value": -1e16}, "alice"),
        ("PUT", f"/responses/{r}", {"value": "abc"}, "alice"),
        ("PUT", f"/responses/{r}", {"value": True and "1e999"}, "alice"),
        ("PUT", f"/responses/{r}", {"narrative": "n" * 20_001}, "alice"),
        ("PUT", f"/responses/{r}", {"narrative": "a\u0000b"}, "alice"),
        ("PUT", f"/responses/{r}", {"status": "accepted"}, "alice"),
        ("POST", f"/responses/{r}/review", {"decision": "approve"}, "coordinator"),
        ("POST", f"/responses/{r}/review", {"decision": "return", "comment": "c" * 5_001}, "coordinator"),
        ("POST", f"/responses/{r}/review", {"decision": "accept", "comment": "ab"}, "coordinator"),
        ("POST", f"/responses/{r}/evidence", {**ok_evidence, "title": "T" * 201}, "alice"),
        ("POST", f"/responses/{r}/evidence", {**ok_evidence, "url": "https://e.edu/" + "a" * 2_000}, "alice"),
        ("POST", f"/responses/{r}/evidence", {**ok_evidence, "note": "n" * 5_001}, "alice"),
        ("POST", f"/responses/{r}/evidence", {**ok_evidence, "kind": "file"}, "alice"),
        ("POST", f"/responses/{r}/evidence", {**ok_evidence, "url": "https://e.edu/a\u0000b"}, "alice"),
        (
            "POST",
            f"/responses/{r}/evidence",
            {"title": "X", "kind": "reference", "reference": {"module": "m" * 121, "entity": "e", "id": "1"}},
            "alice",
        ),
        (
            "POST",
            f"/responses/{r}/evidence",
            {"title": "X", "kind": "reference", "reference": {"module": "m", "entity": "e"}},
            "alice",
        ),
        (
            "POST",
            f"/responses/{r}/evidence",
            {"title": "X", "kind": "reference", "reference": {"module": "m", "entity": "e", "id": "\u0000"}},
            "alice",
        ),
        ("POST", "/action-items", {**ok_item, "title": "T" * 201}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "source": "s" * 121}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "description": "d" * 10_001}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "owner_id": "me"}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "due_on": "2200-01-01"}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "due_on": "0001-01-01"}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "cycle_id": "x"}, "coordinator"),
        ("POST", "/action-items", {**ok_item, "title": "a\u0000b"}, "coordinator"),
        ("PATCH", f"/action-items/{i}", {"status": "open"}, "coordinator"),
        ("PATCH", f"/action-items/{i}", {"status": "bogus"}, "coordinator"),
        ("PATCH", f"/action-items/{i}", {"due_on": "9999-12-31"}, "coordinator"),
        ("PATCH", f"/action-items/{i}", {"note": "n" * 5_001}, "coordinator"),
    ]


def test_bad_request_bodies_are_refused_with_422(ids):
    d = ids["desk"]
    who = {"coordinator": d.coordinator, "alice": d.alice}
    for method, path, body, role in bodies(ids):
        r = d.client.request(method, BASE + path, json=body, headers=who[role])
        assert r.status_code == 422, (method, path, str(body)[:80], r.status_code, r.text[:200])


def test_json_that_is_not_an_object_or_not_json_is_refused(ids):
    d = ids["desk"]
    for content in ("", "{", "null", "[1]", '"text"', '{"code": NaN}', '{"code": "X", "name": "X", "active": NaN}'):
        r = raw(d.client, "POST", "/frameworks", content, d.coordinator)
        assert r.status_code == 422, content
    r = raw(d.client, "PUT", f"/responses/{ids['response']}", '{"value": 1e999}', d.alice)
    assert r.status_code == 422
    r = raw(d.client, "PUT", f"/responses/{ids['response']}", '{"value": NaN}', d.alice)
    assert r.status_code == 422
    r = raw(d.client, "PUT", f"/responses/{ids['response']}", '{"value": -Infinity}', d.alice)
    assert r.status_code == 422
    r = raw(d.client, "PUT", f"/responses/{ids['response']}", '{"value": 1' + "0" * 5_000 + "}", d.alice)
    assert r.status_code in (400, 422)  # an integer past Python's digit limit: refused, never a 500


def test_the_numeric_bounds_are_inclusive_and_exact(ids):
    d = ids["desk"]
    path = f"/responses/{ids['response']}"
    for value in (1e15, -1e15, 0, 0.1, 123456789012345):
        r = d.put(path, {"value": value}, d.alice)
        assert r.status_code == 200 and r.json()["value"] == value, value


def test_string_bounds_are_inclusive(ids):
    d = ids["desk"]
    f = d.framework(code="C" * 40, name="N" * 200, description="D" * 10_000)
    assert (len(f["code"]), len(f["name"]), len(f["description"])) == (40, 200, 10_000)
    ev = d.post(
        f"/responses/{ids['response']}/evidence",
        {"title": "T" * 200, "kind": "link", "url": "https://e.edu/" + "a" * (2_000 - 14), "note": "n" * 5_000},
        d.alice,
    )
    assert ev.status_code == 201


def test_date_bounds_are_inclusive(ids):
    d = ids["desk"]
    ok = d.post(
        "/cycles",
        {"framework_id": ids["framework"], "name": "Wide", "period_start": "1900-01-01", "period_end": "2199-12-31"},
    )
    assert ok.status_code == 201
    item = d.post("/action-items", {"title": "x", "owner_id": UUID, "due_on": "2199-12-31"})
    assert item.status_code == 201 and item.json()["overdue"] is False
    assert d.get("/stats/action-items").status_code == 200  # a far due date breaks no sum


@pytest.mark.parametrize(
    "query",
    [
        "/responses?limit=0",
        "/responses?limit=101",
        "/responses?limit=-1",
        "/responses?limit=abc",
        "/responses?limit=99999999999999999999",
        "/responses?status=bogus",
        "/responses?status=pending,accepted",
        "/responses?overdue=maybe",
        "/responses?owner=nobody",
        "/responses?owner=me,other",
        f"/responses?owner={UUID},{UUID}",
        "/responses?cycle_id=x",
        f"/responses?cycle_id={UUID},{UUID}",
        "/action-items?limit=0",
        "/action-items?limit=101",
        "/action-items?status=bogus",
        "/action-items?owner=x",
        "/action-items?cycle_id=x",
        "/action-items?overdue=2",
        "/cycles?status=bogus",
        "/cycles?framework_id=x",
        "/frameworks?active=maybe",
        f"/frameworks/{UUID}/metrics?active=maybe",
        f"/frameworks/{UUID}/metrics?criterion=" + "c" * 201,
        "/responses?cursor=abc!",
        "/responses?cursor=" + "A" * 17,
        "/responses?cursor=" + base64.urlsafe_b64encode(b"-1").decode(),
        "/responses?cursor=" + base64.urlsafe_b64encode(b"1.5").decode(),
        "/responses?cursor=" + base64.urlsafe_b64encode(b"1e3").decode(),
        "/responses?cursor=" + base64.urlsafe_b64encode(b" 1").decode(),
        "/responses?cursor=" + base64.urlsafe_b64encode(b"99999999").decode(),
        "/responses?cursor=" + base64.urlsafe_b64encode("١".encode()).decode(),  # an Arabic-Indic digit
        "/responses?cursor=" + base64.urlsafe_b64encode("²".encode()).decode(),  # a superscript digit
        "/action-items?cursor=%C3%A9",
        "/action-items?cursor=" + base64.urlsafe_b64encode(b"-5").decode(),
        "/responses?cycle_id=a%00b",
        "/responses?owner=a%00b",
        "/action-items?cycle_id=a%00b",
        "/cycles?framework_id=a%00b",
        f"/frameworks/{UUID}/metrics?criterion=a%00b",
        "/action-items?cursor=a%00b",
    ],
)
def test_bad_query_parameters_are_422_never_500(desk, query):
    assert desk.get(query).status_code == 422, query


def test_a_cursor_of_ascii_digits_is_the_only_cursor_that_works(desk):
    d = desk
    assert d.get("/responses?cursor=" + base64.urlsafe_b64encode(b"0").decode()).status_code == 200
    assert d.get("/responses?cursor=" + base64.urlsafe_b64encode(b"1000000").decode()).status_code == 200
    assert d.get("/responses?cursor=" + base64.urlsafe_b64encode(b"1000001").decode()).status_code == 422
    r = d.get("/responses?cursor=!!")
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "invalid_cursor")


def test_path_ids_that_are_not_uuids_name_nothing(desk):
    d = desk
    _, everything = d.org.user("iqac-accreditation-coordinator", "iqac-accreditation-contributor")
    evidence = {"title": "X", "kind": "link", "url": "https://example.edu"}
    assignments = {"assignments": [{"metric_id": UUID, "owner_id": UUID, "due_on": "2026-12-01"}]}
    metric = {"code": "X", "title": "X", "kind": "qualitative"}
    for bad in ("nope", "123", "a%00b", UUID + "0", UUID[:-1]):
        for method, path, body in (
            ("GET", f"/cycles/{bad}", None),
            ("PATCH", f"/cycles/{bad}", {"name": "X"}),
            ("POST", f"/cycles/{bad}/status", {"status": "collecting"}),
            ("POST", f"/cycles/{bad}/assignments", assignments),
            ("GET", f"/responses/{bad}", None),
            ("PUT", f"/responses/{bad}", {"narrative": "X"}),
            ("POST", f"/responses/{bad}/submit", None),
            ("POST", f"/responses/{bad}/review", {"decision": "accept"}),
            ("POST", f"/responses/{bad}/evidence", evidence),
            ("DELETE", f"/responses/{bad}/evidence/{UUID}", None),
            ("DELETE", f"/responses/{UUID}/evidence/{bad}", None),
            ("PATCH", f"/action-items/{bad}", {"status": "in_progress"}),
            ("PATCH", f"/frameworks/{bad}", {"name": "X"}),
            ("GET", f"/frameworks/{bad}/metrics", None),
            ("POST", f"/frameworks/{bad}/metrics", metric),
            ("PATCH", f"/metrics/{bad}", {"title": "X"}),
        ):
            r = d.client.request(method, BASE + path, json=body, headers=everything)
            assert (r.status_code, r.json()["detail"]["code"]) == (404, "not_found"), (method, path, r.status_code)


def test_request_bodies_refuse_nul_anywhere():
    with pytest.raises(ValidationError, match="NUL"):
        s.FrameworkUpdateInput(name="IQAC\u0000cell")
    with pytest.raises(ValidationError, match="NUL"):
        s.CycleInput(framework_id=UUID, name="a\u0000b", period_start="2025-04-01", period_end="2026-03-31")
    with pytest.raises(ValidationError, match="NUL"):
        s.EvidenceInput(title="x", kind="reference", reference={"module": "m\u0000", "entity": "e", "id": "1"})


def test_nul_in_the_url_is_refused_before_the_database(desk):
    d = desk
    assert d.get("/cycles/a%00b").status_code == 404
    refused = d.get("/responses?owner=a%00b")
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "invalid_query")


def test_text_with_unicode_and_quotes_is_stored_and_matched_literally(desk):
    d = desk
    f = d.framework(code="NAAC-%_", name="Accréditation – \"quoted\" 'name' 中文")
    assert d.ok(d.get("/frameworks"))[0]["name"] == f["name"]
    m = d.metric(f["id"], criterion="100% of _all_ \\ criteria")
    assert (
        d.ok(d.get(f"/frameworks/{f['id']}/metrics?criterion=100%25%20of%20_all_%20%5C%20criteria"))[0]["id"] == m["id"]
    )
    assert d.ok(d.get(f"/frameworks/{f['id']}/metrics?criterion=%25")) == []
