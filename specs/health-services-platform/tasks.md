# 陆合铭云健康服务平台实施任务清单

## 任务概述

本任务清单将《陆合铭云健康服务平台设计文档》转化为可执行的编码任务。该平台整合"基建联防/健行天下/职健行动"三大业务线，包含企业官网、管理后台系统、小程序端、H5端等多个端侧系统。每个任务都是独立的、可测试的代码实现步骤，按照依赖关系递进式完成。代码中必须使用中文注释。

---

## 阶段 1：项目基础设施搭建

- [x] 1. 初始化项目结构和配置
  - [x] 1.1 创建后端项目目录结构（app/models, app/services, app/api, app/utils, app/middleware）
  - [x] 1.2 创建前端项目目录结构（企业官网/管理后台/H5 三个独立 Vue 项目）
  - [x] 1.3 编写 Docker Compose 配置文件（nginx, backend, mysql, redis, rabbitmq）
  - [x] 1.4 编写后端 Dockerfile 与依赖安装方案（uv + pyproject.toml/uv.lock）
    - 已收敛：以 `pyproject.toml` + `uv.lock` 作为唯一依赖源；Dockerfile 使用 `uv sync --frozen` 安装依赖
  - [x] 1.5 配置环境变量模板文件（.env.example）
  - _需求: 技术栈规范_

- [x] 2. 配置 FastAPI 应用核心
  - [x] 2.1 创建 FastAPI 应用入口和配置加载
  - [x] 2.2 配置 CORS、请求日志、异常处理中间件
  - [x] 2.3 实现统一响应体格式（success/data/error/requestId）
  - [x] 2.4 配置 OpenAPI/Swagger 文档自动生成
  - _需求: API 通用约定_

- [x] 3. 配置数据库和缓存连接
  - [x] 3.1 配置 MySQL 8.0 连接池（SQLAlchemy async）
  - [x] 3.2 配置 Redis 7.0 连接（缓存与会话）
  - [x] 3.3 实现数据库迁移工具配置（Alembic）
  - _需求: 数据存储规范_

- [x] 4. 检查点 - 确保基础设施正常运行
  - 确保所有测试通过，如有问题请询问用户。
  - 已验证：`python -m pytest backend` 通过（health 接口统一响应体与 requestId 注入）。

---

## 阶段 2：核心数据模型实现

- [ ] 5. 实现用户与身份模型
  - [x] 5.1 创建 User 模型（id, phone, unionid, nickname, avatar, identities, enterpriseId）
  - [x] 5.2 创建 Enterprise 企业信息库模型
  - [x] 5.3 创建 UserEnterpriseBinding 用户企业绑定关系模型（状态：PENDING/APPROVED/REJECTED）
  - [x]* 5.4 编写属性测试：企业绑定唯一性
    - **Property 10: 企业绑定唯一性**
    - **Validates: 属性 10**
  - _需求: 用户模型、企业绑定规则_

- [ ] 6. 实现商品与分类模型
  - [x] 6.1 创建 Product 商品模型（fulfillmentType: VIRTUAL_VOUCHER/SERVICE）
  - [x] 6.2 创建 ProductCategory 商品分类模型
  - [x] 6.3 创建 TaxonomyNode 分类体系模型（type: VENUE/PRODUCT/CONTENT）
  - [x] 6.4 创建 ServicePackage 服务包模板模型（区域级别、等级、服务类目×次数）
  - [x]* 6.5 编写属性测试：价格优先级计算一致性
    - **Property 12: 价格优先级计算一致性**
    - **Validates: 属性 12**
  - _需求: 商品模型、价格优先级规则_

- [x] 7. 实现订单与支付模型
  - [x] 7.1 创建 Order 订单主表模型（orderType: PRODUCT/VIRTUAL_VOUCHER/SERVICE_PACKAGE）
  - [x] 7.2 创建 OrderItem 订单明细模型
  - [x] 7.3 创建 Payment 支付记录模型
    - 说明：`design.md` 未给出 Payment 字段清单；为保证 v1 可落地，暂按“最小可执行口径”补充如下（后续若与真实对账/支付网关字段不一致，以更新后的规格为准）：
      - 字段（v1 最小）：id, orderId, paymentMethod, paymentStatus, amount, providerPayload(JSON), createdAt, updatedAt
  - [x] 7.4 创建 Refund 退款记录模型
  - [x] 7.5 创建 AfterSaleCase 售后申请模型
  - [x]* 7.6 编写属性测试：统一订单模型一致性
    - **Property 20: 统一订单模型一致性**
    - **Validates: 属性 20**
  - _需求: 订单模型、状态迁移规则_

- [x] 8. 实现权益与核销模型
  - [x] 8.1 创建 ServicePackageInstance 高端服务卡实例模型
  - [x] 8.2 创建 Entitlement 权益模型（ownerId 为唯一裁决字段）
  - [x] 8.3 创建 EntitlementTransfer 权益转赠记录模型
    - 说明：`design.md` 未给出 EntitlementTransfer 字段清单；v1 最小字段口径暂定：id, entitlementId, fromOwnerId, toOwnerId, transferredAt
  - [x] 8.4 创建 RedemptionRecord 核销记录模型
  - [x]* 8.5 编写属性测试：权益归属者唯一性
    - **Property 22: 权益归属者唯一性**
    - **Validates: 属性 22**
  - [x]* 8.6 编写属性测试：权益生成双形态完整性
    - **Property 21: 权益生成双形态完整性**
    - **Validates: 属性 21**
  - _需求: 权益模型、归属裁决规则_

- [x] 9. 实现预约与场所模型
  - [x] 9.1 创建 Venue 健康场所模型（区域归属、发布状态）
    - 规格来源：`design.md` -> `interface Venue`
  - [x] 9.2 创建 VenueService 场所服务模型
    - 规格缺口：`design.md` 未给出 `VenueService` 字段清单（仅在接口响应中出现 services 字段形态）。
    - v1 最小字段草案（已回填至 `design.md`，作为最新版规格）：`id, venueId, serviceType, title, fulfillmentType("VIRTUAL_VOUCHER"|"SERVICE"), productId?, bookingRequired, redemptionMethod("QR_CODE"|"VOUCHER_CODE"), applicableRegions?, status("ENABLED"|"DISABLED"), createdAt, updatedAt`
  - [x] 9.3 创建 VenueSchedule 场所排期配置模型
    - 规格缺口：`design.md` 未给出 `VenueSchedule` 字段清单（仅定义了 available-slots 响应结构）。
    - v1 最小字段草案（已回填至 `design.md`，作为最新版规格）：`id, venueId, serviceType, bookingDate("YYYY-MM-DD"), timeSlot("HH:mm-HH:mm"), capacity, remainingCapacity, status("ENABLED"|"DISABLED"), createdAt, updatedAt`
  - [x] 9.4 创建 Booking 预约模型（bookingDate + timeSlot 格式）
    - 规格来源：`design.md` -> `interface Booking`（明确 bookingDate + timeSlot 为存储口径）
  - [x]* 9.5 编写属性测试：预约取消时间窗口
    - **Property 18: 预约取消时间窗口**
    - **Validates: 属性 18**
  - _需求: 预约模型、取消窗口规则_

- [x] 10. 实现经销商与结算模型
  - [x] 10.1 创建 Dealer 经销商信息模型
    - 规格缺口：`design.md` 未给出 `Dealer` 字段清单（仅在原型表格列与停用影响矩阵中出现）。
    - v1 最小字段草案（已回填至 `design.md`，作为最新版规格）：`id, name, level?, parentDealerId?, status("ACTIVE"|"SUSPENDED"), contactName?, contactPhone?, createdAt, updatedAt`
  - [x] 10.2 创建 DealerHierarchy 经销商层级关系模型
    - 规格缺口：`design.md` 未给出 `DealerHierarchy` 字段清单。
    - v1 最小字段草案（已回填至 `design.md`，作为最新版规格，闭包表口径）：`id, ancestorDealerId, descendantDealerId, depth, createdAt`
  - [x] 10.3 创建 DealerLink 经销商链接模型（含签名参数）
    - 规格来源：`design.md` -> `interface DealerLink` + 「经销商参数签名（sign）规则」
    - 实现约束草案（已回填至 `design.md`，作为最新版规格）：服务端密钥通过环境变量 `DEALER_SIGN_SECRET` 配置（仅后端保存；不得在前端/URL 暴露）
  - [x] 10.4 创建 SettlementRecord 结算记录模型
    - 规格来源：`design.md` -> `interface SettlementRecord`
  - [x]* 10.5 编写属性测试：经销商参数解析和防篡改
    - **Property 5: 经销商参数解析和防篡改**
    - **Validates: 属性 5**
  - _需求: 经销商模型、签名规则_

