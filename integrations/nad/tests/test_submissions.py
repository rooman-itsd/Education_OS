"""record_manual_upload, get_submission and verify_learner_id."""

import uuid
from datetime import timedelta

from eos_nad.domain.models import Submission
from nad_support import awards_batch, credits_batch, ctx, err, ok, rows


def prepared(adapter, org, op="publish_awards", batch=None):
    return ok(adapter.invoke(op, ctx(org), batch or (awards_batch() if op == "publish_awards" else credits_batch())))


def upload(sid, **kw):
    body = {
        "submission_id": sid,
        "uploaded_on": "2026-11-05",
        "uploaded_by": str(uuid.uuid4()),
        "portal_reference": "NAD-REF-778899",
    }
    body.update(kw)
    return body


def test_recording_the_upload_moves_the_submission_to_uploaded_manually(adapter, documents, org):
    sid = prepared(adapter, org)["submission_id"]
    ack, _ = documents.add(org.id, b"%PDF acknowledgement")
    body = upload(sid, acknowledgement_document_id=ack)
    assert ok(adapter.invoke("record_manual_upload", ctx(org), body)) == {
        "submission_id": sid,
        "status": "uploaded_manually",
    }
    [sub] = rows(Submission, org.id)
    assert (sub.status, sub.portal_reference, str(sub.uploaded_on), sub.uploaded_by) == (
        "uploaded_manually",
        "NAD-REF-778899",
        "2026-11-05",
        body["uploaded_by"],
    )
    assert sub.acknowledgement_document_id == ack
    got = ok(adapter.invoke("get_submission", ctx(org), {"submission_id": sid}))
    assert got["status"] == "uploaded_manually" and got["submission_id"] == sid and got["updated_at"]


def test_recording_the_same_facts_again_changes_nothing_but_other_facts_conflict(adapter, org):
    sid = prepared(adapter, org)["submission_id"]
    body = upload(sid)
    first = ok(adapter.invoke("record_manual_upload", ctx(org), body))
    assert ok(adapter.invoke("record_manual_upload", ctx(org), body)) == first
    assert (
        err(adapter.invoke("record_manual_upload", ctx(org), {**body, "portal_reference": "OTHER"}))["code"]
        == "conflict"
    )


def test_only_a_prepared_submission_can_be_recorded(adapter, org):
    bad = awards_batch(batch_key="bad")
    bad["records"][0]["learner"]["apaar_id"] = "1"
    rejected = ok(adapter.invoke("publish_awards", ctx(org), bad))["submission_id"]
    assert err(adapter.invoke("record_manual_upload", ctx(org), upload(rejected)))["code"] == "conflict"
    assert err(adapter.invoke("record_manual_upload", ctx(org), upload(str(uuid.uuid4()))))["code"] == "not_found"


def test_the_upload_date_and_acknowledgement_are_checked(adapter, org, now):
    sid = prepared(adapter, org)["submission_id"]
    future = (now + timedelta(days=2)).date().isoformat()
    past = (now - timedelta(days=30)).date().isoformat()
    for bad in ({"uploaded_on": future}, {"uploaded_on": past}, {"acknowledgement_document_id": str(uuid.uuid4())},
                {"portal_reference": ""}, {"portal_reference": "r" * 101}, {"uploaded_on": "yesterday"}, {"uploaded_by": "me"}):  # fmt: skip
        assert err(adapter.invoke("record_manual_upload", ctx(org), upload(sid, **bad)))["code"] == "invalid_request", (
            bad
        )
    assert rows(Submission, org.id)[0].status == "manual_action_required"


def test_credits_submissions_are_recorded_the_same_way(adapter, org):
    sid = prepared(adapter, org, "publish_credits")["submission_id"]
    assert ok(adapter.invoke("record_manual_upload", ctx(org), upload(sid)))["status"] == "uploaded_manually"


def test_get_submission_reports_local_state_with_row_errors(adapter, org):
    bad = awards_batch()
    bad["records"][1]["learner"]["apaar_id"] = "x"
    sid = ok(adapter.invoke("publish_awards", ctx(org), bad))["submission_id"]
    got = ok(adapter.invoke("get_submission", ctx(org), {"submission_id": sid}))
    assert got["status"] == "rejected" and got["accepted_rows"] == 0
    assert got["rejected_rows"] == [{"row": 2, "field": "learner.apaar_id", "code": "apaar_invalid"}]
    assert err(adapter.invoke("get_submission", ctx(org), {"submission_id": str(uuid.uuid4())}))["code"] == "not_found"
    assert err(adapter.invoke("get_submission", ctx(org), {"submission_id": "nope"}))["code"] == "invalid_request"


def test_another_organisations_submission_is_not_found(adapter, org, other_org):
    sid = prepared(adapter, org)["submission_id"]
    assert err(adapter.invoke("get_submission", ctx(other_org), {"submission_id": sid}))["code"] == "not_found"
    assert err(adapter.invoke("record_manual_upload", ctx(other_org), upload(sid)))["code"] == "not_found"


def test_verify_learner_id_is_unverifiable_until_the_api_specs_arrive(adapter, org):
    learner = {
        "apaar_id": "123456789012",
        "name": "Asha Rao",
        "date_of_birth": "2004-01-01",
        "person_id": str(uuid.uuid4()),
    }
    assert ok(adapter.invoke("verify_learner_id", ctx(org), {"learner": learner})) == {
        "status": "unverifiable",
        "mismatched_fields": [],
    }
    # whatever the name or date of birth says, never verified, never not_found, never mismatch
    for override in ({"name": "Someone Else"}, {"date_of_birth": "1990-05-05"}, {"apaar_id": "999999999999"}):
        assert (
            ok(adapter.invoke("verify_learner_id", ctx(org), {"learner": {**learner, **override}}))["status"]
            == "unverifiable"
        )
    for live in ("sandbox", "live"):
        assert (
            ok(adapter.invoke("verify_learner_id", ctx(org, mode=live), {"learner": learner}))["status"]
            == "unverifiable"
        )


def test_verify_learner_id_refuses_a_malformed_id(adapter, org):
    for bad in (
        {"apaar_id": "12345"},
        {"apaar_id": "12345678901a"},
        {"apaar_id": ""},
        {"name": ""},
        {"date_of_birth": "not a date"},
    ):
        learner = {"apaar_id": "123456789012", "name": "Asha Rao", "date_of_birth": "2004-01-01", **bad}
        e = err(adapter.invoke("verify_learner_id", ctx(org), {"learner": learner}))
        assert e["code"] == "invalid_request" and "Asha" not in e["detail"]
    assert err(adapter.invoke("verify_learner_id", ctx(org), {}))["code"] == "invalid_request"
