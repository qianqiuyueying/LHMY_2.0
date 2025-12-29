# 接口契约（API Contracts）

> 说明：本文件用于固化 Admin 相关 API 的“可生产”契约：路由、请求/响应、错误码、幂等、审计要求。
> 约束：本规格为唯一真相；若与现有实现不一致，必须先提规格变更并由拍板人确认后再改代码。

## 0. 本次基线：高风险 + 高频 Top 5 接口（先写规格，不改代码）

> 选择依据（来自 `flow-catalog.md`）：登录链路（高频）、审计查询（高频/敏感）、结算（资金高风险，且上线后会频繁操作/排查）。

- **AUTH-LOGIN**：`POST /api/v1/admin/auth/login`
- **AUTH-REFRESH**：`POST /api/v1/admin/auth/refresh`
- **AUDIT-LIST**：`GET /api/v1/admin/audit-logs`
- **SETTLEMENT-GENERATE**：`POST /api/v1/admin/dealer-settlements/generate`
- **SETTLEMENT-MARK-SETTLED**：`POST /api/v1/admin/dealer-settlements/{id}/mark-settled`

## 1. 通用约定

### 1.1 Base URL
- **前缀**：`/api/v1`

### 1.2 统一响应体（Envelope）
- **成功**：
  - `success: true`
  - `data: <any>`
  - `error: null`
  - `requestId: string`
- **失败**：
  - `success: false`
  - `data: null`
  - `error: { code: string, message: string, details?: any }`
  - `requestId: string`
- **代码证据**：`backend/app/utils/response.py`（`ok()`/`fail()`）

### 1.3 认证与 Header
- **Authorization**：`Bearer <token>`
- **requestId**：后端中间件生成并回传（见 `observability.md`）
- **Idempotency-Key**：可选；当接口要求幂等时，以 `Idempotency-Key: <string>` 传入（详见各接口）

### 1.4 状态机写操作的统一口径（你已拍板：生产友好）

适用范围：所有**审核/发布/下线/启停用/结算标记/提交审核**等“状态机写操作”。

- **重复提交到同一目标状态**（例如已 `APPROVED` 再 approve；已 `PUBLISHED` 再 publish）：
  - 返回：**200（或 204）**
  - 语义：**幂等 no-op**
  - 响应：必须返回“当前资源状态/版本号”（若使用 envelope，则放在 `data`）
- **会改变结果 / 非法状态流转**（例如已 `APPROVED` 还去 reject；已 `OFFLINE` 再 publish 但不满足条件）：
  - 返回：**409**
  - 错误码：统一为 `STATE_CONFLICT` 或 `INVALID_STATE_TRANSITION`
  - 前端提示：按错误码提示“状态已变化，请刷新”

## 2. Admin Auth（管理端认证）

### 2.1 POST /admin/auth/login
**用途**：管理员用户名密码登录；若开启 2FA 则返回 challenge（高频）。

**鉴权规则**
- **是否需要 Authorization**：否（公共接口）
- **允许角色**：PUBLIC

**请求（schema）**
- `Content-Type: application/json`
- Body：
  - `username: string`（`minLength=1`）
  - `password: string`（`minLength=1`）

**响应（schema）**
- 200 + Envelope(success=true)
  - **分支 A：直接登录成功**
    - `data.token: string`
    - `data.admin: { id: string, username: string, phoneBound: boolean }`
  - **分支 B：需要 2FA**
    - `data.requires2fa: true`
    - `data.challengeId: string`

**错误码枚举**
- 401 `ADMIN_CREDENTIALS_INVALID`：用户名或密码错误（包括非 ACTIVE）
- 400 `INVALID_ARGUMENT`：参数校验失败（理论上应存在；现状依赖 pydantic）
- 429 `RATE_LIMITED`：触发“登录失败锁定/限流”（见 `security.md#1.4.3`）
- 500 `INTERNAL_ERROR`：服务端异常（统一错误码见 `#7`）

**幂等要求**
- **不要求** `Idempotency-Key`
- 重复请求语义：允许多次尝试；当账号开启 2FA 时会生成新的 challenge（现状：每次登录都会生成新的 challengeId）

**审计要求**
- 必须记录：`LOGIN`（成功时）
- 建议记录：登录失败/锁定事件（需拍板是否落审计表/安全日志；见 `security.md#1.4.3`）

**分页/排序**：不适用

**证据入口**
- 后端：`backend/app/api/v1/admin_auth.py`（`admin_login`，`POST /admin/auth/login`）

### 2.2 POST /admin/auth/2fa/challenge
- **用途**：发送 2FA 短信验证码
- **请求**：`{ challengeId: string }`
- **响应**：`{ sent: bool, expiresInSeconds: number, resendAfterSeconds: number }`
- **错误码**
  - 400 `INVALID_ARGUMENT`：challengeId 无效
  - 429 `RATE_LIMITED`：触发短信限流/锁定
- **代码证据**：`backend/app/api/v1/admin_auth.py`（`admin_2fa_challenge`）

### 2.3 POST /admin/auth/2fa/verify
- **用途**：验证短信验证码并签发 token
- **请求**：`{ challengeId: string, smsCode: string }`
- **响应**：`{ token: string, admin: { id: string, username: string, phoneBound: true } }`
- **错误码（示例）**
  - 400 `ADMIN_2FA_INVALID`
  - 400 `ADMIN_2FA_EXPIRED`
  - 429 `RATE_LIMITED`：触发验证码校验限流/锁定
- **代码证据**：`backend/app/api/v1/admin_auth.py`（`admin_2fa_verify`）

### 2.4 POST /admin/auth/refresh
**用途**：续期；旧 token 进入 blacklist，立即失效（高频）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：ADMIN

**请求（schema）**
- Header：
  - `Authorization: Bearer <token>`（必填）
- Body：无

**响应（schema）**
- 200 + Envelope(success=true)
  - `data.token: string`（新 token）

**错误码枚举**
- 401 `UNAUTHENTICATED`：未登录/Authorization 缺失/旧 token 已进入 blacklist/无效 token

**幂等要求**
- **不要求** `Idempotency-Key`
- **重复请求语义（需与实现一致）**：
  - 同一旧 token 第一次 refresh：200 返回新 token，并将旧 token jti 写入 blacklist（TTL=旧 token 剩余时间）
  - 同一旧 token 再次 refresh：401 `UNAUTHENTICATED`（因为旧 token 已 blacklist）

**审计要求**
- 待拍板：是否需要记录 `REFRESH` 审计事件（现状：未见写审计）

**分页/排序**：不适用

**证据入口**
- 后端：`backend/app/api/v1/admin_auth.py`（`admin_refresh`，`POST /admin/auth/refresh`）

### 2.5 POST /admin/auth/logout
- **用途**：登出；token 进入 blacklist
- **请求**：无（Header 认证）
- **响应**：`{ success: true }`
- **代码证据**：`backend/app/api/v1/admin_auth.py`（`admin_logout`）

### 2.6 POST /admin/auth/change-password
- **用途**：修改管理员密码
- **请求**：`{ oldPassword: string, newPassword: string }`（密码策略见 `security.md#1.4.2`）
- **响应**：`{ ok: true }`
- **错误码**
  - 400 `INVALID_ARGUMENT`：旧密码错误/新密码不满足密码策略（见 `security.md#1.4.2`）
  - 401 `UNAUTHENTICATED`
- **代码证据**：`backend/app/api/v1/admin_auth.py`（`admin_change_password`）

### 2.7 Admin Phone Bind（绑定手机号，用于 2FA 与高风险门禁）
> 目的：未绑定 phone 的 admin 允许登录，但在高风险操作前必须绑定手机号（你已拍板，见 `security.md#1.4.4`）。

#### 2.7.1 POST /admin/auth/phone-bind/challenge
- **用途**：对指定手机号发送绑定验证码（需要已登录 ADMIN）
- **鉴权**：ADMIN
- **请求**：`{ phone: string }`（CN：`^1\\d{10}$`）
- **响应**：`{ sent: bool, expiresInSeconds: number, resendAfterSeconds: number }`
- **错误码**：
  - 400 `INVALID_PHONE`
  - 429 `RATE_LIMITED`

#### 2.7.2 POST /admin/auth/phone-bind/verify
- **用途**：校验验证码并绑定手机号（需要已登录 ADMIN）
- **鉴权**：ADMIN
- **请求**：`{ phone: string, smsCode: string }`
- **响应**：`{ ok: true, phoneBound: true }`
- **错误码**：
  - 400 `INVALID_PHONE` / `SMS_CODE_INVALID` / `SMS_CODE_EXPIRED`
  - 429 `RATE_LIMITED`
  - 409 `STATE_CONFLICT`：已绑定（重复绑定）
- **审计（必须）**：
  - action=`UPDATE`，resourceType=`ADMIN_AUTH`，resourceId=`adminId`
  - metadata：`requestId`, `phoneMasked`

## 2A. Provider Auth（服务商认证）

### 2A.1 POST /provider/auth/login
**用途**：PROVIDER / PROVIDER_STAFF 登录（高频）。

**鉴权规则**
- PUBLIC（不需要 Authorization）

**请求**
- Body：`{ username: string, password: string }`

**响应**
- 200：`{ token: string, actor: { id, username, actorType, providerId } }`

**错误码**
- 401 `UNAUTHENTICATED`：用户名或密码错误（或账号非 ACTIVE）
- 500 `INTERNAL_ERROR`

**幂等**
- 不要求 `Idempotency-Key`；每次成功登录签发新 token（同账号多次登录视为并行会话，v1 不做互斥）

**审计（必须）**
- 成功登录写 `LOGIN`（resourceType=`PROVIDER_AUTH`，metadata 包含 `requestId/path/method/ip/ua`）

**证据入口**
- `backend/app/api/v1/provider_auth.py::provider_login`

### 2A.2 POST /provider/auth/refresh
**用途**：续期 provider token；旧 token 进入 blacklist（高频）。

**鉴权规则**
- 需要 Authorization（provider token）
- actorType：`PROVIDER|PROVIDER_STAFF`

**响应**
- 200：`{ token: string }`

**错误码**
- 401 `UNAUTHENTICATED`：未登录/旧 token 已 blacklist/无效 token

**幂等**
- 不要求 `Idempotency-Key`
- 同一旧 token 二次 refresh：401 `UNAUTHENTICATED`（blacklist 生效）

**审计**
- v1：未强制要求写 `REFRESH`（与 Admin refresh 同口径，若要记需你拍板）

**证据入口**
- `backend/app/api/v1/provider_auth.py::provider_refresh`

### 2A.3 POST /provider/auth/change-password
**用途**：修改 Provider/ProviderStaff 自己的密码（敏感）。

**鉴权规则**
- 需要 Authorization（provider token）
- actorType：`PROVIDER|PROVIDER_STAFF`

**请求**
- Body：`{ oldPassword: string, newPassword: string }`
- 口径（v1 最小，与现状对齐）：`newPassword.length >= 8`

**响应**
- 200：`{ ok: true }`

**错误码**
- 400 `INVALID_ARGUMENT`：旧密码错误/新密码长度不足
- 401 `UNAUTHENTICATED`：未登录/账号无效

**审计（必须）**
- action=`UPDATE`，resourceType=`PROVIDER_AUTH`，resourceId=`actorId`，summary=`PROVIDER 修改密码` / `PROVIDER_STAFF 修改密码`
- metadata 最小：`requestId/path/method/ip/ua`（不得记录明文密码）

**证据入口**
- `backend/app/api/v1/provider_auth.py::provider_change_password`

## 2B. Dealer Auth（经销商认证）

### 2B.1 POST /dealer/auth/login
**用途**：DEALER 登录（高频）。

**鉴权规则**
- PUBLIC（不需要 Authorization）

**请求**
- Body：`{ username: string, password: string }`

**响应**
- 200：`{ token: string, actor: { id, username, actorType: "DEALER", dealerId } }`

**错误码**
- 401 `UNAUTHENTICATED`：用户名或密码错误（或账号非 ACTIVE）
- 403 `FORBIDDEN`：经销商已停用（DealerStatus != ACTIVE）

**幂等**
- 不要求 `Idempotency-Key`；每次成功登录签发新 token（v1 不做互斥）

**审计（必须）**
- 成功登录写 `LOGIN`（resourceType=`DEALER_AUTH`，metadata 包含 `requestId/path/method/ip/ua`）

**证据入口**
- `backend/app/api/v1/dealer_auth.py::dealer_login`

### 2B.2 POST /dealer/auth/change-password
**用途**：修改 Dealer 自己的密码（敏感）。

**鉴权规则**
- 需要 Authorization（dealer token）
- actorType：`DEALER`

**请求**
- Body：`{ oldPassword: string, newPassword: string }`
- 口径（v1 最小，与现状对齐）：`newPassword.length >= 8`

**响应**
- 200：`{ ok: true }`

**错误码**
- 400 `INVALID_ARGUMENT`：旧密码错误/新密码长度不足
- 401 `UNAUTHENTICATED`：未登录/账号无效

**审计（必须）**
- action=`UPDATE`，resourceType=`DEALER_AUTH`，resourceId=`dealerUserId`
- metadata 最小：`requestId/path/method/ip/ua`（不得记录明文密码）

**证据入口**
- `backend/app/api/v1/dealer_auth.py::dealer_change_password`

