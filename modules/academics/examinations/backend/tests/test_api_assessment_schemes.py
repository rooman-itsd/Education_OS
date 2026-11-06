"""listAssessmentSchemes, createAssessmentScheme, getAssessmentScheme, replaceAssessmentScheme,
activateAssessmentScheme."""

from decimal import Decimal

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    VIEWER,
    all_outbox,
    assessment_body,
    audit_entries,
    component,
    err,
    make_assessment,
    ok,
    uid,
)

URL = f"{BASE}/assessment-schemes"


def activate(client, headers, scheme_id, status=200):
    return ok(client.post(f"{URL}/{scheme_id}/activate", headers=headers), status)


def test_the_operations_need_their_keys(client, org):
    _, head = org.user(HEAD)  # write-department
    _, viewer = org.user(VIEWER)
    _, faculty = org.user(FACULTY)  # reads assessment schemes
    _, student = org.user(STUDENT)
    scheme = make_assessment(client, org.controller())
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=assessment_body()).status_code == 401
    for headers in (head, viewer, faculty):
        assert client.get(URL, headers=headers).status_code == 200
        assert client.get(f"{URL}/{scheme['id']}", headers=headers).status_code == 200
    assert client.get(URL, headers=student).status_code == 403
    assert client.get(f"{URL}/{scheme['id']}", headers=student).status_code == 403
    for headers in (viewer, faculty, student):  # reading is not writing
        responses = (
            client.post(URL, json=assessment_body(), headers=headers),
            client.put(f"{URL}/{scheme['id']}", json=assessment_body(scheme["course_offering_id"]), headers=headers),
            client.post(f"{URL}/{scheme['id']}/activate", headers=headers),
        )
        for r in responses:
            assert r.status_code == 403
            assert r.json()["detail"]["code"] == "forbidden"
    # write-department is the key the contract names; write-all widens it (department scope is pending, Q13)
    assert ok(client.post(URL, json=assessment_body(), headers=head), 201)["status"] == "draft"


def test_create_makes_a_draft_version_1_and_it_reads_back(client, org, h):
    offering = uid()
    body = assessment_body(
        offering,
        [
            component("INT", 40, kind="continuous", pass_marks=None),
            component("END", 60, pass_marks=35, max_marks=100),
        ],
        pass_percent=45.5,
    )
    created = ok(client.post(URL, json=body, headers=h), 201)
    assert created["organisation_id"] == org.id
    assert created["course_offering_id"] == offering
    assert (created["version"], created["status"], created["pass_percent"]) == (1, "draft", 45.5)
    by_code = {c["code"]: c for c in created["components"]}
    assert by_code["INT"]["pass_marks"] is None and by_code["END"]["pass_marks"] == 35.0
    assert by_code["END"]["weightage_percent"] == 60.0 and by_code["INT"]["kind"] == "continuous"
    assert all(c["id"] for c in created["components"])
    assert ok(client.get(f"{URL}/{created['id']}", headers=h)) == created


def test_a_draft_may_be_incomplete_but_activation_checks_the_weightages(client, h):
    draft = make_assessment(client, h, components=[component("END", 70)])  # adds up to 70: allowed as a draft
    detail = err(client.post(f"{URL}/{draft['id']}/activate", headers=h), 422, "weightage_not_100")
    assert Decimal(detail["details"]["total"]) == 70
    assert ok(client.get(f"{URL}/{draft['id']}", headers=h))["status"] == "draft"


def test_activation_needs_weightages_of_exactly_100(client, h):
    for weights, code in (([30, 30, 30], "weightage_not_100"), ([60, 50], "weightage_not_100")):
        parts = [component(f"C{i}", w) for i, w in enumerate(weights)]
        draft = make_assessment(client, h, components=parts)
        err(client.post(f"{URL}/{draft['id']}/activate", headers=h), 422, code)
    exact = make_assessment(client, h, components=[component("A", 33.33), component("B", 33.33), component("C", 33.34)])
    assert activate(client, h, exact["id"])["status"] == "active"  # exact decimal sums: no float drift


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"course_offering_id": "x"}, "invalid_id", "course_offering_id"),
        ({"pass_percent": 101}, "above_maximum", "pass_percent"),
        ({"pass_percent": -1}, "below_minimum", "pass_percent"),
        ({"pass_percent": "40"}, "invalid_number", "pass_percent"),
        ({"components": []}, "no_components", "components"),
        ({"components": "x"}, "invalid_components", "components"),
        ({"components": ["x"]}, "invalid_component", "components[0]"),
        ({"components": [component(weightage=0)]}, "invalid_weightage", "components[0].weightage_percent"),
        ({"components": [component(weightage=101)]}, "above_maximum", "components[0].weightage_percent"),
        ({"components": [component(max_marks=0)]}, "invalid_max_marks", "components[0].max_marks"),
        ({"components": [component(kind="viva")]}, "invalid_choice", "components[0].kind"),
        ({"components": [component(pass_marks=101)]}, "invalid_pass_marks", "components[0].pass_marks"),
        ({"components": [component(code=" ")]}, "invalid_text", "components[0].code"),
        ({"components": [component("A", 50), component("A", 50)]}, "duplicate_component_code", "components"),
        ({"surprise": 1}, "unknown_field", "surprise"),
    ],
)
def test_invalid_input_is_400_and_creates_nothing(client, org, h, change, code, field):
    detail = err(client.post(URL, json={**assessment_body(), **change}, headers=h), 400, code)
    assert detail["details"]["field"] == field
    assert ok(client.get(URL, headers=h))["total"] == 0
    assert audit_entries(org.id) == []


