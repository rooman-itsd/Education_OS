"""Values too big for their columns, cursors this API never handed out, and numbers no revision can have are 422 (or
404), never a 500: the cases found in review of the other support modules."""

import base64

import pytest

HUGE = 2**63
UUID = "11111111-1111-4111-8111-111111111111"


@pytest.mark.parametrize(
    "over",
    [
        {"title": "t" * 201},
        {"summary": "s" * 501},
        {"body": "b" * 200_001},
        {"tags": ["t" * 41]},
        {"tags": ["t"] * 51},
        {"references": [{"module": "m" * 61, "entity": "e", "id": "1"}]},
        {"references": [{"module": "m", "entity": "e", "id": "1" * 101}]},
        {"slug": "s" * 121},
        {"slug": "Not A Slug"},
        {"review_by": "9999-12-31"},
        {"review_by": "0001-01-01"},
        {"change_note": "c" * 501},
        {"category_id": "not-a-uuid"},
    ],
)
def test_article_values_too_big_or_malformed_are_a_422(desk, over):
    assert desk.post("/articles", desk.body(**over), desk.author).status_code == 422


def test_category_and_feedback_bounds(desk):
    assert desk.post("/categories", {"name": "n" * 81}).status_code == 422
    assert desk.post("/categories", {"name": "X", "position": HUGE}).status_code == 422
    assert desk.post("/categories", {"name": "X", "position": 100_001}).status_code == 422
    a = desk.published()
    assert (
        desk.post(f"/articles/{a['id']}/feedback", {"helpful": True, "comment": "c" * 1001}, desk.reader).status_code
        == 422
    )
    assert desk.post(f"/articles/{a['id']}/publish", {"review_by": "9999-12-31"}).status_code == 422


def test_numbers_no_revision_can_have(desk):
    a = desk.published()
    assert desk.get(f"/articles/{a['id']}/revisions/{HUGE}", desk.author).status_code == 422
    assert desk.put(f"/articles/{a['id']}/draft?from_revision={HUGE}", None, desk.author).status_code == 422
    assert desk.get(f"/articles/{a['id']}/revisions/{2**31 - 1}", desk.author).status_code == 404


@pytest.mark.parametrize("raw", [b"99999999999999999999", b"-5", b"abc", b"1000001"])
def test_cursors_this_api_did_not_hand_out_are_a_422(desk, raw):
    desk.published()
    cursor = base64.urlsafe_b64encode(raw).decode()
    r = desk.get(f"/articles?cursor={cursor}", desk.reader)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "invalid_cursor")
    a = desk.published(title="Another")
    assert desk.get(f"/articles/{a['id']}/feedback?cursor={cursor}", desk.viewer).status_code == 422
    assert desk.get("/articles?cursor=!!!", desk.reader).status_code == 422


def test_single_value_parameters_refuse_lists(desk):
    a = desk.published()
    assert desk.get(f"/articles/{a['id']}?view=published,open", desk.author).status_code == 422
    assert desk.get("/articles?audience=everyone,staff", desk.viewer).status_code == 422
    assert desk.get("/stats/top-articles?metric=views,helpful", desk.viewer).status_code == 422
    assert desk.get(f"/articles/{UUID}", desk.reader).status_code == 404
    assert desk.get("/articles/not-an-id", desk.reader).status_code == 404


def test_nul_characters_never_reach_the_database(desk):
    """Postgres text cannot hold NUL; SQLite can, so without these checks the bug would only show in production."""
    assert desk.post("/articles", desk.body(title="Wi\u0000Fi"), desk.author).status_code == 422
    assert desk.post("/articles", desk.body(tags=["a\u0000"]), desk.author).status_code == 422
    assert desk.post("/categories", {"name": "\u0000"}).status_code == 422
    for path in ("/articles/%00", "/articles/%00/revisions", "/articles/%00/feedback"):
        assert desk.get(path, desk.viewer if "feedback" in path else desk.editor).status_code == 404, path
    assert desk.patch("/categories/%00", {"name": "X"}).status_code == 404
    assert desk.post("/articles/%00/publish", {}).status_code == 404
