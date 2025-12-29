# 需求与规则（Requirements）

## 1. 权限矩阵（RBAC Matrix）

> 说明：本节是“可生产化 Admin”的核心约束之一。任何新增页面/接口必须先补齐矩阵项。

### 1.1 角色（Actor / Role）
- **ADMIN**：管理后台管理员
- **DEALER**：经销商
- **PROVIDER**：场所/服务提供方

> 注：前端 `isProvider()` 将 `PROVIDER_STAFF` 视为 `PROVIDER` 域（见 `frontend/admin/src/lib/auth.ts` 与 `frontend/admin/src/router/index.ts`）。

### 1.2 权限粒度（最小可行版本）
- **V1（基线）**：以“角色 + 页面/路由”与“接口契约”作为权限粒度；禁止仅靠前端拦截/隐藏按钮
- **V2（可选）**：动作级（读/写/发布/导出/结算标记等）

### 1.3 页面/路由 × 角色矩阵（当前前端路由树的唯一口径）

> 来源证据：`frontend/admin/src/router/index.ts`（路由定义 + `router.beforeEach` 守卫）。

图例：
- **PUBLIC**：无需登录
- **✅**：允许访问（前端守卫允许；后端仍必须强制鉴权）
- **❌**：禁止访问（前端守卫将跳转 `/403` 或 `/login`）

