# 事实索引（Facts Index）

> 规则：每条事实必须包含**证据入口**（文件路径 + 关键函数/调用点 + 接口路径）。需要更强证据时可补充行号范围与运行截图/日志。

## 1. 前端（frontend/admin）事实

### F-FE-001 Admin 应用入口使用 Vue + ElementPlus，并挂载 Router
- **证据入口**
  - 文件：`frontend/admin/src/main.ts`
  - 关键调用点：`createApp(App).use(router).use(ElementPlus).mount('#app')`
  - Router 来源：`frontend/admin/src/router/index.ts`（`export const router = createRouter(...)`）

### F-FE-002 路由树与守卫：public/role/403/login next（三域共享同一前端）
- **事实**
  - **路由树骨架**（节选）
    - `/` → redirect `/admin`
    - `public`：`/login`、`/admin-2fa`
    - 业务布局：`/` + `AppLayout`，其下 children 根据 `meta.role` 分域：`ADMIN` / `DEALER` / `PROVIDER`
    - `/403`：Forbidden 页面
    - `/:pathMatch(.*)*`：NotFound 页面
  - **守卫策略**
    - 若 `to.meta.public`：允许访问，并强制浅色主题（登录/2FA 等公共页）
    - 否则：必须 `getSession()` 存在；若无 session → 跳转 `/login?next=<to.fullPath>&reason=UNAUTHENTICATED`
    - 若存在 `to.meta.role`：使用 `isAdmin/isDealer/isProvider` 判定，不满足则跳 `/403`
- **证据入口**
  - 文件：`frontend/admin/src/router/index.ts`
  - 关键调用点：`router.beforeEach((to) => { ... })`
  - 关键字段：`to.meta.public`、`to.meta.role`、`next` query、`reason=UNAUTHENTICATED`

### F-FE-003 Session 存储策略：localStorage 持久化 token + actorType + actorUsername
- **事实**
  - Session shape：`{ token, actorType, actorUsername? }`
  - localStorage keys：
    - `lhmy.admin.token`
    - `lhmy.admin.actorType`
    - `lhmy.admin.actorUsername`
  - 通过 `lsGet/lsSet/lsRemove` 包装 localStorage，避免异常导致页面崩溃
- **证据入口**
  - 文件：`frontend/admin/src/lib/auth.ts`
    - 函数：`getSession()`、`setSession()`、`clearSession()`
  - 文件：`frontend/admin/src/lib/storage.ts`
    - 函数：`lsGet()` / `lsSet()` / `lsRemove()`（封装 `window.localStorage.*`）

### F-FE-004 Token 注入与 401 统一处理：默认注入 Bearer；401 清 session 并跳登录（携带 next）
- **事实**
  - API baseUrl：`VITE_API_BASE_URL`（默认 `/api/v1`，并去掉末尾 `/`）
  - 默认行为：`opts.auth !== false` 时从 `getSession()` 取 token，注入 `Authorization: Bearer <token>`
  - 支持幂等 header：若传 `idempotencyKey` 则注入 `Idempotency-Key`
  - 请求缓存策略：`cache: 'no-store'`（避免旧列表/错误 NOT_FOUND）
  - 401 统一处理：`clearSession()`，并 `window.location.assign('/login?reason=UNAUTHENTICATED&next=...')`
- **证据入口**
  - 文件：`frontend/admin/src/lib/api.ts`
  - 关键函数：`apiRequest(path, opts)`
  - 关键调用点：
    - `headers.Authorization = \`Bearer ${session.token}\``
    - `headers['Idempotency-Key'] = opts.idempotencyKey`
    - `if (resp.status === 401 && opts?.auth !== false) { clearSession(); window.location.assign(...) }`

### F-FE-005 登录策略（单入口三域）：优先 Admin → Provider → Dealer；成功后写 session 并跳转 next
- **事实**
  - 登录页：同一入口（`/login`）按顺序尝试三类登录接口
  - Admin 登录可能触发 2FA：若返回 `requires2fa` 则跳转 `/admin-2fa?challengeId=...&next=...`
  - 成功后 `setSession({ token, actorType, actorUsername })` 并跳转：`next` 或默认首页（Admin: `/admin/dashboard`，Provider: `/provider/workbench`，Dealer: `/dealer/dashboard`）
