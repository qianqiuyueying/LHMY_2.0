#!/usr/bin/env sh
set -eu

# v1 发布（本地/测试）最小可执行：
# - 使用 docker compose 构建并启动服务
# - 后端容器启动时会自动执行 alembic upgrade head（见 docker-compose.yml）

echo "== LHMY deploy (local/test) =="
docker compose up -d --build

NGINX_PORT="${NGINX_PORT:-80}"
echo "health check via nginx: /api/v1/openapi.json (port=${NGINX_PORT})"
deadline=$(( $(date +%s) + 90 ))
ok=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  if curl -fsS "http://127.0.0.1:${NGINX_PORT}/api/v1/openapi.json" >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" -ne 1 ]; then
  echo "OpenAPI health check failed (timeout 90s)" >&2
  exit 1
fi
echo "OpenAPI status=200"
echo "== Done =="