## 3. Admin Users（用户查询）

### 3.1 GET /admin/users
- **用途**：用户列表（分页、过滤）
- **查询参数**：`phone, nickname, identity, enterpriseId, enterpriseName, page, pageSize`
- **响应**：`{ items: [...], page, pageSize, total }`
- **隐私约束**：列表返回 `phoneMasked`（不得返回 phone 明文）
- **错误码**：400 `INVALID_ARGUMENT`（identity 不合法）
- **代码证据**：`backend/app/api/v1/admin_users.py`（`admin_list_users`）

### 3.2 GET /admin/users/{id}
- **用途**：用户详情（仍为 phoneMasked）
- **错误码**：404 `NOT_FOUND`
- **代码证据**：`backend/app/api/v1/admin_users.py`（`admin_get_user`）

## 4. Admin Redemptions（核销记录）

### 4.1 GET /admin/redemptions
- **用途**：核销记录列表（分页、过滤）
- **查询参数**：`dateFrom, dateTo, serviceType, status, operatorId, userId, page, pageSize`
- **响应**：`{ items: [...], page, pageSize, total }`
- **错误码**：400 `INVALID_ARGUMENT`（日期格式）
- **代码证据**：`backend/app/api/v1/admin_redemptions.py`（`admin_list_redemptions`）

## 5. Admin Dealer Settlements（经销商结算 - 高风险）

### 5.1 GET /admin/dealer-commission
- **用途**：读取分账规则配置（含 defaultRate、overrides）
- **响应**：`{ defaultRate: number, dealerOverrides: object, updatedAt?: string|null }`
- **代码证据**：`backend/app/api/v1/admin_dealer_settlements.py`（`admin_get_dealer_commission`）

### 5.2 PUT /admin/dealer-commission
- **用途**：更新分账规则配置
- **请求**：`{ defaultRate: number (0~1), dealerOverrides?: { [dealerId]: number } }`
- **响应**：同请求并附 `updatedAt`
- **审计**：TBD（需在 `security.md` 明确“必审计”与字段）
- **代码证据**：`backend/app/api/v1/admin_dealer_settlements.py`（`admin_put_dealer_commission`）

### 5.3 POST /admin/dealer-settlements/generate
**用途**：按周期生成结算单（聚合订单）（资金高风险写；通常会被频繁触发/重试）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：ADMIN

**请求（schema）**
- Body：
  - `cycle: string`：格式 `YYYY-MM`（例如 `2025-12`）

**响应（schema）**
- 200 + Envelope(success=true)
  - `data.cycle: string`
  - `data.created: number`：本次新增条数
  - `data.existing: number`：本次返回的“已存在/并发已存在”条数
  - `data.items: SettlementGenerateItem[]`

SettlementGenerateItem（返回字段与现状对齐）：
- `id: string`
- `dealerId: string`
- `cycle: string`
- `orderCount: number`
- `amount: number`
- `status: string`
- `createdAt: string|null`（ISO）
- `settledAt: string|null`（ISO）
- `grossAmount: number`
- `commissionRate: number`
- `generated: boolean`：本次是否新生成（false=已存在/并发已存在）
- `payoutMethod?: string|null`（仅当 generated=true 且有快照时返回）
- `payoutAccount?: object|null`（同上；accountNo 为 masked）
- `payoutReference?: string|null`（同上）
- `payoutNote?: string|null`（同上）
- `payoutMarkedAt?: string|null`（同上）

**错误码枚举**
- 400 `INVALID_ARGUMENT`：cycle 格式不合法（必须 `YYYY-MM`）
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`

**幂等要求**
- **不要求** `Idempotency-Key`
- **幂等语义（以资源幂等为准）**
  - Key：`(dealerId, cycle)`
  - 若该 key 已存在：必须返回现有记录，且不得覆盖（防止口径漂移）
  - 并发重复：若插入发生唯一冲突，视为已存在并返回 existing

**审计要求**
- 必须：生成动作应记录审计事件（建议 `CREATE` 或 `UPDATE`，resourceType=`SETTLEMENT_RECORD`，metadata 包含 cycle/created/existing/筛选口径）
- 现状：未见明确审计写入（需你确认后再进入实现）

**分页/排序**：不适用（返回聚合结果列表）

**证据入口**
- 后端：`backend/app/api/v1/admin_dealer_settlements.py`（`admin_generate_dealer_settlements`，`POST /admin/dealer-settlements/generate`）

### 5.4 GET /admin/dealer-settlements
- **用途**：结算单列表
- **查询参数**：`page, pageSize, dealerId?, cycle?, status?`
- **代码证据**：`backend/app/api/v1/admin_dealer_settlements.py`（`admin_list_dealer_settlements`）

### 5.5 POST /admin/dealer-settlements/{id}/mark-settled
**用途**：标记结算完成（资金高风险操作，需强审计）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：ADMIN

**请求（schema）**
- Path：
  - `id: string`（结算单 ID；不能为空）
- Body：
  - `payoutReference?: string|null`（maxLength=128）
  - `payoutNote?: string|null`（maxLength=512）

**响应（schema）**
- 200 + Envelope(success=true)
  - `data.id: string`
  - `data.status: string`（预期为 `SETTLED`）
  - `data.settledAt: string|null`（ISO）
  - `data.payoutReference: string|null`
  - `data.payoutNote: string|null`
  - `data.payoutMarkedAt: string|null`（ISO）

**错误码枚举**
- 400 `INVALID_ARGUMENT`：id 为空 / body 校验失败
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 404 `NOT_FOUND`：结算单不存在
- 409 `STATE_CONFLICT`：结算单已冻结，禁止结算
- 409 `INVALID_STATE_TRANSITION`：非法状态流转（如从非允许状态标记结算；具体状态机需补齐）

**幂等要求（你已拍板的统一口径）**
- **不强制要求** `Idempotency-Key`（可选：未来若需要更强防重复可引入）
- **重复提交（目标=SETTLED）**：
  - 若当前已是 `SETTLED`：返回 **200 幂等 no-op**，并返回当前 `status/settledAt/payoutMarkedAt`（以及版本号如有）
  - 若当前可从“未结算”转到 `SETTLED`：执行一次性状态变更并返回 200
- **非法状态流转**：返回 **409**（`STATE_CONFLICT` / `INVALID_STATE_TRANSITION`）

**审计要求（必须）**
- 必须记录：结算标记动作（建议 action=`UPDATE` 或新增 action=`SETTLE`，resourceType=`SETTLEMENT_RECORD`，resourceId=`{id}`）
- metadata 最小字段：`payoutReference`（如允许）、`payoutNote`（如允许）、`requestId`、操作者 id

**分页/排序**：不适用

**证据入口**
- 后端：`backend/app/api/v1/admin_dealer_settlements.py`（`admin_mark_dealer_settlement_settled`，`POST /admin/dealer-settlements/{id}/mark-settled`）

## 6. Admin Website Config（配置发布类）
> 目标：固化“官网配置可运行时发布”的最小生产口径（门禁 + 审计 + 版本推进）。

**统一约定**
- GET：仅 `require_admin`
- PUT（发布类写操作）：**高风险门禁** `require_admin_phone_bound`
  - 未绑定手机号：403 `ADMIN_PHONE_REQUIRED`
- **版本推进**：PUT 成功后服务端生成新 `version`（字符串，时间戳）；no-op 不推进 version
- **幂等 no-op**：当除 `version` 外的字段不变时，返回 200 且不写审计、不更新
- **审计（必须）**：action=`UPDATE`，resourceType=`WEBSITE_CONFIG`，resourceId=配置 key
  - metadata 最小：`requestId/key/beforeVersion/afterVersion/changedFields`

### 6.1 SEO（Site SEO）
- `GET /admin/website/site-seo`
- `PUT /admin/website/site-seo`
  - 400 `INVALID_ARGUMENT`：canonicalBaseUrl 非 http(s) 或必填字段缺失（由 pydantic 校验）

### 6.2 导航开关（Nav Control）
- `GET /admin/website/nav-control`
- `PUT /admin/website/nav-control`
  - 400 `INVALID_ARGUMENT`：navItems 缺项/多项

### 6.3 维护模式（Maintenance Mode）
- `GET /admin/website/maintenance-mode`
- `PUT /admin/website/maintenance-mode`
  - 400 `INVALID_ARGUMENT`：allowPaths 项不以 `/` 开头等

### 6.4 导流外链（External Links）
- `GET /admin/website/external-links`
- `PUT /admin/website/external-links`
  - 400 `INVALID_ARGUMENT`：URL 非 http(s)

### 6.5 页脚配置（Footer Config）
- `GET /admin/website/footer-config`
- `PUT /admin/website/footer-config`

### 6.6 首页推荐场所（Home Recommended Venues）
- `GET /admin/website/home/recommended-venues`
- `PUT /admin/website/home/recommended-venues`
  - 400 `INVALID_ARGUMENT`：重复 venueId / 场所不存在 / 场所未发布

**证据入口**
- 后端：`backend/app/api/v1/admin_website_config.py`

## 7. 错误码与语义（最小集合）
> 约定：HTTP 状态码 + `error.code` 共同表达语义；**前端不得只看 message**。
>
> 目标：形成“后端可预测、前端可统一处理”的最小闭环（对应 `TASK-P0-007`）。

### 7.1 通用错误码（跨接口通用）
> 说明：
> - 下表是“跨接口通用”的最小集合；各接口仍可定义更细的业务错误码（例如 `ADMIN_CREDENTIALS_INVALID`）。
> - 所有错误都必须用 envelope 形式返回：`success=false, data=null, error={code,message,details?}, requestId`。

| HTTP | code | 含义 |
|---|---|---|
| 400 | INVALID_ARGUMENT | 参数非法/校验失败 |
| 401 | UNAUTHENTICATED | 未登录/登录态无效 |
| 403 | FORBIDDEN | 无权限 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | STATE_CONFLICT | 状态冲突（如冻结禁止结算、资源状态已变化） |
| 409 | INVALID_STATE_TRANSITION | 非法状态流转（会改变结果的重复提交/不允许的状态迁移） |
| 409 | ALREADY_EXISTS | 资源已存在（例如 username 重复） |
| 429 | RATE_LIMITED | 请求过于频繁/触发限流 |
| 500 | INTERNAL_ERROR | 服务端内部错误（不暴露堆栈） |

### 7.2 典型业务错误码（仅在对应接口出现）
- 401 `ADMIN_CREDENTIALS_INVALID`：管理员用户名/密码错误（或账号非 ACTIVE）
- 400 `ADMIN_2FA_INVALID`：2FA 验证失败
- 400 `ADMIN_2FA_EXPIRED`：2FA 已过期
- 403 `ADMIN_PHONE_REQUIRED`：高风险操作前置条件未满足（未绑定手机号）

### 7.3 前端处理动作（基线）
> 说明：这是**生产友好**的最小 UX 口径；页面可在不违反本口径的前提下补充更细的提示，但不得改 code 语义。

- **401 UNAUTHENTICATED**
  - 动作：清理 session → 跳转登录页 `/login?reason=UNAUTHENTICATED&next=<current>`
  - 备注：避免在页面重复弹 message（由全局跳转兜底）
- **403 FORBIDDEN**
  - 动作：跳转 `/403`
- **403 ADMIN_PHONE_REQUIRED**
  - 动作：提示“请先绑定手机号”，并引导进入 `/account/security` 完成绑定（不得跳 403）
- **400 INVALID_ARGUMENT**
  - 动作：提示“参数错误：{message}”，并展示 `code/requestId`（便于排障）
- **404 NOT_FOUND**
  - 动作：提示“资源不存在”，并展示 `code/requestId`
- **409 STATE_CONFLICT / INVALID_STATE_TRANSITION**
  - 动作：提示“状态已变化，请刷新”（或更具体的业务 message），并展示 `code/requestId`
- **429 RATE_LIMITED**
  - 动作：提示“操作太频繁，请稍后重试”，并展示 `code/requestId`
- **500 INTERNAL_ERROR**
  - 动作：提示“系统繁忙，请稍后重试”，并展示 `requestId`

## 8. 幂等约定（Baseline）
- **生成类**：如 `generate`，同 key（cycle+dealer）重复调用不得产生重复记录
- **发布类/写入类**：应明确“覆盖/拒绝/版本号 CAS”策略（TBD）
- **实现证据占位**：每个写接口需在任务完成时补齐“幂等点证明”（SQL 唯一约束/事务/Redis 锁/版本号等）

## 9. 审计日志查询（Top 5：AUDIT-LIST）

### 9.1 GET /admin/audit-logs
**用途**：审计日志查询（高频 + 敏感，排障主入口）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：ADMIN

**请求（schema）**
- Query（均为可选，未传表示不过滤）：
  - `actorType?: "ADMIN"|"USER"|"DEALER"|"PROVIDER"|"PROVIDER_STAFF"`
  - `actorId?: string`
  - `action?: "CREATE"|"UPDATE"|"PUBLISH"|"OFFLINE"|"APPROVE"|"REJECT"|"LOGIN"|"LOGOUT"`
  - `resourceType?: string`
  - `resourceId?: string`
  - `keyword?: string`（按 summary 模糊匹配）
  - `dateFrom?: string`（`YYYY-MM-DD` 或 ISO datetime；含义：createdAt >= dateFrom）
  - `dateTo?: string`（同上；createdAt <= dateTo）
  - `page?: number`（默认 1）
  - `pageSize?: number`（默认 20，最大 100）

**响应（schema）**
- 200 + Envelope(success=true)
  - `data.items: AuditLogItem[]`
  - `data.page: number`
  - `data.pageSize: number`
  - `data.total: number`

AuditLogItem：
- `id: string`
- `actorType: string`
- `actorId: string`
- `action: string`
- `resourceType: string`
- `resourceId?: string|null`
- `summary?: string|null`
- `ip?: string|null`
- `userAgent?: string|null`
- `metadata?: any|null`（出参兜底脱敏：password/token/smsCode/phone 等）
- `createdAt: string`（ISO）

**错误码枚举**
- 400 `INVALID_ARGUMENT`：时间格式不合法（dateFrom/dateTo）
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`

