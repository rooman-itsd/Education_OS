from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

STATUSES = ("pending_verification", "pending_approval", "active", "suspended", "archived")


class Organisation(Base, TimestampMixin):
    """The tenant. The one table that is not itself tenant-scoped, because it defines the tenants."""

    __tablename__ = "tenancy_organisation"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    academy_type: Mapped[str] = mapped_column(String(60))
    # A package change the organisation asked for, waiting for super admin approval.
    requested_academy_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_verification")
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    # Deletion with retention (DPDP). A super admin's DELETE archives the organisation and sets delete_after;
    # the purge removes every row of the organisation once that moment has passed; a restore before the purge
    # puts status_before_deletion back and clears the three fields.
    delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_before_deletion: Mapped[str | None] = mapped_column(String(30), nullable=True)

    def to_dict(self, **extra) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "academy_type": self.academy_type,
            "requested_academy_type": self.requested_academy_type,
            "country": self.country,
            "status": self.status,
            "status_reason": self.status_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delete_after": self.delete_after.isoformat() if self.delete_after else None,
            "deletion_requested_by": self.deletion_requested_by,
            "deletion_requested_at": self.deletion_requested_at.isoformat() if self.deletion_requested_at else None,
            **extra,
        }


class RegistrationToken(Base, TenantMixin):
    __tablename__ = "tenancy_registration_token"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class OrganisationModule(Base, TenantMixin):
    """Per-organisation module state: an admin toggle (enabled) or a super-admin override (override)."""

    __tablename__ = "tenancy_organisation_module"
    __table_args__ = (UniqueConstraint("organisation_id", "module", name="uq_tenancy_org_module"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    module: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    override: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
