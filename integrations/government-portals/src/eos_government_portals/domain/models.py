"""Own schema: every table is prefixed government_portals_ and carries organisation_id with a forced RLS policy.

The data used to prepare a package is not kept (it belongs to the calling module, which can prepare again): only the
package, its files by document id, its checklist, its validation issues and the filing record.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "government_portals_"

STATUSES = ("draft", "prepared", "invalid", "submitted", "uploaded_manually", "acknowledged", "superseded")
FILED_STATUSES = ("submitted", "uploaded_manually", "acknowledged")  # a filed package is read-only
_ACTIVE = text("status != 'superseded'")


def iso(value: datetime | date | None) -> str | None:
    """ISO 8601. SQLite returns datetimes without a zone, so UTC is added before formatting."""
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat() if value else None


class Package(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}package"
    # One live package per caller key: preparing again supersedes the previous one. The database enforces it, so two
    # simultaneous prepares cannot both leave a live package.
    __table_args__ = (
        Index(
            "uq_government_portals_package_live_key",
            "organisation_id",
            "package_key",
            unique=True,
            sqlite_where=_ACTIVE,
            postgresql_where=_ACTIVE,
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    package_key: Mapped[str] = mapped_column(String(100))
    form_code: Mapped[str] = mapped_column(String(64), index=True)
    format_version: Mapped[str] = mapped_column(String(20))
    period: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    caller_module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    caller_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    portal_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    acknowledgement_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "package_key": self.package_key,
            "form_code": self.form_code,
            "period": self.period,
            "status": self.status,
            "portal_reference": self.portal_reference,
            "submitted_on": iso(self.submitted_on),
            "created_at": iso(self.created_at),
        }


class PackageFile(Base, TenantMixin):
    __tablename__ = f"{PREFIX}package_file"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    package_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36))
    filename: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # upload | keying_sheet | website_copy | evidence | bundle
    metric: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def to_dict(self) -> dict:
        return {"document_id": self.document_id, "filename": self.filename, "role": self.role}


TABLES = (Package.__table__, PackageFile.__table__)