- [x] 11. 实现系统支撑模型
  - [x] 11.1 创建 AuditLog 审计日志模型
    - 规格来源：`design.md` -> `interface AuditLog`
  - [x] 11.2 创建 CmsChannel 和 CmsContent 内容管理模型
    - 规格来源：`design.md` -> `interface CmsChannel/CmsContent`
  - [x] 11.3 创建 SystemConfig 系统配置模型
    - 规格缺口：`design.md` 未给出 `SystemConfig` 字段契约（仅列出表名与“系统配置/AI配置中心”等需求）。
    - v1 最小字段草案（已回填至 `design.md`，作为最新版规格）：`id, key(unique), valueJson, description?, status("ENABLED"|"DISABLED"), createdAt, updatedAt`
  - [x] 11.4 创建 Notification 消息通知记录模型
    - 规格缺口：`design.md` 未给出 `Notification` 字段契约（仅在 admin 顶栏出现“通知”入口、并列出表名）。
    - v1 最小字段草案（已回填至 `design.md`，作为最新版规格）：`id, receiverType("ADMIN"|"USER"|"DEALER"|"PROVIDER"|"PROVIDER_STAFF"), receiverId, title, content, status("UNREAD"|"READ"), createdAt, readAt?`
  - _需求: 审计日志、CMS 内容模型_

- [x] 12. 生成数据库迁移脚本
  - [x] 12.1 生成所有模型的 Alembic 迁移脚本
    - 已生成：`backend/alembic/versions/94f73bae3568_stage2_models_9_11.py`
  - [x] 12.2 执行迁移并验证表结构
    - 已执行 `alembic upgrade head`，并验证 `lhmy` 库中已创建 31 张表（含 `venues/bookings/dealers/dealer_links/settlement_records/audit_logs/system_configs/notifications` 等）。
  - _需求: 数据库设计_

- [x] 13. 检查点 - 确保数据模型正确
  - 已验证：`python -m pytest backend` 通过（当前共 10 个测试用例，包括属性 18、属性 5）。

---

## 阶段 3：统一身份认证服务

- [x] 14. 实现短信验证码服务
  - [x] 14.1 实现短信验证码生成与存储（Redis，5分钟有效期）
    - 已实现：`backend/app/services/sms_code_service.py`（`sms:code:{scene}:{phone}`，TTL=300s）
  - [x] 14.2 实现发送频控（60秒间隔、每日20次上限）
    - 已实现：60s 冷却 `sms:cooldown:{scene}:{phone}`；每日 20 次上限 `sms:daily:{YYYYMMDD}:{scene}:{phone}`（UTC 自然日）
  - [x] 14.3 实现验证码校验与失败锁定（10次失败锁定30分钟）
    - 已实现：失败计数 `sms:fail:{scene}:{phone}`；达到 10 次后锁定 `sms:lock:{scene}:{phone}`（锁定期内按 `RATE_LIMITED(429)` 返回，符合 v1 最小口径）
  - [x] 14.4 实现 POST /api/v1/auth/request-sms-code 接口
    - 已实现：`backend/app/api/v1/auth.py` -> `POST /api/v1/auth/request-sms-code`
  - _需求: 短信验证码规则_

- [x] 15. 实现 H5 端用户认证
  - [x] 15.1 实现 POST /api/v1/auth/login 接口（phone + smsCode）
    - 已实现：`backend/app/api/v1/auth.py` -> `POST /api/v1/auth/login`（`channel:"H5"`）
  - [x] 15.2 实现 JWT Token 生成与验证
    - 已实现：`backend/app/utils/jwt_token.py`（Bearer Token；配置项 `JWT_SECRET/JWT_ALGORITHM/JWT_EXPIRE_SECONDS` 已接入 `settings`）
  - [x] 15.3 实现用户身份信息返回（identities: MEMBER/EMPLOYEE）
    - 已实现：`backend/app/services/user_identity_service.py`（EMPLOYEE：`users.enterprise_id`；MEMBER：持有未过期 ACTIVE `service_package_instances`）
  - _需求: H5 认证接口契约_

- [x] 16. 实现小程序端用户认证
  - [x] 16.1 实现 POST /api/v1/mini-program/auth/login 接口（微信 code 换 unionid）
    - 已实现：`backend/app/api/v1/mini_program_auth.py` -> `POST /api/v1/mini-program/auth/login`
    - 已实现：`backend/app/services/wechat_code_exchange.py`（支持 `jscode2session` + `mock:unionid/openid`）
    - 说明：已新增 `users.openid` 字段用于承载 openid（unionid 拿不到时不再写入 `users.unionid`）
  - [x] 16.2 实现 POST /api/v1/mini-program/auth/bind-phone 接口（短信验证绑定手机号）
    - 已实现：`backend/app/api/v1/mini_program_auth.py` -> `POST /api/v1/mini-program/auth/bind-phone`（短信场景 `MP_BIND_PHONE`）
  - [x] 16.3 实现账号合并逻辑（一对一约束、数据迁移）
    - 已实现：以“手机号账户”为主账户合并；迁移 `entitlements/service_package_instances/orders/bookings/after_sale_cases/redemption_records/entitlement_transfers` 的裁决字段
    - 已补充迁移脚本：`backend/alembic/versions/3b1c2a9f1d2c_stage3_auth_rbac_enterprise.py`（新增 `users.phone/users.unionid` 唯一索引；MySQL 口径不支持 partial index，直接 UNIQUE 即可满足“非空唯一”）
  - [x]* 16.4 编写属性测试：跨端身份联通
    - **Property 7: 服务包权益生成可见性**（验证合并后同一 userId 联通）
    - **测试内容**：H5 购买 → 权益生成 → 小程序登录 → 绑定手机号合并 → 合并后权益可见
    - 已实现（v1 最小）：`backend/tests/test_property_cross_channel_identity_connectivity.py`（验证合并后数据裁决字段迁移规则）
    - **Validates: 属性 7 + 跨端身份联通口径**
  - _需求: 小程序认证、跨端身份联通口径_

- [x] 17. 实现 Admin 后台认证
  - [x] 17.1 实现 POST /api/v1/admin/auth/login 接口（账号密码）
    - 已实现：`backend/app/api/v1/admin_auth.py` -> `POST /api/v1/admin/auth/login`
    - 已实现：`admins` 表模型 `backend/app/models/admin.py`（含 `username/password_hash/status/phone?`）
    - 初始账号（开发/测试）：支持 `ADMIN_INIT_USERNAME/ADMIN_INIT_PASSWORD`（首次登录前自动创建）
  - [x] 17.2 实现 2FA 短信挑战与验证（可选）
    - 已实现：`POST /api/v1/admin/auth/2fa/challenge` + `POST /api/v1/admin/auth/2fa/verify`（Redis challenge + 短信 scene `ADMIN_2FA`）
  - [x] 17.3 实现 Token 刷新与登出接口
    - 已实现：`POST /api/v1/admin/auth/refresh`（续期并 blacklist 旧 token）
    - 已实现：`POST /api/v1/admin/auth/logout`（Redis blacklist：`admin:token:blacklist:{jti}`）
  - _需求: Admin 认证接口契约_

- [x] 18. 实现 RBAC 权限控制
  - [x] 18.1 实现角色定义（USER/ADMIN/DEALER/PROVIDER/PROVIDER_STAFF）
    - 已实现：`backend/app/services/rbac.py` -> `ActorType`
  - [x] 18.2 实现数据范围裁决中间件（ownerId/dealerId/providerId）
    - 已实现（v1 最小）：`backend/app/middleware/rbac_context.py`（解析 Bearer Token 注入 `request.state.actor`；阶段3仅落地 USER/ADMIN）
  - [x] 18.3 实现资源与动作权限检查装饰器
    - 已实现（v1 最小）：`backend/app/services/rbac.py` -> `require_actor_types(...)`（动作级别细分按 `design.md` v1 约束暂不启用）
  - _需求: RBAC 权限矩阵_

- [x] 19. 实现企业绑定服务
  - [x] 19.1 实现 POST /api/v1/auth/bind-enterprise 接口
    - 已实现：`backend/app/api/v1/auth.py` -> `POST /api/v1/auth/bind-enterprise`
  - [x] 19.2 实现企业名称智能匹配（从历史企业库）
    - 已实现：`backend/app/api/v1/auth.py` -> `GET /api/v1/auth/enterprise-suggestions`
    - 匹配规则：`backend/app/services/enterprise_matching.py`（精确/前缀/包含/编辑距离<=2，最多10条）
  - [x] 19.3 实现绑定唯一性校验（APPROVED 后拒绝新申请）
    - 已实现：存在 `APPROVED` 时返回 `STATE_CONFLICT(409)`（复用属性10约束）
  - [x]* 19.4 编写属性测试：企业名称智能匹配
    - **Property 9: 企业名称智能匹配**
    - 已实现：`backend/tests/test_property_enterprise_name_matching.py`
    - **Validates: 属性 9**
  - [x]* 19.5 编写属性测试：企业信息持久化
    - **Property 11: 企业信息持久化**
    - 已实现：`backend/tests/test_property_enterprise_name_matching.py`（企业名规范化口径）
    - **Validates: 属性 11**
  - _需求: 企业绑定规则_

