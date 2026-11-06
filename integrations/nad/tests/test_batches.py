"""publish_awards, correct_awards and publish_credits: row validation (the whole batch is refused with row errors),
idempotency, corrections, templates and bounds."""

import copy
import uuid

from eos_nad.domain.models import LodgedAward, Submission, SubmissionFile
from nad_support import awards_batch, credits_batch, ctx, err, fixture, ok, record, rows, settings


def publish(adapter, org, batch=None, **kw):
    return adapter.invoke("publish_awards", ctx(org, **kw), batch or awards_batch())


def errors_of(result) -> list[tuple]:
    out = ok(result)
    assert out["status"] == "rejected" and out["upload_files"] == [] and out["steps"] == []
    return sorted((e["row"], e["field"], e["code"]) for e in out["row_errors"])


def test_a_valid_batch_returns_manual_action_required_with_the_file_and_steps(adapter, documents, org):
    out = ok(publish(adapter, org))
    assert out["status"] == "manual_action_required" and out["row_errors"] == []
    [f] = out["upload_files"]
    assert documents.get(org.id, f["document_id"]).startswith(b"NAD INSTITUTION ID,")
    assert len(out["steps"]) == 4 and "DEG-UG-01" in out["steps"][2] and "nad.digilocker.gov.in" in out["steps"][1]
    [sub] = rows(Submission, org.id)
    assert (sub.kind, sub.depository, sub.channel, sub.rows) == ("awards", "nad", "manual_upload", 3)
    assert (
        sub.caller_reference == sub.batch_key == "cycle-2026-11:prog-bsc-phy:degree"
        and sub.template_code == "DEG-UG-01"
    )
    assert [a.status for a in rows(LodgedAward, org.id)] == ["lodged"] * 3
    [file] = rows(SubmissionFile, org.id)
    assert file.template_version == "1" and file.rows == 3


def test_nothing_personal_is_kept_in_the_database(adapter, org):
    ok(publish(adapter, org))
    blob = " ".join(repr(vars(r)) for model in (Submission, SubmissionFile, LodgedAward) for r in rows(model, org.id))
    for private in ("Asha", "Rao", "123456789012", "2004-01-01", "EN-2023-0001"):
        assert private not in blob
    assert all(len(a.apaar_id_hash) == 64 for a in rows(LodgedAward, org.id))


def test_one_bad_row_refuses_the_whole_batch_with_row_errors(adapter, documents, org):
    batch = awards_batch()
    batch["records"][1]["learner"]["apaar_id"] = "12345"
    batch["records"][2]["learner"].pop("name")
    result = publish(adapter, org, batch)
    assert errors_of(result) == [(2, "learner.apaar_id", "apaar_invalid"), (3, "learner.name", "missing")]
    assert documents.files == {} and rows(LodgedAward, org.id) == []  # nothing prepared, nothing lodged
    [sub] = rows(Submission, org.id)
    assert (sub.status, sub.rows, sub.rejected_rows, sub.accepted_rows) == ("rejected", 3, 2, 0)


def test_the_row_error_codes(adapter, org):
    cases = {
        "apaar_missing": (lambda r: r["learner"].pop("apaar_id"), "learner.apaar_id"),
        "apaar_invalid": (lambda r: r["learner"].update(apaar_id="12345678901a"), "learner.apaar_id"),
        "missing": (lambda r: r["learner"].pop("date_of_birth"), "learner.date_of_birth"),
        "out_of_range": (lambda r: r["learner"].update(date_of_birth="2999-01-01"), "learner.date_of_birth"),
    }
    for code, (mutate, field) in cases.items():
        batch = awards_batch(batch_key=f"k-{code}", records=[record(1)])
        mutate(batch["records"][0])
        assert errors_of(publish(adapter, org, batch)) == [(1, field, code)], code


