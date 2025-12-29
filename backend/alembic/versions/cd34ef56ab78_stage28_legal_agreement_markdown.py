"""stage28 legal agreement markdown

Revision ID: cd34ef56ab78
Revises: bc23de45fa67
Create Date: 2025-12-22

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "cd34ef56ab78"
down_revision = "bc23de45fa67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("legal_agreements", sa.Column("content_md", sa.Text(), nullable=True, comment="Markdown 内容"))


def downgrade() -> None:
    op.drop_column("legal_agreements", "content_md")


