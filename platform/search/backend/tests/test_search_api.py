"""The routes of the draft openapi, mounted alone (no host, no tenancy): auth, tenancy, input bounds, 503, cursors."""

import uuid

import pytest
from eos_audit.domain.models import AuditRecord
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_search.api.router import router
from eos_search.application import cursor, state
from eos_search.infrastructure.config import SearchConfig
from fastapi import FastAPI
from fastapi.testclient import TestClient
from search_support import (
    ARTICLE,
    COURSE,
    PERSON,
    PREFIX,
    SuperAdmin,
    article,
    course,
    index,
    person,
)
from sqlalchemy import select


@pytest.fixture
def client(search_registry, search_engine):
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    return TestClient(app)


@pytest.fixture
def seeded(search_org, search_registry, search_engine):
    """Courses, a person, a public and an internal article in the organisation, indexed."""
    o = search_org.id
    for i in range(5):
        index(
            search_engine,
            search_registry,
            o,
            COURSE,
            f"c{i}",
            course(f"Harbour studies {i}", f"HS-{i}", "boats and tides", credits=i),
        )
    index(search_engine, search_registry, o, PERSON, "p1", person("Harbourmaster Pillai"))
    index(search_engine, search_registry, o, ARTICLE, "a1", article("Harbour safety notice", "wear a vest"))
    index(search_engine, search_registry, o, ARTICLE, "a2", article("Harbour disciplinary file", internal=True))
    return search_org


def get(client, org, user, path, **params):
    return client.get(f"{PREFIX}{path}", params=params, headers=org.headers(user))


def test_every_route_needs_a_token(client):
    for path in (
        "/query?q=x",
        "/modules/knowledge-base/query?q=x",
        "/suggest?q=xx",
        "/types",
        "/reindex",
        "/health",
        "/platform/health",
    ):
        assert client.get(f"{PREFIX}{path}").status_code == 401, path
    assert client.post(f"{PREFIX}/reindex", json={"module": "knowledge-base"}).status_code == 401
    assert client.get(f"{PREFIX}/reindex/{uuid.uuid4()}").status_code == 401


def test_query_returns_hits_facets_total_and_only_what_the_caller_may_read(client, seeded):
    r = get(client, seeded, seeded.staff, "/query", q="harbour")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 7  # 5 courses + the person + the public article; the internal one is invisible
    assert {f["type"]: (f["label"], f["count"]) for f in body["facets"]} == {
        COURSE: ("Courses", 5),
        PERSON: ("Students", 1),
        ARTICLE: ("Articles", 1),
    }
    assert "disciplinary" not in r.text.lower()
    assert body["total_is_lower_bound"] is False and body["next_cursor"] is None
    # A reader of internal articles sees the other one too.
    assert get(client, seeded, seeded.kb_staff, "/query", q="disciplinary").json()["total"] == 1


def test_a_plain_member_may_search_but_sees_nothing_without_read_permissions(client, seeded):
    r = get(client, seeded, seeded.member, "/query", q="harbour")
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 0 and r.json()["facets"] == []
    assert get(client, seeded, seeded.member, "/types").json() == {"items": []}


def test_another_organisation_finds_nothing_and_a_super_admin_has_no_organisation_to_search(
    client, seeded, search_other_org, search_db
):
    r = get(client, search_other_org, search_other_org.everything, "/query", q="harbour")
    assert r.json()["total"] == 0 and r.json()["facets"] == []
    assert get(client, search_other_org, search_other_org.everything, "/suggest", q="harb").json() == {
        "suggestions": []
    }
    root = SuperAdmin(search_db)
    assert client.get(f"{PREFIX}/query", params={"q": "harbour"}, headers=root.headers).status_code == 403


def test_organisation_id_in_the_query_string_is_a_422(client, seeded, search_other_org):
    for path, params in (
        ("/query", {"q": "harbour"}),
        ("/suggest", {"q": "harb"}),
        ("/types", {}),
        ("/modules/knowledge-base/query", {"q": "harbour"}),
    ):
        r = get(client, seeded, seeded.everything, path, organisation_id=search_other_org.id, **params)
        assert r.status_code == 422, path
        assert search_other_org.id not in r.text