def test_result_and_course_rules(adapter, org):
    def go(mutate, expected, award_kind="degree", template="DEG-UG-01"):
        r = record(1)
        mutate(r)
        batch = awards_batch(batch_key=str(uuid.uuid4()), records=[r], award_kind=award_kind, template_code=template)
        assert errors_of(publish(adapter, org, batch)) == expected

    go(lambda r: r["result"].update(cgpa=10.5), [(1, "result.cgpa", "out_of_range")])
    go(lambda r: r["result"].update(percentage=100.5), [(1, "result.percentage", "out_of_range")])
    go(lambda r: r.update(result={"result_status": "pass"}), [(1, "result", "missing")])
    go(lambda r: r["result"].pop("result_status"), [(1, "result.result_status", "missing")])
    go(lambda r: r.pop("result"), [(1, "result", "missing")])
    go(lambda r: r.pop("issued_on"), [(1, "issued_on", "missing")])
    go(lambda r: r.update(issued_on="1950-01-01"), [(1, "issued_on", "out_of_range")])
    go(lambda r: r.pop("award_number"), [(1, "award_number", "missing")])
    go(lambda r: r.update(award_number="bad\x00no"), [(1, "award_number", "invalid")])
    go(lambda r: None, [(1, "courses", "missing")], award_kind="marksheet", template="MS-UG-01")
    course = {"code": "C1", "title": "T", "credits": 4, "grade": "A", "grade_point": 9}
    go(lambda r: r.update(courses=[course] * 13), [(1, "courses", "too_many_courses")])
    go(lambda r: r.update(courses=[{**course, "credits": 31}]), [(1, "courses.1.credits", "out_of_range")])
    go(lambda r: r.update(courses=[{**course, "grade_point": 11}]), [(1, "courses.1.grade_point", "out_of_range")])
    go(lambda r: r.update(courses=[{"code": "C1", "title": "T"}]), [(1, "courses.1.marks", "missing")])
    go(lambda r: r.update(courses=[{**course, "max_marks": 50, "marks": 60}]), [(1, "courses.1.marks", "out_of_range")])
    go(lambda r: r.update(courses=[{**course, "code": " "}]), [(1, "courses.1.code", "missing")])


def test_malformed_records_are_row_errors_not_exceptions(adapter, org):
    batch = awards_batch(
        records=[
            record(1),
            "not an object",
            7,
            None,
            {"learner": "x"},
            {"result": {"cgpa": "NaN"}},
            {"award_number": "a" * 61},
        ]
    )
    errs = errors_of(publish(adapter, org, batch))
    assert (2, "record", "invalid") in errs and (3, "record", "invalid") in errs and (4, "record", "invalid") in errs
    assert any(e[0] == 5 for e in errs) and any(e[0] == 6 and e[1] == "result.cgpa" for e in errs)
    assert any(e[0] == 7 and e[1] == "award_number" for e in errs)
    assert all(e[0] != 1 for e in errs)


def test_nan_and_infinity_are_refused(adapter, org):
    for bad in (float("nan"), float("inf"), float("-inf")):
        r = record(1)
        r["result"]["cgpa"] = bad
        errs = errors_of(publish(adapter, org, awards_batch(batch_key=str(uuid.uuid4()), records=[r])))
        assert errs == [(1, "result.cgpa", "invalid")]


def test_row_errors_are_bounded(adapter, org):
    batch = awards_batch(records=[{} for _ in range(1500)])
    out = ok(publish(adapter, org, batch))
    assert out["status"] == "rejected" and len(out["row_errors"]) == 1000


def test_duplicate_award_numbers_in_a_batch_and_against_earlier_batches(adapter, org):
    batch = awards_batch(records=[record(1), record(2, award_number="DEG-2026-0001")])
    assert errors_of(publish(adapter, org, batch)) == [(2, "award_number", "duplicate")]
    ok(publish(adapter, org))
    again = awards_batch(batch_key="another-batch", records=[record(9, award_number="DEG-2026-0002")])
    assert errors_of(publish(adapter, org, again)) == [(1, "award_number", "already_lodged")]
    other = awards_batch(
        batch_key="a-different-kind",
        award_kind="marksheet",
        template_code="MS-UG-01",
        records=[record(9, award_number="DEG-2026-0002", courses=[{"code": "C", "title": "T", "marks": 5}])],
    )
    assert ok(publish(adapter, org, other))["status"] == "manual_action_required"  # unique per award kind