- [x] 20. 实现用户信息查询
  - [x] 20.1 实现 GET /api/v1/users/profile 接口
    - 已实现：`backend/app/api/v1/users.py` -> `GET /api/v1/users/profile`
  - [x] 20.2 返回身份信息、企业信息、会员有效期
    - 已实现：返回 `identities/enterpriseId/enterpriseName/memberValidUntil`（会员有效期取 ACTIVE 卡实例最大 `valid_until`）
  - _需求: 用户信息接口契约_

- [x] 21. 检查点 - 确保认证服务正常
  - 已验证：`python -m pytest backend` 通过（当前共 13 个测试用例，覆盖阶段3新增的跨端合并规则/企业匹配规则等属性测试）。

---

## 阶段 4：商品与订单服务

- [x] 22. 实现商品管理服务
  - [x] 22.1 实现 GET /api/v1/products 商品列表接口（筛选、分页）
    - 已实现：`backend/app/api/v1/products.py` -> `GET /api/v1/products`（keyword/categoryId/providerId/fulfillmentType + page/pageSize）
  - [x] 22.2 实现 GET /api/v1/products/{id} 商品详情接口
    - 已实现：`backend/app/api/v1/products.py` -> `GET /api/v1/products/{id}`
    - 修复：`provider.name` 由 `providers` 表提供（模型：`backend/app/models/provider.py`；迁移：`backend/alembic/versions/1c7d4b2f0a19_stage4_add_providers_table.py`）
  - [x] 22.3 实现价格优先级计算（活动价>会员价>员工价>原价）
    - 已实现：`backend/app/services/pricing.py` -> `resolve_price(...)`
    - 已接入：下单金额计算 `backend/app/api/v1/orders.py`（按优先级裁决出 unitPrice/totalAmount）
  - [x] 22.4 实现商品状态过滤（仅返回 ON_SALE）
    - 已实现：列表/详情均仅允许 `products.status=ON_SALE`（否则按 `NOT_FOUND`/不返回）
  - _需求: 商品接口契约、价格优先级_

- [x] 23. 实现分类管理服务
  - [x] 23.1 实现 GET /api/v1/product-categories 商品分类列表接口
    - 已实现：`backend/app/api/v1/product_categories.py` -> `GET /api/v1/product-categories`（仅 `status=ENABLED`）
  - [x] 23.2 实现 GET /api/v1/mini-program/taxonomy-nodes 分类体系接口
    - 已实现：`backend/app/api/v1/taxonomy_nodes.py` -> `GET /api/v1/mini-program/taxonomy-nodes?type=...`（仅 `status=ENABLED`）
  - [x] 23.3 实现 Admin 分类管理接口（CRUD）
    - 已实现：
      - `backend/app/api/v1/product_categories.py` -> `GET/POST/PUT /api/v1/admin/product-categories`
      - `backend/app/api/v1/taxonomy_nodes.py` -> `GET/POST/PUT /api/v1/admin/taxonomy-nodes`
    - 鉴权：复用 admin token（含 blacklist 校验）
  - _需求: 分类接口契约_

- [x] 24. 实现订单创建服务
  - [x] 24.1 实现 POST /api/v1/orders 创建订单接口
    - 已实现：`backend/app/api/v1/orders.py` -> `POST /api/v1/orders`
  - [x] 24.2 实现幂等性控制（Idempotency-Key）
    - 已实现：`backend/app/services/idempotency.py`（Redis 24h 缓存首结果）
    - 已接入：`POST /api/v1/orders`、`POST /api/v1/orders/{id}/pay`
  - [x] 24.3 实现订单类型校验（小程序不允许 SERVICE_PACKAGE）
    - 已实现：创建订单时拒绝 `SERVICE_PACKAGE`（v1：CreateOrder 仅允许 PRODUCT/VIRTUAL_VOUCHER；同时做保守校验）
  - [x]* 24.4 编写属性测试：购物车和订单管理一致性
    - **Property 1: 购物车和订单管理一致性**
    - **Validates: 属性 1**
    - 已实现（v1 最小）：`backend/app/services/cart_order_rules.py` + `backend/tests/test_property_cart_order_consistency.py`
  - _需求: 订单创建接口契约_

- [x] 25. 实现订单支付服务
  - [x] 25.1 实现 POST /api/v1/orders/{id}/pay 支付接口
    - 已实现：`backend/app/api/v1/orders.py` -> `POST /api/v1/orders/{id}/pay`
  - [x] 25.2 集成微信支付（返回 wechatPayParams）
    - 已实现（v1 最小联调）：返回 `wechatPayParams` 的 mock 结构（后续对接微信支付需先补充验签/下单等规格）
  - [x] 25.3 实现支付回调处理与状态更新
    - 已实现（v1 最小核心逻辑）：`backend/app/services/payment_callbacks.py` -> `mark_payment_succeeded(...)`（更新 `orders/paymentStatus+paidAt` 与 `payments/paymentStatus+payload`）
    - 规格缺口：`design.md` 未定义微信支付回调 HTTP 端点与验签报文；当前先实现可复用核心逻辑，待补齐规格后挂接路由。
  - [x]* 25.4 编写属性测试：履约流程启动正确性
    - 已实现（v1 最小）：`backend/app/services/fulfillment_routing.py` + `backend/tests/test_property_fulfillment_flow_routing.py`
    - **Property 3: 履约流程启动正确性**
    - **Validates: 属性 3**
  - _需求: 支付接口契约_

- [x] 26. 实现订单查询服务
  - [x] 26.1 实现 GET /api/v1/orders 订单列表接口（按数据范围过滤）
    - 已实现：`backend/app/api/v1/orders.py` -> `GET /api/v1/orders`（仅本人）
  - [x] 26.2 实现 GET /api/v1/orders/{id} 订单详情接口
    - 已实现：`backend/app/api/v1/orders.py` -> `GET /api/v1/orders/{id}`（USER：仅本人；ADMIN：全量；DEALER/PROVIDER 延后）
  - _需求: 订单查询接口契约_

- [x] 27. 检查点 - 确保订单服务正常
  - 已验证：`python -m pytest backend` 通过（当前共 16 个测试用例，新增覆盖属性 1/3 的属性测试）。

---

## 阶段 5：权益管理服务

- [x] 28. 实现权益生成服务
  - [x] 28.1 实现支付成功后权益自动生成逻辑
    - 规格缺口：`design.md` 定义了 `Entitlement.validFrom/validUntil` 字段但未定义计算规则；同时未约束 `voucherCode` 的格式/长度。
    - v1 最小口径（已确认并实现）：
      - `validFrom = orders.paidAt`
      - `validUntil = orders.paidAt + 365 days`（默认 1 年；后续若 service package / product 补齐有效期配置再替换为配置口径）
      - `voucherCode = uuid4().hex[:16].upper()`（稳定、短码、便于人工核对；仍保证高概率唯一）
    - 已实现：`backend/app/services/entitlement_generation.py` + `backend/app/services/payment_callbacks.py`（支付成功后生成权益，幂等：已生成则不重复）
  - [x] 28.2 实现虚拟券权益生成（二维码 + 券码双形态）
    - 已实现：虚拟券订单（`orderType=VIRTUAL_VOUCHER`）按 `OrderItem.quantity` 生成 N 条 `Entitlement(entitlementType=VOUCHER)`，每条包含 `qrCode + voucherCode`
    - v1 约束（补充口径）：`Entitlement.serviceType` 取 `productId`（稳定 code），与 `VenueService.serviceType` 保持一致裁决口径
  - [x] 28.3 实现高端服务卡实例与权益生成（N 条权益对应 N 个服务类目）
    - 已实现：服务包订单（`orderType=SERVICE_PACKAGE`）生成 `ServicePackageInstance` + N 条 `Entitlement(entitlementType=SERVICE_PACKAGE)`（N=模板 `package_services` 数量）
    - 说明：小程序端不允许创建 SERVICE_PACKAGE 订单；当前仅实现“支付成功后交付”核心逻辑，待 H5 下单接口补齐后可直接复用
  - [x]* 28.4 编写属性测试：虚拟服务券生成完整性
    - **Property 2: 虚拟服务券生成完整性**
    - **Validates: 属性 2**
    - 已实现：`backend/tests/test_property_2_virtual_voucher_entitlement_shape.py`
  - _需求: 权益生成规则_

