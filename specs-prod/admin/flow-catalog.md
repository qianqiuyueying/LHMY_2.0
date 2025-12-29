# 线路目录（Flow Catalog）

> 目的：把“管理系统可走的线路（页面/流程/接口组合）”做成索引，便于权限矩阵、测试计划、发布回滚逐条对齐。

## 1. 目录结构约定
每条线路至少包含：
- **Flow ID**：如 `FLOW-AUTH-LOGIN`
- **入口**：URL / 菜单路径 / 触发方式
- **参与角色**：ADMIN / DEALER / PROVIDER（如适用）
- **前端页面**：组件路径（例如 `frontend/admin/src/pages/...`）
- **后端接口**：接口列表（方法 + 路径）
- **关键业务规则**：引用 `requirements.md` 章节
- **审计/日志**：引用 `security.md`、`observability.md`
- **最小测试**：引用 `test-plan.md`

## 2. 已知线路（基于现有路由与接口的最小骨架）

### FLOW-AUTH-LOGIN（登录）
- **入口**：`/login`
- **参与角色**：ADMIN / DEALER / PROVIDER（同一登录页，具体逻辑待确认）
- **前端页面**：`frontend/admin/src/pages/LoginPage.vue`
- **后端接口（至少）**
  - `POST /api/v1/admin/auth/login`（ADMIN）
  - （TBD）DEALER/PROVIDER 登录接口与返回会话形状
- **关联事实**：`facts.md#F-BE-006`、`facts.md#F-FE-002`

### FLOW-AUTH-2FA（管理员二次验证）
- **入口**：`/admin-2fa`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/Admin2faPage.vue`
- **后端接口**
  - `POST /api/v1/admin/auth/2fa/challenge`
  - `POST /api/v1/admin/auth/2fa/verify`
- **关联事实**：`facts.md#F-BE-006`

### FLOW-ACCOUNT-SECURITY（账号安全：修改密码等）
- **入口**：`/account/security`
- **参与角色**：已登录的任意 actor（按前端注释 “any authenticated actor”）
- **前端页面**：`frontend/admin/src/pages/AccountSecurityPage.vue`
- **后端接口（至少）**
  - `POST /api/v1/admin/auth/change-password`（ADMIN 变更已确认）
  - （TBD）DEALER/PROVIDER 的 change-password 是否存在
- **关联事实**：`facts.md#F-BE-006`

### FLOW-AUDIT-LOGS（审计日志查询）
- **入口**：`/admin/audit-logs`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminAuditLogsPage.vue`
- **后端接口**：
  - `GET /api/v1/admin/audit-logs`
- **风险等级**：高（审计/导出/敏感信息）

### FLOW-DEALER-SETTLEMENTS（经销商结算管理）
- **入口**：`/admin/dealer-settlements`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
- **后端接口**：见 `facts.md#F-BE-009`
- **风险等级**：高（资金/结算）

### FLOW-USERS（用户查询）
- **入口**：`/admin/users`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminUsersPage.vue`
- **后端接口**：见 `facts.md#F-BE-007`
- **风险等级**：中（隐私/脱敏）

### FLOW-REDEMPTIONS（核销记录）
- **入口**：`/admin/redemptions`（前端路由未列出：TBD；后端接口已存在）
- **参与角色**：ADMIN
- **后端接口**：见 `facts.md#F-BE-008`

### FLOW-WEBSITE-CONFIG（官网配置发布）
- **入口**：`/admin/website/*`
- **参与角色**：ADMIN
- **前端页面**：
  - `AdminWebsiteExternalLinksPage.vue` / `AdminWebsiteFooterConfigPage.vue` / `AdminWebsiteHomeRecommendedVenuesPage.vue` / `AdminWebsiteSiteSeoPage.vue` / `AdminWebsiteNavControlPage.vue` / `AdminWebsiteMaintenanceModePage.vue`
- **后端接口**：见 `facts.md#F-BE-010`
- **风险等级**：中（配置发布/线上影响）

### FLOW-ADMIN-DASHBOARD（仪表盘）
- **入口**：`/admin/dashboard`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminDashboardPage.vue`
- **后端接口**
  - `GET /api/v1/admin/dashboard/summary`
- **风险等级**：中（高频入口；聚合统计易引发性能与口径争议）

### FLOW-ADMIN-ENTERPRISE（企业与绑定审核）
- **入口**
  - `/admin/enterprise-bindings`（企业绑定审核）
  - `/admin/enterprises`（企业信息库）
- **参与角色**：ADMIN
- **前端页面**
  - `frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue`
  - `frontend/admin/src/pages/admin/AdminEnterprisesPage.vue`
- **后端接口（至少）**
  - `GET /api/v1/admin/enterprise-bindings`
  - `PUT /api/v1/admin/enterprise-bindings/{id}/approve`
  - `PUT /api/v1/admin/enterprise-bindings/{id}/reject`
  - `GET /api/v1/admin/enterprises`
  - `GET /api/v1/admin/enterprises/{id}`
  - `PUT /api/v1/admin/enterprises/{id}`（仅允许更新 name）
- **风险等级**：高（企业身份/员工身份授予；需要幂等与审计闭环）

### FLOW-ADMIN-AFTER-SALES（售后审核）
- **入口**：`/admin/after-sales`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue`
- **后端接口（至少）**
  - `GET /api/v1/admin/after-sales`
  - `PUT /api/v1/admin/after-sales/{id}/decide`
- **风险等级**：高（退款/争议裁决；必须 phone bound + 幂等口径 + 审计）

### FLOW-ADMIN-ENTITLEMENTS（权益/核销/转赠）
- **入口**：`/admin/entitlements`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue`
- **后端接口（至少）**
  - `GET /api/v1/entitlements`（Admin 监管只读：禁止返回凭证明文）
  - `GET /api/v1/admin/redemptions`
  - `GET /api/v1/admin/entitlement-transfers`
- **风险等级**：高（权益状态/凭证敏感信息；需脱敏与权限边界明确）

### FLOW-ADMIN-AI（AI 配置与审计）
- **入口**：`/admin/ai`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminAiConfigPage.vue`
- **后端接口（至少）**
  - `GET /api/v1/admin/ai/config`
  - `PUT /api/v1/admin/ai/config`
  - `GET /api/v1/admin/ai/audit-logs`
- **风险等级**：高（配置影响/密钥敏感；必须审计与脱敏）

### FLOW-ADMIN-BOOKINGS（平台预约监管）
- **入口**：`/admin/bookings`
- **参与角色**：ADMIN
- **前端页面**：`frontend/admin/src/pages/admin/AdminBookingsPage.vue`
- **后端接口（必须）**
  - `GET /api/v1/admin/bookings`（只读监管查询接口；避免复用 `/provider/*` 造成权限模型混淆）
  - `DELETE /api/v1/admin/bookings/{id}`（强制取消，原因必填，幂等键）
- **风险等级**：高（履约/用户体验/争议）

## 3. 待确认/待补齐
- **路线覆盖性**：把 `frontend/admin/src/router/index.ts` 中所有 `meta.role='ADMIN'` 的页面逐条补齐到本目录
- **接口对齐**：每条页面需要列出“调用哪些 API、错误码与权限门槛”