**幂等要求**：不适用（读接口）

**审计要求**
- 不要求对“查询本身”写审计（默认不写）；若监管要求可在后续任务中补充“审计查询也审计”

**分页/排序**
- 分页：`page/pageSize`，`pageSize<=100`
- 排序：按 `created_at desc`（固定）

**证据入口**
- 后端：`backend/app/api/v1/audit_logs.py`（`admin_list_audit_logs`，`GET /admin/audit-logs`）

## 9A. 平台预约监管（Admin Bookings）

### 9A.1 GET /admin/bookings
**用途**：平台侧预约监管查询（只读）。**你已拍板：必须使用 `/admin/*` 语义边界，不复用 `/provider/*`**。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：仅 ADMIN

**请求（Query - 最小集合，你已拍板）**
- `status?: "PENDING"|"CONFIRMED"|"CANCELLED"|"COMPLETED"`
- `serviceType?: string`（服务编码）
- `keyword?: string`（语义：匹配 bookingId / userId / venueId；实现建议“等值优先”）
- `dateFrom?: string`（`YYYY-MM-DD`，按 bookingDate 起）
- `dateTo?: string`（`YYYY-MM-DD`，按 bookingDate 止，**含当日**）
- `venueId?: string`（精确过滤某场所；不要求立刻在前端暴露）
- `providerId?: string`（精确过滤某服务商；不要求立刻在前端暴露）
- `page?: number`（默认 1，整数 ≥ 1）
- `pageSize?: number`（默认 20；建议限制为 10/20/50/100；后端可额外上限 100）

**排序口径（固定，不对外暴露 sort 参数）**
- `bookingDate DESC, createdAt DESC`

**响应（Response - 最小字段，你已拍板）**
- 200 + Envelope(success=true)
  - `data.items: AdminBookingItem[]`
  - `data.page: number`
  - `data.pageSize: number`
  - `data.total: number`

AdminBookingItem（最小字段）：
- `id: string`
- `entitlementId: string`
- `userId: string`
- `venueId: string`
- `serviceType: string`
- `bookingDate: string`（`YYYY-MM-DD`）
- `timeSlot: string`（如 `HH:mm-HH:mm`）
- `status: "PENDING"|"CONFIRMED"|"CANCELLED"|"COMPLETED"`
- `confirmationMethod: "AUTO"|"MANUAL"`
- `confirmedAt?: string|null`
- `createdAt: string`

允许但不要求（可选扩展字段，若后端已有 DTO 可顺带返回）：
- `sourceType?` / `orderId?` / `orderItemId?` / `productId?` / `cancelledAt?` / `cancelReason?` 等

**错误码枚举（最小，你已拍板）**
- 400 `INVALID_ARGUMENT`：日期格式错误、page/pageSize 越界、status 枚举非法等
- 401 `UNAUTHENTICATED`：未登录/Token 无效
- 403 `FORBIDDEN`：非 ADMIN

**幂等要求**：不适用（读接口）

**审计要求**
- 默认不要求对“查询本身”写审计（避免爆量）；如监管要求可后续增补“查询审计”

**实现证据占位**
- 后端：`backend/app/api/v1/bookings.py::admin_list_bookings`（`GET /admin/bookings`）

### 9A.2 DELETE /admin/bookings/{id}
**用途**：平台侧强制取消预约（例外处置）。必须填写原因、必须幂等（网络重试/重复点击友好）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：仅 ADMIN

**请求**
- Header：
  - `Idempotency-Key: string`（**必填**）
- Path：
  - `id: string`（bookingId）
- Body（JSON）：
  - `reason: string`（必填；trim 后不可为空）

**响应**
- 200 + Envelope(success=true)
  - `data`: Booking DTO（复用 `_booking_dto` 字段集合；至少包含你拍板的最小字段）

**错误码（最小集合）**
- 400 `INVALID_ARGUMENT`：reason 为空；缺少 `Idempotency-Key`
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 404 `NOT_FOUND`
- 409 `INVALID_STATE_TRANSITION`：预约已 `COMPLETED`（非法状态流转）

**幂等/状态机兜底（按 1.4 统一口径）**
- 目标状态：`CANCELLED`
- 重复提交到同一目标状态：
  - 若当前已是 `CANCELLED`：返回 **200 幂等 no-op**（返回当前资源状态）
  - 若同一 `Idempotency-Key` 重复请求：返回 **200 幂等复放**（返回首次结果）
- 非法状态流转：
  - `COMPLETED` 再取消：返回 **409 `INVALID_STATE_TRANSITION`**

**审计要求（必须）**
- 必须记录：强制取消（action=`UPDATE`，resourceType=`BOOKING`，resourceId=`{id}`）
- metadata 最小字段：`requestId`、`beforeStatus`、`afterStatus`、`reason`（可截断）、
  `bookingDate/timeSlot/venueId/serviceType/userId`

**证据入口**
- 后端：`backend/app/api/v1/bookings.py::admin_cancel_booking`（`DELETE /admin/bookings/{id}`）

## 9B. 订单监管（Admin Orders）

> 说明：本节为 `FLOW-ORDERS` 的“可生产”契约基线。**当前后端已存在实现**（见“证据入口”），但缺少在 `specs-prod/admin/` 下的契约固化与一致性验收。

### 9B.1 GET /admin/orders
**用途**：平台订单监管列表（分页、过滤；隐私字段脱敏）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：仅 ADMIN

**请求（Query）**
- `orderNo?: string`（订单号；现状口径：`orderNo=id`）
- `userId?: string`
- `phone?: string`（模糊匹配；**隐私：仅允许作为过滤，不返回明文**）
- `orderType?: "PRODUCT"|"SERVICE_PACKAGE"`
- `fulfillmentType?: "SERVICE"|"PHYSICAL_GOODS"`
- `paymentStatus?: "PENDING"|"PAID"|"FAILED"|"REFUNDED"`
- `dealerId?: string`
- `providerId?: string`（后端现状：从订单明细聚合推导，若同订单存在多个 provider 则 providerId 为空）
- `dateFrom?: string`（`YYYY-MM-DD` 或 ISO datetime；含义：createdAt >= dateFrom）
- `dateTo?: string`（同上；createdAt <= dateTo）
- `page?: number`（默认 1，>=1）
- `pageSize?: number`（默认 20，建议 10/20/50/100，后端上限 100）

**排序（固定，不对外暴露 sort 参数）**
- `createdAt DESC`

**响应（Response）**
- 200 + Envelope(success=true)
  - `data.items: AdminOrderItem[]`
  - `data.page: number`
  - `data.pageSize: number`
  - `data.total: number`

AdminOrderItem（与现状实现对齐的最小字段）：
- `id: string`
- `orderNo: string`
- `userId: string`
- `buyerPhoneMasked?: string|null`
- `orderType: string`
- `paymentStatus: string`
- `fulfillmentType?: string|null`
- `fulfillmentStatus?: string|null`
- `totalAmount: number`
- `goodsAmount: number`
- `shippingAmount: number`
- `shippingCarrier?: string|null`
- `trackingNoLast4?: string|null`
- `shippedAt?: string|null`
- `dealerId?: string|null`
- `providerId?: string|null`
- `createdAt: string`
- `paidAt?: string|null`

**错误码（最小集合）**
- 400 `INVALID_ARGUMENT`：dateFrom/dateTo 格式不合法、page/pageSize 越界等
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`

**幂等要求**：不适用（读接口）

**审计要求**
- 默认不要求对“查询本身”写审计（避免爆量）；如监管要求后续增补“查询审计”

**证据入口**
- 后端：`backend/app/api/v1/orders.py::admin_list_orders`（`GET /admin/orders`）

### 9B.2 POST /admin/orders/{id}/ship
**用途**：管理员发货（仅物流商品订单）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：仅 ADMIN

**请求**
- Path：`id: string`
- Body：
  - `carrier: string`（minLength=1, maxLength=64）
  - `trackingNo: string`（minLength=3, maxLength=64）

**响应**
- 200 + Envelope(success=true)
  - `data`: 返回订单详情 DTO（现状实现：`_order_dto`）

**错误码（最小集合，结合现状实现）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 404 `NOT_FOUND`：订单不存在
- 400 `INVALID_ARGUMENT`：非物流商品订单不可发货
- 409 `STATE_CONFLICT`：仅已支付订单可发货 / 订单状态不允许发货

**幂等/状态机兜底（按 1.4 统一口径，草案）**
- 目标状态：`fulfillmentStatus=SHIPPED`
- **重复提交到同一目标状态**：
  - 若订单当前已是 `SHIPPED`：
    - **当 (carrier, trackingNo) 与已存在一致**：返回 200 幂等 no-op，并返回当前订单状态/字段
    - **当 (carrier, trackingNo) 不一致**：返回 409 `INVALID_STATE_TRANSITION`（避免“二次覆盖运单号”造成对账风险）
- **非法状态流转**：
  - 当前为 `DELIVERED/RECEIVED` 再 ship：返回 409 `INVALID_STATE_TRANSITION`

**审计要求（必须）**
- 必须记录：`UPDATE`（resourceType=`ORDER`，resourceId=`{id}`）
- metadata 最小字段：
  - `requestId`
  - `before.fulfillmentStatus` / `after.fulfillmentStatus`
  - `carrier`
  - `trackingNo`（建议脱敏：仅后 4 位；避免明文入审计）

**证据入口**
- 后端：`backend/app/api/v1/orders.py::admin_ship_order`（`POST /admin/orders/{id}/ship`）

### 9B.3 POST /admin/orders/{id}/deliver
**用途**：管理员标记妥投（仅物流商品订单）。

**鉴权规则**
- **是否需要 Authorization**：是（`Bearer <adminToken>`）
- **允许角色**：仅 ADMIN

**请求**
- Path：`id: string`
- Body：无

**响应**
- 200 + Envelope(success=true)
  - `data`: 返回订单详情 DTO（现状实现：`_order_dto`）

**错误码（最小集合，结合现状实现）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 404 `NOT_FOUND`
- 400 `INVALID_ARGUMENT`：非物流商品订单不可标记妥投
- 409 `STATE_CONFLICT`：仅已发货订单可标记妥投

**幂等/状态机兜底（按 1.4 统一口径，草案）**
- 目标状态：`fulfillmentStatus=DELIVERED`
- **重复提交到同一目标状态**：
  - 若订单当前已是 `DELIVERED`：返回 200 幂等 no-op，并返回当前订单状态/字段
- **非法状态流转**：
  - 当前为 `RECEIVED` 再 deliver：返回 409 `INVALID_STATE_TRANSITION`

**审计要求（必须）**
- 必须记录：`UPDATE`（resourceType=`ORDER`，resourceId=`{id}`）
- metadata 最小字段：
  - `requestId`
  - `before.fulfillmentStatus` / `after.fulfillmentStatus`

**证据入口**
- 后端：`backend/app/api/v1/orders.py::admin_mark_delivered`（`POST /admin/orders/{id}/deliver`）

## 9C. 投放链接（Dealer Links）

> 说明：本节为 `FLOW-DEALER-LINKS` 的“可生产”契约基线（高风险：可被滥用导流下单；必须权限硬校验 + 强审计 + 防重复）。
>
> 代码现状：后端已存在 `GET/POST /dealer-links`、`POST /dealer-links/{id}/disable`，并支持 `DEALER/ADMIN` 二选一鉴权（证据见本节末）。

### 9C.1 POST /dealer-links
**用途**：生成投放链接（两类）：
- **入口链接**：`sellableCardId=null`（经销商入口，H5 展示该经销商全部可售卡）
- **授权某卡链接**：`sellableCardId=<id>`（用于组合生成“某卡直达链接”，前端可能在入口链接上拼 `sellableCardId`）

**鉴权规则**
- **Authorization**：是（`Bearer <token>`）
- **允许角色**：DEALER 或 ADMIN
- **数据范围**
  - DEALER：后端从 token 推导 `dealerId`，**禁止前端传 dealerId**
  - ADMIN：允许传 `dealerId`（用于运营代配/排查）

**请求（Body）**
- `dealerId?: string|null`（仅 ADMIN 场景允许；DEALER 场景忽略/禁止）
- `sellableCardId?: string|null`（可空：入口链接）
- `campaign?: string|null`（maxLength=128）
- `validFrom?: string|null`（`YYYY-MM-DD`；可空）
- `validUntil: string`（`YYYY-MM-DD`；必填；含当日 23:59:59）

**响应（Response）**
- 200 + Envelope(success=true)
  - `data: DealerLinkDto`

DealerLinkDto（与现状对齐）：
- `id: string`
- `dealerId: string`
- `productId?: string|null`（历史字段，可为空）
- `sellableCardId?: string|null`
- `campaign?: string|null`
- `status: "ENABLED"|"DISABLED"|"EXPIRED"`
- `validFrom?: string|null`
- `validUntil?: string|null`
- `url: string`（后端回填示例：`/h5?dealerLinkId=<id>`）
- `uv?: number|null`
- `paidCount?: number|null`
- `createdAt: string`
- `updatedAt: string`

**错误码（最小集合，结合现状实现）**
- 400 `INVALID_ARGUMENT`：
  - `dealerId` 缺失/不存在（ADMIN 场景）
  - `validUntil` 缺失或日期格式不合法
  - `validFrom` 格式不合法 / `validFrom > validUntil`
  - `sellableCardId` 不存在
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`：
  - 经销商已停用
  - 可售卡已停用

