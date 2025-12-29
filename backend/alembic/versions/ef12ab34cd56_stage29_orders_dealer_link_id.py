"""stage29: orders add dealer_link_id for dealer attribution tracing (H5).

Revision ID: ef12ab34cd56
Revises: cd34ef56ab78
Create Date: 2025-12-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ef12ab34cd56"
down_revision = "cd34ef56ab78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("dealer_link_id", sa.String(length=36), nullable=True, comment="投放链接ID（dealerLinkId）"))
    op.create_index(op.f("ix_orders_dealer_link_id"), "orders", ["dealer_link_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_dealer_link_id"), table_name="orders")
    op.drop_column("orders", "dealer_link_id")