def test_types_lists_what_the_caller_may_use_with_filterable_fields(client, seeded):
    items = get(client, seeded, seeded.staff, "/types").json()["items"]
    by = {i["type"]: i for i in items}
    assert set(by) == {PERSON, COURSE, ARTICLE}
    assert by[COURSE] == {
        "type": COURSE,
        "module": "academic-management",
        "label": "Courses",
        "filterable": ["status", "credits"],
    }
    only_kb = get(client, seeded, seeded.kb_staff, "/types").json()["items"]
    assert [i["type"] for i in only_kb] == [ARTICLE]


def test_the_types_parameter_ignores_unknown_and_not_visible_types(client, seeded):
    r = get(client, seeded, seeded.staff, "/query", q="harbour", types=f"{ARTICLE},nope.nothing,{PERSON}x")
    assert r.status_code == 200 and {i["type"] for i in r.json()["items"]} == {ARTICLE}
    assert get(client, seeded, seeded.staff, "/query", q="harbour", types="x.y," * 21).status_code == 422


def test_module_query_filters_and_404(client, seeded):
    r = get(client, seeded, seeded.staff, "/modules/academic-management/query", q="harbour", filters="credits:3")
    assert r.status_code == 200 and [i["id"] for i in r.json()["items"]] == ["c3"]
    assert (
        get(
            client, seeded, seeded.staff, "/modules/academic-management/query", q="harbour", filters="description:x"
        ).status_code
        == 422
    )
    assert get(client, seeded, seeded.staff, "/modules/no-such-module/query", q="x").status_code == 404
    assert get(client, seeded, seeded.staff, "/modules/Bad_Module/query", q="x").status_code == 422
    # The same answer for everyone, whatever they may read: 404 means "not enabled or nothing searchable".
    assert get(client, seeded, seeded.member, "/modules/no-such-module/query", q="x").status_code == 404
    assert get(client, seeded, seeded.member, "/modules/knowledge-base/query", q="harbour").status_code == 200


def test_a_module_the_organisation_lost_is_a_404_on_the_next_request(client, seeded, search_db):
    from eos_core.tenant import organisation_scope

    with organisation_scope(seeded.id):
        state.set_entitlement(search_db, seeded.id, ["academic-management"])
        search_db.commit()
    assert get(client, seeded, seeded.staff, "/modules/knowledge-base/query", q="harbour").status_code == 404
    assert get(client, seeded, seeded.staff, "/modules/academic-management/query", q="harbour").status_code == 200
    types = {i["type"] for i in get(client, seeded, seeded.staff, "/types").json()["items"]}
    assert types == {COURSE}


def test_suggest_returns_title_completions_within_bounds(client, seeded):
    r = get(client, seeded, seeded.staff, "/suggest", q="harbourm")
    assert r.status_code == 200 and r.json()["suggestions"] == [
        {"type": PERSON, "id": "p1", "text": "Harbourmaster Pillai"}
    ]
    assert len(get(client, seeded, seeded.staff, "/suggest", q="harb", limit=2).json()["suggestions"]) == 2
    for params in ({"q": "h"}, {"q": "x" * 51}, {"q": "ab", "limit": 11}, {"q": "ab", "limit": 0}, {}):
        assert get(client, seeded, seeded.staff, "/suggest", **params).status_code == 422, params
    assert get(client, seeded, seeded.staff, "/suggest", q="  ").status_code == 422
    assert "disciplinary" not in get(client, seeded, seeded.staff, "/suggest", q="harbour d").text.lower()


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "x" * 201},
        {"q": "ok", "limit": 0},
        {"q": "ok", "limit": 51},
        {"q": "ok", "limit": "many"},
        {"q": "ok", "cursor": "x" * 2001},
        {"q": "ok", "cursor": "garbage"},
        {"q": "ok", "cursor": "a.b"},
        {"q": "ok", "types": "t" * 1001},
    ],
)
def test_out_of_bounds_input_is_a_422_never_a_500(client, seeded, params):
    r = get(client, seeded, seeded.staff, "/query", **params)
    assert r.status_code == 422, (params, r.text[:200])