**幂等/防重复（需要拍板后落地）**
- 目标：避免“重复点击/网络重试”生成多条重复链接（风控与排障困难）。
- 建议（最小可生产）：
  - 要求 Header：`Idempotency-Key`（可选 -> 建议改为必填，需你拍板）
  - 幂等键作用域：`operation=create_dealer_link` + `actorType/actorId` + `Idempotency-Key`
  - 重复请求：返回 200 幂等 no-op（复用第一次的返回体）

**审计要求（必须）**
- 必须记录：创建投放链接（action=`CREATE`）
- resourceType：`DEALER_LINK`
- resourceId：`{id}`
- metadata 最小字段：
  - `requestId`
  - `dealerId`
  - `sellableCardId`（可空）
  - `validFrom/validUntil`
  - `campaign`（可空）

**证据入口**
- 后端：`backend/app/api/v1/dealer_links.py::create_dealer_link`（`POST /dealer-links`）

### 9C.2 GET /dealer-links
**用途**：投放链接列表查询（分页、过滤、关键字）。

**鉴权规则**
- **Authorization**：是
- **允许角色**：DEALER 或 ADMIN
- **数据范围**
  - DEALER：强制限定 `dealerId = token.dealerId`
  - ADMIN：可传 `dealerId` 做过滤

**请求（Query）**
- `dealerId?: string`（仅 ADMIN 可用）
- `status?: "ENABLED"|"DISABLED"|"EXPIRED"`
- `sellableCardId?: string`
- `dateFrom?: string`（`YYYY-MM-DD`，按 createdAt 起）
- `dateTo?: string`（`YYYY-MM-DD`，按 createdAt 止）
- `keyword?: string`（匹配 id/dealerId/sellableCardId/campaign/url）
- `page?: number`（默认 1）
- `pageSize?: number`（默认 20，上限 100）

**响应**
- 200 + Envelope(success=true)
  - `data: { items: DealerLinkDto[], page, pageSize, total }`

**错误码**
- 400 `INVALID_ARGUMENT`：dateFrom/dateTo 格式不合法
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`

**幂等/审计**：读接口默认不审计；幂等不适用

**证据入口**
- 后端：`backend/app/api/v1/dealer_links.py::list_dealer_links`（`GET /dealer-links`）

### 9C.3 POST /dealer-links/{id}/disable
**用途**：停用投放链接（高风险写操作，必须强审计）。

**鉴权规则**
- **Authorization**：是
- **允许角色**：DEALER 或 ADMIN
- **数据范围**：
  - DEALER：仅可停用“自己 dealerId 的链接”
  - ADMIN：可停用任意链接

**请求**
- Path：`id: string`
- Body：无

**响应**
- 200 + Envelope(success=true)
  - `data: DealerLinkDto`（返回停用后的链接；若已 EXPIRED 保持 EXPIRED）

**错误码（最小集合，结合现状实现）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`：DEALER 越权停用他人链接
- 404 `NOT_FOUND`

**幂等/状态机兜底**
- 目标状态：`DISABLED`（但若已 EXPIRED 则保持 EXPIRED）
- 重复提交：
  - 已 DISABLED：200 no-op 返回当前状态
  - 已 EXPIRED：200 no-op 返回 EXPIRED

**审计要求（必须）**
- 必须记录：停用投放链接（action=`UPDATE`）
- resourceType：`DEALER_LINK`
- resourceId：`{id}`
- metadata 最小字段：`requestId`、`beforeStatus`、`afterStatus`、`dealerId`

**证据入口**
- 后端：`backend/app/api/v1/dealer_links.py::disable_dealer_link`（`POST /dealer-links/{id}/disable`）

## 9D. 导出（Export）

> v1 形态（你已拍板）：**同步导出直接下载、不落盘（TTL=0）**。

### 9D.1 GET /dealer/orders/export（CSV）
**用途**：导出“经销商订单归属”列表为 CSV（与 `/dealer/orders` 列表字段对齐）。

**鉴权规则**
- **Authorization**：是（DEALER/ADMIN 二选一）
- **数据范围**：
  - DEALER：强制限定本 dealerId（后端从 token 推导）
  - ADMIN：必须显式传 `dealerId`（用于代查/排障）

**请求（Query）**
- `dealerId?: string`（仅 ADMIN 必填）
- `dealerLinkId?: string`
- `orderNo?: string`
- `phone?: string`（仅用于过滤；导出仍为 `buyerPhoneMasked`）
- `paymentStatus?: "PENDING"|"PAID"|"FAILED"|"REFUNDED"`
- `dateFrom: string`（必填 `YYYY-MM-DD`，按 createdAt 起）
- `dateTo: string`（必填 `YYYY-MM-DD`，按 createdAt 止，**含当日**）

**约束（你已拍板）**
- **dateFrom + dateTo 必填**：任一缺失 → 400 `INVALID_ARGUMENT`
- **maxRows=5000**：超限 → 400 `INVALID_ARGUMENT`（提示缩小范围/增加筛选）

**响应**
- 200：`Content-Disposition: attachment; filename="dealer-orders-<dealerId>-<dateFrom>-<dateTo>.csv"`
- Content-Type：`text/csv; charset=utf-8`
- Body：UTF-8（带 BOM）CSV 内容

**CSV 列（与前端 DealerOrdersPage 现状对齐）**
- 订单号、投放链接ID、卡片、区域级别、手机号（masked）、支付状态、金额、创建时间、支付时间

**错误码**
- 400 `INVALID_ARGUMENT`：dateFrom/dateTo 缺失或格式不合法；导出行数 > 5000；dealerId 缺失（ADMIN 场景）
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`

**审计要求（必须）**
- action：v1 先用 `UPDATE`（不新增枚举）
- resourceType：`EXPORT_DEALER_ORDERS`
- resourceId：`dealerId`
- metadata 最小字段：`requestId`、`dealerId`、filters、`rowCount`、`maxRows`

**文件生命周期**
- v1：不落盘（TTL=0），下载即销毁

**证据入口**
- 后端：`backend/app/api/v1/dealer.py::export_dealer_orders_csv`（`GET /dealer/orders/export`）
- 前端：`frontend/admin/src/pages/dealer/DealerOrdersPage.vue::exportCsv`（改为后端下载）

## 9E. 账号管理（Admin Accounts - 高风险）

> 目标：固化“创建/重置/冻结/启用”账号的最小生产口径（审计 + phone 绑定门禁 + 幂等行为）。

### 9E.1 门禁与前置条件（统一）
- 角色：ADMIN
- 高风险门禁：写操作（create/reset/suspend/activate）必须满足 `require_admin_phone_bound`
  - 403 `ADMIN_PHONE_REQUIRED`：未绑定手机号（见 `security.md#1.4.4`）

### 9E.2 ProviderUser
- `GET /admin/provider-users`：分页查询（读接口，仅 require_admin）
- `POST /admin/provider-users`：创建 ProviderUser（同时创建 Provider + 默认 Venue）
  - 409 `ALREADY_EXISTS`：username 重复
  - 审计：action=`CREATE`，resourceType=`PROVIDER_USER`，metadata 含 `targetUserId/providerId/requestId`（不得记录明文密码）
  - 响应包含 `password`（仅本次返回一次；不得有查询明文密码接口）
- `POST /admin/provider-users/{id}/reset-password`：重置密码（高风险）
  - 404 `NOT_FOUND`
  - 审计：action=`UPDATE`，resourceType=`PROVIDER_USER`（不得记录明文密码）
  - 响应包含 `password`（仅本次返回一次）
- `POST /admin/provider-users/{id}/suspend`：冻结（状态写）
  - 幂等：已 SUSPENDED → 200 no-op（不刷审计）
  - 审计：action=`UPDATE`，metadata 含 before/after
- `POST /admin/provider-users/{id}/activate`：启用（状态写）
  - 幂等：已 ACTIVE → 200 no-op（不刷审计）
  - 审计：action=`UPDATE`

### 9E.3 ProviderStaff
- `GET /admin/provider-staff`：分页查询
- `POST /admin/provider-staff`：创建 staff（高风险）
  - 404 `NOT_FOUND`：provider 不存在
  - 409 `ALREADY_EXISTS`：username 与 providerUser/providerStaff 冲突
  - 审计：action=`CREATE`，resourceType=`PROVIDER_STAFF`
  - 响应包含 `password`（仅本次返回一次）
- `POST /admin/provider-staff/{id}/reset-password`：重置密码（高风险）
  - 404 `NOT_FOUND`
  - 审计：action=`UPDATE`，resourceType=`PROVIDER_STAFF`
- `POST /admin/provider-staff/{id}/suspend|activate`：状态切换（幂等 no-op 同上）

### 9E.4 DealerUser
- `GET /admin/dealer-users`：分页查询
- `POST /admin/dealer-users`：创建 DealerUser（同时创建 Dealer）
  - 409 `ALREADY_EXISTS`
  - 审计：action=`CREATE`，resourceType=`DEALER_USER`
  - 响应包含 `password`（仅本次返回一次）
- `POST /admin/dealer-users/{id}/reset-password`：重置密码（高风险）
  - 404 `NOT_FOUND`
  - 审计：action=`UPDATE`，resourceType=`DEALER_USER`
- `POST /admin/dealer-users/{id}/suspend|activate`：状态切换（幂等 no-op 同上）

## 9F. 场所审核（Admin Venues Review - 高风险）

> 目标：固化 `publish/reject/offline` 的最小生产口径（phone 绑定门禁 + 审计 + 幂等 no-op）。

### 9F.1 GET /admin/venues
- 鉴权：ADMIN（require_admin）
- Query：`keyword/providerId/publishStatus/page/pageSize`
- 响应：`{ items, page, pageSize, total }`

### 9F.2 GET /admin/venues/{id}
- 鉴权：ADMIN（require_admin）
- 404：`NOT_FOUND`
- 审计：该接口属于“敏感详情查看”（含联系方式），已按 `TASK-P0-006` 写 `VIEW` 审计（metadata 仅记录 phoneMasked）

### 9F.3 POST /admin/venues/{id}/publish
- 角色：ADMIN
- 高风险门禁：`require_admin_phone_bound`（未绑定 → 403 `ADMIN_PHONE_REQUIRED`）
- 目标状态：`PUBLISHED`
- 幂等：
  - 已 `PUBLISHED` 再 publish：200 no-op（不刷审计）
- 审计：
  - action=`PUBLISH`，resourceType=`VENUE`，resourceId=`{id}`
  - metadata：`requestId`、`beforePublishStatus`、`afterPublishStatus`

### 9F.4 POST /admin/venues/{id}/reject
- 角色：ADMIN
- 高风险门禁：`require_admin_phone_bound`
- 目标状态：`DRAFT`
- 幂等：
  - 已 `DRAFT` 再 reject：200 no-op（不刷审计）
- 审计：action=`REJECT`（非 no-op 时）

### 9F.5 POST /admin/venues/{id}/offline
- 角色：ADMIN
- 高风险门禁：`require_admin_phone_bound`
- 目标状态：`OFFLINE`
- 幂等：
  - 已 `OFFLINE` 再 offline：200 no-op（不刷审计）
- 审计：action=`OFFLINE`（非 no-op 时）

### 9F.6 状态机非法迁移（你已拍板）
- **禁止 DRAFT -> OFFLINE**：返回 409 `INVALID_STATE_TRANSITION`
- **禁止 PUBLISHED -> DRAFT（reject）**：返回 409 `INVALID_STATE_TRANSITION`（已发布要么保持发布，要么先 OFFLINE）

## 9G. CMS 内容发布/下线（Admin CMS - 高风险：线上内容）

> 目标：固化“内容上线/下线”的最小生产口径（phone 绑定门禁 + 审计 + 幂等 no-op + 409 语义）。

### 9G.1 POST /admin/cms/contents/{id}/publish
- **用途**：发布内容到指定渠道（官网/小程序）。
- **鉴权**：仅 ADMIN
- **高风险门禁**：`require_admin_phone_bound`（未绑定 → 403 `ADMIN_PHONE_REQUIRED`）
- **请求**
  - Path：`id: string`
  - Query：`scope?: "WEB"|"MINI_PROGRAM"`（默认 `WEB`）
- **响应**
  - 200 + Envelope(success=true)
  - `data`：CmsContent DTO（至少含：`id/title/channelId/status/publishedAt/mpStatus/mpPublishedAt/updatedAt`）