@pytest.mark.parametrize("missing", ["course_offering_id", "pass_percent", "components"])
def test_a_missing_field_is_400(client, h, missing):
    body = assessment_body()
    del body[missing]
    assert err(client.post(URL, json=body, headers=h), 400, "missing_field")["details"]["field"] == missing


def test_each_new_scheme_of_an_offering_takes_the_next_version_and_earlier_ones_are_kept(client, h):
    offering = uid()
    v1 = make_assessment(client, h, offering)
    activate(client, h, v1["id"])
    v2 = make_assessment(client, h, offering, [component("A", 50), component("B", 50)])
    assert (v1["version"], v2["version"]) == (1, 2)
    assert make_assessment(client, h)["version"] == 1  # another offering counts from 1
    assert ok(client.get(f"{URL}/{v1['id']}", headers=h)) == {**v1, "status": "active"}
    versions = ok(client.get(f"{URL}?course_offering_id={offering}", headers=h))["items"]
    assert [(s["version"], s["status"]) for s in versions] == [(1, "active"), (2, "draft")]


def test_activating_supersedes_the_previous_active_scheme_and_keeps_it_as_it_was(client, org, h):
    offering = uid()
    v1 = make_assessment(client, h, offering)
    activate(client, h, v1["id"])
    v2 = make_assessment(client, h, offering, [component("A", 50), component("B", 50)], pass_percent=50)
    assert activate(client, h, v2["id"])["status"] == "active"
    old = ok(client.get(f"{URL}/{v1['id']}", headers=h))
    assert old["status"] == "superseded"
    assert {k: old[k] for k in ("version", "pass_percent", "components")} == {
        k: v1[k] for k in ("version", "pass_percent", "components")
    }  # content and component ids preserved
    active = ok(client.get(f"{URL}?course_offering_id={offering}&status=active", headers=h))
    assert [s["id"] for s in active["items"]] == [v2["id"]] and active["total"] == 1
    # the third version supersedes the second; the first stays superseded
    v3 = make_assessment(client, h, offering)
    activate(client, h, v3["id"])
    statuses = {
        s["version"]: s["status"] for s in ok(client.get(f"{URL}?course_offering_id={offering}", headers=h))["items"]
    }
    assert statuses == {1: "superseded", 2: "superseded", 3: "active"}
    actions = sorted(e.action for e in audit_entries(org.id, v1["id"]))
    assert actions == ["assessment_scheme.activated", "assessment_scheme.created", "assessment_scheme.superseded"]


def test_activating_leaves_other_offerings_alone(client, h):
    first, second = make_assessment(client, h), make_assessment(client, h)
    activate(client, h, first["id"])
    activate(client, h, second["id"])
    assert ok(client.get(f"{URL}/{first['id']}", headers=h))["status"] == "active"


def test_only_a_draft_can_be_activated(client, h):
    offering = uid()
    v1 = make_assessment(client, h, offering)
    activate(client, h, v1["id"])
    err(client.post(f"{URL}/{v1['id']}/activate", headers=h), 409, "scheme_not_draft")  # active
    v2 = make_assessment(client, h, offering)
    activate(client, h, v2["id"])
    err(client.post(f"{URL}/{v1['id']}/activate", headers=h), 409, "scheme_not_draft")  # superseded
    assert ok(client.get(f"{URL}/{v2['id']}", headers=h))["status"] == "active"


def test_replace_a_draft_keeps_its_id_version_and_matching_component_ids(client, h):
    offering = uid()
    draft = make_assessment(client, h, offering, [component("A", 50), component("B", 50)])
    ids = {c["code"]: c["id"] for c in draft["components"]}
    body = assessment_body(offering, [component("A", 40, name="Renamed"), component("C", 60)], pass_percent=55)
    replaced = ok(client.put(f"{URL}/{draft['id']}", json=body, headers=h))
    assert (replaced["id"], replaced["version"], replaced["status"]) == (draft["id"], 1, "draft")
    assert replaced["pass_percent"] == 55.0
    by_code = {c["code"]: c for c in replaced["components"]}
    assert sorted(by_code) == ["A", "C"]
    assert (
        by_code["A"]["id"] == ids["A"]
        and by_code["A"]["name"] == "Renamed"
        and by_code["A"]["weightage_percent"] == 40.0
    )
    assert by_code["C"]["id"] != ids["B"]
    assert ok(client.get(f"{URL}/{draft['id']}", headers=h)) == replaced