- [x] 29. 实现权益二维码签名
  - [x] 29.1 实现二维码 payload 生成（entitlementId/voucherCode/ts/nonce/sign）
  - [x] 29.2 实现 HMAC-SHA256 签名算法
  - [x] 29.3 实现签名有效期校验（10分钟）
  - 已实现：`backend/app/services/entitlement_qr_signing.py`（错误码：`QR_SIGN_INVALID/QR_SIGN_EXPIRED`）
  - _需求: 权益二维码 payload 签名规则_

- [x] 30. 实现权益查询服务
  - [x] 30.1 实现 GET /api/v1/entitlements 权益列表接口
  - [x] 30.2 实现 GET /api/v1/entitlements/{id} 权益详情接口
  - [x] 30.3 实现 ownerId 数据范围过滤
  - 已实现：`backend/app/api/v1/entitlements.py`（USER：仅本人 ownerId；ADMIN：全量；PROVIDER/PROVIDER_STAFF 延后）
  - _需求: 权益查询接口契约_

- [x] 31. 实现权益核销服务
  - [x] 31.1 实现 POST /api/v1/entitlements/{id}/redeem 核销接口
    - v1 已确认并实现：仅 ADMIN 可核销（PROVIDER/PROVIDER_STAFF 待账号体系阶段补齐后开放）
    - 已实现：`backend/app/api/v1/entitlements.py` -> `POST /api/v1/entitlements/{id}/redeem`
  - [x] 31.2 实现二维码/券码校验逻辑
    - v1 已确认并实现入参口径：
      - `redemptionMethod="QR_CODE"`：`voucherCode` 字段承载 **完整二维码 payload 文本**（`entitlementId=...&voucherCode=...&ts=...&nonce=...&sign=...`），服务端验签（错误码：`QR_SIGN_INVALID/QR_SIGN_EXPIRED`）
      - `redemptionMethod="VOUCHER_CODE"`：`voucherCode` 字段承载 **券码本身**（与 `Entitlement.voucherCode` 比对，不匹配则 `REDEEM_NOT_ALLOWED`）
  - [x] 31.3 实现核销成功才扣次数逻辑
    - 已实现：`backend/app/services/entitlement_redeem_rules.py` + 接口内落库更新（仅 SUCCESS 才扣减/置 USED）
  - [x] 31.4 实现需要预约的服务必须已确认预约校验
    - 已实现：按 `VenueService.bookingRequired` 裁决；需要预约时必须存在 `Booking.status=CONFIRMED`（否则 `BOOKING_REQUIRED`）
  - [x]* 31.5 编写属性测试：核销成功才扣次数
    - **Property 15: 核销成功才扣次数**
    - **Validates: 属性 15**
    - 已实现：`backend/tests/test_property_15_redeem_only_success_decrements.py`
  - [x]* 31.6 编写属性测试：预约与核销关联性
    - **Property 16: 预约与核销关联性**
    - **Validates: 属性 16**
    - 已实现：`backend/app/services/booking_redeem_rules.py` + `backend/tests/test_property_16_booking_required_for_redeem.py`
  - _需求: 核销接口契约、核销规则_

- [x] 32. 实现权益转赠服务
  - [x] 32.1 实现 POST /api/v1/entitlements/{id}/transfer 转赠接口
    - 已实现：`backend/app/api/v1/entitlements.py` -> `POST /api/v1/entitlements/{id}/transfer`（USER：仅本人 ownerId；ADMIN：全量）
    - v1 口径：服务包权益转赠以 **同一张 ServicePackageInstance** 为范围（属性 8），会转出该卡实例下所有权益并迁移卡实例 ownerId（通过创建新实例 + 新权益实现）
  - [x] 32.2 实现"从未使用"条件校验（核销记录为0、remainingCount==totalCount）
    - 已实现：服务包范围内所有权益满足 `remainingCount==totalCount` 且 SUCCESS 核销记录数为 0 才允许转赠
  - [x] 32.3 实现 ownerId 迁移与会员身份更新
    - 已实现：转赠服务包时迁移 ServicePackageInstance.ownerId（通过创建新 ACTIVE 实例）；`GET /api/v1/users/profile` 的会员身份由 ACTIVE 且未过期的实例裁决（20.2 已实现）
  - [x]* 32.4 编写属性测试：服务包退款和转赠条件
    - **Property 8: 服务包退款和转赠条件**
    - **Validates: 属性 8**
    - 已实现：`backend/app/services/entitlement_transfer_rules.py` + `backend/tests/test_property_8_service_package_transfer_condition.py`
  - _需求: 转赠接口契约、转赠条件_

- [x] 33. 实现权益类型与适用范围
  - [x] 33.1 实现基建联防权益全平台通用逻辑
  - [x] 33.2 实现健行天下权益区域限制逻辑
  - [x]* 33.3 编写属性测试：权益类型和适用范围匹配
    - **Property 13: 权益类型和适用范围匹配**
    - **Validates: 属性 13**
    - 已实现：`backend/app/services/entitlement_scope_rules.py` + `backend/tests/test_property_13_entitlement_scope_matching.py`
  - _需求: 权益适用范围规则_

- [x] 34. 检查点 - 确保权益服务正常
  - 已验证：`python -m pytest backend` 通过（当前共 23 个测试用例）。

---

## 阶段 6：预约管理服务

- [x] 35. 实现场所管理服务
  - [x] 35.1 实现 GET /api/v1/venues 场所列表接口（区域筛选、权益适用过滤）
    - 已实现：`backend/app/api/v1/venues.py` -> `GET /api/v1/venues`
    - 说明（v1 最小）：当传 `entitlementId` 时要求 USER 登录且权益必须 `ownerId==本人`，并按属性 14 过滤场所
    - 说明（v1 最小）：`taxonomyId` 暂按 `VenueService.serviceType` 解释进行过滤（规格未给出显式关联，后续若调整以更新后的规格为准）
  - [x] 35.2 实现 GET /api/v1/venues/{id} 场所详情接口
    - 已实现：`backend/app/api/v1/venues.py` -> `GET /api/v1/venues/{id}`（未登录仅返回公开字段；登录后返回 contactPhone/services，并支持 entitlementId 计算 eligible）
  - [x] 35.3 实现场所发布状态过滤（仅返回 PUBLISHED）
    - 已实现：venues 列表/详情均强制 `publishStatus=PUBLISHED`；否则统一 `NOT_FOUND`
  - [x]* 35.4 编写属性测试：权益使用场所过滤正确性
    - **Property 14: 权益使用场所过滤正确性**
    - **Validates: 属性 14**
    - 已实现：`backend/app/services/venue_filtering_rules.py` + `backend/tests/test_property_14_entitlement_venue_filtering.py`
  - _需求: 场所接口契约_

- [x] 36. 实现可用时段查询
  - [x] 36.1 实现 GET /api/v1/venues/{id}/available-slots 接口
    - 已实现：`backend/app/api/v1/venues.py` -> `GET /api/v1/venues/{id}/available-slots`
  - [x] 36.2 实现排期容量计算逻辑
    - 已实现：直接读取 `venue_schedules.remainingCapacity` 作为 v1 容量口径（排期写入/维护在 provider 后台阶段补齐）
  - _需求: 可用时段接口契约_

- [x] 37. 实现预约创建服务
  - [x] 37.1 实现 POST /api/v1/bookings 创建预约接口
    - 已实现：`backend/app/api/v1/bookings.py` -> `POST /api/v1/bookings`
  - [x] 37.2 实现权益归属校验（ownerId）
    - 已实现：create booking 时强制 `Entitlement.ownerId==当前用户`（否则 `ENTITLEMENT_NOT_OWNED`）
  - [x] 37.3 实现容量校验与扣减
    - 已实现：基于 `venue_schedules.remainingCapacity` 扣减；不足返回 `CAPACITY_FULL`
  - [x] 37.4 实现自动/人工确认模式
    - 已实现：`backend/app/services/booking_confirmation_rules.py`
    - v1 配置口径（最小）：`system_configs.key="BOOKING_CONFIRMATION_METHOD"`，`valueJson.method in ("AUTO","MANUAL")`，缺省 `AUTO`
  - [x]* 37.5 编写属性测试：预约确认机制正确性
    - **Property 17: 预约确认机制正确性**
    - **Validates: 属性 17**
    - 已实现：`backend/app/services/booking_confirmation_rules.py` + `backend/tests/test_property_17_booking_confirmation_mode.py`
  - _需求: 预约创建接口契约_

