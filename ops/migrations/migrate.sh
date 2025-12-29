#!/usr/bin/env sh
set -eu

# v1 目标：
# - 演练 alembic upgrade/downgrade 的“可执行 + 可回滚”
# - 输出可留档的终端日志（建议：把执行输出重定向到文件）
#
# 使用示例：
#   sh ops/migrations/migrate.sh 2>&1 | tee migrate-evidence.txt
#
# 前置：
# - 已安装 docker compose
# - 在项目根目录执行（与 docker-compose.yml 同级）

echo "== LHMY migrations rehearsal =="

echo "1) 启动基础设施（mysql/redis/rabbitmq）..."
docker compose up -d mysql redis rabbitmq

echo "2) 启动 backend（容器启动时会自动 alembic upgrade head）..."
docker compose up -d backend

echo "3) 查看当前迁移版本（alembic current）..."
docker compose exec -T backend alembic current

echo "4) 回滚 1 个版本（alembic downgrade -1）..."
docker compose exec -T backend alembic downgrade -1

echo "5) 再次升级到 head（alembic upgrade head）..."
docker compose exec -T backend alembic upgrade head

echo "6) 最小健康检查（OpenAPI 200）..."
curl -fsS "http://127.0.0.1:8000/api/v1/openapi.json" >/dev/null
echo "OpenAPI status=200"

echo "== Done =="

