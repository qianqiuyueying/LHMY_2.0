## 设计总纲（多端：Admin / Website / H5 / 小程序 / 后端）

### 1) 端侧与系统边界

- **Admin（`frontend/admin`）**
  - 目标：承载运营与管理后台能力（Admin/Dealer/Provider 多角色），用于配置、审核、监管与履约侧工作台。
  - 约束：通过统一 API 前缀与鉴权隔离不同角色（ADMIN/DEALER/PROVIDER/PROVIDER_STAFF）。
- **Website（`frontend/website`）**
  - 目标：企业官网信息展示与导流（进入小程序 / H5 购买），并提供 SEO 基础 meta 管理。
  - 约束：官网以“读侧”为主，不承担交易闭环；配置下发/维护模式由后端读侧接口提供。
- **H5（`frontend/h5`）**
  - 目标：作为“健行天下服务包购买入口”（下单与发起支付），并提供“去小程序使用权益”的引导。
  - 约束：H5 不直接承载权益使用/预约；权益使用发生在小程序。
- **小程序（`frontend/mini-program`）**
  - 目标：权益查看与使用、预约、商城（商品）下单与支付、订单查询、个人中心（登录/绑手机/企业绑定入口）。
  - 约束：小程序端不创建 `SERVICE_PACKAGE` 类型订单（购买入口在 H5）。
- **后端（`backend`）**
  - 目标：为 H5/小程序提供统一 API、鉴权、幂等、支付、权益、预约、配置下发与可观测性；生产环境提供启动门禁避免带默认密钥上线。

### 2) 生产部署形态（必须）

- **生产/测试**：统一走 `docker compose`（见项目根 `docker-compose.yml`、`ops/release/deploy.ps1` / `ops/release/deploy.sh`）
- **本地开发**：
  - 前端：本地启动各端（Vite / 微信开发者工具）
  - 后端：优先跑在 docker（与生产一致）；允许用 `uv` 本地启动进行调试（能力保留，但不作为生产口径）

### 3) 上线 DoD（Definition of Done，最小门禁）

#### 3.1 后端启动门禁（生产）

- 当 `APP_ENV=production` 时，后端启动时必须校验关键配置，否则**拒绝启动**  
  证据入口：`backend/app/main.py` 中 `_validate_production_settings()`。

#### 3.2 健康检查与 API 文档入口

- OpenAPI 文档必须可访问（用于探活与契约确认）：
  - `/openapi.json`（FastAPI 默认）
  - `/api/v1/openapi.json`（兼容入口）
  证据入口：`backend/app/main.py`、`backend/app/api/v1/openapi_proxy.py`。

#### 3.3 核心链路“可用”（最小）

- **H5：落地页 → 确认购买 →（短信登录）→ 创建订单 → 发起支付 → 支付结果页**
- **小程序：登录 → 浏览 → 下单 → 发起支付 → 订单查询；权益列表/详情；预约链路**

> 说明：本节只定义“必须可用”的链路，不定义 UI 像素或交互细节。

### 4) 兼容性与长期可维护性原则（必须遵守）

#### 4.1 API 前缀与统一响应体

- API 前缀统一为 `/api/v1`（后端路由聚合入口：`backend/app/api/v1/router.py`）。
- 业务响应统一形态：
  - 成功：`{ success: true, data: <T>, requestId?: string }`
  - 失败：`{ success: false, error: { code, message, details? }, requestId?: string }`
  - 非业务错误（HTTPException）可能返回 `detail` 结构（小程序端有兼容处理）。

#### 4.2 鉴权 token 与 channel 隔离

- USER token 在不同端侧携带不同 `channel`：
  - H5：`/api/v1/auth/login` 创建 token，`channel="H5"`
  - 小程序：`/api/v1/mini-program/auth/login` 创建 token，`channel="MINI_PROGRAM"`
- 部分接口会要求 channel 匹配（例如小程序绑手机要求 `require_channel="MINI_PROGRAM"`）。

#### 4.3 幂等（Idempotency-Key）

- 任何**写操作**（创建订单/支付/创建预约/AI chat 等）必须使用 `Idempotency-Key`，避免重试造成重复副作用。
  - H5：`frontend/h5/src/lib/api.ts` 提供 `newIdempotencyKey()`，并在下单/支付时携带。
  - 小程序：`frontend/mini-program/utils/api.js` 提供 `genIdempotencyKey()`，并在下单/支付/预约/AI chat 时携带。
  - 后端：`backend/app/services/idempotency.py`（缓存/重放）；典型入口 `backend/app/api/v1/orders.py`、`bookings.py`、`ai.py`。

#### 4.4 请求链路追踪（RequestId）

- 小程序请求会注入 `X-Request-Id`，用于端到端定位。
  证据入口：`frontend/mini-program/utils/api.js`。


