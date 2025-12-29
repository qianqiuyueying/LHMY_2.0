"""stage17: provider onboarding statuses

规格来源：
- specs/health-services-platform/provider-onboarding-v1.md
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "2f1c0b9a6c02"
down_revision = "c7b6a19f3c21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column(
            "infra_commerce_status",
            sa.String(length=16),
            nullable=False,
            server_default="NOT_OPENED",
            comment="基建联防开通状态：NOT_OPENED/OPENED",
        ),
    )
    op.add_column(
        "providers",
        sa.Column(
            "health_card_status",
            sa.String(length=16),
            nullable=False,
            server_default="NOT_APPLIED",
            comment="健行天下开通状态：NOT_APPLIED/SUBMITTED/APPROVED/REJECTED",
        ),
    )
    op.add_column(
        "providers",
        sa.Column("health_card_agreement_accepted_at", sa.DateTime(), nullable=True, comment="健行天下协议勾选时间"),
    )
    op.add_column(
        "providers",
        sa.Column("health_card_submitted_at", sa.DateTime(), nullable=True, comment="健行天下申请提交时间"),
    )
    op.add_column(
        "providers",
        sa.Column("health_card_reviewed_at", sa.DateTime(), nullable=True, comment="健行天下审核时间"),
    )
    op.add_column(
        "providers",
        sa.Column("health_card_review_notes", sa.String(length=512), nullable=True, comment="健行天下审核备注/驳回原因"),
    )

    op.create_index("ix_providers_infra_commerce_status", "providers", ["infra_commerce_status"], unique=False)
    op.create_index("ix_providers_health_card_status", "providers", ["health_card_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_providers_health_card_status", table_name="providers")
    op.drop_index("ix_providers_infra_commerce_status", table_name="providers")

    op.drop_column("providers", "health_card_review_notes")
    op.drop_column("providers", "health_card_reviewed_at")
    op.drop_column("providers", "health_card_submitted_at")
    op.drop_column("providers", "health_card_agreement_accepted_at")
    op.drop_column("providers", "health_card_status")
    op.drop_column("providers", "infra_commerce_status")

