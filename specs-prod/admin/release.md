# 发布与回滚（Release / Rollback）

## 1. 发布前检查（Pre-flight）
- **规格**：本次变更引用的 specs 条目已确认（链接到 `tasks.md` 具体任务）
- **数据库**：若有迁移，确认：
  - 可前向/可回滚（或明确不可回滚并给出替代方案）
  - 兼容双写/灰度（如需要）
- **配置**：生产环境敏感配置已满足启动门禁（见 `backend/app/main.py:_validate_production_settings`）
- **可观测性**：关键路径日志字段齐全（见 `observability.md`）
- **权限**：高风险操作有后端强制鉴权与审计（见 `security.md`）

## 1.1 本项目的“可执行入口”（代码证据）
- **后端依赖管理**：`uv` + `pyproject.toml/uv.lock`（根目录）
- **后端启动**：
  - Docker：`docker-compose.yml`（backend 容器启动会自动 `alembic upgrade head`，healthcheck `/api/v1/health/ready`）
  - 本地：`uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`（按环境变量连接 DB/Redis）
- **前端 Admin**：`frontend/admin/package.json`
  - build：`npm run build`（或 pnpm/yarn 等同）
  - e2e（可选）：`npm run e2e`
- **监控（可选）**：`docker-compose.monitoring.yml`（Prometheus/Grafana，占位但可运行）
- **备份/恢复（可选）**：`docker-compose.ops.yml` + `ops/backup/mysql/*.sh`

## 2. 发布步骤（Baseline）
> 目标：给出“能在目标环境直接执行”的命令与验证点（v1 最小）。

### 2.1 发布（推荐：Docker Compose）
> 适用：预发/生产（单机/轻量），或作为 CI/CD 的参考步骤。

1) **备份（强烈建议，DB 有风险变更时必须）**
- 备份命令（生成 `./backups/mysql/<db>_<ts>.sql`）：
  - `docker compose -f docker-compose.yml -f docker-compose.ops.yml run --rm mysql_backup`
- 验证：备份文件落盘成功；记录文件名到本次发布记录。

2) **部署后端（含迁移）**
- 启动/更新：
  - `docker compose up -d --build backend celery_worker celery_beat`
- 说明：backend 容器启动时会自动执行 `alembic upgrade head`（见 `docker-compose.yml`）。
- 验证：
  - `GET /api/v1/health/ready` 返回 success
  - `GET /metrics` 可抓取

3) **部署 Nginx（包含前端）**
- 启动/更新：
  - `docker compose up -d --build nginx`
- 验证：
  - `GET /api/v1/health/live`（经 nginx 代理）可用
  - Admin 登录页可访问（`/login`）

4) **冒烟验证（必须）**
- 执行：`specs-prod/admin/release-smoke.md`（见 2.3）
- 记录：把结果落盘到 `specs-prod/admin/evidence/release/YYYY-MM-DD.md`

### 2.2 发布（本地/非 Docker，开发/联调）
> 适用：本地/联调环境；生产通常不建议此方式。

- 后端：
  - `uv sync --dev`
  - `uv run alembic upgrade head`
  - `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 前端：
  - `cd frontend/admin`
  - `npm ci`
  - `npm run build`
  - `npm run preview`

### 2.3 冒烟清单（Release Smoke Checklist）
见：`specs-prod/admin/release-smoke.md`

## 3. 回滚步骤（Baseline）
> 原则：回滚必须可执行，且不依赖“拍脑袋手工修复”。

### 3.1 仅前端回滚
- 条件：后端无破坏性变更、API 契约保持兼容
- 步骤：
  - Docker 场景：回滚 nginx 到上一镜像/tag（由发布系统/镜像仓库决定）
  - 验证：`/login` 可访问；关键页面可打开；接口仍可用

### 3.2 后端回滚
- 条件：需确保 DB 变更可回滚或向后兼容
- 步骤（Docker Compose v1 最小）：
  1) 回滚 `backend/celery_worker/celery_beat` 到上一镜像/tag（由发布系统决定）
  2) 若 DB 变更需要回滚：
     - 使用备份恢复（高风险，需审批）：
       - `docker compose -f docker-compose.yml -f docker-compose.ops.yml run --rm -e BACKUP_FILE=/backups/<file>.sql mysql_restore`
  3) 重启服务：
     - `docker compose up -d backend celery_worker celery_beat nginx`

## 4. 回滚验证
- 登录/鉴权可用
- 高风险操作（结算标记/导出/发布）不可出现越权或数据口径漂移

## 5. 本次演练记录（模板）
> 每次发布/回滚演练都必须落盘一份记录文件到 `specs-prod/admin/evidence/release/`。
- 记录模板：`specs-prod/admin/evidence/release/TEMPLATE.md`


