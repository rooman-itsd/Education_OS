"""listGradingSchemes, createGradingScheme, getGradingScheme, replaceGradingScheme, setDefaultGradingScheme."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BANDS,
    BASE,
    FACULTY,
    STUDENT,
    VIEWER,
    all_outbox,
    audit_entries,
    cycle_body,
    err,
    grading_body,
    make_cycle,
    make_grading,
    ok,
    session_for,
    uid,
)
from eos_examinations.infrastructure.models import ExamCycleRow  # noqa: E402

URL = f"{BASE}/grading-schemes"


def test_the_operations_need_their_keys(client, org):
    _, viewer = org.user(VIEWER)
    _, faculty = org.user(FACULTY)  # holds no grading-scheme key
    _, student = org.user(STUDENT)
    scheme = make_grading(client, org.controller())
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=viewer).status_code == 200
    assert client.get(f"{URL}/{scheme['id']}", headers=viewer).status_code == 200
    for headers in (faculty, student):
        assert client.get(URL, headers=headers).status_code == 403
        assert client.get(f"{URL}/{scheme['id']}", headers=headers).status_code == 403
    for headers in (viewer, faculty, student):  # reading is not managing
        responses = (
            client.post(URL, json=grading_body(), headers=headers),
            client.put(f"{URL}/{scheme['id']}", json=grading_body(), headers=headers),
            client.post(f"{URL}/{scheme['id']}/set-default", headers=headers),
        )
        for r in responses:
            assert r.status_code == 403
            assert r.json()["detail"]["code"] == "forbidden"
    assert client.post(URL, json=grading_body()).status_code == 401


def test_create_returns_the_scheme_and_it_can_be_read_back(client, org, h):
    created = make_grading(client, h)
    assert created["name"] == "10 point"
    assert created["organisation_id"] == org.id
    assert created["is_default"] is False
    assert created["in_use"] is False
    assert created["bands"] == [
        {"min_percent": 0.0, "max_percent": 40.0, "grade": "F", "grade_point": 0.0, "is_pass": False},
        {"min_percent": 40.0, "max_percent": 100.0, "grade": "P", "grade_point": 6.0, "is_pass": True},
    ]
    assert ok(client.get(f"{URL}/{created['id']}", headers=h)) == created
    assert ok(client.get(URL, headers=h)) == {"items": [created], "total": 1}


def test_a_missing_scheme_is_404(client, h):
    err(client.get(f"{URL}/{uid()}", headers=h), 404, "grading_scheme_not_found")
    err(client.put(f"{URL}/{uid()}", json=grading_body(), headers=h), 404, "grading_scheme_not_found")
    err(client.post(f"{URL}/{uid()}/set-default", headers=h), 404, "grading_scheme_not_found")
    err(client.get(f"{URL}/not-a-uuid", headers=h), 404, "grading_scheme_not_found")


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"bands": BANDS}, "missing_field", "name"),
        ({"name": "x"}, "missing_field", "bands"),
        ({"name": "x", "bands": BANDS, "is_default": True}, "unknown_field", "is_default"),
        ({"name": " ", "bands": BANDS}, "invalid_text", "name"),
        ({"name": "x", "bands": "A"}, "invalid_bands", "bands"),
        ({"name": "x", "bands": []}, "no_bands", "bands"),
        ({"name": "x", "bands": ["A"]}, "invalid_band", "bands[0]"),
        (
            {"name": "x", "bands": [{**BANDS[0], "min_percent": 50, "max_percent": 40}]},
            "invalid_band",
            "bands[0].max_percent",
        ),
        ({"name": "x", "bands": [{**BANDS[0], "max_percent": 101}]}, "above_maximum", "bands[0].max_percent"),
        ({"name": "x", "bands": [{**BANDS[0], "min_percent": -1}]}, "below_minimum", "bands[0].min_percent"),
        ({"name": "x", "bands": [{**BANDS[0], "grade_point": -1}]}, "below_minimum", "bands[0].grade_point"),
        ({"name": "x", "bands": [{**BANDS[0], "is_pass": "yes"}]}, "invalid_boolean", "bands[0].is_pass"),
        ({"name": "x", "bands": [{**BANDS[0], "grade": ""}]}, "invalid_text", "bands[0].grade"),
        ({"name": "x", "bands": [BANDS[0], {**BANDS[1], "grade": "F"}]}, "duplicate_grade", "bands"),
    ],
)
def test_invalid_input_is_400_and_creates_nothing(client, h, body, code, field):
    detail = err(client.post(URL, json=body, headers=h), 400, code)
    assert detail["details"]["field"] == field
    assert ok(client.get(URL, headers=h))["total"] == 0


def test_bands_are_validated_one_by_one_but_coverage_is_not_enforced_yet(client, h):
    """The inclusive-boundary rule is unconfirmed (docs/reviewer-decisions.md): gaps and touching bands are accepted."""
    gap = [{**BANDS[0], "max_percent": 30}, {**BANDS[1], "min_percent": 50}]
    assert ok(client.post(URL, json=grading_body("gap", gap), headers=h), 201)["name"] == "gap"
    short = [{**BANDS[1], "min_percent": 60}]
    assert ok(client.post(URL, json=grading_body("short", short), headers=h), 201)["name"] == "short"


def test_replace_swaps_name_and_bands_and_keeps_the_id_and_default(client, h):
    scheme = make_grading(client, h)
    ok(client.post(f"{URL}/{scheme['id']}/set-default", headers=h))
    new_bands = [{"min_percent": 0, "max_percent": 100, "grade": "S", "grade_point": 10, "is_pass": True}]
    replaced = ok(client.put(f"{URL}/{scheme['id']}", json=grading_body("Single", new_bands), headers=h))
    assert replaced["id"] == scheme["id"]
    assert replaced["name"] == "Single"
    assert [b["grade"] for b in replaced["bands"]] == ["S"]
    assert replaced["is_default"] is True
    assert ok(client.get(f"{URL}/{scheme['id']}", headers=h)) == replaced


def test_an_invalid_replace_changes_nothing(client, h):
    scheme = make_grading(client, h)
    err(client.put(f"{URL}/{scheme['id']}", json=grading_body("x", []), headers=h), 400, "no_bands")
    assert ok(client.get(f"{URL}/{scheme['id']}", headers=h)) == scheme


def test_a_scheme_used_by_a_cycle_with_published_results_cannot_change(client, org, h):
    scheme = make_grading(client, h)
    cycle = make_cycle(client, h, scheme["id"])
    ok(client.put(f"{URL}/{scheme['id']}", json=grading_body("still free"), headers=h))  # a draft cycle: allowed
    assert ok(client.get(f"{URL}/{scheme['id']}", headers=h))["in_use"] is False
    with session_for(org.id) as db:  # publication is a later slice: put the cycle at that status directly
        db.get(ExamCycleRow, cycle["id"]).status = "results_published"
        db.commit()
    assert ok(client.get(f"{URL}/{scheme['id']}", headers=h))["in_use"] is True
    assert ok(client.get(URL, headers=h))["items"][0]["in_use"] is True
    detail = err(
        client.put(f"{URL}/{scheme['id']}", json=grading_body("late"), headers=h), 409, "grading_scheme_in_use"
    )
    assert "create a new one" in detail["message"]
    assert ok(client.get(f"{URL}/{scheme['id']}", headers=h))["name"] == "still free"


def test_set_default_moves_the_default_and_there_is_only_one(client, h):
    first, second = make_grading(client, h, "first"), make_grading(client, h, "second")
    assert ok(client.post(f"{URL}/{first['id']}/set-default", headers=h))["is_default"] is True
    assert ok(client.post(f"{URL}/{second['id']}/set-default", headers=h))["is_default"] is True
    items = {s["name"]: s["is_default"] for s in ok(client.get(URL, headers=h))["items"]}
    assert items == {"first": False, "second": True}


def test_setting_the_current_default_again_is_a_no_op(client, org, h):
    scheme = make_grading(client, h)
    ok(client.post(f"{URL}/{scheme['id']}/set-default", headers=h))
    before = len(audit_entries(org.id))
    assert ok(client.post(f"{URL}/{scheme['id']}/set-default", headers=h))["is_default"] is True
    assert len(audit_entries(org.id)) == before


def test_each_organisation_has_its_own_default_and_cannot_see_the_others(client, org, other_org, h):
    mine = make_grading(client, h, "mine")
    other_h = other_org.controller()
    theirs = make_grading(client, other_h, "theirs")
    ok(client.post(f"{URL}/{mine['id']}/set-default", headers=h))
    ok(client.post(f"{URL}/{theirs['id']}/set-default", headers=other_h))
    assert ok(client.get(f"{URL}/{mine['id']}", headers=h))["is_default"] is True  # not cleared by the other's
    assert [s["name"] for s in ok(client.get(URL, headers=h))["items"]] == ["mine"]
    assert [s["name"] for s in ok(client.get(URL, headers=other_h))["items"]] == ["theirs"]
    for r in (
        client.get(f"{URL}/{theirs['id']}", headers=h),
        client.put(f"{URL}/{theirs['id']}", json=grading_body("hijack"), headers=h),
        client.post(f"{URL}/{theirs['id']}/set-default", headers=h),
    ):
        err(r, 404, "grading_scheme_not_found")
    assert ok(client.get(f"{URL}/{theirs['id']}", headers=other_h))["name"] == "theirs"


def test_each_change_is_audited_and_none_publishes_an_event(client, org):
    user, headers = org.user("examinations-controller")
    scheme = ok(client.post(URL, json=grading_body(), headers=headers), 201)
    ok(client.put(f"{URL}/{scheme['id']}", json=grading_body("renamed"), headers=headers))
    other = make_grading(client, headers, "other")
    ok(client.post(f"{URL}/{scheme['id']}/set-default", headers=headers))
    ok(client.post(f"{URL}/{other['id']}/set-default", headers=headers))
    entries = audit_entries(org.id, scheme["id"])
    by_action = {e.action: e for e in entries}  # the clock is frozen, so rows are told apart by action
    assert sorted(by_action) == [
        "grading_scheme.created",
        "grading_scheme.default_cleared",
        "grading_scheme.default_set",
        "grading_scheme.replaced",
    ]
    assert {e.actor for e in entries} == {user}
    created, replaced = by_action["grading_scheme.created"], by_action["grading_scheme.replaced"]
    assert created.entity_type == "grading_scheme" and created.before is None
    assert created.after["name"] == "10 point" and len(created.after["bands"]) == 2
    assert replaced.before["name"] == "10 point" and replaced.after["name"] == "renamed"
    default_set = by_action["grading_scheme.default_set"]
    assert default_set.before == {"is_default": False} and default_set.after == {"is_default": True}
    cleared = by_action["grading_scheme.default_cleared"]
    assert cleared.before == {"is_default": True} and cleared.after == {"is_default": False}
    assert all(e.organisation_id == org.id for e in entries)
    assert all_outbox(org.id) == []  # grading-scheme changes publish no event (the contract names none)


def test_reads_write_no_audit_entry(client, org, h):
    scheme = make_grading(client, h)
    count = len(audit_entries(org.id))
    client.get(URL, headers=h)
    client.get(f"{URL}/{scheme['id']}", headers=h)
    client.get(f"{URL}/{uid()}", headers=h)
    assert len(audit_entries(org.id)) == count


def test_a_cycle_can_use_a_scheme_only_of_its_own_organisation(client, other_org, h):
    theirs = make_grading(client, other_org.controller())
    err(
        client.post(f"{BASE}/exam-cycles", json=cycle_body(grading_scheme_id=theirs["id"]), headers=h),
        422,
        "unknown_grading_scheme",
    )
