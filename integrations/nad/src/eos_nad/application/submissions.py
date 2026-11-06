"""record_manual_upload, get_submission and verify_learner_id."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import select

from ..domain.errors import AdapterError
from ..domain.models import Submission, iso
from .runtime import Runtime
from .schemas import Context, GetSubmissionInput, RecordUploadInput, VerifyInput


def _find(db, submission_id) -> Submission:
    row = db.scalar(scoped(db, select(Submission).where(Submission.id == str(submission_id)), Submission))
    if row is None:
        raise AdapterError("not_found", "no submission has this id")
    return row


def record_manual_upload(rt: Runtime, ctx: Context, inp: RecordUploadInput) -> tuple[dict, str | None]:
    """A person uploaded the file on the depository's portal. Moves the submission to uploaded_manually. The same
    facts again change nothing; different facts, or a submission with nothing to upload, are a conflict."""
    with rt.db(ctx) as db:
        sub = _find(db, inp.submission_id)
        same = (
            sub.uploaded_on == inp.uploaded_on
            and sub.uploaded_by == str(inp.uploaded_by)
            and sub.portal_reference == inp.portal_reference
            and sub.acknowledgement_document_id
            == (str(inp.acknowledgement_document_id) if inp.acknowledgement_document_id else None)
        )
        if sub.status == "uploaded_manually":
            if same:
                return {"submission_id": sub.id, "status": sub.status}, sub.id
            raise AdapterError("conflict", "this upload was already recorded with different details")
        if sub.status != "manual_action_required":
            raise AdapterError("conflict", f"a {sub.status} submission has no manual upload to record")
        today = rt.clock().date()
        created = sub.created_at.date()
        if inp.uploaded_on > today or inp.uploaded_on < created:
            raise AdapterError("invalid_request", "uploaded_on must be between the day the file was prepared and today")
        if (
            inp.acknowledgement_document_id
            and rt.documents_for(ctx).get(str(ctx.organisation_id), str(inp.acknowledgement_document_id)) is None
        ):
            raise AdapterError("invalid_request", "acknowledgement_document_id is not a document of this organisation")
        sub.status = "uploaded_manually"
        sub.uploaded_on, sub.uploaded_by = inp.uploaded_on, str(inp.uploaded_by)
        sub.portal_reference = inp.portal_reference
        sub.acknowledgement_document_id = (
            str(inp.acknowledgement_document_id) if inp.acknowledgement_document_id else None
        )
        db.commit()
        return {"submission_id": sub.id, "status": sub.status}, sub.id


def get_submission(rt: Runtime, ctx: Context, inp: GetSubmissionInput) -> tuple[dict, str | None]:
    """Local status: neither depository reports back in v1.0 (status_polling is false)."""
    with rt.db(ctx) as db:
        sub = _find(db, inp.submission_id)
        return {
            "submission_id": sub.id,
            "status": sub.status,
            "accepted_rows": sub.accepted_rows,
            "rejected_rows": list(sub.row_errors or []),
            "updated_at": iso(sub.updated_at),
        }, sub.id


def verify_learner_id(rt: Runtime, ctx: Context, inp: VerifyInput) -> tuple[dict, str | None]:
    """No verification API is open to institutions yet, so the honest answer is unverifiable. A well-formed id is
    never called verified, and never called not_found, on a guess."""
    rt.require_mode(ctx, rt.config())
    return {"status": "unverifiable", "mismatched_fields": []}, None