- [x] 38. 实现预约确认服务
  - [x] 38.1 实现 PUT /api/v1/bookings/{id}/confirm 确认接口
    - 已实现：`backend/app/api/v1/bookings.py` -> `PUT /api/v1/bookings/{id}/confirm`（仅 `PENDING -> CONFIRMED`）
  - [x] 38.2 实现 PROVIDER/ADMIN 权限校验
    - v1 最小：先落地 ADMIN 鉴权；PROVIDER/PROVIDER_STAFF 登录与数据范围在对应账号体系阶段补齐后收敛（实现文件已预留扩展点：`_try_get_admin_context`）
  - _需求: 预约确认接口契约_

- [x] 39. 实现预约取消服务
  - [x] 39.1 实现 DELETE /api/v1/bookings/{id} 取消接口
    - 已实现：`backend/app/api/v1/bookings.py` -> `DELETE /api/v1/bookings/{id}`（仅本人）
  - [x] 39.2 实现取消窗口校验（≥2小时允许，<2小时拒绝）
    - 已实现：基于 `backend/app/services/booking_rules.py`（属性18）；不满足返回 `BOOKING_CANCEL_WINDOW_CLOSED`
  - [x] 39.3 实现容量释放逻辑
    - 已实现：`backend/app/services/booking_capacity_rules.py`（释放不超过 capacity）
  - [x]* 39.4 编写属性测试：预约取消状态恢复
    - **Property 19: 预约取消状态恢复**
    - **Validates: 属性 19**
    - 已实现：`backend/app/services/booking_capacity_rules.py` + `backend/tests/test_property_19_booking_cancel_releases_capacity.py`
  - _需求: 预约取消接口契约_

- [x] 40. 实现预约查询服务
  - [x] 40.1 实现 GET /api/v1/bookings 用户预约列表接口
    - 已实现：`backend/app/api/v1/bookings.py` -> `GET /api/v1/bookings`（仅本人；status/dateFrom/dateTo/page/pageSize）
  - [x] 40.2 实现 GET /api/v1/provider/bookings 服务提供方预约列表接口
    - 已实现：`backend/app/api/v1/bookings.py` -> `GET /api/v1/provider/bookings`（v1 暂按 ADMIN；status/dateFrom/dateTo/serviceType/keyword/page/pageSize）
  - _需求: 预约查询接口契约_

- [x] 41. 检查点 - 确保预约服务正常
  - 确保所有测试通过，如有问题请询问用户。
  - 已验证：`python -m pytest backend` 通过（当前共 28 个测试用例）。

---

## 阶段 7：经销商服务（健行天下）

- [x] 42. 实现经销商链接生成
  - [x] 42.1 实现 POST /api/v1/dealer-links 创建链接接口
    - 已实现：`backend/app/api/v1/dealer_links.py` -> `POST /api/v1/dealer-links`
    - v1 说明：由于尚未实现 DEALER 账号体系，当前接口先按 ADMIN 访问；并临时要求 request body 传入 `dealerId`（后续补齐 token 后移除）。
  - [x] 42.2 实现 HMAC-SHA256 签名生成（dealerId/ts/nonce/sign）
    - 已实现：`backend/app/services/dealer_signing.py`
    - 已补齐配置：`backend/app/utils/settings.py` -> `DEALER_SIGN_SECRET`（settings.dealer_sign_secret）
  - [x] 42.3 实现链接 URL 与二维码生成
    - 已实现：创建时生成 `DealerLink.url`（相对路径示例：`/h5/buy?dealerId=...&ts=...&nonce=...&sign=...`）
    - v1 口径：规格未定义“二维码图片资源字段”，因此二维码图像由前端基于 `url` 生成。
  - _需求: 经销商链接接口契约_

- [x] 43. 实现经销商链接管理
  - [x] 43.1 实现 GET /api/v1/dealer-links 链接列表接口
    - 已实现：`backend/app/api/v1/dealer_links.py` -> `GET /api/v1/dealer-links`
  - [x] 43.2 实现 POST /api/v1/dealer-links/{id}/disable 停用接口
    - 已实现：`backend/app/api/v1/dealer_links.py` -> `POST /api/v1/dealer-links/{id}/disable`
  - [x] 43.3 实现链接过期自动处理
    - 已实现：惰性过期更新（list/disable 时将 `validUntil < now` 的 `ENABLED` 链接更新为 `EXPIRED`）
  - _需求: 经销商链接管理接口契约_

- [x] 44. 实现经销商参数校验
  - [x] 44.1 实现 GET /api/v1/dealer-links/verify 签名校验接口
    - 已实现：`backend/app/api/v1/dealer_links.py` -> `GET /api/v1/dealer-links/verify`（无 auth，用于 H5 预校验）
  - [x] 44.2 实现签名有效期校验（10分钟）
    - 已实现：`backend/app/services/dealer_signing.py` -> `verify_params`（`abs(now-ts) <= 10min`）
  - [x] 44.3 实现 H5 下单时经销商归属绑定
    - v1 口径：由于尚未单独落地 H5 的“健行天下 SERVICE_PACKAGE 下单接口”，先在统一 `POST /api/v1/orders` 支持 H5 渠道携带经销商参数并写入 `orders.dealerId`：
      - 已实现：`backend/app/api/v1/orders.py` -> `POST /api/v1/orders`（query: `dealerId/ts/nonce/sign`；仅 `channel=H5` 允许）
  - _需求: 经销商参数签名规则_

- [x] 45. 实现经销商订单与结算
  - [x] 45.1 实现 GET /api/v1/dealer/orders 归属订单列表接口
    - 已实现：`backend/app/api/v1/dealer.py` -> `GET /api/v1/dealer/orders`
    - v1 说明：当前按 ADMIN 访问并通过 query 传入 `dealerId` 限定范围；默认仅返回 `orderType=SERVICE_PACKAGE` 的订单。
  - [x] 45.2 实现 GET /api/v1/dealer/settlements 结算记录接口
    - 已实现：`backend/app/api/v1/dealer.py` -> `GET /api/v1/dealer/settlements`（按 dealerId 范围过滤）
  - [x] 45.3 实现结算周期计算逻辑
    - 已实现：`backend/app/services/settlement_cycle.py` -> `compute_settlement_cycle_monthly`（v1 固定口径：自然月 YYYY-MM）
    - 已补齐测试：`backend/tests/test_settlement_cycle_monthly.py`
  - _需求: 经销商订单结算接口契约_

- [x] 46. 检查点 - 确保经销商服务正常
  - 确保所有测试通过，如有问题请询问用户。
  - 已验证：2025-12-18 `python -m pytest backend` 通过（当前共 29 个测试用例）。

---

## 阶段 8：售后与退款服务

- [x] 47. 实现售后申请服务
  - [x] 47.1 实现售后申请创建接口
    - 已实现：`POST /api/v1/after-sales`（`backend/app/api/v1/after_sales.py`）
    - v1 最小：创建后自动进入 `UNDER_REVIEW`（满足状态机 `SUBMITTED -> UNDER_REVIEW`，不额外引入“受理”接口）
  - [x] 47.2 实现售后状态流转（SUBMITTED → UNDER_REVIEW → DECIDED → CLOSED）
    - 已实现：创建 `SUBMITTED -> UNDER_REVIEW`（自动受理）；admin 裁决 `UNDER_REVIEW -> DECIDED -> CLOSED`
  - _需求: 售后模型、状态迁移规则_

- [x] 48. 实现退款服务
  - [x] 48.1 实现退款申请与审核逻辑
    - v1 最小：退款执行链路由 admin 售后裁决触发（`decision=APPROVE`）
    - 已实现：`backend/app/services/refund_service.py`（创建 `Refund` + 更新订单/权益状态）
  - [x] 48.2 实现未核销虚拟券退款校验
    - 已实现：`backend/app/services/refund_rules.py` + `refund_service.validate_virtual_voucher_refund_allowed`
    - 若已发生 `SUCCESS` 核销：拒绝（错误码：`REFUND_NOT_ALLOWED`）
  - [x] 48.3 实现退款成功后订单状态更新（PAID → REFUNDED）
    - 已实现：`refund_service.execute_full_refund_for_order`（更新 `Order.payment_status=REFUNDED`，并将订单下 `Entitlement.status=REFUNDED`）
    - 已补齐枚举：`EntitlementStatus.REFUNDED`
  - [x]* 48.4 编写属性测试：未核销退款规则
    - **Property 4: 未核销退款规则**
    - **Validates: 属性 4**
    - 已实现：`backend/tests/test_property_4_unredeemed_refund_rule.py`
  - _需求: 退款规则_

