## LHMY_2.0（陆合铭云健康服务平台）

本仓库为“陆合铭云健康服务平台”实现代码，覆盖三条业务线：**基建联防 / 健行天下 / 职健行动**，包含多端：企业官网、管理后台（Admin/Dealer/Provider）、H5、小程序。

## 规格与文档（Spec-Driven 开发入口）

- **主规格（设计文档）**：`specs/health-services-platform/design.md`
- **原型（信息结构/流程约束）**：`specs/health-services-platform/prototypes/`
- **实施任务清单（产品/交付主线，规格→实现→测试最强索引）**：`specs/health-services-platform/tasks.md`
- **维护性重构任务清单（代码去重/可维护性优化，实施时同步更新）**：`specs/lhmy-2.0-maintenance/tasks.md`
- **交接与代码地图（仓库沉淀）**：`readme/`
  - `readme/00_交接索引.md`
  - `readme/10_规格对齐与代码地图.md`
  - `readme/20_本地开发与运维速记.md`

建议阅读顺序：`design.md` → `prototypes/` → `tasks.md`。

## 项目结构

- `backend/`：FastAPI 后端（依赖由 **uv** 管理）
- `frontend/`
  - `frontend/admin`：管理后台（Vue3 + Element Plus；包含 admin/dealer/provider 页面）
  - `frontend/h5`：H5（Vue3 + Vant4；健行天下服务包购买入口）
  - `frontend/shared`：Web 三端共享纯逻辑（TS 工具函数：`http/*`、`auth/*`、`storage/*`；**小程序不引用**）
  - `frontend/website`：企业官网（Vue3 + Naive UI）
  - `frontend/mini-program`：微信小程序（原生）
- `docker-compose.yml`：nginx / backend / mysql / redis / rabbitmq
- `docker-compose.ops.yml`：运维辅助（如 MySQL 备份容器）
- `docker-compose.monitoring.yml`：监控预留（Prometheus/Grafana）
- `ops/`：运维脚本
- `monitoring/`：监控配置

## 快速开始

### 方式 A：Docker Compose（推荐）

1) 准备环境变量：从 `ops/env/env.example` 复制为 `.env`，按需填写（MySQL/Redis/RabbitMQ/JWT/各类密钥）。

2) 启动：

```bash
docker compose up -d
```

后端默认端口与 Nginx 反代配置以 `docker-compose.yml` / `nginx/` 为准。

#### 常见构建问题：`@shared/*` 找不到（TS2307）

如果你在构建 `nginx`（website 静态站点）时遇到类似错误：

- `error TS2307: Cannot find module '@shared/http/base' ...`

说明构建时需要的 `frontend/shared/` 没有进入构建上下文。仓库目前的约定是：

- Web 三端（admin/website/h5）通过 `@shared/*` 引用 `frontend/shared/` 的纯逻辑工具
- 小程序不引用 `frontend/shared/`（见 `specs/lhmy-2.0-maintenance/tasks.md`：**FE-DEDUPE-MP-API**）
- `nginx/Dockerfile` 在 `npm run build` 前会复制 `frontend/shared/`，确保容器内 typecheck/build 能解析 `@shared/*`

> 更推荐使用仓库内脚本（会做健康检查）：
> - Windows：`ops/release/deploy.ps1`
> - macOS/Linux：`sh ops/release/deploy.sh`
>
> 健康检查：`http://127.0.0.1:${NGINX_PORT:-80}/api/v1/openapi.json` 返回 200

管理后台初始管理员账号（开发/测试）：
- 在 `.env` 中设置 `ADMIN_INIT_USERNAME`、`ADMIN_INIT_PASSWORD`
- 首次启动时会自动创建该账号（若数据库中不存在同名账号）
- 使用该账号调用 `POST /api/v1/admin/auth/login` 登录

#### 图片上传（/static/uploads）与“未来图床/OSS”配置

后端上传接口 `POST /api/v1/uploads/images` 默认返回相对路径：`/static/uploads/YYYY/MM/xxx.jpg`，由后端 `StaticFiles` 提供并可被 Nginx 反代。

如需将图片 URL 变为**带域名的绝对地址**（便于未来切 CDN/图床），可在 `.env` 中设置：
- `ASSETS_PUBLIC_BASE_URL=https://your-cdn-domain.com`

