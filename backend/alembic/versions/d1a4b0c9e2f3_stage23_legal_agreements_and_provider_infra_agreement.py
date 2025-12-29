"""stage23: legal agreements + provider infra agreement accepted at

Revision ID: d1a4b0c9e2f3
Revises: c3e2f1a0b9c8
Create Date: 2025-12-21

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a4b0c9e2f3"
down_revision = "c3e2f1a0b9c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_agreements",
        sa.Column("id", sa.String(length=36), nullable=False, comment="协议ID"),
        sa.Column("code", sa.String(length=64), nullable=False, comment="协议唯一编码"),
        sa.Column("title", sa.String(length=256), nullable=False, server_default="", comment="标题"),
        sa.Column("content_html", sa.Text(), nullable=False, comment="HTML 内容"),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="0", comment="版本号"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT", comment="状态：DRAFT/PUBLISHED/OFFLINE"),
        sa.Column("published_at", sa.DateTime(), nullable=True, comment="发布时间"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_legal_agreements_code", "legal_agreements", ["code"], unique=True)

    op.add_column("providers", sa.Column("infra_commerce_agreement_accepted_at", sa.DateTime(), nullable=True, comment="基建联防协议勾选时间"))


def downgrade() -> None:
    op.drop_column("providers", "infra_commerce_agreement_accepted_at")
    op.drop_index("ix_legal_agreements_code", table_name="legal_agreements")
    op.drop_table("legal_agreements")