- **证据入口**
  - 文件：`frontend/admin/src/pages/LoginPage.vue`
  - 关键调用点：`smartLogin()`
  - 关键接口路径：
    - `POST /api/v1/admin/auth/login`（`apiRequest('/admin/auth/login', { auth: false, ... })`）
    - `POST /api/v1/provider/auth/login`
    - `POST /api/v1/dealer/auth/login`

### F-FE-006 2FA 页：先 challenge 再 verify；verify 成功后写 session 并跳转 next
- **证据入口**
  - 文件：`frontend/admin/src/pages/Admin2faPage.vue`
  - 关键接口路径：
    - `POST /api/v1/admin/auth/2fa/challenge`
    - `POST /api/v1/admin/auth/2fa/verify`

### F-FE-007 修改密码（敏感操作）：按 actorType 选择 endpoint（Admin/Provider/Dealer）
- **证据入口**
  - 文件：`frontend/admin/src/pages/AccountSecurityPage.vue`
  - 关键调用点：`submit()` 中选择 endpoint
  - 关键接口路径：
    - `POST /api/v1/admin/auth/change-password`
    - `POST /api/v1/provider/auth/change-password`
    - `POST /api/v1/dealer/auth/change-password`

## 2. 关键页面与 API 调用清单（按三域）

> 说明：三域指 **ADMIN / DEALER / PROVIDER**，都在同一前端工程 `frontend/admin` 中，通过 `meta.role` 与 session.actorType 分流。

### 2.1 ADMIN 域（运营后台）

#### ADMIN-Auth / Security
- **登录页**：`/login`
  - **页面**：`frontend/admin/src/pages/LoginPage.vue`
  - **接口**：`POST /api/v1/admin/auth/login`
- **2FA 页**：`/admin-2fa`
  - **页面**：`frontend/admin/src/pages/Admin2faPage.vue`
  - **接口**：`POST /api/v1/admin/auth/2fa/challenge`、`POST /api/v1/admin/auth/2fa/verify`
- **安全设置**：`/account/security`
  - **页面**：`frontend/admin/src/pages/AccountSecurityPage.vue`
  - **接口**：`POST /api/v1/admin/auth/change-password`

#### ADMIN-Observability / Audit
- **审计日志**：`/admin/audit-logs`
  - **页面**：`frontend/admin/src/pages/admin/AdminAuditLogsPage.vue`
  - **接口**：`GET /api/v1/admin/audit-logs`
  - **后端证据**：`backend/app/api/v1/audit_logs.py`（`@router.get("/admin/audit-logs")`）

#### ADMIN-核心运营
- **仪表盘**：`/admin/dashboard`
  - **页面**：`frontend/admin/src/pages/admin/AdminDashboardPage.vue`
  - **接口**：`GET /api/v1/admin/dashboard/summary`
  - **后端证据**：`backend/app/api/v1/admin_dashboard.py`（`@router.get("/admin/dashboard/summary")`）
- **用户列表**：`/admin/users`
  - **页面**：`frontend/admin/src/pages/admin/AdminUsersPage.vue`
  - **接口**：`GET /api/v1/admin/users`、`GET /api/v1/admin/users/{id}`
- **订单监管**：`/admin/orders`
  - **页面**：`frontend/admin/src/pages/admin/AdminOrdersPage.vue`
  - **接口**：`GET /api/v1/admin/orders`、`POST /api/v1/admin/orders/{id}/ship`
  - **后端证据**：`backend/app/api/v1/orders.py`（`@router.get("/admin/orders")`、`@router.post("/admin/orders/{id}/ship")`）
- **预约管理（监管）**：`/admin/bookings`
  - **页面**：`frontend/admin/src/pages/admin/AdminBookingsPage.vue`
  - **接口**
    - 列表：`GET /api/v1/provider/bookings`（页面提示：平台监管视图，但当前实现复用 provider 列表）
    - 强制取消：`DELETE /api/v1/admin/bookings/{id}`（带 `Idempotency-Key`，body 含 reason）
  - **后端证据**：`backend/app/api/v1/bookings.py`（`@router.delete("/admin/bookings/{id}")`）