| 路由/页面 | 前端组件（证据入口） | ADMIN | DEALER | PROVIDER | 备注（守卫口径） |
|---|---|---:|---:|---:|---|
| `/login` | `frontend/admin/src/pages/LoginPage.vue` | PUBLIC | PUBLIC | PUBLIC | `meta.public=true` |
| `/admin-2fa` | `frontend/admin/src/pages/Admin2faPage.vue` | PUBLIC | PUBLIC | PUBLIC | `meta.public=true` |
| `/account/security` | `frontend/admin/src/pages/AccountSecurityPage.vue` | ✅ | ✅ | ✅ | 任意已登录 actor 可访问（无 `meta.role`） |
| `/403` | `frontend/admin/src/pages/ForbiddenPage.vue` | ✅ | ✅ | ✅ | 任意已登录 actor 可访问（用于被拦截后展示） |
| `/:pathMatch(.*)*` | `frontend/admin/src/pages/NotFoundPage.vue` | ✅ | ✅ | ✅ | 任意已登录 actor 可访问（非 public，需登录） |
| `/admin`（redirect） | - | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/dashboard` | `frontend/admin/src/pages/admin/AdminDashboardPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/legal/agreements` | `frontend/admin/src/pages/admin/AdminLegalAgreementsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/enterprise-bindings` | `frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/enterprises` | `frontend/admin/src/pages/admin/AdminEnterprisesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/users` | `frontend/admin/src/pages/admin/AdminUsersPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/accounts` | `frontend/admin/src/pages/admin/AdminAccountsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/tags` | `frontend/admin/src/pages/admin/AdminTagsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/products` | `frontend/admin/src/pages/admin/AdminProductsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/orders` | `frontend/admin/src/pages/admin/AdminOrdersPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/orders/ecommerce-product` | `frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` + `orderType=PRODUCT` |
| `/admin/orders/service-package` | `frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` + `orderType=SERVICE_PACKAGE` |
| `/admin/after-sales` | `frontend/admin/src/pages/admin/AdminAfterSalesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/entitlements` | `frontend/admin/src/pages/admin/AdminEntitlementsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/service-packages` | `frontend/admin/src/pages/admin/AdminServicePackagesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/service-categories` | `frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/sellable-cards` | `frontend/admin/src/pages/admin/AdminSellableCardsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/provider-onboarding/health-card` | `frontend/admin/src/pages/admin/AdminProviderHealthCardOnboardingPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/venues` | `frontend/admin/src/pages/admin/AdminVenuesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/dealer-settlements` | `frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/service-package-pricing` | `frontend/admin/src/pages/admin/AdminServicePackagePricingPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/bookings` | `frontend/admin/src/pages/admin/AdminBookingsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/cms` | `frontend/admin/src/pages/admin/AdminCmsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/mini-program` | `frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/ai` | `frontend/admin/src/pages/admin/AdminAiConfigPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/regions/cities` | `frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/website/external-links` | `frontend/admin/src/pages/admin/AdminWebsiteExternalLinksPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/website/footer-config` | `frontend/admin/src/pages/admin/AdminWebsiteFooterConfigPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/website/home/recommended-venues` | `frontend/admin/src/pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/website/site-seo` | `frontend/admin/src/pages/admin/AdminWebsiteSiteSeoPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/website/nav-control` | `frontend/admin/src/pages/admin/AdminWebsiteNavControlPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/website/maintenance-mode` | `frontend/admin/src/pages/admin/AdminWebsiteMaintenanceModePage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/audit-logs` | `frontend/admin/src/pages/admin/AdminAuditLogsPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/admin/notifications/send` | `frontend/admin/src/pages/admin/AdminNotificationsSendPage.vue` | ✅ | ❌ | ❌ | `meta.role=ADMIN` |
| `/dealer`（redirect） | - | ❌ | ✅ | ❌ | `meta.role=DEALER` |
| `/dealer/dashboard` | `frontend/admin/src/pages/dealer/DealerDashboardPage.vue` | ❌ | ✅ | ❌ | `meta.role=DEALER` |
| `/dealer/links` | `frontend/admin/src/pages/dealer/DealerLinksPage.vue` | ❌ | ✅ | ❌ | `meta.role=DEALER` |
| `/dealer/orders` | `frontend/admin/src/pages/dealer/DealerOrdersPage.vue` | ❌ | ✅ | ❌ | `meta.role=DEALER` |
| `/dealer/settlements` | `frontend/admin/src/pages/dealer/DealerSettlementsPage.vue` | ❌ | ✅ | ❌ | `meta.role=DEALER` |
| `/dealer/notifications` | `frontend/admin/src/pages/dealer/DealerNotificationsPage.vue` | ❌ | ✅ | ❌ | `meta.role=DEALER` |
| `/provider`（redirect） | - | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/workbench` | `frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/venues` | `frontend/admin/src/pages/provider/ProviderVenuesPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/notifications` | `frontend/admin/src/pages/provider/ProviderNotificationsPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/services` | `frontend/admin/src/pages/provider/ProviderServicesPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/products` | `frontend/admin/src/pages/provider/ProviderProductsPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/schedules` | `frontend/admin/src/pages/provider/ProviderSchedulesPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/bookings` | `frontend/admin/src/pages/provider/ProviderBookingsPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/redeem` | `frontend/admin/src/pages/provider/ProviderRedeemPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |
| `/provider/redemptions` | `frontend/admin/src/pages/provider/ProviderRedemptionsPage.vue` | ❌ | ❌ | ✅ | `meta.role=PROVIDER` |

### 1.4 后端必须校验的授权关系（门禁点清单，禁止仅靠前端隐藏按钮）

> 本节定义“什么算完成后端越权门禁”。任何仅靠前端路由守卫/隐藏按钮而后端不校验的情况，**不算完成**。

#### AUTH-001 认证必须在后端强制（除明确公共接口）
- **要求**：除明确 `auth=false` 的公共接口外，后端必须拒绝未携带/无效 token。
- **证据入口**
  - 前端默认注入：`frontend/admin/src/lib/api.ts`（`Authorization: Bearer ...`）
  - 后端统一依赖：`backend/app/api/v1/deps.py`（`require_admin/require_user/optional_actor`）

#### AUTH-002 角色必须在后端强制（ActorType）
- **要求**：`/api/v1/admin/**` 仅 ADMIN；`/api/v1/dealer/**` 仅 DEALER；`/api/v1/provider/**` 仅 PROVIDER/PROVIDER_STAFF。
- **证据入口（示例）**
  - ADMIN：`backend/app/api/v1/admin_accounts.py`（多处 `Depends(require_admin)`）
  - DEALER：`backend/app/api/v1/dealer_notifications.py`（`require_actor_types(... allowed={DEALER})`）
  - PROVIDER：`backend/app/api/v1/provider_notifications.py`（`allowed={PROVIDER, PROVIDER_STAFF}`）

#### AUTH-003 token 过期/黑名单必须生效（会话失效）
- **要求**：过期 token 或已进入 blacklist 的 token 必须被拒绝（401/403 视接口策略，但必须拒绝执行业务写）。
- **证据入口**
  - ADMIN blacklist 校验：`backend/app/services/rbac.py`
  - ADMIN refresh/logout 写 blacklist：`backend/app/api/v1/admin_auth.py`

#### AUTHZ-OBJ-001 资源归属（ownership）必须后端强制（防越权访问他人资源）
- **要求**：
  - Provider 只能操作归属其 `providerId` 的 `Venue/Product/Service/Schedule/Booking` 等资源
  - Dealer 只能操作归属其 `dealerId` 的 `DealerLink/SettlementAccount/SettlementRecord` 等资源
- **证据入口（已存在的强校验样例）**
  - Provider 对场所/商品的归属裁决：`backend/app/api/v1/provider.py`（大量 `Venue.provider_id == ctx.providerId` 与 `Product.provider_id == ctx.providerId`）
  - Provider 核销时 venue 归属裁决：`backend/app/api/v1/entitlements.py`（`Venue.provider_id == provider_ctx.providerId`）
  - Dealer Links 列表强制 dealerId（限定数据范围）：`backend/app/api/v1/dealer_links.py`（`forced_dealer_id = ctx.dealerId`）

#### AUTHZ-ACTION-001 高风险写操作必须后端强制（审核/发布/下线/启停用/结算）
- **要求**：所有高风险写入口必须至少同时满足：
  - 认证（AUTH-001）
  - 角色门禁（AUTH-002）
  - 资源归属（AUTHZ-OBJ-001，如适用）
  - 状态机/冲突校验（例如冻结禁止结算、状态不允许审核等）
- **证据入口（示例）**
  - 结算冻结冲突：`backend/app/api/v1/admin_dealer_settlements.py`（`FROZEN` → 409 `STATE_CONFLICT`）
  - 预约强制取消入口：`backend/app/api/v1/bookings.py`（`DELETE /admin/bookings/{id}` 受 `require_admin`）

#### AUTHZ-IDEMP-001 幂等键必须后端强制（避免重复扣减/重复取消/重复写入）
- **要求**：对“扣减/取消/生成”等敏感写接口，必须定义并强制 Idempotency-Key（或等价幂等策略）。
- **证据入口**
  - 前端注入：`frontend/admin/src/lib/api.ts`（`Idempotency-Key`）
  - 后端强制：`backend/app/api/v1/entitlements.py`（`_require_idempotency_key` + `IdempotencyService`）

## 2. 关键业务规则（Key Rules）

### R-SEC-001 禁止越权（后端强制）
- 后端必须基于 `require_admin/require_actor_types`（或等价机制）做强制鉴权
- 前端路由守卫仅作为 UX 优化，不能视为安全边界

### R-AUD-001 高风险操作必须可审计
高风险包含但不限于：资金/结算标记、审核发布、导出、权限/账号管理、配置发布。
- 需要：actor、动作、资源、结果、requestId、IP、UA、变更摘要、必要元数据

### R-PII-001 隐私数据最小化
- 列表接口默认不得返回明文手机号/身份证/银行卡等
- 如需明文展示必须在规格中明确：权限门槛、审计、脱敏策略、导出策略

#### R-PII-001.1 敏感字段清单（v1 草案）
> 说明：该清单是“实现与测试的对照表”。任何新增字段/接口必须先补清单。

| 字段/示例 | 分类 | 默认出参（List/Detail/Export） | 脱敏口径（v1） | 备注/证据 |
|---|---|---|---|---|
| `phone` / `buyerPhone` | PII | 禁止/禁止/禁止 | `phoneMasked=138****1234` | 已实现：`admin_users.py`；导出：`dealer.py::export_dealer_orders_csv` |
| `contactPhone` | PII | 禁止/默认禁止/禁止 | `contactPhoneMasked` | 现状多端返回明文，需拍板治理（见 `security.md#2.3.4`） |
| `accountNo` | FUNDS | 禁止/禁止/禁止 | `accountNoMasked`（仅后4） | 已实现：`dealer.py::get_dealer_settlement_account` |
| `payoutReference` | FUNDS | 默认禁止/默认禁止/禁止 | `payoutReferenceLast4` | 审计已按后4位记录，接口回包需拍板（见 `security.md#2.3.5`） |
| `payoutAccount`（JSON） | FUNDS | 默认禁止/默认禁止/禁止 | 白名单 + 脱敏 | 需拍板字段白名单 |
| `shippingTrackingNo` | FULFILLMENT | 默认禁止/默认禁止/禁止 | `trackingNoLast4` | 现状 Admin 订单列表/详情返回明文（见 `security.md#2.3.4`） |
| `shippingAddress`（JSON） | FULFILLMENT | 禁止/默认禁止/禁止 | 内含 phone 必须脱敏 | 需拍板是否允许返回详细地址 |
| `qrCode`/`voucherCode` | SECRET | 禁止/禁止/禁止 | 不提供 | USER 侧存在（核销凭证），Admin 侧建议禁止出参明文 |
| token/password/smsCode | SECRET | 禁止/禁止/禁止 | `***` | 审计查询已兜底脱敏：`audit_logs.py::_mask_sensitive` |

#### R-PII-001.2 验收要点（与 TASK-P0-006 对齐）
- 列表接口中不出现明文字段（phone/contactPhone/accountNo/trackingNo/address 明文等）
- 详情/导出若允许出现明文，必须：
  - 在规格中明确“为什么需要、谁能看、如何审计、如何回滚”

### R-IDEMP-001 幂等约定
- 对“生成/发布/批量操作”等接口必须定义幂等策略（请求幂等键/状态幂等/冲突错误码）

## 3. DoD（验收用例：至少 5 条）

> 本节为“权限矩阵 + 后端越权门禁点”的最小验收集合；每次权限相关迭代至少跑通这些用例（可在 `test-plan.md` 进一步固化为自动化测试）。

### DoD-CASE-001 未登录访问受保护页面（前端守卫）
- **步骤**：无 session 直接访问任意非 public 页面（例如 `/admin/dashboard`）
- **期望**：跳转 `/login?reason=UNAUTHENTICATED&next=<原路径>`
- **证据入口**：`frontend/admin/src/router/index.ts`（`if (!session) return { path:'/login', query:{ next, reason:'UNAUTHENTICATED' } }`）

### DoD-CASE-002 未登录调用受保护 API（后端鉴权）
- **步骤**：不带 Authorization 调用任意受保护 API（例如 `GET /api/v1/admin/users`）
- **期望**：401（`UNAUTHENTICATED`）
- **证据入口**：`backend/app/api/v1/deps.py`（`require_admin` 401）

### DoD-CASE-003 角色不符访问页面（前端守卫）
- **步骤**：以 DEALER session 访问 `/admin/users`
- **期望**：跳转 `/403`
- **证据入口**：`frontend/admin/src/router/index.ts`（`requiredRole==='ADMIN' && !isAdmin(...) => /403`）

### DoD-CASE-004 角色不符调用 API（后端必须拦截）
- **步骤**：以 DEALER token 调用 `GET /api/v1/admin/users`
- **期望**：403（`FORBIDDEN`）或 401（视实现策略，但必须拒绝）
- **证据入口**：`backend/app/api/v1/deps.py`（`require_actor_types` 返回 403）

### DoD-CASE-005 越权访问他人资源（资源归属校验）
- **步骤**：以 PROVIDER 身份，调用 `POST /api/v1/entitlements/{id}/redeem`，传入不属于该 provider 的 `venueId`
- **期望**：403（`FORBIDDEN`）
- **证据入口**：`backend/app/api/v1/entitlements.py`（provider 场景校验 `Venue.provider_id == provider_ctx.providerId`）

### DoD-CASE-006 token 失效（blacklist）访问
- **步骤**：使用已 refresh/logout 的旧 ADMIN token 调用任意 admin API
- **期望**：401（`UNAUTHENTICATED`）
- **证据入口**：`backend/app/services/rbac.py`（blacklist 校验）与 `backend/app/api/v1/admin_auth.py`（refresh/logout 写 blacklist）

### DoD-CASE-007 正常访问（正向）
- **步骤**：以 ADMIN 登录后访问 `/admin/users`，并调用 `GET /api/v1/admin/users`
- **期望**：页面可见；API 返回成功 envelope（`success=true`），且列表不包含手机号明文（仅 `phoneMasked`）
- **证据入口**：`backend/app/api/v1/admin_users.py`（`phoneMasked`）

## 4. 错误码约定（占位）
详见 `api-contracts.md#7-错误码与语义`（通用错误码表 + 前端动作映射）。