- **幂等/状态机兜底（按 1.4 统一口径）**
  - 目标状态：`PUBLISHED`
  - 若当前已是目标状态：返回 **200 幂等 no-op**（返回当前资源状态；不刷审计）
  - 非法状态迁移：返回 **409 `INVALID_STATE_TRANSITION`**
- **错误码（最小集合）**
  - 400 `INVALID_ARGUMENT`：scope 非法等
  - 401 `UNAUTHENTICATED`
  - 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`
  - 404 `NOT_FOUND`
  - 409 `INVALID_STATE_TRANSITION`
- **审计（必须）**
  - 非 no-op 时写审计：action=`PUBLISH`，resourceType=`CMS_CONTENT`，resourceId=`{id}`
  - metadata 最小：`requestId`、`scope`、`beforeStatus`、`afterStatus`

### 9G.2 POST /admin/cms/contents/{id}/offline
- **用途**：下线内容（指定渠道）。
- **鉴权**：仅 ADMIN
- **高风险门禁**：`require_admin_phone_bound`
- **请求**
  - Path：`id: string`
  - Query：`scope?: "WEB"|"MINI_PROGRAM"`（默认 `WEB`）
- **响应**：同 9G.1（返回 CmsContent DTO）
- **幂等/状态机兜底**
  - 目标状态：`OFFLINE`
  - 若当前已是目标状态：返回 **200 幂等 no-op**（不刷审计）
  - 非法状态迁移：返回 **409 `INVALID_STATE_TRANSITION`**
- **错误码**：同 9G.1
- **审计（必须）**
  - 非 no-op 时写审计：action=`OFFLINE`，resourceType=`CMS_CONTENT`，resourceId=`{id}`
  - metadata 最小：`requestId`、`scope`、`beforeStatus`、`afterStatus`

## 9H. 小程序配置发布/下线（Admin Mini Program Config - 高风险：渠道配置）

> 目标：固化“草稿保存 + 发布/下线”的最小生产口径（phone 绑定门禁 + 审计 + 幂等 no-op + 版本推进）。

**统一约定**
- GET：`require_admin`
- PUT（草稿保存）：`require_admin`（不推进 `version`；不强制审计，v1 最小）
- POST publish/offline（生效发布类）：`require_admin_phone_bound`
  - 未绑定手机号：403 `ADMIN_PHONE_REQUIRED`
- **版本推进**：仅在 publish/offline **真实发生变更** 时推进 `version`（字符串时间戳）；no-op 不推进
- **幂等 no-op**：重复提交到同一目标状态 → 200 no-op（返回当前 version；不刷审计）
- **审计（必须）**：publish/offline 非 no-op 写审计
  - resourceType=`MINI_PROGRAM_CONFIG`
  - resourceId：`ENTRIES` / `PAGES:{id}` / `COLLECTIONS:{id}`
  - action：`PUBLISH` / `OFFLINE`
  - metadata 最小：`requestId/key/(pageId|collectionId)/afterPublished`

### 9H.1 Entries（首页入口）
- `GET /admin/mini-program/entries`
- `PUT /admin/mini-program/entries`：保存草稿（保留每项 `published` 状态，不推进全局 version）
- `POST /admin/mini-program/entries/publish`：将全部 items `published=true`
- `POST /admin/mini-program/entries/offline`：将全部 items `published=false`

### 9H.2 Pages（页面库）
- `GET /admin/mini-program/pages`
- `PUT /admin/mini-program/pages/{id}`：保存草稿（写 `draftVersion/draftUpdatedAt`）
- `POST /admin/mini-program/pages/{id}/publish`
- `POST /admin/mini-program/pages/{id}/offline`

### 9H.3 Collections（高级集合）
- `GET /admin/mini-program/collections`
- `PUT /admin/mini-program/collections/{id}`：保存草稿
- `POST /admin/mini-program/collections/{id}/publish`
- `POST /admin/mini-program/collections/{id}/offline`

## 9I. 城市配置发布/下线/导入（Admin Regions Cities - 高风险：全局基础数据）

> 目标：固化“草稿维护 + 全量发布/下线 + 一键导入”的最小生产口径（phone 绑定门禁 + 审计 + 幂等 no-op + 回滚说明）。

**存储承载**
- `SystemConfig.key = REGION_CITIES`
- `value_json.items = [{ code,name,sort,enabled,published }]`
- `value_json.version`：仅 publish/offline 真实变更时推进

**统一约定**
- `GET /admin/regions/cities`：`require_admin`
- `PUT /admin/regions/cities`（草稿保存）：`require_admin`（不推进 version；保留每条 code 的 published 回显）
- `POST /admin/regions/cities/publish|offline|import-cn`：`require_admin_phone_bound`
  - 未绑定手机号：403 `ADMIN_PHONE_REQUIRED`
- **幂等 no-op（发布类）**：
  - 重复 publish（已全 published）→ 200 no-op（version 不推进、不刷审计）
  - 重复 offline（已全 unpublished）→ 200 no-op
- **审计（必须）**：
  - publish：action=`PUBLISH`
  - offline：action=`OFFLINE`
  - import-cn：action=`UPDATE`（v1 最小用 UPDATE 表达导入）
  - resourceType=`REGION_CITIES`，resourceId=`REGION_CITIES`
  - metadata 最小：`requestId/op/replace/itemCount/version/afterPublished`

### 9I.1 GET /admin/regions/cities
- 响应：`{ items, version }`

### 9I.2 PUT /admin/regions/cities
- 请求：`{ items: AdminRegionItem[] }`
- 校验：code 形如 `PROVINCE:110000` / `CITY:110100`；code 唯一性（后端兜底）

### 9I.3 POST /admin/regions/cities/publish
- 行为：将所有 items `published=true`，并推进 version（仅当真实变更时）

### 9I.4 POST /admin/regions/cities/offline
- 行为：将所有 items `published=false`，并推进 version（仅当真实变更时）

### 9I.5 POST /admin/regions/cities/import-cn
- Query：`replace?: boolean`（默认 true）
- 行为：一键导入“全国省级 + 地级（不含区县）”到草稿；默认覆盖草稿
- 回滚（v1 最小）：导入前先手动导出/复制当前草稿 JSON（或用 git/DB 备份）；导入后若不符合预期可用 PUT 恢复草稿并重新 publish

## 9J. 通知发送（Admin Notifications Send - 敏感：触达/成本）

> 目标：把“手工发送站内通知”的生产口径固化（门禁 + 防重复 + 限流 + 审计）。

### 9J.1 POST /admin/notifications/send
- **用途**：管理员手工发送站内通知（可群发/定向），写入 `notifications` 表（fan-out）。

**鉴权规则**
- 角色：仅 ADMIN
- 高风险门禁：`require_admin_phone_bound`（未绑定 → 403 `ADMIN_PHONE_REQUIRED`）

**请求（JSON）**
- `title: string`（1..256）
- `content: string`（1..4000）
- `category?: "SYSTEM"|"ACTIVITY"|"OPS"`（默认 SYSTEM）
- `audience: { mode, targets? }`
  - `mode: "ALL_ADMINS"|"ALL_DEALERS"|"ALL_PROVIDERS"|"TARGETED"`
  - `targets?: Array<{ receiverType: "ADMIN"|"DEALER"|"PROVIDER"|"PROVIDER_STAFF"; receiverId: string }>`
    - 仅当 `mode=TARGETED` 必填

**防重复（幂等）**
- **强制** `Idempotency-Key`：重复提交同 key → 200 幂等复放（不重复 fan-out 写库）

**限流与容量保护**
- v1 最小（你已拍板）：
  - 每个 ADMIN：`POST /admin/notifications/send` ≤ 20 次 / 10 分钟（超出 → 429 `RATE_LIMITED`）
  - `targetsCount` 上限：5000（超出 → 400 `INVALID_ARGUMENT`）

**响应**
- 200 + Envelope(success=true)
  - `data: { success: true, createdCount: number }`

**错误码（最小集合）**
- 400 `INVALID_ARGUMENT`：targets 为空/receiverType 非法/receiverId 不存在或非 ACTIVE/targetsCount 超限等
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`
- 429 `RATE_LIMITED`

**审计（必须）**
- action=`CREATE`，resourceType=`NOTIFICATION_SEND`
- metadata 最小：`requestId/mode/category/createdCount`（禁止写入通知正文与收件人明文全量列表）

**实现证据入口（现状）**
- 后端：`backend/app/api/v1/admin_notifications.py::admin_send_notifications`

## 9K. 场所核销（Redeem Entitlement - 高风险：扣减次数）

> 目标：固化“扣减次数”的最小生产口径（幂等 + 归属校验 + 审计 + 错误码可预测）。

### 9K.1 POST /entitlements/{id}/redeem
**用途**：核销权益（扣减 remainingCount；必要时派生预约完成）。

**鉴权规则（现状实现）**
- 允许角色：`ADMIN` 或 `PROVIDER/PROVIDER_STAFF`
- `ADMIN`：可跨主体核销（但仍需 `VenueService` 存在且启用）
- `PROVIDER/PROVIDER_STAFF`：必须满足场所归属（`Venue.provider_id == providerId`），否则 403 `FORBIDDEN`

**请求**
- Header：
  - `Idempotency-Key: string`（**必填**）
- Path：
  - `id: string`（entitlementId）
- Body（JSON）：
  - `venueId: string`（必填）
  - `redemptionMethod: "QR_CODE"|"VOUCHER_CODE"|"BOTH"`（必填；其中 `BOTH` 为兼容场所服务配置）
  - `voucherCode: string`（必填）
    - 当 `redemptionMethod=QR_CODE`：该字段承载“完整二维码 payload 文本”（服务端验签）
    - 当 `redemptionMethod=VOUCHER_CODE`：该字段承载“券码本身”（服务端比对）

**响应（现状实现）**
- 200 + Envelope(success=true)
  - `data: { redemptionRecordId: string; entitlementId: string; status: "SUCCESS"; remainingCount: number; entitlementStatus: string }`

**幂等与防重复（现状实现）**
- 强制 `Idempotency-Key`
- 同一操作者（ADMIN/PROVIDER）+ 同一 `entitlementId` + 同一 `Idempotency-Key`：200 幂等复放（不重复扣减、不重复写核销记录）

**后端关键校验（现状实现）**
- entitlement 必须存在，否则 404 `ENTITLEMENT_NOT_FOUND`
- entitlement 状态必须为 `ACTIVE`，否则 409 `STATE_CONFLICT`
- 有效期：未生效/已过期 → 409 `REDEEM_NOT_ALLOWED`
- 次数：remainingCount<=0 → 409 `REDEEM_NOT_ALLOWED`
- 场所服务：`VenueService(venueId, serviceType)` 必须存在且 ENABLED；核销方式需匹配（服务端允许 `BOTH`）→ 409 `REDEEM_NOT_ALLOWED`
- 预约前置（booking_required=true）：必须存在 `CONFIRMED` 预约，否则 409 `BOOKING_REQUIRED`
- 二维码 payload 验签失败/不匹配：403（`QR_SIGN_INVALID` 或验签返回码）
- 券码不匹配：409 `REDEEM_NOT_ALLOWED`

**审计要求（待你拍板）**
- 你已确认 Provider Core 写操作必须审计；核销属于“扣减次数”高风险写操作
- **你已拍板：必须写 `AuditLog`（幂等复放不重复写）**
  - action：`UPDATE`
  - resourceType：`ENTITLEMENT_REDEEM`
  - resourceId：`{entitlementId}`
  - metadata 最小：`requestId/venueId/serviceType/redemptionMethod/operatorId/operatorType/beforeRemaining/afterRemaining/beforeStatus/afterStatus/redemptionRecordId`

**待你确认点（确认后再进入编码）**
1) **错误码收敛**：你已拍板 v1 **先保持现状错误码**，避免破坏兼容；后续再开“错误码收敛”专项卡统一迁移。

**实现证据入口（现状）**
- 后端：`backend/app/api/v1/entitlements.py::redeem_entitlement`
- 前端：`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`

## 9L. 仪表盘（Admin Dashboard - 高频入口）

### 9L.1 GET /admin/dashboard/summary
**用途**：Admin 仪表盘概览统计（KPI + 趋势 + 待办）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN（非 ADMIN 必须 403）

**请求**
- Query：
  - `range: "7d" | "30d"`（可选，默认 `7d`）

**响应（schema）**
- 200 + Envelope(success=true)
- `data`：
  - `range: "7d" | "30d"`
  - `today`：
    - `newMemberCount: number`：今日新增会员数（按 `ServicePackageInstance.owner_id` 去重；以 `created_at` 计）
    - `servicePackagePaidCount: number`：今日服务包支付成功数（`Order.order_type=SERVICE_PACKAGE` 且 `payment_status=PAID`；以 `paid_at` 计）
    - `ecommercePaidCount: number`：今日电商支付成功数（`Order.order_type=PRODUCT` 且 `payment_status=PAID`；以 `paid_at` 计）
    - `refundRequestCount: number`：今日售后/退款申请数（以 `AfterSaleCase.created_at` 计；v1 口径：不区分 type/status）
    - `redemptionSuccessCount: number`：今日核销成功数（`RedemptionRecord.status=SUCCESS`；以 `redemption_time` 计）
  - `trends`：
    - `servicePackageOrders: Array<{ date: "YYYY-MM-DD"; count: number }>`：范围内每日服务包支付成功数（以 `paid_at` 分组）
    - `ecommerceOrders: Array<{ date: "YYYY-MM-DD"; count: number }>`：范围内每日电商支付成功数（以 `paid_at` 分组）
    - `redemptions: Array<{ date: "YYYY-MM-DD"; count: number }>`：范围内每日核销成功数（以 `redemption_time` 分组）
  - `todos`：
    - `refundUnderReviewCount: number`：退款待审核数（`AfterSaleCase.status=UNDER_REVIEW` 全量）
    - `abnormalOrderCount: number`：异常订单数（v1 口径：`Order.payment_status=FAILED` 全量）
    - `enterpriseBindingPendingCount: number`：企业绑定待处理数（`UserEnterpriseBinding.status=PENDING` 全量）

