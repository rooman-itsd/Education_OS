"""Own schema `nad_*`. Every table carries organisation_id (TenantMixin) and, on Postgres, a forced tenant_isolation
policy (db/migrations). Learners' rows are NOT kept: the upload file holds them, in platform/documents."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

KINDS = ("awards", "award_corrections", "credits")
STATUSES = (
    "prepared",
    "submitted",
    "accepted",
    "partially_accepted",
    "rejected",
    "manual_action_required",
    "uploaded_manually",
)


def iso(value: datetime | date | None) -> str | None:
    """ISO 8601. Datetimes are UTC; SQLite returns them without a zone, so one is added before formatting."""
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat() if value else None


class Submission(Base, TenantMixin):
    __tablename__ = "nad_submission"
    __table_args__ = (UniqueConstraint("organisation_id", "batch_key", name="uq_nad_submission_batch_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # awards | award_corrections | credits
    depository: Mapped[str] = mapped_column(String(3))  # nad | abc
    channel: Mapped[str] = mapped_column(String(20), default="manual_upload")  # api | manual_upload
    award_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)
    template_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    programme_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    session: Mapped[str] = mapped_column(String(7), index=True)
    term: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    rows: Mapped[int] = mapped_column(Integer, default=0)
    accepted_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejected_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caller_reference: Mapped[str] = mapped_column(String(100))
    batch_key: Mapped[str] = mapped_column(String(100))
    payload_digest: Mapped[str] = mapped_column(String(64))  # SHA-256 of the batch, so a retry is told from a clash
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)  # why a correction was lodged
    steps: Mapped[list] = mapped_column(JSON, default=list)
    row_errors: Mapped[list] = mapped_column(JSON, default=list)  # [{row, field, code}]: never the learner's data
    portal_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploaded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acknowledgement_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "kind": self.kind,
            "depository": self.depository,
            "channel": self.channel,
            "award_kind": self.award_kind,
            "programme_code": self.programme_code,
            "session": self.session,
            "term": self.term,
            "status": self.status,
            "rows": self.rows,
            "accepted_rows": self.accepted_rows,
            "rejected_rows": self.rejected_rows,
            "caller_reference": self.caller_reference,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class SubmissionFile(Base, TenantMixin):
    __tablename__ = "nad_submission_file"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36))
    filename: Mapped[str] = mapped_column(String(200))
    rows: Mapped[int] = mapped_column(Integer)
    template_version: Mapped[str] = mapped_column(String(10))


class LodgedAward(Base, TenantMixin):
    """An award this organisation prepared for NAD, so a duplicate is refused and a correction can name it. The
    APAAR id is kept only as a keyed hash."""

    __tablename__ = "nad_lodged_award"
    __table_args__ = (UniqueConstraint("organisation_id", "award_kind", "award_number", name="uq_nad_lodged_award"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    award_number: Mapped[str] = mapped_column(String(60))
    award_kind: Mapped[str] = mapped_column(String(30))
    person_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    apaar_id_hash: Mapped[str] = mapped_column(String(64))
    submission_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(20), default="lodged")  # lodged | corrected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Used by the Alembic chain (db/migrations) to touch only this adapter's tables.
PREFIX = "nad_"
TABLES = [m.__table__ for m in (Submission, SubmissionFile, LodgedAward)]
