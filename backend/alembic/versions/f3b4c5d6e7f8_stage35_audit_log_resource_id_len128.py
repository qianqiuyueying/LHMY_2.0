"""stage35: audit log resource_id length to 128.

Revision ID: f3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2025-12-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "audit_logs",
        "resource_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=128),
        existing_nullable=True,
        comment="资源ID",
    )


def downgrade() -> None:
    op.alter_column(
        "audit_logs",
        "resource_id",
        existing_type=sa.String(length=128),
        type_=sa.String(length=36),
        existing_nullable=True,
        comment="资源ID",
    )