**错误码（v1 最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`：`range` 非法（你拍板后再改实现，避免 422 漂移）

**幂等**
- 读接口，不要求 `Idempotency-Key`

**审计**
- v1 默认不审计（读）；如后续需要“关键查询也审计”，必须单独开规格项/任务卡（避免审计噪音）

**证据入口（现状实现）**
- 前端：`frontend/admin/src/pages/admin/AdminDashboardPage.vue::load`（调用 `/admin/dashboard/summary`）
- 后端：`backend/app/api/v1/admin_dashboard.py::admin_dashboard_summary`

**待你确认点（确认后再进入编码）**
1) **字段名与结构**：以本节为准（对齐前端 `DashboardSummary`），后端需要调整现状返回（当前实现存在 `todo/trends` 字段名不一致）。
2) **refundRequestCount 口径**：v1 先按“AfterSaleCase 今日创建总数（不区分 type/status）”是否同意？若不同意，请你指定：按 type=REFUND？还是按 status=SUBMITTED？
3) **range 非法的错误码**：是否必须从 FastAPI 默认 422 收敛为 400 `INVALID_ARGUMENT`（更符合平台统一错误码基线）？

## 9M. 企业与绑定审核（Admin Enterprise & Bindings - 高风险：企业身份）

> 目标：固化“企业身份/员工身份授予”的最小生产口径（权限门禁 + 状态机幂等 + 审计 + 错误码可预测）。

### 9M.1 GET /admin/enterprise-bindings
**用途**：企业绑定申请列表（审核台）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求**
- Query：
  - `status: "PENDING" | "APPROVED" | "REJECTED"`（可选）
  - `phone: string`（可选；模糊匹配用户手机号；仅用于筛选，不得明文出参）
  - `enterpriseName: string`（可选；模糊匹配企业名称）
  - `dateFrom/dateTo: YYYY-MM-DD`（可选；按 bindingTime 范围过滤；非法日期 → 400 `INVALID_ARGUMENT`）
  - `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应**
- 200 + Envelope(success=true)
- `data: { items, page, pageSize, total }`
- item 字段（前端唯一口径，禁止扩出用户手机号明文）：
  - `id: string`
  - `userId: string`
  - `userPhoneMasked?: string|null`
  - `enterpriseId: string`
  - `enterpriseName: string`
  - `status: "PENDING"|"APPROVED"|"REJECTED"`
  - `bindingTime: string`（ISO8601）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（dateFrom/dateTo 不合法等）

**审计**
- v1 默认不审计读。

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/auth.py::admin_list_enterprise_bindings`
- 前端：`frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue::load`

### 9M.2 PUT /admin/enterprise-bindings/{id}/approve
**用途**：审核通过绑定申请（PENDING -> APPROVED），并给用户授予 EMPLOYEE（写入 `users.enterprise_*` 与 identities）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **高风险门禁（你已拍板）**：`require_admin_phone_bound`（未绑定返回 403 `ADMIN_PHONE_REQUIRED`）

**请求**
- Path：`id: string`（bindingId）
- Body：无

**响应**
- 200 + Envelope(success=true)
- `data: { id: string; status: "APPROVED" }`（至少返回当前状态）

**错误码（最小集合）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`
- 404 `NOT_FOUND`：binding/user/enterprise 不存在
- 409 `INVALID_STATE_TRANSITION|STATE_CONFLICT`
  - **同一目标状态重复提交**：已 APPROVED 再 approve → 200 幂等 no-op（不重复写审计、不重复授予）
  - **非法状态流转**：已 REJECTED 还 approve → 409 `INVALID_STATE_TRANSITION`
  - **业务冲突**：同一用户已存在 APPROVED 生效绑定 → 409 `STATE_CONFLICT`

**幂等**
- 不强制 `Idempotency-Key`（按状态机幂等即可）

**审计（必须，敏感写操作）**
- action=`UPDATE`
- resourceType=`ENTERPRISE_BINDING_REVIEW`
- resourceId=`{bindingId}`
- metadata 最小：`requestId/bindingId/userId/enterpriseId/beforeStatus/afterStatus`

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/auth.py::admin_approve_enterprise_binding`
- 前端：`frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue::approve`

### 9M.3 PUT /admin/enterprise-bindings/{id}/reject
**用途**：审核驳回绑定申请（PENDING -> REJECTED）。

**鉴权规则**：同 9M.2

**请求**：Path `id`

**响应**
- 200：`data: { id: string; status: "REJECTED" }`

**错误码/幂等/审计**
- 与 9M.2 同口径：
  - 已 REJECTED 再 reject → 200 no-op
  - 已 APPROVED 再 reject → 409 `INVALID_STATE_TRANSITION`
  - 审计 action=`UPDATE`，resourceType=`ENTERPRISE_BINDING_REVIEW`，metadata 含 before/after

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/auth.py::admin_reject_enterprise_binding`
- 前端：`frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue::reject`

### 9M.4 GET /admin/enterprises
**用途**：企业信息库列表（用于检索/查看）。

**鉴权规则**
- ADMIN

**请求**
- Query：
  - `keyword?: string`（模糊匹配 name）
  - `cityCode?: string`（精确）
  - `source?: "USER_FIRST_BINDING"|"IMPORT"|"MANUAL"`
  - `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应**
- 200：`data: { items, page, pageSize, total }`
- item 最小字段（前端用到）：
  - `id,name,cityCode,source,createdAt`

**错误码**
- 401/403
- 400 `INVALID_ARGUMENT`：source 不合法

**审计**：v1 默认不审计读

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_enterprises.py::admin_list_enterprises`
- 前端：`frontend/admin/src/pages/admin/AdminEnterprisesPage.vue::load`

### 9M.5 GET /admin/enterprises/{id}
**用途**：企业详情（查看）。

**鉴权规则**：ADMIN

**响应**：200 返回企业详情（最小字段同 9M.4；可多字段但不得包含敏感信息）

**错误码**：404 `NOT_FOUND`

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_enterprises.py::admin_get_enterprise`
- 前端：`frontend/admin/src/pages/admin/AdminEnterprisesPage.vue::openDetail`

### 9M.6 PUT /admin/enterprises/{id}
**用途**：更新企业名称（v1 从严：仅允许更新 `name`）。

**鉴权规则**
- ADMIN
- **高风险门禁（你已拍板）**：`require_admin_phone_bound`（未绑定返回 403 `ADMIN_PHONE_REQUIRED`）

**请求**
- Body：`{ name: string }`（minLength=1，maxLength=256；extra 字段禁止）

**响应**：200 返回更新后的企业 DTO（至少含 id/name/source/cityCode/createdAt）

**错误码**
- 401/403
- 403 `ADMIN_PHONE_REQUIRED`（若启用 phone bound 门禁）
- 404 `NOT_FOUND`
- 400 `INVALID_ARGUMENT`：body 校验失败

**审计（必须，敏感写操作）**
- action=`UPDATE`
- resourceType=`ENTERPRISE`
- resourceId=`{enterpriseId}`
- metadata 最小：`requestId/enterpriseId/beforeName/afterName`

**待你确认点（确认后再进入编码）**
1) **phone bound 门禁**：你已拍板 `approve/reject/enterprise name update` 一律启用 `require_admin_phone_bound`。
2) **状态机幂等口径**：你已拍板按统一口径执行（同目标状态重复提交=200 no-op；非法迁移=409 `INVALID_STATE_TRANSITION`）。
3) **审计 resourceType 命名**：你已拍板使用两类：`ENTERPRISE_BINDING_REVIEW`、`ENTERPRISE`。

## 9N. 售后审核（Admin After-Sales - 高风险：退款/争议）

> 目标：固化“退款/争议裁决”的最小生产口径（phone bound 门禁 + 状态机幂等 + 审计 + 错误码可预测）。

### 9N.1 GET /admin/after-sales
**用途**：售后单列表（筛选 + 分页）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求**
- Query：
  - `type: "RETURN"|"REFUND"|"AFTER_SALE_SERVICE"`（可选）
  - `status: "SUBMITTED"|"UNDER_REVIEW"|"DECIDED"|"CLOSED"`（可选）
  - `dateFrom/dateTo: YYYY-MM-DD`（可选；按 createdAt 范围过滤；非法 → 400 `INVALID_ARGUMENT`）
  - `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应**
- 200 + Envelope(success=true)
- `data: { items, page, pageSize, total }`
- item 最小字段（前端用到的口径）：
  - `id, orderId, userId, type, status, amount, reason?, decision?, decisionNotes?, createdAt, updatedAt`
  - 可额外返回：`evidenceUrls/decidedBy`（前端可忽略）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（日期不合法）

**审计**
- v1 默认不审计读。

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/after_sales.py::admin_list_after_sales`
- 前端：`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue::load`

### 9N.2 PUT /admin/after-sales/{id}/decide
**用途**：售后裁决（同意/驳回）。v1 现状实现：裁决后直接闭环（最终状态为 `CLOSED`，但保留 decision 字段）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **高风险门禁（你已拍板）**：`require_admin_phone_bound`（未绑定返回 403 `ADMIN_PHONE_REQUIRED`）

**请求**
- Path：`id: string`（afterSaleId）
- Body：
  - `decision: "APPROVE"|"REJECT"`
  - `decisionNotes?: string|null`（maxLength=1024）

**响应**
- 200 + Envelope(success=true)
- `data: AfterSaleCase`（建议直接返回最新状态/decision/updatedAt，便于前端刷新）

**状态机幂等口径（你已拍板）**
- 仅允许 `UNDER_REVIEW` 发起裁决：
  - `UNDER_REVIEW + APPROVE/REJECT` → 200（裁决成功）
- **同目标状态重复提交（幂等 no-op）**
  - 若售后单已 `CLOSED` 且 `decision == body.decision`：返回 200 no-op（不重复退款/不重复写审计）
- **非法迁移/冲突**
  - 若售后单已 `CLOSED` 但 `decision != body.decision`：409 `INVALID_STATE_TRANSITION`
  - 若售后单不在 `UNDER_REVIEW` 且未满足上述 no-op 条件：409 `INVALID_STATE_TRANSITION`

**错误码（最小集合）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`
- 404 `NOT_FOUND`
- 400 `INVALID_ARGUMENT`（decision 不合法/notes 超长）
- 409 `INVALID_STATE_TRANSITION|STATE_CONFLICT`
  - v1 现状：退款通道不满足条件时可能返回 `REFUND_NOT_ALLOWED`（409）

**幂等**
- 不强制 `Idempotency-Key`（按状态机幂等即可）

**审计（必须，敏感写操作）**
- action：**统一 `UPDATE`（你已拍板）**；metadata 记录 `decision=APPROVE|REJECT` 与 before/after
- resourceType：`AFTER_SALES`
- resourceId：`{afterSaleId}`
- metadata 最小：`requestId/afterSaleId/orderId/userId/beforeStatus/afterStatus/decision/beforeDecision/afterDecision`

**确认结果（已拍板，可进入编码/测试）**
1) decide 一律启用 `require_admin_phone_bound`
2) 幂等口径：同 decision 重复提交=200 no-op；冲突 decision/非法迁移=409 `INVALID_STATE_TRANSITION`
3) 审计 action：统一 `UPDATE`，在 metadata 里记录 decision + before/after
4) 退款失败错误码：v1 保持 `REFUND_NOT_ALLOWED`（409）不收敛

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/after_sales.py::admin_decide_after_sale`
- 前端：`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue::decide`

## 9O. 权益/核销/转赠（Admin Entitlements - 高风险：权益状态/凭证敏感信息）

> 目标：固化平台监管只读视图的最小口径：**权限边界清晰**、**三类列表可用**、**Admin 侧禁止输出 qrCode/voucherCode 明文**。

### 9O.1 GET /entitlements（Admin/USER 共享端点，Admin 监管只读）
**用途**：
- USER：查看本人权益（可能包含凭证信息，用于自身核销/展示）
- ADMIN：平台监管查询权益列表（**严禁**返回凭证明文）

**鉴权规则**
- 需要 Authorization（Bearer token）
- 允许角色：`ADMIN` 或 `USER`
- **Admin 安全出参**：当 actorType=ADMIN 时必须使用“admin safe DTO”（不得包含 `qrCode/voucherCode`）

**请求**
- Query：
  - `type?: string`（现状：`SERVICE_PACKAGE`；扩展型字段，按 DB 值过滤）
  - `status?: string`（现状：按 DB 值过滤；建议允许 `ACTIVE|USED|EXPIRED|TRANSFERRED|REFUNDED` 等）
  - `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应**