def test_the_same_batch_again_changes_nothing(adapter, documents, org):
    first, again = ok(publish(adapter, org)), ok(publish(adapter, org))
    assert first == again and len(rows(Submission, org.id)) == 1 and len(documents.files) == 1


def test_the_same_key_with_another_batch_is_a_conflict(adapter, org):
    ok(publish(adapter, org))
    changed = awards_batch(records=[record(1)])
    assert err(publish(adapter, org, changed))["code"] == "conflict"
    assert (
        err(adapter.invoke("publish_credits", ctx(org), credits_batch(batch_key=awards_batch()["batch_key"])))["code"]
        == "conflict"
    )


def test_a_rejected_batch_can_be_resubmitted_fixed_under_the_same_key(adapter, org):
    bad = awards_batch()
    bad["records"][0]["learner"]["apaar_id"] = "1"
    assert ok(publish(adapter, org, bad))["status"] == "rejected"
    assert ok(publish(adapter, org, bad))["status"] == "rejected"  # idempotent while unchanged
    fixed = ok(publish(adapter, org))
    assert fixed["status"] == "manual_action_required"
    [sub] = rows(Submission, org.id)
    assert sub.status == "manual_action_required" and sub.rejected_rows == 0 or sub.rejected_rows is None
    assert len(rows(SubmissionFile, org.id)) == 1


def test_corrections_name_an_award_already_lodged_for_the_same_learner(adapter, org):
    fix = fixture("corrections_batch.json")
    e = err(adapter.invoke("correct_awards", ctx(org), fix))
    assert e["code"] == "not_found" and "row(s) 1 " in e["detail"] and not e["retryable"]
    ok(publish(adapter, org))
    out = ok(adapter.invoke("correct_awards", ctx(org), fix))
    assert out["status"] == "manual_action_required"
    assert [a.status for a in sorted(rows(LodgedAward, org.id), key=lambda a: a.award_number)] == [
        "corrected",
        "lodged",
        "lodged",
    ]
    assert {s.kind for s in rows(Submission, org.id)} == {"awards", "award_corrections"}
    assert rows(Submission, org.id)[0].reason or rows(Submission, org.id)[1].reason
    other = copy.deepcopy(fix)
    other["batch_key"] = "wrong-learner"
    other["records"][0]["learner"]["apaar_id"] = "999999999999"  # not the learner the award was lodged for
    assert errors_of(adapter.invoke("correct_awards", ctx(org), other)) == [(1, "learner.apaar_id", "mismatch")]


def test_correcting_twice_is_allowed_with_a_new_batch_key(adapter, org):
    ok(publish(adapter, org))
    fix = fixture("corrections_batch.json")
    ok(adapter.invoke("correct_awards", ctx(org), fix))
    fix2 = copy.deepcopy(fix)
    fix2["batch_key"] = "second-revaluation"
    fix2["records"][0]["result"]["cgpa"] = 8.7
    assert ok(adapter.invoke("correct_awards", ctx(org), fix2))["status"] == "manual_action_required"


def test_template_and_connection_checks(adapter, org):
    assert err(publish(adapter, org, awards_batch(template_code="NOPE")))["code"] == "invalid_request"
    assert err(publish(adapter, org, awards_batch(award_kind="diploma")))["code"] == "invalid_request"
    wrong_level = awards_batch(programme={**awards_batch()["programme"], "level": "postgraduate"})
    assert err(publish(adapter, org, wrong_level))["code"] == "invalid_request"
    assert err(publish(adapter, org, settings=settings(award_templates=[])))["code"] == "not_configured"
    assert err(publish(adapter, org, settings={"award_templates": "bad"}))["code"] == "not_configured"
    no_id = settings(nad_institution_id=None)
    assert err(publish(adapter, org, mode="live", settings=no_id))["code"] == "not_configured"