- **权益与核销（监管）**：`/admin/entitlements`
  - **页面**：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue`
  - **接口**
    - 权益列表：`GET /api/v1/entitlements`（非 `/admin/*` 前缀）
    - 核销记录：`GET /api/v1/admin/redemptions`
    - 转赠记录：`GET /api/v1/admin/entitlement-transfers`

#### ADMIN-账号与权限相关（高风险）
- **账号管理（创建/重置/冻结/启用）**：`/admin/accounts`
  - **页面**：`frontend/admin/src/pages/admin/AdminAccountsPage.vue`
  - **接口（示例）**
    - Provider 账号：`GET/POST /api/v1/admin/provider-users`，`POST /api/v1/admin/provider-users/{id}/reset-password`，`POST /api/v1/admin/provider-users/{id}/suspend`，`POST /api/v1/admin/provider-users/{id}/activate`
    - Provider 员工：`GET/POST /api/v1/admin/provider-staff`，`POST /api/v1/admin/provider-staff/{id}/reset-password`，`POST /api/v1/admin/provider-staff/{id}/suspend`，`POST /api/v1/admin/provider-staff/{id}/activate`
    - Dealer 账号：`GET/POST /api/v1/admin/dealer-users`，`POST /api/v1/admin/dealer-users/{id}/reset-password`，`POST /api/v1/admin/dealer-users/{id}/suspend`，`POST /api/v1/admin/dealer-users/{id}/activate`
  - **后端证据**：`backend/app/api/v1/admin_accounts.py`

#### ADMIN-审核/发布/下线/启停（高风险）
- **法律协议（发布/下线）**：`/admin/legal/agreements`
  - **页面**：`frontend/admin/src/pages/admin/AdminLegalAgreementsPage.vue`
  - **接口**：`GET/PUT /api/v1/admin/legal/agreements/{code}`，`POST /api/v1/admin/legal/agreements/{code}/publish`，`POST /api/v1/admin/legal/agreements/{code}/offline`
  - **后端证据**：`backend/app/api/v1/admin_legal.py`
- **CMS（发布/下线）**：`/admin/cms`
  - **页面**：`frontend/admin/src/pages/admin/AdminCmsPage.vue`
  - **接口**：`/api/v1/admin/cms/channels*`、`/api/v1/admin/cms/contents*`，含 `POST /admin/cms/contents/{id}/publish|offline`（带 query `scope=WEB|MINI_PROGRAM`）
  - **后端证据**：`backend/app/api/v1/cms.py`
- **小程序配置（发布/下线）**：`/admin/mini-program`
  - **页面**：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`
  - **接口（示例）**：
    - 管理端：`GET/PUT /api/v1/admin/mini-program/entries`，`POST /api/v1/admin/mini-program/entries/publish|offline`
    - 页面/集合：`PUT /api/v1/admin/mini-program/pages/{id}`，`POST /api/v1/admin/mini-program/pages/{id}/publish|offline`
    - 集合：`PUT /api/v1/admin/mini-program/collections/{id}`，`POST /api/v1/admin/mini-program/collections/{id}/publish|offline`
  - **后端证据**：`backend/app/api/v1/admin_mini_program_config.py`
- **场所审核（发布/驳回/下线）**：`/admin/venues`
  - **页面**：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`
  - **接口**：`GET /api/v1/admin/venues`，`GET /api/v1/admin/venues/{id}`，`POST /api/v1/admin/venues/{id}/publish|reject|offline`
  - **后端证据**：`backend/app/api/v1/admin_venues.py`
- **服务包计价规则（保存草稿/发布/下线）**：`/admin/service-package-pricing`
  - **页面**：`frontend/admin/src/pages/admin/AdminServicePackagePricingPage.vue`
  - **接口**：`GET/PUT /api/v1/admin/service-package-pricing`，`POST /api/v1/admin/service-package-pricing/publish|offline`
  - **后端证据**：`backend/app/api/v1/admin_service_package_pricing.py`
- **可售卡（启用/停用）**：`/admin/sellable-cards`
  - **页面**：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue`
  - **接口**：`GET/POST /api/v1/admin/sellable-cards`，`PUT /api/v1/admin/sellable-cards/{id}`，`POST /api/v1/admin/sellable-cards/{id}/enable|disable`
  - **后端证据**：`backend/app/api/v1/admin_sellable_cards.py`
- **服务分类（启用/停用）**：`/admin/service-categories`
  - **页面**：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue`
  - **接口**：`GET/POST /api/v1/admin/service-categories`，`PUT /api/v1/admin/service-categories/{id}`，`POST /api/v1/admin/service-categories/{id}/enable|disable`
  - **后端证据**：`backend/app/api/v1/admin_service_categories.py`
- **商品审核（通过/驳回/下架）**：`/admin/products`
  - **页面**：`frontend/admin/src/pages/admin/AdminProductsPage.vue`
  - **接口**：`GET /api/v1/admin/products`，`PUT /api/v1/admin/products/{id}/approve|reject|off-shelf`
  - **后端证据**：`backend/app/api/v1/products.py`
- **售后审核（decide）**：`/admin/after-sales`
  - **页面**：`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue`
  - **接口**：`GET /api/v1/admin/after-sales`，`PUT /api/v1/admin/after-sales/{id}/decide`
  - **后端证据**：`backend/app/api/v1/after_sales.py`
- **城市配置（发布/下线/导入）**：`/admin/regions/cities`
  - **页面**：`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`
  - **接口**：`GET/PUT /api/v1/admin/regions/cities`，`POST /api/v1/admin/regions/cities/publish|offline|import-cn`
  - **后端证据**：`backend/app/api/v1/admin_regions.py`
- **通知发送（敏感：触达/成本）**：`/admin/notifications/send`
  - **页面**：`frontend/admin/src/pages/admin/AdminNotificationsSendPage.vue`
  - **接口**：`GET /api/v1/admin/notification-receivers`，`POST /api/v1/admin/notifications/send`
  - **后端证据**：`backend/app/api/v1/admin_notification_receivers.py`、`backend/app/api/v1/admin_notifications.py`
- **经销商结算（资金高风险）**：`/admin/dealer-settlements`
  - **页面**：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - **接口**：`GET/PUT /api/v1/admin/dealer-commission`，`POST /api/v1/admin/dealer-settlements/generate`，`GET /api/v1/admin/dealer-settlements`，`POST /api/v1/admin/dealer-settlements/{id}/mark-settled`
  - **后端证据**：`backend/app/api/v1/admin_dealer_settlements.py`

### 2.2 DEALER 域（经销商后台）
- **登录**：复用 `/login`（见 `F-FE-005`）
- **链接管理**：`/dealer/links`
  - **页面**：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`
  - **接口**：
    - `GET /api/v1/dealer/sellable-cards`
    - `GET/POST /api/v1/dealer-links`
    - `POST /api/v1/dealer-links/{id}/disable`
  - **后端证据**：`backend/app/api/v1/dealer_links.py`（含 `@router.post("/dealer-links/{id}/disable")`）
- **订单**：`/dealer/orders`
  - **页面**：`frontend/admin/src/pages/dealer/DealerOrdersPage.vue`
  - **接口**：`GET /api/v1/dealer/orders`
- **结算**：`/dealer/settlements`
  - **页面**：`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`
  - **接口**：`GET/PUT /api/v1/dealer/settlement-account`，`GET /api/v1/dealer/settlements`
  - **后端证据**：`backend/app/api/v1/dealer.py`（`@router.put("/dealer/settlement-account")`）
- **通知**：`/dealer/notifications`
  - **页面**：`frontend/admin/src/pages/dealer/DealerNotificationsPage.vue`
  - **接口**：`GET /api/v1/dealer/notifications`，`POST /api/v1/dealer/notifications/{id}/read`
  - **后端证据**：`backend/app/api/v1/dealer_notifications.py`

### 2.3 PROVIDER 域（服务提供方后台）
- **登录**：复用 `/login`（见 `F-FE-005`）
- **工作台**：`/provider/workbench`
  - **页面**：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`
  - **接口（示例）**：`GET /api/v1/provider/onboarding`，`POST /api/v1/provider/onboarding/infra/open`，`POST /api/v1/provider/onboarding/health-card/submit`，`GET /api/v1/provider/workbench/stats`
- **场所维护**：`/provider/venues`
  - **页面**：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
  - **接口（示例）**：`GET /api/v1/provider/venues`，`GET/PUT /api/v1/provider/venues/{id}`，`POST /api/v1/provider/venues/{id}/submit-showcase`，并复用公共数据：`GET /api/v1/regions/cities`、`GET /api/v1/tags`
- **商品**：`/provider/products`
  - **页面**：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
  - **接口（示例）**：`GET/POST /api/v1/provider/products`，`PUT /api/v1/provider/products/{id}`（含状态变更），并复用：`GET /api/v1/service-categories`、`GET /api/v1/regions/cities`、`GET /api/v1/tags`
- **服务（上架到场所）**：`/provider/services`
  - **页面**：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`
  - **接口**：`POST /api/v1/provider/venues/{venueId}/services`，`PUT /api/v1/provider/venues/{venueId}/services/{id}`
- **排期/容量（批量更新，敏感：影响履约）**：`/provider/schedules`
  - **页面**：`frontend/admin/src/pages/provider/ProviderSchedulesPage.vue`
  - **接口**：`PUT /api/v1/provider/venues/{venueId}/schedules/batch`
- **预约（场所侧日常）**：`/provider/bookings`
  - **页面**：`frontend/admin/src/pages/provider/ProviderBookingsPage.vue`
  - **接口**：`GET /api/v1/provider/bookings`，`POST /api/v1/provider/bookings/{id}/cancel`，以及 `PUT /api/v1/bookings/{id}/confirm`（带 `Idempotency-Key`）
- **核销（高风险：扣减次数）**：`/provider/redeem`
  - **页面**：`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`
  - **接口**：`POST /api/v1/entitlements/{entitlementId}/redeem`（带 `Idempotency-Key`）
- **通知**：`/provider/notifications`
  - **页面**：`frontend/admin/src/pages/provider/ProviderNotificationsPage.vue`
  - **接口**：`GET /api/v1/provider/notifications`，`POST /api/v1/provider/notifications/{id}/read`

## 3. 敏感操作清单（必须有后端强制鉴权 + 审计 + 回滚策略；本节仅列“事实”）

> 规则：这里的“敏感”以**资金/审核/发布/导出/权限/账号**为主，辅以可能影响履约与用户权益的操作。

### 3.1 会话与账号安全
- **登录/2FA/refresh/logout（ADMIN）**
  - 前端证据：`frontend/admin/src/pages/LoginPage.vue`、`frontend/admin/src/pages/Admin2faPage.vue`
  - 后端证据：`backend/app/api/v1/admin_auth.py`
  - 接口：`POST /api/v1/admin/auth/login`、`POST /api/v1/admin/auth/2fa/*`、`POST /api/v1/admin/auth/refresh`、`POST /api/v1/admin/auth/logout`
- **修改密码（多域）**
  - 前端证据：`frontend/admin/src/pages/AccountSecurityPage.vue`（按 actorType 选 endpoint）
  - 后端证据：`backend/app/api/v1/admin_auth.py`、`backend/app/api/v1/provider_auth.py`、`backend/app/api/v1/dealer_auth.py`
  - 接口：`POST /api/v1/*/auth/change-password`
- **创建/重置/冻结/启用 Provider/ProviderStaff/Dealer 账号（高风险：权限与主体）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminAccountsPage.vue`（`saveCreate/resetPassword/toggle*Status`）
  - 后端证据：`backend/app/api/v1/admin_accounts.py`
  - 接口：`POST /api/v1/admin/*-users`、`POST /api/v1/admin/*/{id}/reset-password`、`POST /api/v1/admin/*/{id}/suspend|activate`