- 200 + Envelope(success=true)
- `data: { items, page, pageSize, total }`
- item（最小字段，按前端现状 + 后端 DTO）：
  - `id, userId, orderId, entitlementType, serviceType, remainingCount, totalCount, validFrom, validUntil, status, ownerId, createdAt`
  - **禁止（Admin 场景）**：`qrCode`、`voucherCode`（你已拍板：Admin 侧彻底禁止凭证明文出参）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`（建议：非 ADMIN/USER 的 token 不允许访问；待你拍板是否需要从现状 401 调整为 403）
- 400 `INVALID_ARGUMENT`（分页/枚举非法等，如引入）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/entitlements.py::list_entitlements`（Admin 使用 `_entitlement_dto_admin_safe` 删除 `qrCode/voucherCode`）
- 前端：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue::loadEntitlements`

### 9O.2 GET /admin/redemptions
**用途**：核销记录查询（Admin 监管只读）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求**
- Query（后端已支持，前端当前仅使用 page/pageSize；其余保留为“可用但不强制暴露”）：
  - `dateFrom/dateTo?: YYYY-MM-DD`（按 redemptionTime 范围；非法 → 400 `INVALID_ARGUMENT`）
  - `serviceType?: string`
  - `status?: string`（`SUCCESS|FAILED`）
  - `operatorId?: string`
  - `userId?: string`
  - `page/pageSize`

**响应**
- 200：`data: { items, page, pageSize, total }`
- item（最小字段，按前端现状）：
  - `id, redemptionTime, userId, venueId, serviceType, operatorId, status, failureReason?, entitlementId, bookingId?`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（日期格式等）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_redemptions.py::admin_list_redemptions`
- 前端：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue::loadRedemptions`

### 9O.3 GET /admin/entitlement-transfers
**用途**：权益转赠记录查询（Admin 监管只读）。

**鉴权规则**：ADMIN

**请求**
- Query（后端已支持，前端当前仅使用 page/pageSize）：
  - `fromOwnerId?: string`
  - `toOwnerId?: string`
  - `entitlementId?: string`
  - `dateFrom/dateTo?: YYYY-MM-DD`（按 transferredAt；非法 → 400 `INVALID_ARGUMENT`）
  - `page/pageSize`

**响应**
- 200：`data: { items, page, pageSize, total }`
- item（最小字段，按现状实现）：
  - `id, transferredAt, fromOwnerId, toOwnerId, entitlementId`
  - 前端 `status` 字段现为可选（后端 v1 未返回；如需补充须另开规格）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_entitlement_transfers.py::admin_list_entitlement_transfers`
- 前端：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue::loadTransfers`

**待你确认点（确认后再进入编码）**
**确认结果（已拍板，可进入编码/测试）**
1) `/entitlements` 对“非 ADMIN/USER token（如 DEALER/PROVIDER）”统一返回 403 `FORBIDDEN`；只有“未携带/无效 token”才是 401 `UNAUTHENTICATED`。
2) 监管口径显式支持 `REFUNDED`（前端可暂不加筛选项，但契约与枚举承认可能出现）。
3) Admin 侧 **全面禁止** `qrCode/voucherCode` 明文出参（list/detail/export），并 **必须** 有自动化测试护栏。

## 9P. AI 配置与审计（Admin AI - 高风险：配置影响/密钥敏感）

> 目标：固化 Admin AI 配置中心的最小口径：**密钥不泄露**、**变更可追溯（审计）**、**写操作可幂等**、**错误码收敛为 400/401/403/409**。
>
> 存储承载：`SystemConfig.key="AI_CONFIG"`；`apiKey` 永远不在响应中明文返回，仅返回 `apiKeyMasked`。

### 9P.1 GET /admin/ai/config
**用途**：读取当前 AI 配置（用于后台配置页面展示）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**响应（200）**
- `data`（最小字段，按前端现状）：
  - `enabled: boolean`
  - `provider: "OPENAI_COMPAT"`（v1 固定）
  - `baseUrl: string`
  - `model: string`
  - `systemPrompt?: string|null`
  - `temperature?: number|null`
  - `maxTokens?: number|null`
  - `timeoutMs?: number|null`
  - `retries?: number|null`
  - `rateLimitPerMinute?: number|null`
  - `version: string`（配置版本号；仅当“实际变更”时变化；用于审计与排障）
  - `apiKeyMasked?: string|null`（脱敏；不得返回 `apiKey` 明文）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_ai.py::admin_get_ai_config`
- 前端：`frontend/admin/src/pages/admin/AdminAiConfigPage.vue::load`

### 9P.2 PUT /admin/ai/config
**用途**：更新 AI 配置（敏感写操作）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定返回 403 `ADMIN_PHONE_REQUIRED`）？

**幂等（待确认口径，推荐）**
- **方案 A（推荐）**：强制 `Idempotency-Key`；同 key 重放返回缓存；审计只记录一次
- **方案 B（不强制）**：不强制幂等键；以“配置对比”实现幂等 no-op：当请求不会造成实际变更时 200 返回当前配置且 **不 bump version、不写审计**

**请求 Body（部分字段可选，按现状）**
- `enabled?: boolean`
- `provider?: "OPENAI_COMPAT"`（v1 固定；传其他值 → 400 `INVALID_ARGUMENT`）
- `baseUrl?: string`
- `apiKey?: string`（可选更新；空字符串视为“不更新”）
- `model?: string`
- `systemPrompt?: string|null`
- `temperature?: number`（0~2）
- `maxTokens?: number`（1~200000）
- `timeoutMs?: number`（100~120000）
- `retries?: number`（0~10）
- `rateLimitPerMinute?: number`（1~100000）

**响应（200）**
- 返回与 9P.1 相同的结构（`apiKeyMasked` + `version` 等）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 400 `INVALID_ARGUMENT`（provider 不支持、字段范围非法等）
- **待确认**：字段范围非法目前 FastAPI/Pydantic 可能返回 422；是否要求收敛为 400 `INVALID_ARGUMENT`（与本规范一致）？

**审计（必须，敏感写操作）**
- action：`UPDATE`
- resourceType：`AI_CONFIG`
- resourceId：`AI_CONFIG`（常量即可）
- metadata 最小：
  - `requestId`
  - `before: { enabled, baseUrl, model, systemPrompt?, temperature?, maxTokens?, timeoutMs?, retries?, rateLimitPerMinute?, version }`
  - `after:  { ...同上... }`
  - `changedFields: string[]`
  - **禁止**：`apiKey` 明文入库（若必须记录：仅记录 `apiKeyMasked` 或 `apiKeyUpdated: true`）
- 幂等复放：不得重复写审计

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_ai.py::admin_put_ai_config`（现状会无条件 bump version；待按确认口径收敛）
- 前端：`frontend/admin/src/pages/admin/AdminAiConfigPage.vue::save`

### 9P.3 GET /admin/ai/audit-logs
**用途**：查询 AI 调用审计（不存储对话内容，只存元数据）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求 Query（按现状）**
- `userId?: string`
- `resultStatus?: "success"|"fail"`
- `provider?: string`
- `model?: string`
- `dateFrom?: ISO8601|YYYY-MM-DD`（非法 → 400 `INVALID_ARGUMENT`）
- `dateTo?: ISO8601|YYYY-MM-DD`（非法 → 400 `INVALID_ARGUMENT`）
- `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应（200）**
- `data: { items, page, pageSize, total }`
- item（最小字段，按现状实现）：
  - `userId: string`
  - `timestamp: string`（ISO8601，本地时区）
  - `provider: string`
  - `model: string`
  - `latencyMs: number`
  - `resultStatus: string`
  - `errorCode?: string|null`
  - `configVersion?: string|null`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（dateFrom/dateTo 非法）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_ai.py::admin_list_ai_audit_logs`（基于 `AuditLog.resource_type=="AI_CHAT"`）

**待你确认点（确认后再进入编码）**
**确认结果（已拍板，可进入编码/测试）**
1) `PUT /admin/ai/config` 启用 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）。
2) 幂等策略：**方案 A**（强制 `Idempotency-Key`；重放返回缓存；审计只记录一次）。
3) 字段校验失败：从现状 422 收敛为 **400 `INVALID_ARGUMENT`**。

## 9Q. 服务包模板管理（Admin Service Packages - 高频：配置类/影响售卖口径）

> 目标：固化“服务包模板（高端服务卡模板）”的最小可生产口径：**仅 ADMIN 可管**、**创建强幂等**、**变更可追溯（审计）**、**已产生实例后严格锁定关键字段**、**错误码收敛为 400/401/403/404/409**。
>
> 数据模型：`ServicePackage`（模板）+ `PackageService`（服务类目×次数）+ `ServicePackageInstance`（实例，用于锁定判断）。

### 9Q.1 GET /admin/service-packages
**用途**：分页查询服务包模板（后台列表页）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求 Query（按现状）**
- `page/pageSize`（默认 1/20；pageSize 最大 100）
- `keyword?: string`（按 name 模糊搜索）

**响应（200）**
- `data: { items, page, pageSize, total }`
- item（最小字段，按前端现状 + 后端实现）：
  - `id: string`
  - `name: string`
  - `regionLevel: string`
  - `tier: string`
  - `description?: string|null`
  - `serviceCount: number`（明细条数）
  - `createdAt?: string|null`
  - `updatedAt?: string|null`

**排序**
- 默认：`updatedAt DESC`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（page/pageSize 非法等，如引入）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_packages.py::admin_list_service_packages`
- 前端：`frontend/admin/src/pages/admin/AdminServicePackagesPage.vue::load`

### 9Q.2 GET /admin/service-packages/{id}
**用途**：读取模板详情（用于编辑弹窗回填）。

**鉴权规则**：ADMIN

**响应（200）**
- `data`（最小字段）：
  - `id, name, regionLevel, tier, description?, services`
  - `services: Array<{ serviceType: string, totalCount: number }>`
  - `locked: boolean`：当该模板已产生任意 `ServicePackageInstance` 时为 true

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 404 `NOT_FOUND`（模板不存在）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_packages.py::admin_get_service_package_detail`
- 前端：`frontend/admin/src/pages/admin/AdminServicePackagesPage.vue::openEdit`

### 9Q.3 POST /admin/service-packages
**用途**：创建服务包模板（敏感写：影响售卖口径/下单入口）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定返回 403 `ADMIN_PHONE_REQUIRED`）？

**幂等（你拍板后执行）**
- **强制** `Idempotency-Key`
- 同一 ADMIN 在 24h 内对同一 `Idempotency-Key` 重复提交：
  - 返回首次结果（200，`data.id` 相同）
  - 不重复创建模板、不重复写审计

**请求 Body（最小字段，按现状）**
- `name: string`（非空）
- `regionLevel: string`（非空；后端会 `upper()`）
- `tier: string`（非空）
- `description?: string|null`
- `services: Array<{ serviceType: string, totalCount: number }>`：
  - 至少 1 条
  - `serviceType` 不得重复
  - `totalCount >= 1`
  - **业务校验**：`serviceType` 必须来自“服务大类字典（ServiceCategory.code）且 status=ENABLED”

**响应（200）**
- `data: { id: string }`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 400 `INVALID_ARGUMENT`（services 为空/重复/totalCount 非法/serviceType 未启用等）
- **待确认**：字段校验失败是否从现状 422 收敛为 400 `INVALID_ARGUMENT`（与本文件通用约定一致）？

**审计（必须，敏感写操作）**
- action：`CREATE`
- resourceType：`SERVICE_PACKAGE_TEMPLATE`
- resourceId：`{templateId}`
- metadata 最小：
  - `requestId, templateId, name, regionLevel, tier, serviceTypes, serviceCounts`
- 幂等复放：不得重复写审计

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_packages.py::admin_create_service_package`（现状：未做幂等/审计）
- 前端：`frontend/admin/src/pages/admin/AdminServicePackagesPage.vue::save`（CREATE 分支）

### 9Q.4 PUT /admin/service-packages/{id}
**用途**：编辑服务包模板（敏感写：影响售卖口径；且存在“已产生实例锁定”规则）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定返回 403 `ADMIN_PHONE_REQUIRED`）？

**幂等（状态机写统一口径）**
- 当请求不会造成实际变更时：200 no-op（不写审计）
- 当模板 `locked=true`：
  - 仅允许修改 `name/description`
  - 修改 `regionLevel/tier` 或修改 `services` → 409 `STATE_CONFLICT`

**请求 Body**：同 9Q.3

**响应（200）**
- `data: { id: string, locked: boolean }`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 404 `NOT_FOUND`（模板不存在）
- 400 `INVALID_ARGUMENT`（入参非法/serviceType 未启用等）
- 409 `STATE_CONFLICT`（locked 时修改被禁止字段；或其他并发冲突）
- **待确认**：字段校验失败是否从现状 422 收敛为 400 `INVALID_ARGUMENT`？

**审计（必须，敏感写操作）**
- action：`UPDATE`
- resourceType：`SERVICE_PACKAGE_TEMPLATE`
- resourceId：`{templateId}`
- metadata 最小：
  - `requestId, templateId, locked`
  - `before: { name, description, regionLevel, tier, services }`
  - `after:  { ... }`
  - `changedFields: string[]`