说明：
- 未设置时：仍返回 `/static/...`（同域访问）
- 设置后：返回 `https://your-cdn-domain.com/static/...`（对外 URL 基址）

---

## 小程序“可部署/可上线”必要步骤（必读）

> 说明：这里**不再引用外部文档**，把上线必须步骤完整收敛到 README，方便交付与执行。

### 0) 一次性准备（环境与平台侧）

- **基础环境**：已安装 Docker Desktop（或 Docker Engine）+ docker compose
- **微信侧（小程序）**：`WECHAT_APPID`、`WECHAT_SECRET`
- **微信支付（v3）**：商户号、商户私钥、商户证书序列号、平台证书序列号、平台证书、APIv3Key、notify_url（公网 https）

### 1) 生产环境必填的关键配置（后端）

当你把 `APP_ENV=production` 时，后端会启用启动门禁：缺少关键配置会**直接拒绝启动**（避免带默认密钥上线）。

- **JWT（必须非默认值）**
  - `JWT_SECRET` / `JWT_SECRET_ADMIN` / `JWT_SECRET_PROVIDER` / `JWT_SECRET_DEALER`
- **签名密钥（必须非默认值）**
  - `ENTITLEMENT_QR_SIGN_SECRET`
  - `DEALER_SIGN_SECRET`
- **小程序登录（必须）**
  - `WECHAT_APPID`
  - `WECHAT_SECRET`
- **微信支付（小程序预支付 + 回调验签/解密，必须）**
  - 预支付：`WECHAT_PAY_MCH_ID`、`WECHAT_PAY_APPID`、`WECHAT_PAY_MCH_CERT_SERIAL`、`WECHAT_PAY_MCH_PRIVATE_KEY_PEM_OR_PATH`、`WECHAT_PAY_NOTIFY_URL`
  - 回调：`WECHAT_PAY_API_V3_KEY`、`WECHAT_PAY_PLATFORM_CERT_SERIAL`、`WECHAT_PAY_PLATFORM_CERT_PEM_OR_PATH`

### 1.1 `.env` 放哪、怎么启动

- `.env` 放在项目根目录（与 `docker-compose.yml` 同级）
- 推荐使用脚本启动（包含健康检查）：
  - Windows：`ops/release/deploy.ps1`
  - macOS/Linux：`sh ops/release/deploy.sh`
- 健康检查：访问 `http://127.0.0.1:${NGINX_PORT:-80}/api/v1/openapi.json` 返回 200

### 1.2 迁移演练（上线前建议留档）

- Windows：`ops/migrations/migrate.ps1`（建议将输出重定向留档）
- macOS/Linux：`sh ops/migrations/migrate.sh`（建议将输出重定向留档）

### 2) 小程序必须配置“request 合法域名”（微信公众平台）

- 小程序调用后端必须使用 **https 域名**
- 需要在微信公众平台配置“request 合法域名”（以及 WebView 相关域名，如有）
- 小程序端 API 地址读取逻辑（`frontend/mini-program/utils/config.js`）：
  - develop/trial：默认 `http://127.0.0.1:8000`（便于本地联调）
  - release：**不会默认指向本地 127**；发布前必须确保指向生产后端域名（https）

### 2.1 运营工具 → 小程序配置中心：跳转类型“**小程序路由（ROUTE）**”使用说明

> 适用页面：管理后台 `内容与投放 → 小程序配置中心`（`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`）

#### 2.1.1 填写规则（Admin 侧校验 + 小程序侧执行）

- **targetId 必须以 `/` 开头**：例如 `/pages/venue-detail/venue-detail?id=xxx`
- **targetId 不能是 `http(s)`**：外链请使用跳转类型 `WEBVIEW`
- **TabBar 页面不能带 query**：如果你把 targetId 写成 `/pages/mall/mall?keyword=xxx`，小程序端会尝试 `navigateTo`，而 TabBar 页禁止 `navigateTo`，会跳转失败。  
  - TabBar 页（固定 5 个）：`/pages/index/index`、`/pages/mall/mall`、`/pages/entitlement/entitlement`、`/pages/order/order`、`/pages/profile/profile`
