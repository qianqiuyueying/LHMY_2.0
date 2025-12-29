"""stage27 cms content markdown

Revision ID: bc23de45fa67
Revises: ab12cd34ef56
Create Date: 2025-12-22

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "bc23de45fa67"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cms_contents", sa.Column("content_md", sa.Text(), nullable=True, comment="正文（Markdown）"))


def downgrade() -> None:
    op.drop_column("cms_contents", "content_md")


