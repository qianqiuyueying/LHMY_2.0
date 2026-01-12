## 完成事实清单：管理后台（frontend/admin）

> 口径：只写“事实”（已经存在的行为/代码结构），每条都给出**证据入口**（文件路径/接口路径/关键函数）。

### A) 工程与入口

- [x] 技术栈：Vue3 + TypeScript + Vite + Element Plus  
  - 证据：`frontend/admin/package.json`（dependencies）、`frontend/admin/src/main.ts`
- [x] 应用入口：`createApp(App).use(router).use(ElementPlus).mount('#app')`  
  - 证据：`frontend/admin/src/main.ts`

### B) 路由结构与权限守卫

- [x] 路由模式：`createWebHistory()`（history 路由）  
  - 证据：`frontend/admin/src/router/index.ts`
- [x] 公共页：`/login`、`/admin-2fa`（meta.public=true）  
  - 证据：`frontend/admin/src/router/index.ts`
- [x] 三大业务域路由树（按角色隔离）
  - Admin：`/admin/*`
  - Dealer：`/dealer/*`
  - Provider：`/provider/*`
  - 证据：`frontend/admin/src/router/index.ts`（routes）
- [x] 路由守卫：未登录跳 `/login?next=...`；按 `to.meta.role` 强制角色匹配，失败跳 `/403`  
  - 证据：`frontend/admin/src/router/index.ts` `router.beforeEach(...)`
- [x] 未登录/会话失效统一提示：跳转到登录页并弹 toast（避免各页面重复展示错误块）  
  - 证据：`frontend/admin/src/router/index.ts`（`reason=UNAUTHENTICATED`）、`frontend/admin/src/pages/LoginPage.vue`（onMounted 提示）、`frontend/admin/src/lib/api.ts`（401 清 session 并跳转）

### C) 会话与鉴权

- [x] Session 存储（localStorage）：token + actorType + actorUsername  
  - key：`lhmy.admin.token`、`lhmy.admin.actorType`、`lhmy.admin.actorUsername`  
  - 证据：`frontend/admin/src/lib/auth.ts` `getSession()/setSession()/clearSession()`
- [x] API 默认携带 `Authorization: Bearer <token>`（除非 `auth:false`）  
  - 证据：`frontend/admin/src/lib/api.ts` `apiRequest()` -> `getSession()`
- [x] 各角色自助“修改密码”（旧密码→新密码），并写入审计日志  
  - 前端入口：`frontend/admin/src/layouts/AppLayout.vue`（安全设置）与 `frontend/admin/src/pages/AccountSecurityPage.vue`  
  - 后端接口：`POST /api/v1/admin/auth/change-password`、`POST /api/v1/provider/auth/change-password`、`POST /api/v1/dealer/auth/change-password`  
  - 审计查询：`backend/app/api/v1/audit_logs.py`（action=UPDATE）

### D) API 客户端（统一入口）

- [x] API BaseUrl 从 `VITE_API_BASE_URL` 读取，默认 `/api/v1`  
  - 证据：`frontend/admin/src/lib/api.ts` `baseUrl()`
- [x] 支持 query 参数拼接、JSON body、`Idempotency-Key` 请求头  
  - 证据：`frontend/admin/src/lib/api.ts` `apiRequest()`
- [x] 统一响应封装：成功 `{success:true,data}`；失败 `{success:false,error}`；失败时抛 `ApiException(status, apiError)`  
  - 证据：`frontend/admin/src/lib/api.ts` `ApiEnvelope`、`ApiException`

### E) 管理后台关键接口依赖（来自代码调用点）

> 注：以下条目来自 `apiRequest(...)` 调用点的静态扫描，作为升级时“关键节点清单”。

#### E1) Provider 侧

- [x] Provider 商品：`POST/PUT /api/v1/provider/products`、`PUT /api/v1/provider/products/{id}`（含状态变更）  
  - 证据：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
  - v2 事实：支持创建/编辑 `PHYSICAL_GOODS`（stock/shippingFee/weight）并提交审核  
    - 证据：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`、`backend/app/api/v1/provider.py`
- [x] Provider 场所提报展示：`POST /api/v1/provider/venues/{id}/submit-showcase`  
  - 证据：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
- [x] Provider 单场所口径：多处不再提供“选择场所”，统一固定为当前唯一场所  
  - 证据：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`、`frontend/admin/src/pages/provider/ProviderServicesPage.vue`、`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`、`frontend/admin/src/pages/provider/ProviderSchedulesPage.vue`、`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
- [x] Provider 上架/入驻：`POST /api/v1/provider/onboarding/infra/open`、`POST /api/v1/provider/onboarding/health-card/submit`  
  - 证据：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`
