"""OIDC subject on users (ADR-0006): the `sub` Keycloak issues in the organisation's realm, unique per
organisation. Nullable: users who never signed in through the provider keep NULL.

Revision ID: identity_0002
Revises: identity_0001
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "identity_0002"
down_revision = "identity_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("identity_user", sa.Column("oidc_subject", sa.String(255), nullable=True))
    op.create_index(
        "ix_identity_user_org_oidc_subject", "identity_user", ["organisation_id", "oidc_subject"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_identity_user_org_oidc_subject", table_name="identity_user")
    with op.batch_alter_table("identity_user") as batch:
        batch.drop_column("oidc_subject")
