"""审计覆盖率验收脚本（v1：近 7 天，按 resourceType 覆盖判定）。

规格来源（单一真相来源）：
- specs-prod/admin/security.md#3.1.1 高风险事件覆盖清单（分母）
- specs-prod/admin/observability.md#2.3 覆盖率定义（近 7 天；每类 >=1 条即覆盖）
- specs-prod/admin/tasks.md#TASK-P0-002

用法：
  uv run python scripts/audit_coverage_report.py --days 7 --output specs-prod/admin/evidence/audit-coverage/2025-12-23.md

说明：
- 脚本直接读取 DB（SQLAlchemy async），不依赖启动 FastAPI。
- 若环境变量未配置 DB 连接，会执行失败；请在预发/生产环境运行并提交输出记录。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    # 允许从仓库根目录直接运行：uv run python scripts/audit_coverage_report.py ...
    sys.path.insert(0, str(_BACKEND_DIR))

REQUIRED_RESOURCE_TYPES = [
    "EXPORT_DEALER_ORDERS",
    "DEALER_SETTLEMENT_BATCH",
    "DEALER_SETTLEMENT",
    "ORDER",
    "DEALER_LINK",
    "BOOKING",
]


@dataclass(frozen=True)
class CoverageRow:
    resource_type: str
    count: int


def _load_env_file(path: Path) -> None:
    """最小 .env 解析器：只支持 KEY=VALUE，忽略空行与 # 注释；不覆盖已存在的环境变量。"""
    if not path.exists() or not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if not key:
            continue
        # 兼容 .env 中出现的小写键（例如 mysql_host/mysql_user），同时写入对应的大写 MYSQL_*，
        # 以匹配 pydantic settings 的默认 env 映射规则。
        candidates = [key]
        key_upper = key.upper()
        if key_upper != key:
            candidates.append(key_upper)
        if key.lower().startswith("mysql_"):
            candidates.append("MYSQL_" + key[len("mysql_") :].upper())

        for kk in dict.fromkeys(candidates):  # 去重并保持顺序
            if kk in os.environ and os.environ[kk] != "":
                continue
            os.environ[kk] = val


def _is_running_in_docker() -> bool:
    # Linux 容器一般会有 /.dockerenv；Windows 本地运行会是 False
    try:
        return Path("/.dockerenv").exists()
    except Exception:
        return False


async def _query_counts(*, since_utc_naive: datetime) -> dict[str, int]:
    # 延迟导入：确保命令行参数 / env_file 覆盖在 Settings 实例化之前生效
    import app.models  # noqa: F401
    from app.models.audit_log import AuditLog
    from app.utils.db import get_engine
    from app.utils.db import get_session_factory

    stmt = (
        select(AuditLog.resource_type, func.count().label("cnt"))
        .where(AuditLog.created_at >= since_utc_naive)
        .group_by(AuditLog.resource_type)
    )
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (await session.execute(stmt)).all()
    # 避免 Windows + asyncio.run 退出时出现 aiomysql 连接析构告警
    try:
        await get_engine().dispose()
    except Exception:
        pass
    out: dict[str, int] = {}
    for rt, cnt in rows:
        if rt is None:
            continue
        out[str(rt)] = int(cnt or 0)
    return out


def _render_markdown(*, days: int, since_iso: str, counts: dict[str, int]) -> str:
    covered = []
    missing = []
    for rt in REQUIRED_RESOURCE_TYPES:
        c = int(counts.get(rt, 0))
        if c >= 1:
            covered.append((rt, c))
        else:
            missing.append(rt)

    total = len(REQUIRED_RESOURCE_TYPES)
    covered_n = len(covered)
    pct = (covered_n / total * 100.0) if total else 0.0

    lines: list[str] = []
    lines.append("# 审计覆盖率（v1）验收记录")
    lines.append("")
    lines.append(f"- 时间窗：近 {days} 天（since `{since_iso}`）")
    lines.append(f"- 覆盖判定：每类 `resourceType` 计数 ≥ 1 即覆盖")
    lines.append(f"- 覆盖率：{covered_n}/{total} = {pct:.1f}%")
    lines.append("")
    lines.append("## 1. 分母（高风险事件清单）")
    for rt in REQUIRED_RESOURCE_TYPES:
        lines.append(f"- `{rt}`")
    lines.append("")
    lines.append("## 2. 统计结果")
    lines.append("")
    lines.append("| resourceType | count | covered |")
    lines.append("|---|---:|---|")
    for rt in REQUIRED_RESOURCE_TYPES:
        c = int(counts.get(rt, 0))
        lines.append(f"| `{rt}` | {c} | {'YES' if c >= 1 else 'NO'} |")
    lines.append("")
    lines.append("## 3. 未覆盖清单（需阻断上线/回归）")
    if not missing:
        lines.append("- （无）")
    else:
        for rt in missing:
            lines.append(f"- `{rt}`")
    lines.append("")
    lines.append("## 4. 备注")
    lines.append("- 本记录由脚本自动生成；如需更严格阈值（按天/按环境），需另行拍板升级规格。")
    return "\n".join(lines) + "\n"