- [x] 49. 实现 Admin 售后仲裁
  - [x] 49.1 实现 GET /api/v1/admin/after-sales 售后列表接口
    - 已实现：`backend/app/api/v1/after_sales.py`
    - v1 最小：支持 `type/status/dateFrom/dateTo/page/pageSize`
  - [x] 49.2 实现 PUT /api/v1/admin/after-sales/{id}/decide 裁决接口
    - 已实现：`backend/app/api/v1/after_sales.py`
    - 规则对齐：仅允许 `status=UNDER_REVIEW` 裁决；否则 `STATE_CONFLICT(409)`
    - `decision=APPROVE`：触发全额退款执行链路（v1 模拟成功）并闭环 `CLOSED`
  - _需求: Admin 售后仲裁接口契约_

- [x] 50. 检查点 - 确保售后服务正常
  - 已验证：2025-12-18 `python -m pytest backend` 通过（当前共 30 个测试用例）。

---

## 阶段 9：CMS 与配置服务

- [x] 51. 实现 CMS 内容服务
  - [x] 51.1 实现 GET /api/v1/mini-program/cms/channels 栏目列表接口
    - 已实现：`backend/app/api/v1/cms.py`（仅返回 `status=ENABLED`）
  - [x] 51.2 实现 GET /api/v1/mini-program/cms/contents 内容列表接口
    - 已实现：`backend/app/api/v1/cms.py`（仅返回 `status=PUBLISHED` + 分页 + keyword/channelId 过滤）
  - [x] 51.3 实现 GET /api/v1/mini-program/cms/contents/{id} 内容详情接口
    - 已实现：`backend/app/api/v1/cms.py`（未发布/不在有效期内统一 `NOT_FOUND`）
  - [x] 51.4 实现内容有效期过滤逻辑
    - 已实现：`effectiveFrom/effectiveUntil` 过滤（小程序读侧）
  - _需求: CMS 内容接口契约_

- [x] 52. 实现 Admin CMS 管理
  - [x] 52.1 实现 Admin 栏目 CRUD 接口
    - 已实现：`backend/app/api/v1/cms.py`（GET/POST/PUT `/api/v1/admin/cms/channels`）
  - [x] 52.2 实现 Admin 内容 CRUD 接口
    - 已实现：`backend/app/api/v1/cms.py`（GET/POST/PUT `/api/v1/admin/cms/contents`）
  - [x] 52.3 实现内容发布/下线接口
    - 已实现：`backend/app/api/v1/cms.py`（`/publish` 写入 `publishedAt`；`/offline` 仅允许从 `PUBLISHED` 下线）
  - _需求: Admin CMS 管理接口契约_

- [x] 53. 实现小程序配置服务
  - [x] 53.1 实现 GET /api/v1/mini-program/entries 首页入口配置接口
    - 已实现：`backend/app/api/v1/mini_program_config.py`（仅返回“已启用+已发布”）
  - [x] 53.2 实现 GET /api/v1/mini-program/pages/{id} 页面配置接口
    - 已实现：`backend/app/api/v1/mini_program_config.py`（仅返回已发布；否则 `NOT_FOUND`）
  - [x] 53.3 实现 GET /api/v1/mini-program/collections/{id}/items 集合数据接口
    - 已实现：`backend/app/api/v1/mini_program_config.py`（仅返回已发布 items；支持 region/taxonomy 过滤）
  - _需求: 小程序配置接口契约_

- [x] 54. 实现 Admin 小程序配置中心
  - [x] 54.1 实现入口配置管理接口
    - 已实现：`backend/app/api/v1/admin_mini_program_config.py`
      - `GET /api/v1/admin/mini-program/entries`
      - `PUT /api/v1/admin/mini-program/entries`（PUT 不允许直接修改 published）
  - [x] 54.2 实现聚合页/信息页配置管理接口
    - 已实现：`backend/app/api/v1/admin_mini_program_config.py`
      - `GET /api/v1/admin/mini-program/pages`
      - `PUT /api/v1/admin/mini-program/pages/{id}`（PUT 不允许直接修改 published）
  - [x] 54.3 实现内容集合 Schema 与数据管理接口
    - 已实现：`backend/app/api/v1/admin_mini_program_config.py`
      - `GET /api/v1/admin/mini-program/collections`
      - `PUT /api/v1/admin/mini-program/collections/{id}`（schema/items 透传 JSON，最小可执行）
  - [x] 54.4 实现配置发布/下线接口
    - 已实现：`backend/app/api/v1/admin_mini_program_config.py`
      - `POST /api/v1/admin/mini-program/entries/publish|offline`
      - `POST /api/v1/admin/mini-program/pages/{id}/publish|offline`
      - `POST /api/v1/admin/mini-program/collections/{id}/publish|offline`
  - **规格补充（待确认）**：
    - `design.md` 目前仅给出小程序配置“读侧”接口（F），以及 admin 侧“存在配置中心/发布能力”的需求描述（无明确 API 契约）。
    - 为使阶段9可落地（v1 最小），建议先以 `SystemConfig(key/valueJson)` 作为存储承载，并补齐以下 admin API 契约（后续可无缝迁移到 B2 通用表方案）：
      - **入口管理**
        - `GET /api/v1/admin/mini-program/entries`
          - Response：`{ items: Array<{ id, name, iconUrl?, position, jumpType, targetId, sort, enabled: boolean, published: boolean }>, version: string }`
        - `PUT /api/v1/admin/mini-program/entries`
          - Request：同上 `{ items, version? }`（version 可由后端生成/覆盖）
          - Rule：仅更新草稿；发布/下线由 publish/offline 接口控制
      - **页面管理**
        - `GET /api/v1/admin/mini-program/pages`
          - Response：`{ items: Array<{ id, type: "AGG_PAGE"|"INFO_PAGE", config: object, version: string, published: boolean }>, version: string }`
        - `PUT /api/v1/admin/mini-program/pages/{id}`
          - Request：`{ type?, config?, published? }`（published 仅允许 false->true 通过 publish，true->false 通过 offline）
      - **集合管理（读侧契约仅要求 items 读接口）**
        - `GET /api/v1/admin/mini-program/collections`
          - Response：`{ items: Array<{ id, name, published: boolean, updatedAt }>, version: string }`
        - `PUT /api/v1/admin/mini-program/collections/{id}`
          - Request（最小）：`{ name?, schema?: object, items?: any[] }`（schema 先透传 JSON，不做强校验）
      - **发布/下线**
        - `POST /api/v1/admin/mini-program/entries/publish|offline`
        - `POST /api/v1/admin/mini-program/pages/{id}/publish|offline`
        - `POST /api/v1/admin/mini-program/collections/{id}/publish|offline`
        - Rule：publish 将 `published=true` 并写入 version；offline 将 `published=false`
      - **内部存储 key（实现细节）**
        - `SystemConfig.key`：`MINI_PROGRAM_ENTRIES` / `MINI_PROGRAM_PAGES` / `MINI_PROGRAM_COLLECTIONS`
  - _需求: Admin 小程序配置中心_

- [x] 55. 检查点 - 确保 CMS 服务正常
  - [x] 确保所有测试通过
    - 已验证：2025-12-18 `python -m pytest backend` 通过（当前共 30 个测试用例）。

---

## 阶段 10：Admin 审核与监管服务

- [x] 56. 实现企业绑定审核
  - [x] 56.1 实现 GET /api/v1/admin/enterprise-bindings 绑定列表接口
    - 已实现：`backend/app/api/v1/auth.py`（支持 status/phone/enterpriseName/dateFrom/dateTo + 分页；手机号返回脱敏）
  - [x] 56.2 实现 PUT /api/v1/admin/enterprise-bindings/{id}/approve 审核通过接口
    - 已实现：`backend/app/api/v1/auth.py`（仅 `PENDING->APPROVED`；写入 `users.enterprise_id/name/binding_time` 并重算 identities=EMPLOYEE）
  - [x] 56.3 实现 PUT /api/v1/admin/enterprise-bindings/{id}/reject 审核驳回接口
    - 已实现：`backend/app/api/v1/auth.py`（仅 `PENDING->REJECTED`）
  - _需求: 企业绑定审核接口契约_

- [x] 57. 实现商品审核与监管
  - [x] 57.1 实现 GET /api/v1/admin/products 商品审核列表接口
    - 已实现：`backend/app/api/v1/products.py`（支持商家=providerId/类目=categoryId/状态/类型筛选 + 分页）
  - [x] 57.2 实现 PUT /api/v1/admin/products/{id}/approve 审核通过接口
    - 已实现：`backend/app/api/v1/products.py`（仅 `PENDING_REVIEW->ON_SALE`）
  - [x] 57.3 实现 PUT /api/v1/admin/products/{id}/reject 审核驳回接口
    - 已实现：`backend/app/api/v1/products.py`（仅 `PENDING_REVIEW->REJECTED`）
  - [x] 57.4 实现 PUT /api/v1/admin/products/{id}/off-shelf 下架接口
    - 已实现：`backend/app/api/v1/products.py`（仅 `ON_SALE->OFF_SHELF`）
  - _需求: 商品审核接口契约_