- [x] Provider 场所服务配置：`POST/PUT /api/v1/provider/venues/{venueId}/services`  
  - 证据：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`
- [x] Provider 预约：确认 `PUT /api/v1/bookings/{id}/confirm`（带幂等键）、取消 `POST /api/v1/provider/bookings/{id}/cancel`  
  - 证据：`frontend/admin/src/pages/provider/ProviderBookingsPage.vue`
- [x] Provider 排班批量：`POST /api/v1/provider/venues/{venueId}/schedules/batch`  
  - 证据：`frontend/admin/src/pages/provider/ProviderSchedulesPage.vue`
- [x] Provider 通知：`POST /api/v1/provider/notifications/{id}/read`  
  - 证据：`frontend/admin/src/pages/provider/ProviderNotificationsPage.vue`

#### E2) Dealer 侧

- [x] Dealer 投放链接禁用：`POST /api/v1/dealer-links/{id}/disable`  
  - 证据：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`
- [x] Dealer 生成投放链接：有效期止（validUntil）必填；前端校验 + 后端兜底  
  - 证据：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`、`backend/app/api/v1/dealer_links.py`
- [x] vNext：Dealer 投放入口 URL 形态为 `"/h5?dealerLinkId=<id>"`（可长期投放）  
  - 事实：不再暴露“链接类型”概念；经销商入口链接用于展示“该经销商可售卡列表”  
  - 事实：支持“指定卡直达”形态：`/h5?dealerLinkId=<id>&sellableCardId=<cardId>`  
  - 证据：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`（入口链接展示/直达链接拼接）、`backend/app/api/v1/dealer_links.py`（url 回填）
- [x] Dealer 订单归属页支持按支付状态/日期筛选，并可按 `dealerLinkId` 定位某个投放链接的成交订单；列表展示卡片摘要并支持导出 CSV  
  - 证据：`frontend/admin/src/pages/dealer/DealerOrdersPage.vue`
- [x] Dealer 维护结算账户（打款信息）：`GET/PUT /api/v1/dealer/settlement-account`  
  - 证据：`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`、`backend/app/api/v1/dealer.py`
- [x] Dealer 通知已读：`POST /api/v1/dealer/notifications/{id}/read`  
  - 证据：`frontend/admin/src/pages/dealer/DealerNotificationsPage.vue`

#### E3) Admin 侧

- [x] 可售卡：`POST/PUT /api/v1/admin/sellable-cards`、`POST /api/v1/admin/sellable-cards/{id}/enable|disable`  
  - 证据：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue`
- [x] 服务包定价：`PUT /api/v1/admin/service-package-pricing`、`POST /api/v1/admin/service-package-pricing/publish|offline`  
  - 证据：`frontend/admin/src/pages/admin/AdminServicePackagePricingPage.vue`
- [x] 场所：`POST /api/v1/admin/venues/{id}/publish|reject|offline`  
  - 证据：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`
- [x] 经销商分账与结算：分账比例配置、按月生成结算单、标记已打款/已结算  
  - `GET/PUT /api/v1/admin/dealer-commission`  
  - `POST /api/v1/admin/dealer-settlements/generate`、`GET /api/v1/admin/dealer-settlements`、`POST /api/v1/admin/dealer-settlements/{id}/mark-settled`  
  - 证据：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`、`backend/app/api/v1/admin_dealer_settlements.py`
- [x] 商品审核：`PUT /api/v1/admin/products/{id}/approve|reject|off-shelf`  
  - 证据：`frontend/admin/src/pages/admin/AdminProductsPage.vue`
  - v2 事实：商品履约类型包含 `SERVICE` 与 `PHYSICAL_GOODS`；物流商品在监管页展示库存/占用/运费等字段  
    - 证据：`frontend/admin/src/pages/admin/AdminProductsPage.vue`、`backend/app/api/v1/products.py`

- [x] 订单监管按业务线拆分（避免混用语境）  
  - 基建联防：`/admin/orders/ecommerce-product`（固定 `orderType=PRODUCT`）  
  - 健行天下：`/admin/orders/service-package`（固定 `orderType=SERVICE_PACKAGE`）  
  - 证据：路由 `frontend/admin/src/router/index.ts`、菜单 `frontend/admin/src/lib/nav.ts`
- [x] 订单监管列表补齐“订单摘要”与“详情抽屉”（面向运营快速识别与跟进）  
  - 列表摘要字段：`firstItemTitle + itemsCount`  
  - 详情抽屉：展示订单关键字段 + `order_items` 明细；物流订单在详情中展示（脱敏）收货地区  
  - 物流动作：支持“发货（录入快递公司/运单号）”与“标记妥投”  
  - 证据：`frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue`；后端：`backend/app/api/v1/orders.py`（`GET /admin/orders`、`GET /orders/{id}`、`POST /admin/orders/{id}/ship|deliver`）

- [x] Provider 服务型商品预约配置会自动生成 VenueService 关联（用于小程序独立预约）  
  - 证据：`backend/app/api/v1/provider.py`（`POST/PUT /api/v1/provider/products`）、`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
- [x] 标签库（全局）：Admin 维护 PRODUCT/SERVICE/VENUE 标签（启用/停用/排序），供 Provider 侧选择  
  - 证据：`frontend/admin/src/pages/admin/AdminTagsPage.vue`、`backend/app/api/v1/taxonomy_nodes.py`、`backend/app/api/v1/tags.py`
