"""一次性初始化管理员账号（生产使用，TASK-P0-005）。

目的：
- 生产环境禁止 ADMIN_INIT_* 自动 seed（请求路径内创建账号）
- 提供一次性脚本创建首个管理员账号，写审计并支持回滚

用法（示例）：
  uv run python scripts/admin_init_once.py create --username admin --password 'YourStrongPass#1' --yes
  uv run python scripts/admin_init_once.py rollback --username admin --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

# Add backend to sys.path
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401  # isort: skip
from app.models.admin import Admin  # isort: skip
from app.models.audit_log import AuditLog  # isort: skip
from app.models.enums import AuditAction, AuditActorType  # isort: skip
from app.services.admin_password_policy import validate_admin_password  # isort: skip
from app.services.password_hashing import hash_password  # isort: skip
from app.utils.db import get_session_factory  # isort: skip
from app.utils.settings import settings  # isort: skip


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    s = str(phone).strip()
    if len(s) < 7:
        return None
    return f"{s[:3]}****{s[-4:]}"


async def _create(*, username: str, password: str) -> int:
    if str(getattr(settings, "app_env", "") or "").strip().lower() != "production":
        print("WARN: 当前 app_env 不是 production，但仍允许执行（按需）。")

    err = validate_admin_password(username=username, new_password=password)
    if err:
        print(f"ERROR: 密码不满足策略：{err}")
        return 2

    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = (await session.scalars(select(Admin).where(Admin.username == username).limit(1))).first()
        if existing is not None:
            print("OK: admin 已存在，跳过创建。")
            return 0

        admin_id = str(uuid4())
        now = datetime.now(tz=UTC).replace(tzinfo=None)
        session.add(
            Admin(
                id=admin_id,
                username=username,
                password_hash=hash_password(password=password),
                status="ACTIVE",
                phone=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin_id,
                action=AuditAction.CREATE.value,
                resource_type="ADMIN",
                resource_id=admin_id,
                summary="BOOTSTRAP 初始化创建管理员账号",
                ip=None,
                user_agent=None,
                metadata_json={"createdBy": "BOOTSTRAP", "username": username, "phoneMasked": _mask_phone(None)},
            )
        )
        await session.commit()

    print("OK: 已创建管理员账号（请妥善保存初始密码）。")
    return 0


async def _rollback(*, username: str) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        admin = (await session.scalars(select(Admin).where(Admin.username == username).limit(1))).first()
        if admin is None:
            print("OK: admin 不存在，无需回滚。")
            return 0

        admin.status = "SUSPENDED"
        session.add(
            AuditLog(
                id=str(uuid4()),
                actor_type=AuditActorType.ADMIN.value,
                actor_id=admin.id,
                action=AuditAction.UPDATE.value,
                resource_type="ADMIN",
                resource_id=admin.id,
                summary="BOOTSTRAP 回滚：禁用管理员账号",
                ip=None,
                user_agent=None,
                metadata_json={"rolledBackBy": "BOOTSTRAP", "username": username, "newStatus": "SUSPENDED"},
            )
        )
        await session.commit()

    print("OK: 已将管理员账号置为 SUSPENDED。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--password", required=True)
    p_create.add_argument("--yes", action="store_true", help="non-interactive confirm")

    p_rb = sub.add_parser("rollback")
    p_rb.add_argument("--username", required=True)
    p_rb.add_argument("--yes", action="store_true", help="non-interactive confirm")

    args = parser.parse_args()
    if not args.yes:
        print("ERROR: 必须显式确认：请追加 --yes")
        return 2

    import asyncio

    if args.cmd == "create":
        return asyncio.run(_create(username=str(args.username).strip(), password=str(args.password)))
    if args.cmd == "rollback":
        return asyncio.run(_rollback(username=str(args.username).strip()))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