def test_replace_refuses_an_active_or_superseded_scheme(client, h):
    offering = uid()
    v1 = make_assessment(client, h, offering)
    activate(client, h, v1["id"])
    err(client.put(f"{URL}/{v1['id']}", json=assessment_body(offering), headers=h), 409, "scheme_not_draft")
    v2 = make_assessment(client, h, offering)
    activate(client, h, v2["id"])
    err(client.put(f"{URL}/{v1['id']}", json=assessment_body(offering), headers=h), 409, "scheme_superseded")
    assert ok(client.get(f"{URL}/{v1['id']}", headers=h))["status"] == "superseded"


def test_replace_cannot_move_a_scheme_to_another_offering_and_a_bad_replace_changes_nothing(client, h):
    draft = make_assessment(client, h)
    err(client.put(f"{URL}/{draft['id']}", json=assessment_body(uid()), headers=h), 400, "course_offering_immutable")
    bad = assessment_body(draft["course_offering_id"], [component("X", 0)])
    err(client.put(f"{URL}/{draft['id']}", json=bad, headers=h), 400, "invalid_weightage")
    assert ok(client.get(f"{URL}/{draft['id']}", headers=h)) == draft


def test_locked_marks_are_never_taken_from_the_request(client, h):
    """No marks exist yet, so nothing can be locked; a request field claiming otherwise is refused, not trusted."""
    draft = make_assessment(client, h)
    for flag in ("has_locked_marks", "locked_marks", "force"):
        body = {**assessment_body(draft["course_offering_id"]), flag: False}
        err(client.put(f"{URL}/{draft['id']}", json=body, headers=h), 400, "unknown_field")


def test_a_missing_scheme_is_404(client, h):
    err(client.get(f"{URL}/{uid()}", headers=h), 404, "assessment_scheme_not_found")
    err(client.put(f"{URL}/{uid()}", json=assessment_body(), headers=h), 404, "assessment_scheme_not_found")
    err(client.post(f"{URL}/{uid()}/activate", headers=h), 404, "assessment_scheme_not_found")


def test_list_filters_and_pages(client, h):
    offering = uid()
    schemes = [make_assessment(client, h, offering) for _ in range(3)]
    make_assessment(client, h)
    activate(client, h, schemes[0]["id"])
    page = ok(client.get(f"{URL}?course_offering_id={offering}&limit=2&offset=1", headers=h))
    assert page["total"] == 3 and [s["version"] for s in page["items"]] == [2, 3]
    assert ok(client.get(f"{URL}?status=active", headers=h))["total"] == 1
    assert ok(client.get(URL, headers=h))["total"] == 4
    err(client.get(f"{URL}?status=bogus", headers=h), 400, "invalid_choice")
    err(client.get(f"{URL}?course_offering_id=x", headers=h), 400, "invalid_id")
    assert client.get(f"{URL}?limit=0", headers=h).status_code == 422  # the shared Limit query bound


def test_each_organisation_sees_and_changes_only_its_own_schemes(client, org, other_org, h):
    offering = uid()
    mine = make_assessment(client, h, offering)
    other_h = other_org.controller()
    theirs = make_assessment(client, other_h, offering)  # the same offering id: versions are counted per organisation
    assert (mine["version"], theirs["version"]) == (1, 1)
    activate(client, h, mine["id"])
    activate(client, other_h, theirs["id"])  # one active scheme per organisation and offering, not across them
    assert [s["id"] for s in ok(client.get(URL, headers=h))["items"]] == [mine["id"]]
    assert [s["id"] for s in ok(client.get(URL, headers=other_h))["items"]] == [theirs["id"]]
    for r in (
        client.get(f"{URL}/{theirs['id']}", headers=h),
        client.put(f"{URL}/{theirs['id']}", json=assessment_body(offering), headers=h),
        client.post(f"{URL}/{theirs['id']}/activate", headers=h),
    ):
        err(r, 404, "assessment_scheme_not_found")
    assert ok(client.get(f"{URL}/{theirs['id']}", headers=other_h))["status"] == "active"
    assert audit_entries(org.id, theirs["id"]) == []
    assert {e.organisation_id for e in audit_entries(other_org.id)} == {other_org.id}


def test_each_change_is_audited_with_the_actor_and_publishes_no_event(client, org):
    user, headers = org.user("examinations-controller")
    offering = uid()
    draft = ok(client.post(URL, json=assessment_body(offering), headers=headers), 201)
    ok(client.put(f"{URL}/{draft['id']}", json=assessment_body(offering, pass_percent=50), headers=headers))
    activate(client, headers, draft["id"])
    entries = {e.action: e for e in audit_entries(org.id, draft["id"])}
    assert sorted(entries) == ["assessment_scheme.activated", "assessment_scheme.created", "assessment_scheme.replaced"]
    assert {e.actor for e in entries.values()} == {user}
    assert entries["assessment_scheme.created"].after["version"] == 1
    assert entries["assessment_scheme.replaced"].before["pass_percent"] == "40"
    assert entries["assessment_scheme.replaced"].after["pass_percent"] == "50"
    assert entries["assessment_scheme.activated"].before == {"status": "draft"}
    assert entries["assessment_scheme.activated"].after["status"] == "active"
    assert all_outbox(org.id) == []  # assessment-scheme changes publish no event (the contract names none)