### 3.2 审核/发布/下线/启停（线上影响）
- **法律协议 publish/offline**
  - 前端证据：`frontend/admin/src/pages/admin/AdminLegalAgreementsPage.vue`
  - 后端证据：`backend/app/api/v1/admin_legal.py`
  - 接口：`POST /api/v1/admin/legal/agreements/{code}/publish|offline`
- **CMS 内容 publish/offline（含 scope=WEB/MINI_PROGRAM）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminCmsPage.vue`
  - 后端证据：`backend/app/api/v1/cms.py`
  - 接口：`POST /api/v1/admin/cms/contents/{id}/publish|offline`
- **小程序配置 publish/offline**
  - 前端证据：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`
  - 后端证据：`backend/app/api/v1/admin_mini_program_config.py`
  - 接口：`POST /api/v1/admin/mini-program/*/publish|offline`
- **场所 publish/reject/offline（审核）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`
  - 后端证据：`backend/app/api/v1/admin_venues.py`
  - 接口：`POST /api/v1/admin/venues/{id}/publish|reject|offline`
- **服务包计价规则 publish/offline**
  - 前端证据：`frontend/admin/src/pages/admin/AdminServicePackagePricingPage.vue`
  - 后端证据：`backend/app/api/v1/admin_service_package_pricing.py`
  - 接口：`POST /api/v1/admin/service-package-pricing/publish|offline`
- **可售卡 enable/disable（影响下单入口）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue`
  - 后端证据：`backend/app/api/v1/admin_sellable_cards.py`
  - 接口：`POST /api/v1/admin/sellable-cards/{id}/enable|disable`