def test_odd_but_legal_input_is_answered(client, seeded):
    for q in (
        "title:* OR (x AND NOT y)",
        '"',
        "\\",
        "*",
        "%00",
        "😀",
        "日本語",
        "<script>alert(1)</script>",
        "x" * 200,
    ):
        assert get(client, seeded, seeded.staff, "/query", q=q).status_code == 200, q
    assert get(client, seeded, seeded.staff, "/query", q="harbour\x00 ").status_code == 200


def test_hits_have_the_contract_shape(client, seeded):
    hit = get(client, seeded, seeded.staff, "/query", q="harbour", types=COURSE).json()["items"][0]
    assert set(hit) == {"type", "id", "title", "snippet", "url", "fields", "score"}
    assert hit["url"].startswith("/academics/courses/") and set(hit["fields"]) <= {"code", "status", "credits"}


def test_cursor_paging_and_binding_over_http(client, seeded, search_org):
    page1 = get(client, seeded, seeded.staff, "/query", q="harbour", limit=3).json()
    assert len(page1["items"]) == 3 and page1["next_cursor"]
    page2 = get(client, seeded, seeded.staff, "/query", q="harbour", limit=3, cursor=page1["next_cursor"]).json()
    assert not {i["id"] for i in page1["items"]} & {i["id"] for i in page2["items"]}
    # another user, another query, another module: all 422 with one sentence that repeats nothing
    other = get(client, seeded, seeded.everything, "/query", q="harbour", limit=3, cursor=page1["next_cursor"])
    assert other.status_code == 422
    assert (
        get(client, seeded, seeded.staff, "/query", q="harbour x", limit=3, cursor=page1["next_cursor"]).status_code
        == 422
    )
    assert (
        get(
            client, seeded, seeded.staff, "/query", q="harbour", limit=3, types=COURSE, cursor=page1["next_cursor"]
        ).status_code
        == 422
    )
    secret = SearchConfig.from_env().cursor_secret
    forged = cursor.sign(secret + "x", {"u": seeded.staff.id, "h": "h", "s": [1, "d"], "n": 1}, ttl_seconds=60)
    assert get(client, seeded, seeded.staff, "/query", q="harbour", cursor=forged).status_code == 422
    for r in (other,):
        assert "harbour" not in r.text


def test_an_outage_is_a_503_with_no_content_never_an_empty_page(client, seeded, search_engine):
    search_engine.down = True
    for path, params in (
        ("/query", {"q": "harbour"}),
        ("/suggest", {"q": "harb"}),
        ("/modules/knowledge-base/query", {"q": "harbour"}),
    ):
        r = get(client, seeded, seeded.staff, path, **params)
        assert r.status_code == 503 and r.json() == {"detail": "search is unavailable"}
    assert get(client, seeded, seeded.staff, "/types").status_code == 200  # no engine involved


def test_permissions_per_route(client, seeded):
    assert get(client, seeded, seeded.staff, "/health").status_code == 403
    assert get(client, seeded, seeded.staff, "/reindex").status_code == 403
    assert get(client, seeded, seeded.admin, "/platform/health").status_code == 403
    assert (
        client.post(
            f"{PREFIX}/reindex", json={"module": "knowledge-base"}, headers=seeded.headers(seeded.staff)
        ).status_code
        == 403
    )


def test_index_health_reports_documents_per_type_for_the_callers_organisation_only(
    client, seeded, search_other_org, search_engine, search_registry
):
    index(search_engine, search_registry, search_other_org.id, COURSE, "x", course("Elsewhere"))
    body = get(client, seeded, seeded.admin, "/health").json()
    docs = {t["type"]: t["documents"] for t in body["types"]}
    assert docs == {PERSON: 1, COURSE: 5, ARTICLE: 2} and body["status"] == "ok" and body["lag_seconds"] is None
    search_engine.down = True
    assert get(client, seeded, seeded.admin, "/health").json()["status"] == "unavailable"


def test_index_health_is_degraded_with_dead_letters_and_shows_lag(client, seeded, search_db):
    from eos_core.tenant import organisation_scope

    with organisation_scope(seeded.id):
        state.record_dead_letter(search_db, seeded.id, "knowledge-base", ARTICLE, "a9", None, "provider_failed")
        search_db.add(
            OutboxEvent(organisation_id=seeded.id, name="knowledge-base.article.published", payload={}, published=False)
        )
        search_db.commit()
    body = get(client, seeded, seeded.admin, "/health").json()
    assert body["status"] == "degraded" and isinstance(body["lag_seconds"], int) and body["lag_seconds"] >= 0


