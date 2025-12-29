$ErrorActionPreference = "Stop"

# v1 目标：
# - 演练 alembic upgrade/downgrade 的“可执行 + 可回滚”
# - 输出可留档的终端日志（建议：把执行输出重定向到文件）
#
# 使用示例（PowerShell）：
#   .\ops\migrations\migrate.ps1 | Tee-Object -FilePath .\migrate-evidence.txt
#
# 前置：
# - 已安装 Docker Desktop
# - 在项目根目录执行（与 docker-compose.yml 同级）

Write-Host "== LHMY migrations rehearsal ==" -ForegroundColor Cyan

Write-Host "1) 启动基础设施（mysql/redis/rabbitmq）..." -ForegroundColor Cyan
docker compose up -d mysql redis rabbitmq

Write-Host "2) 启动 backend（容器启动时会自动 alembic upgrade head）..." -ForegroundColor Cyan
docker compose up -d backend

Write-Host "3) 查看当前迁移版本（alembic current）..." -ForegroundColor Cyan
docker compose exec -T backend alembic current

Write-Host "4) 回滚 1 个版本（alembic downgrade -1）..." -ForegroundColor Yellow
docker compose exec -T backend alembic downgrade -1

Write-Host "5) 再次升级到 head（alembic upgrade head）..." -ForegroundColor Cyan
docker compose exec -T backend alembic upgrade head

Write-Host "6) 最小健康检查（OpenAPI 200）..." -ForegroundColor Cyan
try {
  $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/api/v1/openapi.json" -TimeoutSec 10
  Write-Host ("OpenAPI status=" + $resp.StatusCode) -ForegroundColor Green
} catch {
  Write-Host "OpenAPI check failed; 请确认 backend 是否已启动并映射到 8000 端口。" -ForegroundColor Red
  throw
}

Write-Host "== Done ==" -ForegroundColor Green

