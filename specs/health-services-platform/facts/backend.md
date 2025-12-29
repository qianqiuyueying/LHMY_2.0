## 完成事实清单：后端（backend，FastAPI）

> 口径：只写“事实”（已经存在的行为/代码结构），每条都给出**证据入口**（文件路径/接口路径/关键函数/服务）。

### A) 应用入口与中间件

- [x] FastAPI 应用入口为 `backend/app/main.py:create_app()`  
  - 证据：`backend/app/main.py`
- [x] 静态资源挂载：`/static`（目录：`backend/app/static`）  
  - 证据：`backend/app/main.py` `app.mount("/static", ...)`
- [x] 中间件链路（RequestId / RequestLogger / RBACContext / AuditLog）  
  - 证据：`backend/app/main.py` `app.add_middleware(...)`
- [x] Prometheus metrics：`/metrics`（不进 schema）  
  - 证据：`backend/app/main.py` `Instrumentator().expose(... endpoint="/metrics")`

### A.1) 异步任务队列（Celery）

- [x] Celery 应用入口存在（broker=RabbitMQ，backend=Redis）  
  - 证据：`backend/app/celery_app.py`
- [x] 周期任务（beat）占位：每分钟扫描“库存占用超时释放”（实现待补齐电商逻辑）  
  - 证据：`backend/app/tasks/inventory.py` `release_expired_stock_reservations`

### B) 生产启动门禁（防止带默认密钥上线）

- [x] 当 `APP_ENV=production` 时，校验关键配置，不满足则拒绝启动  
  - 校验项（事实）：JWT secrets、签名密钥、微信登录、微信支付预支付关键配置  
  - 证据：`backend/app/main.py` `_validate_production_settings()`

### C) 路由聚合与 OpenAPI 兼容入口

- [x] 所有 v1 API 统一挂载到 `/api/v1`  
  - 证据：`backend/app/main.py` `app.include_router(... prefix="/api/v1")`
- [x] v1 路由聚合表（各模块 router include）  
  - 证据：`backend/app/api/v1/router.py`
- [x] OpenAPI 兼容入口：`GET /api/v1/openapi.json`  
  - 证据：`backend/app/api/v1/openapi_proxy.py`

### C.1) 健康探针（liveness/readiness）

- [x] liveness：`GET /api/v1/health/live`（仅进程存活）  
- [x] readiness：`GET /api/v1/health/ready`（检查 DB/Redis 可用）  
  - 证据：`backend/app/api/v1/health.py`

### D.5) 预约（vNow：支持“订单明细预约”独立流）

- [x] 预约来源支持扩展：`ENTITLEMENT`（服务包权益）与 `ORDER_ITEM`（基建联防服务型商品订单明细）  
  - 证据：`backend/app/models/booking.py`（`source_type/order_id/order_item_id/product_id`）、迁移 `backend/alembic/versions/f1c2d3e4a5b6_stage25_booking_order_item_source.py`
- [x] 订单明细预约上下文解析：`GET /api/v1/bookings/order-item-context?orderId=...&orderItemId=...`  
  - 证据：`backend/app/api/v1/bookings.py`

### D) H5 端关键契约（后端侧证据）

#### D1) H5 只读配置（SystemConfig 承载）

- [x] FAQ/条款：`GET /api/v1/h5/landing/faq-terms`（key=`H5_LANDING_FAQ_TERMS`）  
- [x] 服务协议：`GET /api/v1/h5/legal/service-agreement`（优先协议中心 `H5_BUY_AGREEMENT`，兼容 key=`H5_SERVICE_AGREEMENT`）  
- [x] 小程序拉起提示：`GET /api/v1/h5/mini-program/launch`（key=`H5_MINI_PROGRAM_LAUNCH`）  
  - 证据：`backend/app/api/v1/h5_config.py`

- [x] 协议/条款统一读侧：`GET /api/v1/legal/{code}`（仅返回已发布版本）  
  - 证据：`backend/app/api/v1/legal.py`、`backend/app/models/legal_agreement.py`

- [x] vNext：H5 投放链接只读解析（无需登录，基于 dealerLinkId）  
  - `GET /api/v1/h5/dealer-links/{dealerLinkId}`：返回经销商 +（可选）可售卡 + 链接有效期信息  
  - `GET /api/v1/h5/dealer-links/{dealerLinkId}/cards`：返回该经销商“已生成投放链接且可用”的卡列表（每项携带其 dealerLinkId，且 sellableCard 附带 `services[serviceType,totalCount]` 便于列表页展示）  
  - `GET /api/v1/h5/dealer-links/{dealerLinkId}/cards/{sellableCardId}`：返回指定卡详情（并校验该 dealer 是否有权售卖该卡）  
  - 证据：`backend/app/api/v1/h5_config.py`

### D.6) 标签库（全局）（后端侧证据）

- [x] 标签读侧：`GET /api/v1/tags?type=PRODUCT|SERVICE|VENUE`（仅返回 enabled 标签）  
  - 证据：`backend/app/api/v1/tags.py`