- **参数编辑器（推荐）**：页面内提供“ROUTE params editor（key/value）”，会对 key/value 进行 URL 编码，并拼回 `?k=v&...`（见 `parseRouteTarget/setRouteTarget/buildQueryString`）。

#### 2.1.2 你的小程序可跳转页面清单（ROUTE）

> 说明：以下为 `frontend/mini-program/app.json` 中注册的页面。除 TabBar 页外，均可用 ROUTE 跳转（`wx.navigateTo`）。

| 页面用途 | ROUTE targetId 示例 | 必填参数 | 备注 |
| --- | --- | --- | --- |
| 首页（Tab） | `/pages/index/index` | 无 | 不要带 query |
| 商城（Tab） | `/pages/mall/mall` | 无 | 不要带 query；如需“带关键词”，请跳转到搜索页或使用小程序内置搜索流（当前实现用 storage 传递关键词） |
| 搜索页 | `/pages/search/search?keyword=健行天下` | 无 | `keyword` 可选；确认搜索后会切到商城 Tab（见 `pages/search/search.js`） |
| 商品详情 | `/pages/mall/product-detail/product-detail?id=PRODUCT_ID` | `id` | `id` 为商品 ID（见 `pages/mall/product-detail/product-detail.js`） |
| 购物车 | `/pages/mall/cart/cart` | 无 |  |
| 场所详情 | `/pages/venue-detail/venue-detail?id=VENUE_ID` | `id` | `id` 为场所 ID（见 `pages/venue-detail/venue-detail.js`） |
| 权益（Tab） | `/pages/entitlement/entitlement` | 无 | 不要带 query |
| 权益详情 | `/pages/entitlement/entitlement-detail/entitlement-detail?id=ENTITLEMENT_ID` | `id` | `id` 为权益 ID（见 `pages/entitlement/entitlement-detail/entitlement-detail.js`） |
| 预约-选场所 | `/pages/booking/venue-select/venue-select?entitlementId=ENTITLEMENT_ID` | `entitlementId` | 由权益详情页跳转复用 |
| 订单（Tab） | `/pages/order/order` | 无 | 不要带 query |
| 订单详情 | `/pages/order/order-detail/order-detail?id=ORDER_ID` | `id` | `id` 为订单 ID（见 `pages/order/order-detail/order-detail.js`） |
| 我的（Tab） | `/pages/profile/profile` | 无 | 不要带 query |
| 客服与帮助 | `/pages/support/support` | 无 |  |
| AI 对话 | `/pages/ai-chat/ai-chat` | 无 |  |
| 聚合页（配置页） | `/pages/aggregate/aggregate?pageId=PAGE_ID` | `pageId` | 更推荐在配置中心使用 `AGG_PAGE`，由系统生成该路由 |
| 信息页（配置页） | `/pages/info/info?pageId=PAGE_ID` | `pageId` | 更推荐在配置中心使用 `INFO_PAGE`，由系统生成该路由 |
| 更多入口（快捷入口全集） | `/pages/index/entries-more/entries-more` | 无 |  |
| WebView 容器页 | `/pages/webview/webview?url=https%3A%2F%2Fexample.com&title=标题` | `url` | 更推荐在配置中心使用 `WEBVIEW`；`url/title` 需要 URL 编码（配置中心 params editor 会自动编码） |

### 3) 支付能力说明（上线前必须验证）

小程序支付入口依赖后端：`POST /api/v1/orders/{id}/pay` 返回可用于 `wx.requestPayment` 的 `wechatPayParams`。

#### 3.1 支付回调地址（notify_url）核对
- 必须公网可访问、必须 https
- 必须能被微信支付服务器访问（公网 DNS、证书正常）
- 路径固定：`/api/v1/payments/wechat/notify`

#### 3.2 支付预支付契约（v1 最小）
- `POST /api/v1/orders/{id}/pay`
  - Header：`Idempotency-Key`
  - Request：`{ paymentMethod: "WECHAT" }`
  - Response（成功）：`HTTP 200 + paymentStatus="PENDING" + wechatPayParams{timeStamp,nonceStr,package,signType="RSA",paySign}`
  - Response（业务失败）：`HTTP 200 + paymentStatus="FAILED" + failureReason`
  - Error（HTTP 失败）：`STATE_CONFLICT(409)`（状态不允许支付）、`UNAUTHENTICATED(401)`

