# 审计覆盖率（高风险事件）验收记录

## 1. 规格依据（单一真相来源）
- `specs-prod/admin/security.md#3.1.1`：高风险事件覆盖清单（分母）
- `specs-prod/admin/observability.md#2.3`：覆盖率定义（近 7 天；每类 ≥ 1 条即覆盖）
- `specs-prod/admin/tasks.md#TASK-P0-002`：DoD（覆盖率可验收 + 未覆盖清单输出）

## 2. 产物与运行方式

### 2.1 SQL（MySQL）
- 文件：`specs-prod/admin/ops/audit_coverage_7d.sql`
- 使用：在目标环境（预发/生产）执行，将查询结果粘贴进当日记录文件。

### 2.2 脚本（推荐）
- 文件：`scripts/audit_coverage_report.py`
- 运行（示例）：

```bash
uv run python scripts/audit_coverage_report.py --days 7 --output specs-prod/admin/evidence/audit-coverage/REPLACE_DATE.md
```

> 说明：脚本会读 DB 并自动生成“覆盖率 + 未覆盖清单”的 markdown，便于纳入发布证据。若 DB 连接失败，脚本仍会生成一份“执行失败记录”（用于留痕），并以非 0 退出码返回。
>
> Windows 提示：控制台可能因编码显示乱码，但输出文件（markdown）为 UTF-8，可直接在 IDE 查看内容是否正常。

#### 2.2.1 本地 MySQL 连接（常见场景）
如果你本机 MySQL 是 `127.0.0.1/localhost` 而不是 docker 网络别名 `mysql`，请用以下任一方式：

- **方式 A：指定 env-file（推荐）**
  - 通常是仓库根目录 `.env`（你提到的 13-15 行即 `MYSQL_USER/MYSQL_PASSWORD` 等）：

```bash
uv run python scripts/audit_coverage_report.py --env-file .env --days 7 --output specs-prod/admin/evidence/audit-coverage/YYYY-MM-DD.md
```

- **方式 B：命令行覆盖 MYSQL_*（不会依赖工作目录）**

```bash
uv run python scripts/audit_coverage_report.py --mysql-host 127.0.0.1 --mysql-port 3306 --mysql-user lhmy --mysql-password YOUR_PASS --mysql-database lhmy --days 7 --output specs-prod/admin/evidence/audit-coverage/YYYY-MM-DD.md
```

## 3. 记录命名
- `YYYY-MM-DD.md`：例如 `2025-12-23.md`


