"""Preparing, superseding and recording a manual filing, with the events each state change publishes."""

import uuid
from datetime import date, timedelta

from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_government_portals.domain.models import Package, PackageFile
from gp_support import load_case, outbox, prepare
from sqlalchemy import func, select


def _record(adapter, org, docs, pid, **kw):
    ack = docs.put(org.id, filename="ack.pdf", content_type="application/pdf", content=b"%PDF acknowledgement")
    args = {
        "package_id": pid,
        "submitted_on": date.today().isoformat(),
        "submitted_by": org.admin_id,
        "portal_reference": "AISHE-2025-26-C-12345",
        "acknowledgement_document_id": ack,
    }
    args.update(kw)
    return adapter.record_manual_submission(org.ctx("aishe"), **args)


def test_prepare_returns_files_checklist_and_a_stored_package(adapter, docs, org):
    r = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="filing-1")
    out = r.output
    assert out["status"] == "prepared" and uuid.UUID(out["package_id"])
    assert [f["role"] for f in out["files"]] == ["keying_sheet", "bundle"]
    assert [s["step"] for s in out["checklist"]] == list(range(1, len(out["checklist"]) + 1))
    assert all({"step", "detail", "portal_section"} == set(s) for s in out["checklist"])
    for f in out["files"]:
        assert docs.get(org.id, f["document_id"]).filename == f["filename"]
    got = adapter.get_package(org.ctx("aishe"), package_id=out["package_id"]).output
    assert got["status"] == "prepared" and got["form_code"] == "aishe.dcf-ii" and got["portal_reference"] is None


def test_preparing_again_for_the_same_key_supersedes_the_previous_package(adapter, docs, org):
    first = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="same").output["package_id"]
    second = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="same").output["package_id"]
    assert first != second
    assert adapter.get_package(org.ctx("aishe"), package_id=first).output["status"] == "superseded"
    assert adapter.get_package(org.ctx("aishe"), package_id=second).output["status"] == "prepared"
    (event,) = [e for e in outbox(org.id, "government-portals.package.prepared") if e.payload["package_id"] == second]
    assert event.payload["superseded_package_id"] == first


def test_an_invalid_package_is_recorded_and_superseded_by_a_corrected_one(adapter, docs, org):
    bad = load_case("aishe-dcf-ii")
    bad["data"]["finance"]["salary_expenditure"] = 10**11
    first = prepare(adapter, org, docs, bad, key="fix-me")
    assert first.output["status"] == "invalid"
    second = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="fix-me")
    assert second.output["status"] == "prepared"
    assert adapter.get_package(org.ctx("aishe"), package_id=first.output["package_id"]).output["status"] == "superseded"


def test_record_manual_submission_keeps_the_reference_and_the_acknowledgement(adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="rec-1").output["package_id"]
    r = _record(adapter, org, docs, pid)
    assert r.output == {"package_id": pid, "status": "acknowledged"} and r.provider_reference == "AISHE-2025-26-C-12345"
    got = adapter.get_package(org.ctx("aishe"), package_id=pid).output
    assert got["portal_reference"] == "AISHE-2025-26-C-12345" and got["submitted_on"] == date.today().isoformat()
    (event,) = outbox(org.id, "government-portals.package.filed")
    assert (
        event.payload["package_id"] == pid
        and event.payload["submitted_by"] == org.admin_id
        and event.actor == org.admin_id
    )


def test_without_an_acknowledgement_the_package_is_uploaded_manually(adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="rec-2").output["package_id"]
    r = _record(adapter, org, docs, pid, acknowledgement_document_id=None)
    assert r.output["status"] == "uploaded_manually"


def test_recording_twice_or_on_a_superseded_or_invalid_package_is_a_conflict(adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="rec-3").output["package_id"]
    assert _record(adapter, org, docs, pid).ok
    assert _record(adapter, org, docs, pid).error.code == "conflict"
    old = prepare(adapter, org, docs, load_case("aishe-dcf-i"), key="rec-4").output["package_id"]
    prepare(adapter, org, docs, load_case("aishe-dcf-i"), key="rec-4")
    assert _record(adapter, org, docs, old).error.code == "conflict"
    bad = load_case("aishe-dcf-i")
    bad["data"]["finance"]["salary_expenditure"] = 10**11
    invalid = prepare(adapter, org, docs, bad, key="rec-5").output["package_id"]
    assert _record(adapter, org, docs, invalid).error.code == "conflict"
    assert len(outbox(org.id, "government-portals.package.filed")) == 1  # only the one real filing