### 4) AI 对话（默认可能是“停用”）

如果你在小程序里看到 `FORBIDDEN: AI 功能已停用`，表示后端配置里 `AI_CONFIG.enabled=false`（属于正常配置态）。

- 管理端接口（Admin）：`GET/PUT /api/v1/admin/ai/config`
- 小程序端会把该状态展示为“AI 暂未开放”，并引导去“客服与帮助”

---

## 小程序上线回归矩阵（v1 手工勾选）

> 说明：小程序端未引入自动化 e2e；v1 以手工回归作为上线门禁证据（建议截图/录屏留档）。

### A. 基础导航
- [ ] 底部 Tab：首页/商城/权益/订单/我的 可切换；高亮不错乱
- [ ] 未登录进入需要登录的页面/操作：提示“请先登录”，并可一键去“我的”

### B. 首页（关键：避免空白/静默失败）
- [ ] 后端正常：Banner/快捷入口/推荐商品/推荐场所至少有一个模块能展示内容
- [ ] 断网/后端不可用：出现“加载失败”错误态 + 可重试
- [ ] 快捷入口为空：显示“暂无快捷入口”提示，并可进入“客服与帮助”

### C. 商城下单与支付反馈
- [ ] 商品详情：可加入购物车/立即购买；按钮可用/禁用态符合状态
- [ ] 创建订单成功：跳转订单详情
- [ ] 待支付订单：点击“立即支付”要么拉起微信支付，要么明确失败提示（不可无反馈）

### D. 权益与预约
- [ ] 权益列表可打开权益详情
- [ ] 权益详情：二维码/券码至少一种可展示；无二维码时有明确提示
- [ ] 从权益详情发起预约：选场所→选日期/时段→提交→结果页可见关键信息
- [ ] 预约列表可见记录；取消预约有明确反馈

### E. 用户支持与排障
- [ ] 我的页存在“客服与帮助”入口
- [ ] 客服与帮助页：FAQ 可加载（为空显示空态；失败可重试）
- [ ] 客服与帮助页：可点击“联系在线客服”（微信原生）
- [ ] 可复制诊断信息（包含 requestId/耗时/URL/状态码等）

---

## 发布与回滚（v1 最小 SOP）

### 发布前
- [ ] 微信公众平台配置核对：request 合法域名 / WebView 业务域名（如用到）已配置
- [ ] 后端环境核对：`APP_ENV=production` + 关键密钥/微信支付配置已填写（否则后端会拒绝启动）
- [ ] 完成上面的“上线回归矩阵”，并留档（截图/录屏/日志）

### 发布后抽检
- [ ] 首页（网络正常/异常各一次）
- [ ] 下单→支付（一次）
- [ ] 权益/预约链路（一次）

### 回滚
- Windows：`ops/release/rollback.ps1`
- macOS/Linux：`sh ops/release/rollback.sh`
> 注：当前 compose 默认“现场 build”，生产环境建议以镜像 tag/CI/CD 进行回滚；脚本提供最小回滚演练与健康检查。

### 方式 B：本地启动后端（uv）

前置：已安装 Python + `uv`。

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：
- Swagger：`/docs`
- OpenAPI：`/openapi.json`

### 方式 C：本地启动前端

每个子项目都是独立 Vite 工程：

```bash
cd frontend/admin
npm i
npm run dev
```

其他端同理：
- `frontend/h5`
- `frontend/website`

小程序：用微信开发者工具打开 `frontend/mini-program`。

## 关键约定（避免二次开发踩坑）

- **API 前缀**：统一 `/api/v1`（路由入口：`backend/app/api/v1/router.py`）
- **鉴权 token 隔离**：USER / ADMIN / PROVIDER 的 token 与上下文隔离（配置与解析逻辑见 `backend/app/utils/`、`backend/app/middleware/`、`backend/app/services/`）
- **幂等**：写操作使用 `Idempotency-Key`（实现：`backend/app/services/idempotency.py`；口径以 `design.md` 为准）
- **正确性属性（Property 1~23）**：对应测试集中在 `backend/tests/`，映射表见 `specs/health-services-platform/tasks.md`

## 测试与质量

后端：

```bash
uv run pytest backend
```

（CI 已在 `.github/workflows/ci.yml` 配置：pytest + black/flake8/mypy + 前端 lint/typecheck。）