- no-op：不得写审计

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_packages.py::admin_update_service_package`（现状：locked 规则已有；未做审计/no-op）
- 前端：`frontend/admin/src/pages/admin/AdminServicePackagesPage.vue::save`（EDIT 分支）

**待你确认点（确认后再进入编码）**
**确认结果（已拍板，可进入编码/测试）**
1) POST/PUT 一律启用 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）。
2) POST 强制 `Idempotency-Key`（24h 内同 key 重放返回首次结果；不重复写审计）。
3) 字段校验失败：从现状 422 收敛为 **400 `INVALID_ARGUMENT`**（避免漂移）。
4) 审计 `resourceType`：接受 `SERVICE_PACKAGE_TEMPLATE`。

## 9R. 服务分类启停用（Admin Service Categories - 高频：配置类/影响模板与供给侧）

> 目标：固化“服务大类字典（serviceType）”的最小可生产口径：**仅 ADMIN 可管**、**启停用必须 phone bound + 审计**、**状态机幂等 no-op**、**错误码收敛为 400/401/403/404/409**。
>
> 数据模型：`ServiceCategory`（`code` 全局唯一；`status=ENABLED|DISABLED`）。

### 9R.1 GET /admin/service-categories
**用途**：分页查询服务大类字典（后台列表页）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求 Query（按现状）**
- `keyword?: string`（按 `code`/`displayName` 模糊搜索）
- `status?: "ENABLED"|"DISABLED"`
- `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应（200）**
- `data: { items, page, pageSize, total }`
- item（最小字段，按前端现状 + 后端实现）：
  - `id, code, displayName, status, sort, createdAt, updatedAt`

**排序**
- 默认：`sort DESC, updatedAt DESC`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（status 非法等）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_categories.py::admin_list_service_categories`
- 前端：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue::load`

### 9R.2 POST /admin/service-categories
**用途**：新增服务大类（配置写操作）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）？

**请求 Body（按现状）**
- `code: string`（2~64；仅大写字母/数字/下划线；全局唯一）
- `displayName: string`（非空）
- `sort?: number`（默认 0）

**响应（200）**
- 返回创建后的 item（同 9R.1 item）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 400 `INVALID_ARGUMENT`（code 格式非法/displayName 为空等）
- 409 `STATE_CONFLICT|CONFLICT`（code 已存在；**待收敛**：现状 code=CONFLICT）

**审计（必须，敏感写操作）**
- action：`CREATE`
- resourceType：`SERVICE_CATEGORY`
- resourceId：`{categoryId}`
- metadata 最小：`requestId, id, code, displayName, sort`

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_categories.py::admin_create_service_category`（现状：未审计；未 phone bound）
- 前端：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue::save`（CREATE 分支）

### 9R.3 PUT /admin/service-categories/{id}
**用途**：编辑服务大类（v1 禁止改 code，仅允许改 displayName/sort）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）？

**幂等**
- 当请求不会造成实际变更：200 no-op（不写审计）

**请求 Body（按现状）**
- `displayName?: string`
- `sort?: number`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 404 `NOT_FOUND`
- 400 `INVALID_ARGUMENT`

**审计（必须，敏感写操作）**
- action：`UPDATE`
- resourceType：`SERVICE_CATEGORY`
- resourceId：`{categoryId}`
- metadata 最小：`requestId, id, before, after, changedFields`
- no-op：不写审计

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_service_categories.py::admin_update_service_category`（现状：未审计；未 no-op）
- 前端：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue::save`（EDIT 分支）

### 9R.4 POST /admin/service-categories/{id}/enable
### 9R.5 POST /admin/service-categories/{id}/disable
**用途**：启用/停用服务大类（敏感：影响新建模板/供给侧选择）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **必须启用** `require_admin_phone_bound`（你拍板后执行）

**幂等（状态机写统一口径）**
- 已在目标状态：200 no-op（不写审计）
- 非法迁移：v1 仅有 ENABLED/DISABLED 两态，无非法迁移；如未来扩展则按 409 `INVALID_STATE_TRANSITION`

**响应（200）**
- 返回更新后的 item（同 9R.1 item）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`
- 404 `NOT_FOUND`

**审计（必须，敏感写操作）**
- action：`UPDATE`（或 `ENABLE`/`DISABLE`；**待你拍板**）
- resourceType：`SERVICE_CATEGORY`
- resourceId：`{categoryId}`
- metadata 最小：`requestId, id, code, beforeStatus, afterStatus`
- no-op：不写审计

**证据入口（现状实现）**
- 后端：
  - `backend/app/api/v1/admin_service_categories.py::admin_enable_service_category`
  - `backend/app/api/v1/admin_service_categories.py::admin_disable_service_category`
- 前端：
  - `frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue::{enable,disable}`

**待你确认点（确认后再进入编码）**
**确认结果（已拍板，可进入编码/测试）**
1) POST/PUT/enable/disable 一律启用 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）。
2) 422→400：请求体校验失败统一收敛为 **400 `INVALID_ARGUMENT`**（避免漂移）。
3) 审计 action：enable/disable **统一 `UPDATE`**。
4) 409 冲突码：`code 已存在` 从现状 `CONFLICT` 收敛为 **`STATE_CONFLICT`**。

## 9S. 可售卡启停用（Admin Sellable Cards - 高风险：影响下单入口/经销商投放）

> 目标：固化“可售卡（SellableCard）”的最小可生产口径：**仅 ADMIN 可管**、**启停用必须 phone bound + 审计**、**状态机幂等 no-op**、**错误码收敛为 400/401/403/404/409**。
>
> 数据模型：`SellableCard`（绑定 `servicePackageTemplateId`，自身携带 `priceOriginal`，`status=ENABLED|DISABLED`）。

### 9S.1 GET /admin/sellable-cards
**用途**：分页查询可售卡（后台列表页）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN

**请求 Query（按现状）**
- `status?: "ENABLED"|"DISABLED"`
- `keyword?: string`（按 id/name/servicePackageTemplateId/regionLevel 模糊搜索）
- `page/pageSize`（默认 1/20；pageSize 最大 100）

**响应（200）**
- `data: { items, page, pageSize, total }`
- item（最小字段，按前端现状 + 后端实现）：
  - `id, name, servicePackageTemplateId, regionLevel, priceOriginal, status, sort, createdAt, updatedAt`

**排序**
- 默认：`sort DESC, updatedAt DESC`

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN`
- 400 `INVALID_ARGUMENT`（status 非法等）

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_sellable_cards.py::admin_list_sellable_cards`
- 前端：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue::load`

### 9S.2 POST /admin/sellable-cards
**用途**：新增可售卡（敏感写：影响经销商选卡与下单入口）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）？

**请求 Body（按现状）**
- `name: string`（1~128）
- `servicePackageTemplateId: string`（必须存在）
- `regionLevel: "CITY"|"PROVINCE"|"COUNTRY"`（且必须与模板 `regionLevel` 一致）
- `priceOriginal: number`（>=0）
- `sort?: number`（默认 0）

**响应（200）**
- 返回创建后的 item（同 9S.1 item）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 400 `INVALID_ARGUMENT`（regionLevel 非法、模板不存在、regionLevel 与模板不一致、字段范围非法等）
- **待确认**：字段校验失败是否从现状 422 收敛为 400 `INVALID_ARGUMENT`？

**审计（必须，敏感写操作）**
- action：`CREATE`
- resourceType：`SELLABLE_CARD`
- resourceId：`{sellableCardId}`
- metadata 最小：`requestId, id, name, servicePackageTemplateId, regionLevel, priceOriginal, sort`

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_sellable_cards.py::admin_create_sellable_card`（现状：未审计；未 phone bound）
- 前端：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue::save`（CREATE 分支）

### 9S.3 PUT /admin/sellable-cards/{id}
**用途**：编辑可售卡（敏感写）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **待确认**：是否要求 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）？

**幂等**
- 当请求不会造成实际变更：200 no-op（不写审计）

**请求 Body**：同 9S.2

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`（若启用 phone bound）
- 404 `NOT_FOUND`
- 400 `INVALID_ARGUMENT`
- **待确认**：字段校验失败是否从现状 422 收敛为 400 `INVALID_ARGUMENT`？

**审计（必须，敏感写操作）**
- action：`UPDATE`
- resourceType：`SELLABLE_CARD`
- resourceId：`{sellableCardId}`
- metadata 最小：`requestId, id, before, after, changedFields`
- no-op：不写审计

**证据入口（现状实现）**
- 后端：`backend/app/api/v1/admin_sellable_cards.py::admin_update_sellable_card`（现状：未审计；未 no-op）
- 前端：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue::save`（EDIT 分支）

### 9S.4 POST /admin/sellable-cards/{id}/enable
### 9S.5 POST /admin/sellable-cards/{id}/disable
**用途**：启用/停用可售卡（高风险：影响经销商投放与下单入口）。

**鉴权规则**
- 需要 Authorization（admin token）
- 允许角色：ADMIN
- **必须启用** `require_admin_phone_bound`（你拍板后执行）

**幂等（状态机写统一口径）**
- 已在目标状态：200 no-op（不写审计）

**响应（200）**
- 返回更新后的 item（同 9S.1 item）

**错误码（最小）**
- 401 `UNAUTHENTICATED`
- 403 `FORBIDDEN` / `ADMIN_PHONE_REQUIRED`
- 404 `NOT_FOUND`

**审计（必须，敏感写操作）**
- action：`UPDATE`（你已在 service-categories 拍板此口径；可售卡建议同口径）
- resourceType：`SELLABLE_CARD`
- resourceId：`{sellableCardId}`
- metadata 最小：`requestId, id, beforeStatus, afterStatus`
- no-op：不写审计

**证据入口（现状实现）**
- 后端：
  - `backend/app/api/v1/admin_sellable_cards.py::admin_enable_sellable_card`
  - `backend/app/api/v1/admin_sellable_cards.py::admin_disable_sellable_card`
- 前端：
  - `frontend/admin/src/pages/admin/AdminSellableCardsPage.vue::{enable,disable}`

**待你确认点（确认后再进入编码）**
**确认结果（已拍板，可进入编码/测试）**
1) POST/PUT/enable/disable 一律启用 `require_admin_phone_bound`（未绑定→403 `ADMIN_PHONE_REQUIRED`）。
2) 422→400：请求体校验失败统一收敛为 **400 `INVALID_ARGUMENT`**（避免漂移）。
3) 审计 action：enable/disable **统一 `UPDATE`**。
4) 审计 `resourceType`：接受 `SELLABLE_CARD`。

## 10. 待你确认点（写完规格后，进入编码前必须拍板）

1) **Top 5 选择是否认可**：是否将 `login/refresh/audit-logs/settlements generate/mark-settled` 作为本轮“高风险+高频”基线？需要替换哪个接口（例如改为 `PUT /admin/dealer-commission` 或 `POST /admin/auth/logout`）？
2) **refresh 的审计策略**：是否要求每次 refresh 产生审计事件？（现状：未见写审计）
3) **结算生成 generate 的审计策略**：是否要求写审计？若写，action 用 `CREATE` 还是 `UPDATE`？resourceType/metadata 最小字段是否按本节建议？
4) **mark-settled 的幂等语义（关键）**：
   - 是否引入 `Idempotency-Key` 并禁止覆盖 payout 字段（方案 A）
   - 或“已 SETTLED 禁止再次标记”（方案 B，返回 409 或 200 返回现有）
5) **mark-settled 的审计字段允许范围**：`payoutReference/payoutNote` 是否属于敏感信息？审计 metadata 里是否允许记录明文/需脱敏？
6) **审计查询是否也需要审计**：监管要求下是否要记录“谁查询了哪些审计日志”（默认不记录，避免爆量）？

7) **订单发货/妥投的幂等口径（新增，Batch2 前必须拍板）**
   - `POST /admin/orders/{id}/ship`：当订单已是 `SHIPPED` 时，是否允许再次提交覆盖 `carrier/trackingNo`？
     - 方案 A（更安全，推荐）：仅当 body 与已存在一致时 200 no-op；不一致返回 409 `INVALID_STATE_TRANSITION`
     - 方案 B（更灵活）：允许覆盖，但必须携带 `Idempotency-Key` 且写审计记录 before/after（风险更高）
   - `POST /admin/orders/{id}/deliver`：当订单已是 `DELIVERED` 时是否 200 no-op（默认是）；当已 `RECEIVED` 再 deliver 是否一律 409（默认是）

8) **投放链接（Dealer Links）的幂等与风控口径（新增，Batch3 前必须拍板）**
   - `POST /dealer-links` 是否 **强制** `Idempotency-Key`（推荐强制：防重复生成）
   - 若不强制：重复点击生成多条链接是否允许？（不建议；会造成风控与排障困难）

9) **导出（Export）v1 形态（新增，Batch4 前必须拍板）**
   - 是否接受 **后端同步导出直接下载（不落盘，TTL=0）** 作为 v1（推荐）
   - 每个导出点的 `maxRows`（建议默认 5000）与“必须收敛过滤条件”（例如 dateFrom/dateTo 是否必填）
   - 审计 action 是否需要新增 `EXPORT` 枚举？（若不新增：v1 可先用 `UPDATE` + resourceType=`EXPORT_*`）