- [x] 标签管理复用 taxonomy-nodes：`GET/POST/PUT /api/v1/admin/taxonomy-nodes`（type 支持 `*_TAG`）  
  - 证据：`backend/app/api/v1/taxonomy_nodes.py`、`backend/app/models/enums.py`（`TaxonomyType.*_TAG`）

### D.5) 经销商分账与结算（后端侧证据）

- [x] 经销商结算账户（打款信息）：`GET/PUT /api/v1/dealer/settlement-account`  
  - 证据：`backend/app/api/v1/dealer.py`、`backend/app/models/dealer_settlement_account.py`
- [x] 经销商订单归属查询：`GET /api/v1/dealer/orders`  
  - 支持筛选：orderNo/phone/paymentStatus/dateFrom/dateTo；并支持按 `dealerLinkId` 精确筛选（用于投放链接追踪）  
  - 返回包含：`dealerLinkId`、`sellableCardId/sellableCardName/regionLevel`（卡片摘要）  
  - 证据：`backend/app/api/v1/dealer.py`
- [x] Admin 生成/查询结算单与标记打款：`POST /api/v1/admin/dealer-settlements/generate`、`GET /api/v1/admin/dealer-settlements`、`POST /api/v1/admin/dealer-settlements/{id}/mark-settled`  
  - 证据：`backend/app/api/v1/admin_dealer_settlements.py`、`backend/app/models/settlement_record.py`

#### D2) 地区配置（跨端复用）

- [x] 地区配置读侧：`GET /api/v1/regions/cities`（key=`REGION_CITIES`，仅返回 enabled+published items）  
  - 事实：返回列表可同时包含 `PROVINCE:*` 与 `CITY:*`（端侧按需过滤）  
  - 证据：`backend/app/api/v1/regions.py`
- [x] 地区配置写侧（Admin 维护并发布）：  
  - 草稿读写：`GET/PUT /api/v1/admin/regions/cities`  
  - 发布/下线：`POST /api/v1/admin/regions/cities/publish`、`POST /api/v1/admin/regions/cities/offline`  
  - 一键导入全国省/市（草稿）：`POST /api/v1/admin/regions/cities/import-cn`（使用 `gb2260` 生成省级+地级，不含区县）  
  - 证据：`backend/app/api/v1/admin_regions.py`、`backend/app/api/v1/router.py`

#### D3) H5 登录（短信验证码）

- [x] 发送短信：`POST /api/v1/auth/request-sms-code`（scene: `H5_BUY` / `MP_BIND_PHONE`）  
  - 依赖服务：`app.services.sms_code_service.SmsCodeService`  
  - 证据：`backend/app/api/v1/auth.py` `request_sms_code()`
- [x] H5 登录：`POST /api/v1/auth/login`（channel 固定 `H5`）  
  - 依赖服务：`SmsCodeService.verify_code()`、`compute_identities_and_member_valid_until()`、`create_user_token(channel="H5")`  
  - 证据：`backend/app/api/v1/auth.py` `h5_login()`

#### D4) 订单创建/支付（幂等、渠道约束、经销商归属）

- [x] 创建订单：`POST /api/v1/orders`（Header: `Idempotency-Key` 必填）  
  - 事实：`SERVICE_PACKAGE` 订单仅允许 `channel="H5"`；小程序不允许创建  
  - 事实（vNext）：H5 创建 `SERVICE_PACKAGE` 订单必须携带 `dealerLinkId`（query），后端将据此绑定订单 `dealerId`，并校验“订单 sellableCardId 属于该经销商已授权可售范围”（严格门禁）  
  - 事实：订单会记录 `dealerLinkId`（用于经销商侧“按投放链接追踪订单”）  
  - 兼容：`dealerId/ts/nonce/sign` 签名校验能力仍保留（用于非 SERVICE_PACKAGE 场景/兼容接口），但不作为服务包购买长期投放主入口  
  - 依赖服务：`app.services.idempotency.IdempotencyService`、`app.services.dealer_signing.verify_params`、`app.services.order_rules.order_items_match_order_type`、`app.services.pricing.resolve_price`、`app.services.entitlement_scope_rules.parse_region_scope`  
  - 证据：`backend/app/api/v1/orders.py` `create_order()`
- [x] 发起支付：`POST /api/v1/orders/{id}/pay`（Header: `Idempotency-Key` 必填）  
  - 事实：支持 `mockFail=1`（非 production）稳定触发失败返回（用于联调/回归）  
  - 事实：若用户无 openid，则返回 `paymentStatus=FAILED` + 明确原因  
  - 依赖：微信支付 JSAPI 预支付封装（同文件内 `_wechatpay_jsapi_prepay/_wechatpay_build_jsapi_pay_params`）  
  - 证据：`backend/app/api/v1/orders.py` `pay_order()`

### E) 小程序端关键契约（后端侧证据）

#### E1) 小程序登录与绑手机（跨端身份联通）