- **服务分类 enable/disable**
  - 前端证据：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue`
  - 后端证据：`backend/app/api/v1/admin_service_categories.py`
  - 接口：`POST /api/v1/admin/service-categories/{id}/enable|disable`
- **商品审核 approve/reject/off-shelf**
  - 前端证据：`frontend/admin/src/pages/admin/AdminProductsPage.vue`
  - 后端证据：`backend/app/api/v1/products.py`
  - 接口：`PUT /api/v1/admin/products/{id}/approve|reject|off-shelf`
- **售后审核 decide**
  - 前端证据：`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue`
  - 后端证据：`backend/app/api/v1/after_sales.py`
  - 接口：`PUT /api/v1/admin/after-sales/{id}/decide`
- **城市配置 publish/offline/import（影响全局区域选择）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`
  - 后端证据：`backend/app/api/v1/admin_regions.py`
  - 接口：`POST /api/v1/admin/regions/cities/publish|offline|import-cn`

### 3.3 资金/结算（最高风险）
- **经销商分账规则修改**
  - 前端证据：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - 后端证据：`backend/app/api/v1/admin_dealer_settlements.py`
  - 接口：`PUT /api/v1/admin/dealer-commission`
- **结算生成（幂等）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - 后端证据：`backend/app/api/v1/admin_dealer_settlements.py`
  - 接口：`POST /api/v1/admin/dealer-settlements/generate`