- [x] 58. 实现订单监管
  - [x] 58.1 实现 GET /api/v1/admin/orders 订单监管列表接口
    - 已实现：`backend/app/api/v1/orders.py`（E-1 v1 最小契约）
  - [x] 58.2 实现多维度筛选（订单号/用户/类型/状态/经销商/服务提供方）
    - 已实现：`backend/app/api/v1/orders.py`（orderNo/userId/phone/orderType/paymentStatus/dealerId/providerId/dateFrom/dateTo）
  - _需求: Admin 订单监管接口契约_

- [x] 59. 实现审计日志服务
  - [x] 59.1 实现审计日志自动记录中间件
    - 已实现：`backend/app/middleware/audit_log.py` + `backend/app/main.py`（写操作自动留痕；不记录 query/body 明文）
  - [x] 59.2 实现 GET /api/v1/admin/audit-logs 审计日志查询接口
    - 已实现：`backend/app/api/v1/audit_logs.py` + `backend/app/api/v1/router.py`
  - [x] 59.3 实现敏感信息脱敏处理
    - 已实现：写侧 metadata 白名单；读侧对 metadata 做兜底脱敏（`backend/app/api/v1/audit_logs.py`）
    - 补充：`admin/auth/login|2fa/verify|logout` 额外写入 LOGIN/LOGOUT 审计（`backend/app/api/v1/admin_auth.py`）
  - _需求: 审计日志接口契约_

- [x] 60. 检查点 - 确保 Admin 服务正常
  - [x] 确保所有测试通过
    - 已验证：2025-12-18 `python -m pytest backend` 通过（当前共 30 个测试用例）。

---

## 阶段 11：AI 对话服务

- [x] 61. 实现 AI 网关服务
  - [x] 61.1 实现 POST /api/v1/ai/chat 对话接口
    - 已实现：`backend/app/api/v1/ai.py`（USER 必须登录；不落库对话内容）
  - [x] 61.2 实现第三方 AI Provider 调用（中转模式）
    - 已实现：`backend/app/api/v1/ai.py`（协议固定 `OPENAI_COMPAT`：`${baseUrl}/v1/chat/completions`）
  - [x] 61.3 实现超时、重试与基础限流
    - 已实现：`backend/app/api/v1/ai.py`（timeout/retries/rateLimitPerMinute 由 `AI_CONFIG` 控制；按 userId 分钟桶限流）
  - [x] 61.4 实现调用元数据审计记录（不存储对话内容）
    - 已实现：`backend/app/api/v1/ai.py`（写入 `audit_logs`：resourceType=`AI_CHAT`，仅元数据）
    - 说明：`backend/app/middleware/audit_log.py` 已对 `/api/v1/ai/chat` 做跳过，避免重复审计
  - **规格补充（已确认，v1 最小可执行）**：
    - `design.md` 已给出“能力要求/配置项/审计字段示例”，但缺少明确 API 契约与 Provider 协议口径。为保证阶段11可实现/可验收，建议补齐如下最小契约：
    - **AI 配置存储承载（实现细节）**
      - `SystemConfig.key = "AI_CONFIG"`
      - `SystemConfig.valueJson`（v1）：
        - `enabled: boolean`
        - `provider: "OPENAI_COMPAT"`（v1 仅支持一种中转协议）
        - `baseUrl: string`（示例：`https://api.openai.com` 或兼容网关地址）
        - `apiKey: string`（仅后端保存；读接口不返回明文）
        - `model: string`
        - `systemPrompt?: string`
        - `temperature?: number`（默认 0.7）
        - `maxTokens?: number`（默认 1024）
        - `timeoutMs?: number`（默认 15000）
        - `retries?: number`（默认 1；仅对网络/5xx 重试）
        - `rateLimitPerMinute?: number`（默认 30；按 userId 维度）
        - `version: string`（发布/变更版本号，用于审计记录 `configVersion`）
    - **对话接口**
      - `POST /api/v1/ai/chat`
        - **Auth**：USER（必须登录；小程序端使用）
        - **Request（v1）**：
          - `{ messages: Array<{ role: "user"|"assistant"|"system", content: string }>, temperature?: number, maxTokens?: number }`
          - 约束：`messages` 不落库；后端仅用于本次中转请求。
        - **Response（v1）**：
          - `{ message: { role: "assistant", content: string }, provider: string, model: string }`
        - **Errors（v1）**：
          - `UNAUTHENTICATED`（401）：未登录
          - `FORBIDDEN`（403）：AI 已停用或配置缺失（不新增错误码）
          - `RATE_LIMITED`（429）：触发频控
          - `INTERNAL_ERROR`（500）：Provider 调用失败（不暴露敏感信息）
    - **Provider 中转协议（v1）**
      - `provider="OPENAI_COMPAT"`：向 `${baseUrl}/v1/chat/completions` 发起请求
      - 请求体：`{ model, messages, temperature, max_tokens }`；Header：`Authorization: Bearer ${apiKey}`
      - 响应解析：取 `choices[0].message.content` 作为 assistant 输出
  - _需求: AI 对话能力_

- [x] 62. 实现 Admin AI 配置中心
  - [x] 62.1 实现 GET /api/v1/admin/ai/config 配置查询接口
    - 已实现：`backend/app/api/v1/admin_ai.py`（不返回 apiKey 明文；返回 apiKeyMasked）
  - [x] 62.2 实现 PUT /api/v1/admin/ai/config 配置更新接口
    - 已实现：`backend/app/api/v1/admin_ai.py`（apiKey 为空则保持原值；更新后写入 version）
  - [x] 62.3 实现 GET /api/v1/admin/ai/audit-logs AI 审计日志接口
    - 已实现：`backend/app/api/v1/admin_ai.py`（从 `audit_logs` 过滤 resourceType=`AI_CHAT`；支持 userId/resultStatus/provider/model/dateFrom/dateTo + 分页）
  - **规格补充（已确认，v1 最小可执行）**：
    - `GET /api/v1/admin/ai/config`
      - **Auth**：ADMIN
      - **Response（v1）**：`{ enabled, provider, baseUrl, model, systemPrompt?, temperature?, maxTokens?, timeoutMs?, retries?, rateLimitPerMinute?, version, apiKeyMasked?: string }`
      - 规则：不返回 `apiKey` 明文，返回 `apiKeyMasked`（如 `sk-****abcd`）或为空
    - `PUT /api/v1/admin/ai/config`
      - **Auth**：ADMIN
      - **Request（v1）**：同 GET 的可写字段；`apiKey?` 可选（为空则保持原值）
      - 规则：更新后写入新的 `version`
    - `GET /api/v1/admin/ai/audit-logs`
      - **Auth**：ADMIN
      - **Query（v1）**：`userId?`、`resultStatus?("success"|"fail")`、`provider?`、`model?`、`dateFrom?`、`dateTo?`、`page/pageSize`
      - **Response（v1）**：`{ items: Array<{ userId: string, timestamp: Date, provider: string, model: string, latencyMs: number, resultStatus: "success"|"fail", errorCode?: string, configVersion?: string }>, page, pageSize, total }`
      - 说明：可基于 `audit_logs` 表过滤 `resourceType="AI_CHAT"` 聚合生成（不存储对话内容）
  - _需求: Admin AI 配置中心_

- [x] 63. 检查点 - 确保 AI 服务正常
  - [x] 确保所有测试通过
    - 已验证：2025-12-18 `python -m pytest backend` 通过（当前共 30 个测试用例）。

---

## 阶段 12：服务提供方后台服务

- [ ] 64. 实现服务提供方场所管理
  - [ ] 64.1 实现场所信息维护接口
  - [ ] 64.2 实现服务管理接口（基建联防商品/健行天下特供服务）
  - [ ] 64.3 实现展示资料提交与审核流程
  - _需求: 服务提供方后台原型_

- [ ] 65. 实现排期与容量管理
  - [ ] 65.1 实现排期配置接口
  - [ ] 65.2 实现容量调整接口
  - _需求: 排期容量管理_

- [ ] 66. 实现服务提供方预约处理
  - [ ] 66.1 实现预约列表查询（按场所过滤）
  - [ ] 66.2 实现人工确认/取消预约
  - _需求: 服务提供方预约管理_

- [ ] 67. 实现核销功能
  - [ ] 67.1 实现扫码核销功能
  - [ ] 67.2 实现券码输入核销功能
  - [ ] 67.3 实现核销记录查询
  - _需求: 服务提供方核销功能_

