## 单机上线（域名 + HTTPS + Nginx 反代）发布手册（vNext）

### 目标

- **单机**：使用 `docker compose` 拉起 mysql/redis/rabbitmq/backend/celery/nginx
- **访问形态**：通过 **域名 + HTTPS（443）** 访问，由 **Nginx** 反向代理 `/api` 并托管 Website 静态资源
- **生产门禁**：生产环境禁止 seed demo 数据

### 0) 准备环境变量

- 复制 `ops/release/env.example` 为项目根 `./.env` 并按需填写
- 生产环境至少要设置：
  - `APP_ENV=production`
  - 所有 `change_me_*` 密钥替换为真实值（否则后端启动会拒绝启动）
  - 微信小程序与微信支付关键配置（尤其 `WECHAT_PAY_NOTIFY_URL` 必须是公网 https）

### 1) 配置 HTTPS（Nginx）

- 将 `nginx/conf.d/https.conf.example` 复制为 `nginx/conf.d/https.conf`，并修改：
  - `server_name`（你的域名）
  - `ssl_certificate` / `ssl_certificate_key`（证书文件路径）
- 把证书放到 `nginx/certs/` 并确保文件名与 `https.conf` 一致（默认示例：`fullchain.pem`、`privkey.pem`）

> 证书签发（推荐）：在宿主机用 certbot/云厂商证书服务生成证书后拷贝/挂载到本目录。  
> 本仓库只提供 Nginx 配置模板与挂载口径，不强制绑定某个证书工具链。

### 2) 部署

- Windows：`powershell -ExecutionPolicy Bypass -File ops/release/deploy.ps1`
- Linux：`sh ops/release/deploy.sh`

### 3) 验收（最小）

- 通过 Nginx 探活（HTTP）：`/api/v1/openapi.json`
- 后端 readiness（依赖可用）：`/api/v1/health/ready`
- 后端 liveness（进程存活）：`/api/v1/health/live`

### 4) 回滚

- Windows：`powershell -ExecutionPolicy Bypass -File ops/release/rollback.ps1`
- Linux：`sh ops/release/rollback.sh`


