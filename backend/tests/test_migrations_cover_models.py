"""REQ-P2-005：验证 Alembic 迁移文件完整性（最小自动化验收）。

口径：
- Base.metadata.tables 中出现的所有表名，必须在某个迁移文件中出现 create_table(op.create_table)。
- 允许 alembic 内置的 alembic_version 表不在迁移中显式创建。
"""

from __future__ import annotations

from pathlib import Path
import re


def _collect_created_tables() -> set[str]:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    tables: set[str] = set()
    for f in versions_dir.glob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        # 解析：匹配 op.create_table( 允许换行/空格，然后是引号包裹的表名
        for m in re.finditer(r"op\.create_table\(\s*['\"]([^'\"]+)['\"]", text, flags=re.MULTILINE):
            name = (m.group(1) or "").strip()
            if name:
                tables.add(name)
    return tables


def test_alembic_migrations_cover_all_models_tables() -> None:
    # 触发模型导入，确保 metadata 完整
    from app.models.base import Base
    import app.models  # noqa: F401

    metadata_tables = set(Base.metadata.tables.keys())
    created_tables = _collect_created_tables()

    missing = sorted(t for t in metadata_tables if t not in created_tables and t != "alembic_version")
    assert missing == [], f"Missing tables in migrations: {missing}"