- **结算标记已结算（mark-settled）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - 后端证据：`backend/app/api/v1/admin_dealer_settlements.py`
  - 接口：`POST /api/v1/admin/dealer-settlements/{id}/mark-settled`

### 3.4 履约/权益（高风险）
- **订单发货（物流）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminOrdersPage.vue`（`submitShip()`）
  - 后端证据：`backend/app/api/v1/orders.py`（`@router.post("/admin/orders/{id}/ship")`）
  - 接口：`POST /api/v1/admin/orders/{id}/ship`
- **预约强制取消（原因必填 + 幂等键）**
  - 前端证据：`frontend/admin/src/pages/admin/AdminBookingsPage.vue`（`cancelBooking()`）
  - 后端证据：`backend/app/api/v1/bookings.py`（`@router.delete("/admin/bookings/{id}")`）
  - 接口：`DELETE /api/v1/admin/bookings/{id}`（Header：`Idempotency-Key`）
- **核销（扣减次数 + 幂等键）**
  - 前端证据：`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`（`redeem()`）
  - 后端证据：`backend/app/api/v1/entitlements.py`（`@router.post("/entitlements/{id}/redeem")`，入参要求 `Idempotency-Key`）
  - 接口：`POST /api/v1/entitlements/{entitlementId}/redeem`（Header：`Idempotency-Key`）

### 3.5 触达/通知（可能涉及成本与合规）
- **平台侧通知发送**
  - 前端证据：`frontend/admin/src/pages/admin/AdminNotificationsSendPage.vue`
  - 后端证据：`backend/app/api/v1/admin_notifications.py`
  - 接口：`POST /api/v1/admin/notifications/send`

## 4. 待补齐（明确缺口）
- **导出（export）现状（需规格拍板生产化策略）**
  - 前端已存在**本地 CSV 导出**（无后端审计/限流/TTL）：`frontend/admin/src/pages/dealer/DealerOrdersPage.vue::exportCsv()`
  - 后端未发现**专用导出接口**（无 `Content-Disposition` / `/export` 路由）；现状导出为“浏览器端 Blob 下载”
  - 影响：无法满足 `TASK-P0-003` 的“权限门槛 + 审计 + 限流 + 文件生命周期”要求，需要在 `security.md#5` 与 `api-contracts.md` 拍板后改造
- **（已补齐）核销后端证据**：`backend/app/api/v1/entitlements.py` 已定位 `/entitlements/{id}/redeem`。
