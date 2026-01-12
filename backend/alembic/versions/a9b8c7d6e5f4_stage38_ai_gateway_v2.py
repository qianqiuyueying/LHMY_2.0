"""stage38 ai gateway v2 (providers + strategies)

Revision ID: a9b8c7d6e5f4
Revises: 1b2c3d4e5f60
Create Date: 2026-01-08

规格来源：
- specs/health-services-platform/ai-gateway-v2.md
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a9b8c7d6e5f4"
down_revision = "1b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 说明：
    # - docker 启动脚本会反复执行 `alembic upgrade head` 直到成功
    # - 若在异常/中断中“表已创建但版本未写入”，会导致 1050 table exists 卡死
    # 因此这里做防御：若表已存在则跳过创建，保证迁移可收敛到成功状态。

    bind = op.get_bind()
    insp = sa.inspect(bind)

    def _ignore_if_exists(exc: Exception) -> bool:
        # MySQL 常见：1050 Table already exists；1061 Duplicate key name（索引已存在）
        msg = str(exc)
        return ("already exists" in msg) or ("Duplicate key name" in msg) or ("1050" in msg) or ("1061" in msg)

    # 表：即使 has_table 反射异常/假阴性，也不应阻塞迁移；以 try/except 兜底
    if not insp.has_table("ai_providers"):
        try:
            op.create_table(
                "ai_providers",
                sa.Column("id", sa.String(length=36), nullable=False, comment="Provider ID"),
                sa.Column("name", sa.String(length=64), nullable=False, comment="Provider 标识（唯一）"),
                sa.Column("provider_type", sa.String(length=64), nullable=False, comment="Provider 类型"),
                sa.Column("credentials", sa.JSON(), nullable=False, comment="凭证（JSON，禁止返回明文）"),
                sa.Column("endpoint", sa.String(length=512), nullable=True, comment="Endpoint（可选）"),
                sa.Column("extra", sa.JSON(), nullable=False, comment="扩展字段（JSON）"),
                sa.Column(
                    "status",
                    sa.String(length=16),
                    nullable=False,
                    server_default="ENABLED",
                    comment="状态：ENABLED/DISABLED",
                ),
                sa.Column(
                    "created_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    comment="创建时间",
                ),
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    comment="更新时间",
                ),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint("name"),
            )
        except Exception as exc:  # noqa: BLE001
            if not _ignore_if_exists(exc):
                raise

    if insp.has_table("ai_providers"):
        try:
            op.create_index("ix_ai_providers_name", "ai_providers", ["name"], unique=True)
        except Exception as exc:  # noqa: BLE001
            if not _ignore_if_exists(exc):
                raise

    if not insp.has_table("ai_strategies"):
        try:
            op.create_table(
                "ai_strategies",
                sa.Column("id", sa.String(length=36), nullable=False, comment="Strategy ID"),
                sa.Column("scene", sa.String(length=64), nullable=False, comment="场景（scene，唯一）"),
                sa.Column("display_name", sa.String(length=128), nullable=False, server_default="", comment="展示名称"),
                sa.Column("provider_id", sa.String(length=36), nullable=True, comment="绑定的 Provider ID（可切换）"),
                # MySQL: TEXT/JSON 不允许 DEFAULT
                sa.Column("prompt_template", sa.Text(), nullable=False, comment="提示词模板（业务语义）"),
                sa.Column("generation_config", sa.JSON(), nullable=False, comment="生成建议配置（JSON）"),
                sa.Column("constraints", sa.JSON(), nullable=False, comment="业务约束（JSON）"),
                sa.Column(
                    "status",
                    sa.String(length=16),
                    nullable=False,
                    server_default="ENABLED",
                    comment="状态：ENABLED/DISABLED",
                ),
                sa.Column(
                    "created_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    comment="创建时间",
                ),
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    comment="更新时间",
                ),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint("scene"),
            )
        except Exception as exc:  # noqa: BLE001
            if not _ignore_if_exists(exc):
                raise

    if insp.has_table("ai_strategies"):
        try:
            op.create_index("ix_ai_strategies_scene", "ai_strategies", ["scene"], unique=True)
        except Exception as exc:  # noqa: BLE001
            if not _ignore_if_exists(exc):
                raise
        try:
            op.create_index("idx_ai_strategies_provider_id", "ai_strategies", ["provider_id"])
        except Exception as exc:  # noqa: BLE001
            if not _ignore_if_exists(exc):
                raise


def downgrade() -> None:
    op.drop_index("idx_ai_strategies_provider_id", table_name="ai_strategies")
    op.drop_index("ix_ai_strategies_scene", table_name="ai_strategies")
    op.drop_table("ai_strategies")

    op.drop_index("ix_ai_providers_name", table_name="ai_providers")
    op.drop_table("ai_providers")

