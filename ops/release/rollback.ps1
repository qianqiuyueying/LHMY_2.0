$ErrorActionPreference = "Stop"

# v1 回滚（本地/测试）最小可执行：
# - 回滚通常意味着“回到上一版本的镜像/代码”再重新部署。
# - 本仓库采用 backend 现场 build 的 docker-compose 方式，因此真正回滚应在 CI/CD 或镜像仓库层面完成。
#
# 本脚本提供“回滚演练”的最小动作：
# 1) 停止当前服务
# 2) 提示用户切换到上一版本（git tag / 镜像 tag）
# 3) 重新启动并做健康检查
#
# 使用示例：
#   .\ops\release\rollback.ps1

Write-Host "== LHMY rollback rehearsal (local/test) ==" -ForegroundColor Yellow

Write-Host "1) 停止服务..." -ForegroundColor Yellow
docker compose down

Write-Host "2) 请切换到“上一版本代码/镜像”后再执行 deploy（示例）：" -ForegroundColor Cyan
Write-Host "   - Git 方式：git checkout <previous-tag-or-commit>" -ForegroundColor Cyan
Write-Host "   - 镜像方式：在 docker-compose.yml 中改为 image: <repo>/backend:<tag>" -ForegroundColor Cyan

Write-Host "3) 重新启动并健康检查..." -ForegroundColor Yellow
docker compose up -d --build
Start-Sleep -Seconds 2
$nginxPort = if ($env:NGINX_PORT) { $env:NGINX_PORT } else { "80" }
$resp = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:" + $nginxPort + "/api/v1/openapi.json") -TimeoutSec 15
if ($resp.StatusCode -ne 200) { throw "OpenAPI health check failed: $($resp.StatusCode)" }
Write-Host "OpenAPI status=200" -ForegroundColor Green

Write-Host "== Done ==" -ForegroundColor Green