- [ ] 68. 检查点 - 确保服务提供方后台正常
  - 确保所有测试通过，如有问题请询问用户。

---

## 阶段 13：前端 - 企业官网

- [ ] 69. 搭建企业官网项目
  - [ ] 69.1 初始化 Vue 3 + Naive UI 项目
  - [ ] 69.2 配置路由与布局组件
  - [ ] 69.3 实现响应式设计基础
  - _需求: 企业官网技术栈_

- [ ] 70. 实现官网页面
  - [ ] 70.1 实现首页（品牌展示、业务线介绍）
  - [ ] 70.2 实现新闻/公告列表与详情页
  - [ ] 70.3 实现服务介绍页
  - [ ] 70.4 实现 SEO 优化配置
  - _需求: 企业官网原型_

---

## 阶段 14：前端 - 管理后台系统

- [ ] 71. 搭建管理后台项目
  - [ ] 71.1 初始化 Vue 3 + Element Plus 项目
  - [ ] 71.2 配置路由、权限与布局组件
  - [ ] 71.3 实现登录与 2FA 验证页面
  - _需求: 管理后台技术栈_

- [ ] 72. 实现平台运营后台（Admin）
  - [ ] 72.1 实现仪表盘页面
  - [ ] 72.2 实现用户与企业绑定管理页面
  - [ ] 72.3 实现商品审核与监管页面
  - [ ] 72.4 实现订单监管页面
  - [ ] 72.5 实现售后仲裁页面
  - [ ] 72.6 实现权益与核销管理页面
  - [ ] 72.7 实现预约管理页面
  - [ ] 72.8 实现 CMS 内容管理页面
  - [ ] 72.9 实现小程序配置中心页面
  - [ ] 72.10 实现 AI 配置中心页面
  - [ ] 72.11 实现审计日志页面
  - _需求: Admin 后台原型_

- [ ] 73. 实现经销商后台（Dealer）
  - [ ] 73.1 实现仪表盘页面
  - [ ] 73.2 实现链接/参数管理页面
  - [ ] 73.3 实现订单归属页面
  - [ ] 73.4 实现结算记录页面
  - _需求: 经销商后台原型_

- [ ] 74. 实现服务提供方后台（Provider）
  - [ ] 74.1 实现工作台页面
  - [ ] 74.2 实现场所信息管理页面
  - [ ] 74.3 实现服务管理页面
  - [ ] 74.4 实现排期/容量管理页面
  - [ ] 74.5 实现预约管理页面
  - [ ] 74.6 实现核销页面
  - [ ] 74.7 实现核销记录页面
  - _需求: 服务提供方后台原型_

---

## 阶段 15：前端 - H5 端

- [ ] 75. 搭建 H5 项目
  - [ ] 75.1 初始化 Vue 3 + Vant 4 项目
  - [ ] 75.2 配置移动端适配
  - _需求: H5 端技术栈_

- [ ] 76. 实现 H5 页面
  - [ ] 76.1 实现营销落地页
  - [ ] 76.2 实现购买页（手机号验证、下单确认）
  - [ ] 76.3 实现支付结果页（成功/失败）
  - [ ] 76.4 实现经销商参数解析与展示
  - [ ]* 76.5 编写属性测试：服务包展示格式一致性
    - **Property 6: 服务包展示格式一致性**
    - **Validates: 属性 6**
  - _需求: H5 端原型_

---

## 阶段 16：前端 - 小程序端

- [ ] 77. 搭建小程序项目
  - [ ] 77.1 初始化微信小程序原生项目
  - [ ] 77.2 配置全局导航与 TabBar
  - _需求: 小程序端技术栈_

- [ ] 78. 实现小程序首页
  - [ ] 78.1 实现首页布局（Banner、快捷入口、推荐）
  - [ ] 78.2 实现 AI 旋钮入口
  - [ ] 78.3 实现可配置入口跳转
  - _需求: 小程序首页原型_

- [ ] 79. 实现聚合页与信息页
  - [ ] 79.1 实现聚合页（侧边栏、地区维度筛选）
  - [ ] 79.2 实现信息页（区块渲染）
  - _需求: 可配置页面原型_

- [ ] 80. 实现商城模块
  - [ ] 80.1 实现商品列表页
  - [ ] 80.2 实现商品详情页（价格优先级展示）
  - [ ] 80.3 实现购物车页
  - [ ] 80.4 实现下单与支付流程
  - _需求: 商城模块原型_

- [ ] 81. 实现权益模块
  - [ ] 81.1 实现权益列表页
  - [ ] 81.2 实现权益详情页（二维码/券码展示）
  - [ ] 81.3 实现适用场所筛选
  - _需求: 权益模块原型_

- [ ] 82. 实现预约模块
  - [ ] 82.1 实现场所选择页
  - [ ] 82.2 实现日期/时段选择页
  - [ ] 82.3 实现预约结果页
  - [ ] 82.4 实现预约列表与取消功能
  - _需求: 预约模块原型_

- [ ] 83. 实现订单模块
  - [ ] 83.1 实现订单列表页
  - [ ] 83.2 实现订单详情页
  - _需求: 订单模块原型_

- [ ] 84. 实现我的模块
  - [ ] 84.1 实现个人中心页（身份展示）
  - [ ] 84.2 实现企业绑定页
  - _需求: 我的模块原型_

- [ ] 85. 实现 AI 对话页
  - [ ] 85.1 实现对话界面
  - [ ] 85.2 实现登录校验
  - [ ] 85.3 实现免责声明展示
  - _需求: AI 对话页原型_

- [ ] 86. 实现场所详情页
  - [ ] 86.1 实现场所信息展示
  - [ ] 86.2 实现服务列表与跳转
  - _需求: 场所详情原型_

---

## 阶段 17：集成测试与部署

- [ ] 87. 实现端到端集成测试
  - [ ] 87.1 编写基建联防购买流程集成测试
  - [ ] 87.2 编写健行天下购买→权益使用→核销流程集成测试
  - [ ] 87.3 编写职健行动企业绑定流程集成测试
  - [ ]* 87.4 编写属性测试：权益激活不可逆性
    - **Property 23: 权益激活不可逆性**
    - **Validates: 属性 23**
  - _需求: 测试策略_

- [ ] 88. 配置 CI/CD 流水线
  - [ ] 88.1 配置自动化测试流水线
  - [ ] 88.2 配置代码质量检查（Black/Flake8/ESLint）
  - [ ] 88.3 配置类型检查（mypy/TypeScript）
  - _需求: 开发工具链_

- [ ] 89. 配置生产环境部署
  - [ ] 89.1 配置 Docker 镜像构建
  - [ ] 89.2 配置 Nginx 反向代理
  - [ ] 89.3 配置数据库备份策略
  - [ ] 89.4 配置监控告警（预留 Prometheus + Grafana）
  - _需求: 部署和运维_

- [ ] 90. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

---

## 正确性属性测试覆盖清单

以下是设计文档中定义的 23 个正确性属性与对应任务的映射：

| 属性编号 | 属性名称 | 对应任务 |
|---------|---------|---------|
| 属性 1 | 购物车和订单管理一致性 | 24.4 |
| 属性 2 | 虚拟服务券生成完整性 | 28.4 |
| 属性 3 | 履约流程启动正确性 | 25.4 |
| 属性 4 | 未核销退款规则 | 48.4 |
| 属性 5 | 经销商参数解析和防篡改 | 10.5 |
| 属性 6 | 服务包展示格式一致性 | 76.5 |
| 属性 7 | 服务包权益生成可见性 | 16.4 |
| 属性 8 | 服务包退款和转赠条件 | 32.4 |
| 属性 9 | 企业名称智能匹配 | 19.4 |
| 属性 10 | 企业绑定唯一性 | 5.4 |
| 属性 11 | 企业信息持久化 | 19.5 |
| 属性 12 | 价格优先级计算一致性 | 6.5 |
| 属性 13 | 权益类型和适用范围匹配 | 33.3 |
| 属性 14 | 权益使用场所过滤正确性 | 35.4 |
| 属性 15 | 核销成功才扣次数 | 31.5 |
| 属性 16 | 预约与核销关联性 | 31.6 |
| 属性 17 | 预约确认机制正确性 | 37.5 |
| 属性 18 | 预约取消时间窗口 | 9.5 |
| 属性 19 | 预约取消状态恢复 | 39.4 |
| 属性 20 | 统一订单模型一致性 | 7.6 |
| 属性 21 | 权益生成双形态完整性 | 8.6 |
| 属性 22 | 权益归属者唯一性 | 8.5 |
| 属性 23 | 权益激活不可逆性 | 87.4 |
