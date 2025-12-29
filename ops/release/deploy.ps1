$ErrorActionPreference = "Stop"

# v1 发布（本地/测试）最小可执行：
# - 使用 docker compose 构建并启动服务
# - 后端容器启动时会自动执行 alembic upgrade head（见 docker-compose.yml）
#
# 使用示例：
#   .\ops\release\deploy.ps1

Write-Host "== LHMY deploy (local/test) ==" -ForegroundColor Cyan

Write-Host "1) 构建并启动（含 mysql/redis/rabbitmq/backend/nginx）..." -ForegroundColor Cyan
docker compose up -d --build

Write-Host "2) 健康检查（OpenAPI 200）..." -ForegroundColor Cyan
$nginxPort = if ($env:NGINX_PORT) { $env:NGINX_PORT } else { "80" }
$deadline = (Get-Date).AddSeconds(90)
$lastErr = $null
while ((Get-Date) -lt $deadline) {
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:" + $nginxPort + "/api/v1/openapi.json") -TimeoutSec 10
    if ($resp.StatusCode -eq 200) {
      $lastErr = $null
      break
    }
    $lastErr = "status=" + $resp.StatusCode
  } catch {
    $lastErr = $_.Exception.Message
  }
  Start-Sleep -Seconds 2
}
if ($lastErr) { throw "OpenAPI health check failed (timeout 90s): $lastErr" }
Write-Host "OpenAPI status=200" -ForegroundColor Green

Write-Host "== Done ==" -ForegroundColor Green