---

## 本地验证（E2E / 迁移演练 / 监控 / 性能基线）

> 这些命令主要来自 `specs/功能实现/admin/tasks.md` 的“生产就绪门禁（Go-Live Gates）”与回归要求，用于把“能跑”变成“可验证 + 可留档证据”。

### 1) 前端 E2E（管理后台冒烟）

**它是什么意思**：在浏览器里自动化执行“登录→进入关键页面”的最小回归，用来避免改动后出现“页面进不去/路由守卫异常/接口报错但没人发现”。

**什么时候用**：
- 修改了 `frontend/admin` 的路由、鉴权、页面加载、错误态、关键表格/筛选后
- 发版前做最小回归留档（可作为证据）

**前置条件**：
- 后端已启动（默认 `http://127.0.0.1:8000`）
- `frontend/admin` 已安装依赖并启动 dev server（默认 `http://localhost:5174`）

**怎么跑**（在 `frontend/admin` 目录下）：

```bash
npm run e2e
```

**如何判断成功**：
- 终端输出 `1 passed`（或全部测试通过）
- 失败时会给出失败页面与定位信息（Playwright trace/screenshot）

**常见问题**：
- 若 Admin 登录启用了强制 2FA，E2E 会报错提示 `requires2fa=true`。E2E 环境建议使用不触发 2FA 的专用账号，或在测试环境关闭 2FA。

---

### 2) 数据库迁移演练（可执行 + 可回滚）

**它是什么意思**：演练 Alembic 迁移是否能在“全新库”成功升级到最新版本，并且能回滚一个版本再恢复到最新版本。用于避免上线后出现“表缺失/迁移失败/无法回滚”的事故。

**什么时候用**：
- 新增/修改 Alembic 迁移后
- 发版前必须做一次演练并留档（日志/截图）

**怎么跑**：
- Windows（PowerShell，在项目根目录）：

```powershell
.\ops\migrations\migrate.ps1 | Tee-Object -FilePath .\migrate-evidence.txt
```

- Linux/macOS（在项目根目录）：

```bash
sh ops/migrations/migrate.sh 2>&1 | tee migrate-evidence.txt
```

**脚本做了什么**：
- `docker compose up -d` 启动 mysql/redis/rabbitmq/backend
- 在 backend 容器里依次执行：
  - `alembic current`
  - `alembic downgrade -1`
  - `alembic upgrade head`
- 最后请求 `GET /api/v1/openapi.json` 作为最小健康检查

---

### 3) 监控启动（Prometheus / Grafana）

**它是什么意思**：启动最小监控栈，并让 Prometheus 抓取后端 `/metrics` 指标；同时加载最小告警规则（如 BackendDown / 5xx 比例过高）。

**什么时候用**：
- 本地/测试环境验证“指标可抓取、告警规则可加载”
- 发版前做可观测性最小闭环验收

**怎么跑**（项目根目录）：

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

**如何判断成功**：
- Prometheus：打开 `http://127.0.0.1:9090`，Targets 里能看到 `lhmy_backend` 为 UP
- Grafana：打开 `http://127.0.0.1:3000`（默认账号密码以 Grafana 默认/你自己的配置为准）

**关键配置文件**：
- 后端 metrics 暴露：`backend/app/main.py`（`/metrics`）
- Prometheus 抓取配置：`monitoring/prometheus/prometheus.yml`
- Prometheus 告警规则：`monitoring/prometheus/alerts.yml`

---

### 4) 性能基线（最小可重复脚本）

**它是什么意思**：对关键探活/契约类接口做一组重复请求，输出 p50/p95/状态码分布的 JSON 报告，用于建立“最小性能基线”与回归对比。

**什么时候用**：
- 发版前/发版后做一次基线留档
- 怀疑性能退化时做对比

**怎么跑**（项目根目录）：

```bash
uv run python backend/scripts/perf_baseline.py > perf-baseline.json
```

**前置条件**：
- 后端已启动（默认 `http://127.0.0.1:8000`）

**可选环境变量**：
- `PERF_BASE_URL`：后端地址（默认 `http://127.0.0.1:8000`）
- `PERF_N`：每个接口请求次数（默认 30）
- `PERF_TIMEOUT_SECONDS`：请求超时（默认 10）