def test_platform_health_is_totals_for_a_super_admin_only(client, seeded, search_db, search_engine):
    root = SuperAdmin(search_db)
    r = client.get(f"{PREFIX}/platform/health", headers=root.headers)
    assert r.status_code == 200
    body = r.json()
    assert (
        body["cluster_status"] == "green"
        and body["indices"] >= 1
        and body["dead_lettered"] == 0
        and body["status"] == "ok"
    )
    assert seeded.id not in r.text and "documents" not in body
    search_engine.down = True
    down = client.get(f"{PREFIX}/platform/health", headers=root.headers).json()
    assert down["status"] == "unavailable" and down["cluster_status"] == "unknown"


# --- reindex -----------------------------------------------------------------------------------------------------
def test_reindex_is_accepted_runs_audited_and_listed(client, search_org, search_providers, search_engine, search_db):
    o = search_org.id
    search_providers["knowledge-base"].put(o, "article", "a1", **article("Backfilled article"))
    r = client.post(
        f"{PREFIX}/reindex", json={"module": "knowledge-base"}, headers=search_org.headers(search_org.admin)
    )
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["module"] == "knowledge-base" and job["type"] is None and job["requested_by"] == search_org.admin.id
    # The inline runner finished the job after the response; the job is readable, listed, and the audit trail has it.
    done = get(client, search_org, search_org.admin, f"/reindex/{job['id']}").json()
    assert done["status"] == "succeeded" and done["documents_indexed"] == 1 and done["finished_at"]
    listed = get(client, search_org, search_org.admin, "/reindex").json()
    assert [j["id"] for j in listed["items"]] == [job["id"]] and listed["next_cursor"] is None
    assert get(client, search_org, search_org.admin, "/reindex", module="knowledge-base", status="succeeded").json()[
        "items"
    ]
    assert get(client, search_org, search_org.admin, "/reindex", status="failed").json()["items"] == []
    assert search_engine.document(f"{o}:{ARTICLE}:a1")
    with platform_scope():
        audit = search_db.scalars(select(AuditRecord).where(AuditRecord.entity_id == job["id"])).all()
        names = [e.name for e in search_db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == o))]
    assert [(a.action, a.module, a.actor) for a in audit] == [("reindex.requested", "search", search_org.admin.id)]
    assert "search.reindex.completed" in names


def test_reindex_validation_and_404s(client, search_org):
    h = search_org.headers(search_org.admin)
    post = lambda body: client.post(f"{PREFIX}/reindex", json=body, headers=h)  # noqa: E731
    assert post({"module": "no-such-module"}).status_code == 404
    assert post({"module": "knowledge-base", "type": "knowledge-base.nothing"}).status_code == 404
    assert post({"module": "knowledge-base", "type": "academic-management.course"}).status_code == 404
    for bad in (
        {},
        {"module": "Bad Module"},
        {"module": "x"},
        {"module": "knowledge-base", "type": "no dots"},
        {"module": "knowledge-base", "organisation_id": "nope"},
        {"module": "knowledge-base", "extra": 1},
        {"module": ["a"]},
        {"module": "knowledge-base", "type": "k" * 200},
    ):
        assert post(bad).status_code == 422, bad
    assert (
        client.post(
            f"{PREFIX}/reindex", content="not json", headers={**h, "content-type": "application/json"}
        ).status_code
        == 422
    )