def test_live_and_sandbox_need_their_ids_and_pepper(adapter, org, monkeypatch):
    assert ok(publish(adapter, org, mode="sandbox"))["status"] == "manual_action_required"  # no API: same file
    monkeypatch.delenv("NAD_APAAR_HASH_PEPPER")
    e = err(publish(adapter, org, awards_batch(batch_key="x"), mode="live"))
    assert e["code"] == "not_configured" and "PEPPER" in e["detail"]
    e = err(
        adapter.invoke(
            "publish_credits", ctx(org, mode="live", settings=settings(abc_institution_id=None)), credits_batch()
        )
    )
    assert e["code"] == "not_configured"


def test_envelope_input_is_validated_without_echoing_values(adapter, org):
    bad = [
        {"batch_key": ""}, {"batch_key": "x" * 101}, {"batch_key": "has space"}, {"award_kind": "thesis"},
        {"template_code": "bad code"}, {"session": "2025-2026"}, {"session": "2025-27"}, {"session": "2025/26"},
        {"records": []}, {"records": "nope"}, {"records": [{}] * 20001},
        {"programme": {**awards_batch()["programme"], "duration_terms": 0}},
        {"programme": {**awards_batch()["programme"], "name": "n" * 201}},
        {"programme": "BSc"},
    ]  # fmt: skip
    for override in bad:
        e = err(publish(adapter, org, awards_batch(**override)))
        assert e["code"] == "invalid_request", override
        assert "Asha" not in e["detail"] and "123456789012" not in e["detail"]
    assert rows(Submission, org.id) == []


def test_credit_rules(adapter, org):
    def go(mutate, expected):
        b = credits_batch(batch_key=str(uuid.uuid4()))
        mutate(b)
        assert errors_of(adapter.invoke("publish_credits", ctx(org), b)) == expected

    go(
        lambda b: b["records"][0]["courses"][0].update(credits_earned=31),
        [(1, "courses.1.credits_earned", "out_of_range")],
    )
    go(lambda b: b["records"][0]["courses"][0].update(grade_point=11), [(1, "courses.1.grade_point", "out_of_range")])
    go(lambda b: b["records"][0]["courses"][0].pop("completed_on"), [(1, "courses.1.completed_on", "missing")])
    go(
        lambda b: b["records"][0]["courses"][0].update(completed_on="2999-01-01"),
        [(1, "courses.1.completed_on", "out_of_range")],
    )
    go(lambda b: b["records"][0].update(courses=[]), [(1, "courses", "missing")])
    go(lambda b: b["records"][1].pop("programme_code"), [(2, "programme_code", "missing")])
    go(lambda b: b["records"][1]["learner"].pop("apaar_id"), [(2, "learner.apaar_id", "apaar_missing")])
    go(lambda b: b["records"][0]["courses"][1].update(code="PHY301"), [(1, "courses.2.code", "duplicate")])
    go(
        lambda b: b["records"][0]["courses"][0].update(credits_earned=float("inf")),
        [(1, "courses.1.credits_earned", "invalid")],
    )


def test_credits_output_and_status(adapter, documents, org):
    out = ok(adapter.invoke("publish_credits", ctx(org), credits_batch()))
    assert out["status"] == "manual_action_required" and len(out["steps"]) == 4 and "abc.gov.in" in out["steps"][1]
    [sub] = rows(Submission, org.id)
    assert (sub.kind, sub.depository, sub.term, sub.rows, sub.template_code) == ("credits", "abc", "5", 2, None)
    assert rows(LodgedAward, org.id) == []  # credits are not awards
    assert err(adapter.invoke("publish_credits", ctx(org), credits_batch(term="")))["code"] == "invalid_request"


def test_one_organisation_cannot_see_or_collide_with_another(adapter, org, other_org):
    ok(publish(adapter, org))
    # an award lodged by `org` does not exist for `other_org`, so it cannot be corrected there
    e = err(adapter.invoke("correct_awards", ctx(other_org), fixture("corrections_batch.json")))
    assert e["code"] == "not_found"
    out = ok(publish(adapter, other_org))  # the same batch_key and award numbers in another organisation
    assert out["status"] == "manual_action_required"
    assert len(rows(Submission, org.id)) == 1 and len(rows(Submission, other_org.id)) == 1