async def main_async(days: int, output: Path | None) -> int:
    now = datetime.now(tz=UTC)
    since = now - timedelta(days=days)
    # created_at 为 naive datetime（项目内普遍以 UTC naive 存储）
    since_naive = since.replace(tzinfo=None)
    try:
        counts = await _query_counts(since_utc_naive=since_naive)
        md = _render_markdown(days=days, since_iso=since.isoformat(), counts=counts)
        print(md)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(md, encoding="utf-8")
        return 0
    except Exception as e:
        # 连接失败等场景：仍然落盘一份“失败记录”，方便预发/生产执行时对照
        msg = f"{type(e).__name__}: {e}"
        lines: list[str] = []
        lines.append("# 审计覆盖率（v1）验收记录 - 执行失败")
        lines.append("")
        lines.append(f"- 时间窗：近 {days} 天（since `{since.isoformat()}`）")
        lines.append(f"- 错误：`{msg}`")
        lines.append("")
        lines.append("## 1. 需要覆盖的分母清单（resourceType）")
        for rt in REQUIRED_RESOURCE_TYPES:
            lines.append(f"- `{rt}`")
        lines.append("")
        lines.append("## 2. 处置建议")
        lines.append("- 请在目标环境（预发/生产）配置正确的 DB 连接后重试。")
        lines.append("- 也可使用 `specs-prod/admin/ops/audit_coverage_7d.sql` 直接在 DB 执行聚合查询并人工记录。")
        fail_md = "\n".join(lines) + "\n"
        print(fail_md)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(fail_md, encoding="utf-8")
        return 2


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--output", type=str, default="")
    p.add_argument(
        "--env-file",
        type=str,
        default="",
        help="可选：指定 .env 文件路径（例如 backend/.env）。若不传，将优先尝试 repo_root/.env，再尝试 backend/.env。",
    )
    p.add_argument("--mysql-host", type=str, default="")
    p.add_argument("--mysql-port", type=int, default=0)
    p.add_argument("--mysql-user", type=str, default="")
    p.add_argument("--mysql-password", type=str, default="")
    p.add_argument("--mysql-database", type=str, default="")
    args = p.parse_args()

    # 1) 先加载 env_file（不覆盖已有 env）
    if str(args.env_file).strip():
        _load_env_file(Path(str(args.env_file)).resolve())
    else:
        root_env = _REPO_ROOT / ".env"
        backend_env = _BACKEND_DIR / ".env"
        if root_env.exists():
            _load_env_file(root_env)
        elif backend_env.exists():
            _load_env_file(backend_env)

    # 1.1) 若不是在容器内运行，并且未显式设置 MYSQL_HOST，则默认使用 127.0.0.1（本机连 docker 暴露端口的常见方式）
    if not _is_running_in_docker():
        if not str(os.environ.get("MYSQL_HOST") or "").strip():
            os.environ["MYSQL_HOST"] = "127.0.0.1"

    # 2) 再应用显式覆盖（覆盖 env）
    if str(args.mysql_host).strip():
        os.environ["MYSQL_HOST"] = str(args.mysql_host).strip()
    if int(args.mysql_port or 0) > 0:
        os.environ["MYSQL_PORT"] = str(int(args.mysql_port))
    if str(args.mysql_user).strip():
        os.environ["MYSQL_USER"] = str(args.mysql_user).strip()
    if str(args.mysql_password).strip():
        os.environ["MYSQL_PASSWORD"] = str(args.mysql_password)
    if str(args.mysql_database).strip():
        os.environ["MYSQL_DATABASE"] = str(args.mysql_database).strip()

    out = Path(args.output) if str(args.output).strip() else None
    return asyncio.run(main_async(days=int(args.days), output=out))


if __name__ == "__main__":
    raise SystemExit(main())