- [x] 区域/城市配置（REGION_CITIES）：草稿保存/发布/下线/一键导入全国省市  
  - `GET/PUT /api/v1/admin/regions/cities`、`POST /api/v1/admin/regions/cities/publish|offline|import-cn`  
  - 证据：
    - 页面（含分页/搜索防抖，改善大数据量卡顿）：`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`
    - 发布/保存持久化修复（避免 JSON 原地修改导致“发布不生效/保存无变化”）：`backend/app/api/v1/admin_regions.py`
- [x] 小程序配置：entries/pages/collections 的保存与发布/下线  
  - `PUT /api/v1/admin/mini-program/entries`、`POST /api/v1/admin/mini-program/entries/publish|offline`  
  - `PUT /api/v1/admin/mini-program/pages/{id}`、`POST /api/v1/admin/mini-program/pages/{id}/publish|offline`  
  - `PUT /api/v1/admin/mini-program/collections/{id}`、`POST /api/v1/admin/mini-program/collections/{id}/publish|offline`  
  - 证据：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`
  - 事实补充：小程序首页 Banner/轮播图复用 entries 中 `position=OPERATION` 项（运营位）
    - 证据：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`、`frontend/mini-program/pages/index/index.js`
  - 事实补充：发布前对 entries 做基础门禁校验（enabled 的入口必须具备合法 `jumpType` + 非空 `targetId`；ROUTE/WEBVIEW/MINI_PROGRAM 做基础格式防呆），避免发布后小程序端“点击无反应”  
    - 证据：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue` `precheckEntriesBeforePublish()`
  - v1 易用性优化事实：提供三步引导（集合→页面→入口），首页入口支持结构化编辑（快捷入口 + Banner/运营位），JSON 作为高级入口  
    - 证据：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`
- [x] CMS 内容：`POST/PUT /api/v1/admin/cms/contents`、`POST /api/v1/admin/cms/contents/{id}/publish|offline`  
  - 证据：`frontend/admin/src/pages/admin/AdminCmsPage.vue`
- [x] 企业/预约/售后/账号等监管类接口（存在调用点）  
  - 证据：`frontend/admin/src/pages/admin/AdminEnterprisesPage.vue`、`AdminBookingsPage.vue`、`AdminAfterSalesPage.vue`、`AdminAccountsPage.vue` 等
  - 事实补充：企业信息库城市筛选为 Select（数据源为已发布的 REGION_CITIES 城市项）  
    - 证据：`frontend/admin/src/pages/admin/AdminEnterprisesPage.vue`（`GET /api/v1/regions/cities`）

- [x] 官网配置-首页推荐场所：支持通过“搜索可选”方式添加场所（保存仍为 venueId）  
  - 场所检索：`GET /api/v1/admin/venues?keyword=...&publishStatus=PUBLISHED`  
  - 保存配置：`PUT /api/v1/admin/website/home/recommended-venues`  
  - 证据：`frontend/admin/src/pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue`、`backend/app/api/v1/admin_venues.py`、`backend/app/api/v1/admin_website_config.py`

#### E3.1) AI 能力平台（v2：Provider/Strategy/绑定/迁移）

- [x] AI Provider（技术配置层）：支持列表/新增/编辑/连接测试（凭证不在响应/审计中返回明文）  
  - 接口：`GET/POST /api/v1/admin/ai/providers`、`PUT /api/v1/admin/ai/providers/{providerId}`、`POST /api/v1/admin/ai/providers/{providerId}/test-connection`  
  - 证据：`backend/app/api/v1/admin_ai.py`、`frontend/admin/src/pages/admin/AdminAiProvidersPage.vue`
- [x] AI Strategy（业务能力层）：支持列表/新增/编辑（不包含模型/凭证/endpoint 等技术字段）  
  - 接口：`GET/POST /api/v1/admin/ai/strategies`、`PUT /api/v1/admin/ai/strategies/{strategyId}`  
  - 证据：`backend/app/api/v1/admin_ai.py`、`frontend/admin/src/pages/admin/AdminAiStrategiesPage.vue`
- [x] Strategy ↔ Provider 绑定：支持切换 Provider（不影响小程序端调用）  
  - 接口：`POST /api/v1/admin/ai/strategies/{strategyId}/bind-provider`  
  - 证据：`backend/app/api/v1/admin_ai.py`、`frontend/admin/src/pages/admin/AdminAiBindingsPage.vue`
- [x] 开发/测试辅助：一键清空 AI Provider/Strategy（避免“重启容器后看到历史残留记录”造成困惑）  
  - 接口：`POST /api/v1/admin/ai/dev/reset`（生产环境 403）  
  - 证据：`backend/app/api/v1/admin_ai.py`、`frontend/admin/src/pages/admin/AdminAiBindingsPage.vue`

### F) 主题策略（事实）

- [x] 登录/2FA 公共页强制浅色；业务页使用用户存储主题  
  - 证据：`frontend/admin/src/router/index.ts` `forceLightTheme()/applyStoredTheme()`