def test_only_a_super_admin_may_name_an_organisation(
    client, search_org, search_other_org, search_providers, search_engine, search_db
):
    h = search_org.headers(search_org.admin)
    for target in (search_other_org.id, search_org.id):  # even their own
        r = client.post(f"{PREFIX}/reindex", json={"module": "knowledge-base", "organisation_id": target}, headers=h)
        assert r.status_code == 403
    root = SuperAdmin(search_db)
    search_providers["knowledge-base"].put(
        search_other_org.id, "article", "a1", **article("Rebuilt for another tenant")
    )
    r = client.post(
        f"{PREFIX}/reindex",
        json={"module": "knowledge-base", "organisation_id": search_other_org.id},
        headers=root.headers,
    )
    assert r.status_code == 202, r.text
    assert search_engine.document(f"{search_other_org.id}:{ARTICLE}:a1") is not None
    # a super admin with no organisation must name one
    assert client.post(f"{PREFIX}/reindex", json={"module": "knowledge-base"}, headers=root.headers).status_code == 422
    # the job belongs to the named organisation, not to the super admin's session
    jobs = get(client, search_other_org, search_other_org.admin, "/reindex").json()["items"]
    assert len(jobs) == 1 and jobs[0]["requested_by"] == root.id
    assert get(client, search_org, search_org.admin, "/reindex").json()["items"] == []


def test_a_second_request_while_one_is_active_is_a_409_naming_the_job(client, search_org, search_db):
    from eos_core.tenant import organisation_scope
    from eos_search.application import reindex as reindex_mod

    with organisation_scope(search_org.id):
        job = reindex_mod.start_reindex(
            search_db, organisation_id=search_org.id, requested_by=None, module="knowledge-base", type_key=None
        )
        search_db.commit()
    h = search_org.headers(search_org.admin)
    r = client.post(f"{PREFIX}/reindex", json={"module": "knowledge-base"}, headers=h)
    assert r.status_code == 409 and job.id in r.json()["detail"]
    r = client.post(f"{PREFIX}/reindex", json={"module": "knowledge-base", "type": ARTICLE}, headers=h)
    assert r.status_code == 409  # a whole-module rebuild covers the type
    assert (
        client.post(f"{PREFIX}/reindex", json={"module": "academic-management"}, headers=h).status_code == 202
    )  # another module


def test_job_reads_are_scoped_and_validated(client, search_org, search_other_org, search_providers):
    h = search_org.headers(search_org.admin)
    job = client.post(f"{PREFIX}/reindex", json={"module": "knowledge-base"}, headers=h).json()
    assert get(client, search_other_org, search_other_org.admin, f"/reindex/{job['id']}").status_code == 404
    assert get(client, search_org, search_org.admin, f"/reindex/{uuid.uuid4()}").status_code == 404
    assert get(client, search_org, search_org.admin, "/reindex/not-a-uuid").status_code == 404
    assert get(client, search_org, search_org.admin, "/reindex", status="bogus").status_code == 422
    assert get(client, search_org, search_org.admin, "/reindex", cursor="junk").status_code == 422


def test_job_listing_pages_with_a_signed_cursor(client, search_org, search_providers):
    h = search_org.headers(search_org.admin)
    ids = [
        client.post(f"{PREFIX}/reindex", json={"module": m, "type": t}, headers=h).json()["id"]
        for m, t in (("knowledge-base", ARTICLE), ("academic-management", COURSE), ("student-information", PERSON))
    ]
    first = get(client, search_org, search_org.admin, "/reindex", limit=2).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = get(client, search_org, search_org.admin, "/reindex", limit=2, cursor=first["next_cursor"]).json()
    assert len(second["items"]) == 1 and second["next_cursor"] is None
    assert {j["id"] for j in first["items"] + second["items"]} == set(ids)
    assert (
        get(
            client,
            search_org,
            search_org.admin,
            "/reindex",
            limit=2,
            module="knowledge-base",
            cursor=first["next_cursor"],
        ).status_code
        == 422
    )


def test_a_validation_error_never_echoes_the_query(client, seeded):
    secret = "needle-" + "x" * 300
    for params in ({"q": secret}, {"q": "ok", "cursor": secret * 10}, {"q": "ok", "types": secret * 10}):
        r = get(client, seeded, seeded.staff, "/query", **params)
        assert r.status_code == 422 and "needle" not in r.text, params
    r = get(client, seeded, seeded.staff, "/suggest", q="needle-" + "y" * 80)
    assert r.status_code == 422 and "needle" not in r.text
    r = get(client, seeded, seeded.staff, "/modules/academic-management/query", q="ok", filters="status:" + secret)
    assert r.status_code == 422 and "needle" not in r.text