- [x] 小程序登录：`POST /api/v1/mini-program/auth/login`（支持 mock code）  
  - 依赖服务：`app.services.wechat_code_exchange.exchange_wechat_code()`、`compute_identities_and_member_valid_until()`、`create_user_token(channel="MINI_PROGRAM")`  
  - 证据：`backend/app/api/v1/mini_program_auth.py` `mini_program_login()`
- [x] 小程序绑手机：`POST /api/v1/mini-program/auth/bind-phone`（要求 token channel 为 `MINI_PROGRAM`）  
  - 依赖服务：`SmsCodeService.verify_code(scene="MP_BIND_PHONE")`  
  - 事实：手机号账户为主账户；会在事务内迁移 ownerId/userId（权益/订单/预约/售后/核销记录/转赠记录等）  
  - 证据：`backend/app/api/v1/mini_program_auth.py` `mini_program_bind_phone()`（update 清单见函数内）

#### E1.1) 小程序登录协议（最小入口）

- [x] 小程序登录服务协议读侧：`GET /api/v1/legal/MP_LOGIN_AGREEMENT`（仅返回已发布版本）  
  - 证据：`backend/app/api/v1/legal.py`

#### E2) 小程序配置读侧（SystemConfig 承载）

- [x] 入口配置：`GET /api/v1/mini-program/entries`（key=`MINI_PROGRAM_ENTRIES`，仅返回 enabled+published）  
- [x] 页面配置：`GET /api/v1/mini-program/pages/{id}`（key=`MINI_PROGRAM_PAGES`，仅返回 published，否则 NOT_FOUND）  
- [x] 集合配置：`GET /api/v1/mini-program/collections/{id}/items`（key=`MINI_PROGRAM_COLLECTIONS`，支持 region/taxonomy 过滤）  
  - 证据：`backend/app/api/v1/mini_program_config.py`

### F) 小程序商城/权益/预约/场所（后端侧证据）

#### F1) 商品与分类

- [x] 商品分类：`GET /api/v1/product-categories`  
  - 证据：`backend/app/api/v1/product_categories.py`
- [x] 商品列表/详情：`GET /api/v1/products`、`GET /api/v1/products/{id}`  
  - 证据：`backend/app/api/v1/products.py`

#### F2) 场所与可预约时段

- [x] 场所列表：`GET /api/v1/venues`（未登录可访问，但仅 PUBLISHED；支持 entitlementId 过滤时要求登录且 ownerId 为本人）  
- [x] 场所详情：`GET /api/v1/venues/{id}`（登录后返回更多字段与 services；可带 entitlementId 计算 eligible）  
- [x] 可预约时段：`GET /api/v1/venues/{id}/available-slots`（要求登录）  
  - 证据：`backend/app/api/v1/venues.py`

#### F3) 权益

- [x] 权益列表/详情：`GET /api/v1/entitlements`、`GET /api/v1/entitlements/{id}`（USER 仅 ownerId；ADMIN 全量）  
- [x] 权益转赠：`POST /api/v1/entitlements/{id}/transfer`（支持 SERVICE_PACKAGE 实例级转赠）  
- [x] 权益核销：`POST /api/v1/entitlements/{id}/redeem`（ADMIN/PROVIDER 才允许；幂等）  
  - 证据：`backend/app/api/v1/entitlements.py`

#### F4) 预约

- [x] 创建预约：`POST /api/v1/bookings`（幂等）  
- [x] 我的预约：`GET /api/v1/bookings`、`DELETE /api/v1/bookings/{id}`  
- [x] 预约详情：`GET /api/v1/bookings/{id}`（USER/ADMIN/PROVIDER 数据范围裁决）  
- [x] 确认预约：`PUT /api/v1/bookings/{id}/confirm`（ADMIN/PROVIDER）  
  - 依赖服务：`booking_capacity_rules`、`booking_state_machine`、`booking_confirmation_rules`、`booking_rules`、`venue_filtering_rules`、`IdempotencyService`  
  - 证据：`backend/app/api/v1/bookings.py`

### G) 支付回调（微信支付 v3）

- [x] 微信支付回调：`POST /api/v1/payments/wechat/notify`  
  - 事实：验签（平台证书）+ 解密（APIv3Key）+ 按 `out_trade_no`（Order.id）落单  
  - 依赖服务：`app.services.payment_callbacks.mark_payment_succeeded`  
  - 证据：`backend/app/api/v1/payments.py`

### H) AI 网关

- [x] AI chat：`POST /api/v1/ai/chat`（要求登录；幂等；按用户频控；不落库对话内容，只记录审计元数据）  
  - 配置：SystemConfig key=`AI_CONFIG`（enabled/baseUrl/apiKey/model 等）  
  - 证据：`backend/app/api/v1/ai.py`

### I) 已修复缺陷（事实）

- [x] Provider 工作台“申请开通健行天下”不再触发 500（补齐 uuid4 导入，避免创建通知时报错）  
  - 证据：`backend/app/api/v1/provider_onboarding.py`

- [x] Provider 开通协议勾选（事实）：基建联防开通/健行天下提交审核均要求 `agree=true` 并记录勾选时间  
  - 证据：`backend/app/api/v1/provider_onboarding.py`、`backend/app/models/provider.py`


