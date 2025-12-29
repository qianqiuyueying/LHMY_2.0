#!/usr/bin/env sh
set -eu

# v1 回滚（本地/测试）最小可执行：
# - 回滚通常意味着“回到上一版本的镜像/代码”再重新部署。
# - 本仓库默认 docker-compose 现场 build，真正回滚应在 CI/CD 或镜像仓库层面完成。
#
# 本脚本提供“回滚演练”的最小动作：
# 1) 停止当前服务
# 2) 提示用户切换到上一版本（git tag / 镜像 tag）
# 3) 重新启动并做健康检查

echo "== LHMY rollback rehearsal (local/test) =="
docker compose down

echo "请切换到上一版本代码/镜像后再执行 deploy："
echo " - Git 方式：git checkout <previous-tag-or-commit>"
echo " - 镜像方式：将 docker-compose.yml 的 backend 改为 image: <repo>/backend:<tag>"

docker compose up -d --build
sleep 2
NGINX_PORT="${NGINX_PORT:-80}"
curl -fsS "http://127.0.0.1:${NGINX_PORT}/api/v1/openapi.json" >/dev/null
echo "OpenAPI status=200"
echo "== Done =="

