"""Add tokens to LinkState for inbound webhook confirmation.

Revision ID: wear_0002
Revises: wear_0001
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "wear_0002"
down_revision = "wear_0001"
branch_labels = None
depends_on = None

P = "wearables_"


def upgrade() -> None:
    op.add_column(f"{P}link_state", sa.Column("tokens", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column(f"{P}link_state", "tokens")