def test_a_filed_package_is_read_only(adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="locked").output["package_id"]
    _record(adapter, org, docs, pid)
    again = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="locked")
    assert again.error.code == "conflict"
    assert adapter.get_package(org.ctx("aishe"), package_id=pid).output["status"] == "acknowledged"


def test_record_validates_its_input(adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="rec-6").output["package_id"]
    tomorrow_plus = (date.today() + timedelta(days=5)).isoformat()
    cases = [
        {"package_id": "nope"},
        {"submitted_by": "nope"},
        {"submitted_on": tomorrow_plus},
        {"submitted_on": "1999-01-01"},
        {"submitted_on": "2025-13-45"},
        {"submitted_on": 20251201},
        {"portal_reference": ""},
        {"portal_reference": "x" * 101},
        {"portal_reference": "bad;reference"},
        {"acknowledgement_document_id": "nope"},
        {"acknowledgement_document_id": str(uuid.uuid4())},  # no such document
    ]
    for override in cases:
        r = _record(adapter, org, docs, pid, **override)
        assert r.error and r.error.code == "invalid_request", override
    assert adapter.get_package(org.ctx("aishe"), package_id=pid).output["status"] == "prepared"


def test_an_acknowledgement_from_another_organisation_is_refused(adapter, docs, org, other_org):
    pid = prepare(adapter, org, docs, load_case("aishe-dcf-ii"), key="rec-7").output["package_id"]
    theirs = docs.put(other_org.id, filename="a.pdf", content_type="application/pdf", content=b"x")
    r = _record(adapter, org, docs, pid, acknowledgement_document_id=theirs)
    assert r.error.code == "invalid_request"


def test_unknown_package_is_not_found(adapter, org):
    ctx = org.ctx("aishe")
    unknown = str(uuid.uuid4())
    assert adapter.get_package(ctx, package_id=unknown).error.code == "not_found"
    assert adapter.submit(ctx, package_id=unknown).error.code == "not_found"
    r = adapter.record_manual_submission(
        ctx, package_id=unknown, submitted_on="2026-01-01", submitted_by=org.admin_id, portal_reference="R1"
    )
    assert r.error.code == "not_found"


def test_submit_answers_manual_action_required_for_every_form(adapter, docs, org):
    for case_name, provider in (("aishe-dcf-i", "aishe"), ("nirf-dcs-overall", "nirf"), ("naac-ssr", "naac")):
        pid = prepare(adapter, org, docs, load_case(case_name)).output["package_id"]
        r = adapter.submit(org.ctx(provider), package_id=pid)
        assert r.error.code == "manual_action_required" and r.error.retryable is False


def test_files_are_rows_of_the_package_and_the_data_is_not_kept(adapter, docs, org):
    pid = prepare(adapter, org, docs, load_case("naac-ssr"), key="rows").output["package_id"]
    with platform_scope(), SessionLocal() as db:
        files = db.execute(select(PackageFile).where(PackageFile.package_id == pid)).scalars().all()
        assert {f.role for f in files} == {"keying_sheet", "upload", "evidence", "bundle"}
        assert {f.metric for f in files if f.role == "evidence"} == {"1.1.1", "2.6.3"}
        pkg = db.get(Package, pid)
        assert "criteria" not in repr(pkg.issues) and pkg.caller_reference == "rows"
        assert db.execute(select(func.count()).select_from(Package).where(Package.package_key == "rows")).scalar() == 1


def test_caller_fields_are_kept_when_given(adapter, docs, org):
    pid = prepare(
        adapter,
        org,
        docs,
        load_case("aishe-dcf-ii"),
        key="c1",
        caller={"module": "regulatory-reports", "reference": "filing-77"},
    ).output["package_id"]
    with platform_scope(), SessionLocal() as db:
        pkg = db.get(Package, pid)
        assert (pkg.caller_module, pkg.caller_reference) == ("regulatory-reports", "filing-77")


def test_package_keys_are_bounded(adapter, docs, org):
    for key in ("", "x" * 101, "has space", "a/b", "ü"):
        r = prepare(adapter, org, docs, load_case("aishe-dcf-i"), key=key)
        assert r.error and r.error.code == "invalid_request", key
