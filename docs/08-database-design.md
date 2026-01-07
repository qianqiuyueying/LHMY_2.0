# 数据库设计文档

> **说明**：这个文档介绍项目的数据库设计，包括表结构、索引设计和数据迁移方法。

## 1. 数据库概述

### 1.1 技术栈

- **数据库**：MySQL（推荐 8.0+）
- **ORM**：SQLAlchemy（异步）
- **迁移工具**：Alembic
- **连接池**：SQLAlchemy async engine

### 1.2 命名规范

- **表名**：小写，复数形式（如 `users`、`orders`）
- **字段名**：小写，下划线分隔（如 `user_id`、`created_at`）
- **主键**：统一使用 UUID（36 字符）
- **外键**：`{表名}_id`（如 `user_id`、`order_id`）
- **时间字段**：`created_at`、`updated_at`、`{动作}_at`（如 `paid_at`）

### 1.3 数据类型约定

- **ID**：`VARCHAR(36)`（UUID）
- **字符串**：根据实际长度选择 `VARCHAR(n)`
- **文本**：`TEXT`（长文本）
- **JSON**：`JSON`（MySQL 5.7+）
- **时间**：`DATETIME`
- **日期**：`DATE`
- **数值**：`DECIMAL`（金额）、`INT`（整数）、`FLOAT`（浮点数）

## 2. ER 图（实体关系图）

### 2.1 核心实体关系

```
用户 (User)
  ├── 用户地址 (UserAddress)
  ├── 企业绑定 (UserEnterpriseBinding)
  ├── 购物车 (Cart)
  │   └── 购物车项 (CartItem)
  └── 订单 (Order)
      ├── 订单明细 (OrderItem)
      ├── 支付 (Payment)
      ├── 退款 (Refund)
      ├── 售后单 (AfterSaleCase)
      └── 权益 (Entitlement)
          ├── 权益转赠 (EntitlementTransfer)
          └── 核销记录 (RedemptionRecord)
              └── 预约 (Booking)

商品 (Product)
  ├── 商品分类 (ProductCategory)
  └── 服务包 (ServicePackage)
      ├── 服务包服务 (PackageService)
      └── 服务包实例 (ServicePackageInstance)

可售卡 (SellableCard)
  └── 经销商链接 (DealerLink)

服务分类 (ServiceCategory)

场所 (Venue)
  ├── 场所服务 (VenueService)
  └── 场所排期 (VenueSchedule)

服务提供方 (Provider)
  ├── 服务提供方用户 (ProviderUser)
  ├── 服务提供方员工 (ProviderStaff)
  ├── 场所 (Venue)
  └── 商品 (Product)

经销商 (Dealer)
  ├── 经销商用户 (DealerUser)
  ├── 经销商层级 (DealerHierarchy)
  ├── 经销商链接 (DealerLink)
  ├── 经销商结算账户 (DealerSettlementAccount)
  └── 结算记录 (SettlementRecord)

企业 (Enterprise)
  └── 用户企业绑定 (UserEnterpriseBinding)

管理员 (Admin)
  ├── 审计日志 (AuditLog)
  └── 通知 (Notification)

CMS 栏目 (CmsChannel)
  └── CMS 内容 (CmsContent)

法律协议 (LegalAgreement)

系统配置 (SystemConfig)

资产 (Asset)

分类节点 (TaxonomyNode)
```

### 2.2 主要关系说明

**用户相关**：
- `User` → `Order`（一对多）
- `User` → `Entitlement`（一对多）
- `User` → `Booking`（一对多）
- `User` → `UserAddress`（一对多）
- `User` → `UserEnterpriseBinding`（一对多）
- `User` → `Cart`（一对一）
- `User` → `AfterSaleCase`（一对多）
- `User` → `Notification`（一对多）

**订单相关**：
- `Order` → `OrderItem`（一对多）
- `Order` → `Payment`（一对多）
- `Order` → `Entitlement`（一对多）
- `Order` → `Refund`（一对多）
- `Order` → `AfterSaleCase`（一对多）
- `Order` → `ServicePackageInstance`（一对多）

**权益相关**：
- `Entitlement` → `Booking`（一对多）
- `Entitlement` → `RedemptionRecord`（一对多）
- `Entitlement` → `EntitlementTransfer`（一对多）

**购物车相关**：
- `Cart` → `CartItem`（一对多）

**服务包相关**：
- `ServicePackage` → `PackageService`（一对多）
- `ServicePackage` → `ServicePackageInstance`（一对多）
- `ServicePackage` → `SellableCard`（一对多）

**商品相关**：
- `Product` → `ProductCategory`（多对一）
- `Product` → `OrderItem`（一对多）
- `Product` → `Booking`（一对多）

**可售卡相关**：
- `SellableCard` → `DealerLink`（一对多）

**场所相关**：
- `Venue` → `VenueService`（一对多）
- `Venue` → `VenueSchedule`（一对多）
- `Venue` → `Booking`（一对多）
- `Venue` → `RedemptionRecord`（一对多）

**服务提供方相关**：
- `Provider` → `ProviderUser`（一对多）
- `Provider` → `ProviderStaff`（一对多）
- `Provider` → `Venue`（一对多）
- `Provider` → `Product`（一对多）

**经销商相关**：
- `Dealer` → `DealerUser`（一对多）
- `Dealer` → `DealerLink`（一对多）
- `Dealer` → `SettlementRecord`（一对多）
- `Dealer` → `DealerSettlementAccount`（一对一）
- `Dealer` → `DealerHierarchy`（一对多，作为祖先或后代）

**企业相关**：
- `Enterprise` → `UserEnterpriseBinding`（一对多）

**管理相关**：
- `Admin` → `AuditLog`（一对多）
- `Admin` → `Notification`（一对多，作为发送者）

**CMS 相关**：
- `CmsChannel` → `CmsContent`（一对多）

## 3. 核心表结构说明

### 3.1 用户相关表

#### users（用户表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 用户ID（主键） | PK |
| `phone` | VARCHAR(20) | 手机号 | ✓ |
| `openid` | VARCHAR(64) | 微信 openid | ✓ |
| `unionid` | VARCHAR(64) | 微信 unionid | ✓ |
| `nickname` | VARCHAR(64) | 昵称 | |
| `avatar` | VARCHAR(512) | 头像URL | |
| `identities` | JSON | 身份数组（MEMBER/EMPLOYEE） | |
| `enterprise_id` | VARCHAR(36) | 企业ID | |
| `enterprise_name` | VARCHAR(128) | 企业名称（冗余） | |
| `binding_time` | DATETIME | 绑定生效时间 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：
- `phone`、`openid`、`unionid` 允许为空（跨端登录）
- `identities` 可叠加（MEMBER/EMPLOYEE）

#### user_addresses（用户地址表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 地址ID（主键） | PK |
| `user_id` | VARCHAR(36) | 用户ID | ✓ |
| `receiver_name` | VARCHAR(64) | 收货人姓名 | |
| `receiver_phone` | VARCHAR(20) | 收货人手机号 | |
| `country_code` | VARCHAR(32) | 国家编码 | |
| `province_code` | VARCHAR(32) | 省编码 | |
| `city_code` | VARCHAR(32) | 市编码 | |
| `district_code` | VARCHAR(32) | 区编码 | |
| `address` | VARCHAR(512) | 详细地址 | |
| `is_default` | BOOLEAN | 是否默认地址 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.2 订单相关表

#### orders（订单表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 订单ID（主键） | PK |
| `user_id` | VARCHAR(36) | 用户ID | ✓ |
| `order_type` | VARCHAR(32) | 订单类型（PRODUCT/SERVICE_PACKAGE） | |
| `total_amount` | DECIMAL | 订单总金额 | |
| `payment_method` | VARCHAR(32) | 支付方式 | |
| `payment_status` | VARCHAR(16) | 支付状态 | |
| `dealer_id` | VARCHAR(36) | 经销商ID | ✓ |
| `dealer_link_id` | VARCHAR(36) | 经销商链接ID | ✓ |
| `fulfillment_type` | VARCHAR(32) | 履约类型 | |
| `fulfillment_status` | VARCHAR(32) | 履约状态 | |
| `goods_amount` | DECIMAL | 商品金额 | |
| `shipping_amount` | DECIMAL | 运费金额 | |
| `shipping_address_json` | JSON | 收货地址快照 | |
| `shipping_carrier` | VARCHAR(64) | 快递公司 | |
| `shipping_tracking_no` | VARCHAR(64) | 运单号 | |
| `shipped_at` | DATETIME | 发货时间 | |
| `delivered_at` | DATETIME | 妥投时间 | |
| `received_at` | DATETIME | 确认收货时间 | |
| `created_at` | DATETIME | 创建时间 | |
| `paid_at` | DATETIME | 支付时间 | |
| `confirmed_at` | DATETIME | 银行转账确认时间 | |

**说明**：
- `order_type`：PRODUCT（商品订单）、SERVICE_PACKAGE（服务包订单）
- `payment_status`：PENDING（待支付）、PAID（已支付）、FAILED（支付失败）、REFUNDED（已退款）

#### order_items（订单明细表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 明细ID（主键） | PK |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `item_type` | VARCHAR(32) | 明细类型 | |
| `item_id` | VARCHAR(36) | 业务对象ID | ✓ |
| `quantity` | INT | 数量 | |
| `unit_price` | DECIMAL | 单价 | |
| `total_price` | DECIMAL | 总价 | |
| `tier` | VARCHAR(64) | 等级/阶梯 | |
| `created_at` | DATETIME | 创建时间 | |

**说明**：
- `item_type`：PRODUCT（商品）、SERVICE_PACKAGE（服务包）
- `item_id`：对应商品ID或服务包ID

#### payments（支付表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 支付ID（主键） | PK |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `payment_method` | VARCHAR(32) | 支付方式 | |
| `amount` | DECIMAL | 支付金额 | |
| `status` | VARCHAR(16) | 支付状态 | |
| `third_party_trade_no` | VARCHAR(128) | 第三方交易号 | |
| `paid_at` | DATETIME | 支付时间 | |
| `created_at` | DATETIME | 创建时间 | |

### 3.3 权益相关表

#### entitlements（权益表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 权益ID（主键） | PK |
| `user_id` | VARCHAR(36) | 用户ID（与 ownerId 一致） | ✓ |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `entitlement_type` | VARCHAR(32) | 权益类型 | |
| `service_type` | VARCHAR(64) | 服务类目标识 | |
| `remaining_count` | INT | 剩余次数 | |
| `total_count` | INT | 总次数 | |
| `valid_from` | DATETIME | 生效时间 | |
| `valid_until` | DATETIME | 到期时间 | |
| `applicable_venues` | JSON | 适用场所 | |
| `applicable_regions` | JSON | 适用区域 | |
| `qr_code` | VARCHAR(2048) | 二维码payload | |
| `voucher_code` | VARCHAR(128) | 券码 | |
| `status` | VARCHAR(16) | 状态 | |
| `service_package_instance_id` | VARCHAR(36) | 服务包实例ID | ✓ |
| `owner_id` | VARCHAR(36) | 当前持有者（唯一裁决字段） | ✓ |
| `activator_id` | VARCHAR(36) | 激活者 | |
| `current_user_id` | VARCHAR(36) | 当前使用者 | |
| `created_at` | DATETIME | 创建时间 | |

**说明**：
- `owner_id` 为唯一裁决字段（属性22）
- `status`：ACTIVE（激活）、USED（已使用）、EXPIRED（已过期）、TRANSFERRED（已转赠）、REFUNDED（已退款）

#### entitlement_transfers（权益转赠表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 转赠ID（主键） | PK |
| `entitlement_id` | VARCHAR(36) | 权益ID | ✓ |
| `transfer_type` | VARCHAR(32) | 转赠类型 | |
| `from_owner_id` | VARCHAR(36) | 转出方 ownerId | ✓ |
| `to_owner_id` | VARCHAR(36) | 转入方 ownerId | ✓ |
| `created_at` | DATETIME | 创建时间 | |

### 3.4 预约相关表

#### bookings（预约表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 预约ID（主键） | PK |
| `source_type` | VARCHAR(16) | 来源类型 | |
| `entitlement_id` | VARCHAR(36) | 权益ID | ✓ |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `order_item_id` | VARCHAR(36) | 订单明细ID | ✓ |
| `product_id` | VARCHAR(36) | 商品ID | ✓ |
| `user_id` | VARCHAR(36) | 用户ID | ✓ |
| `venue_id` | VARCHAR(36) | 场所ID | ✓ |
| `service_type` | VARCHAR(64) | 服务类目标识 | |
| `booking_date` | DATE | 预约日期 | ✓ |
| `time_slot` | VARCHAR(16) | 时段（HH:mm-HH:mm） | |
| `status` | VARCHAR(16) | 状态 | |
| `confirmation_method` | VARCHAR(16) | 确认方式 | |
| `confirmed_at` | DATETIME | 确认时间 | |
| `cancelled_at` | DATETIME | 取消时间 | |
| `created_at` | DATETIME | 创建时间 | |

**说明**：
- `source_type`：ENTITLEMENT（权益预约）、ORDER_ITEM（订单项预约）
- `status`：PENDING（待确认）、CONFIRMED（已确认）、CANCELLED（已取消）、COMPLETED（已完成）

#### redemption_records（核销记录表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 核销ID（主键） | PK |
| `entitlement_id` | VARCHAR(36) | 权益ID | ✓ |
| `booking_id` | VARCHAR(36) | 预约ID | ✓ |
| `redemption_method` | VARCHAR(32) | 核销方式 | |
| `user_id` | VARCHAR(36) | 用户ID | ✓ |
| `venue_id` | VARCHAR(36) | 场所ID | ✓ |
| `created_at` | DATETIME | 创建时间 | |

### 3.5 商品相关表

#### products（商品表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 商品ID（主键） | PK |
| `provider_id` | VARCHAR(36) | 服务提供方ID | ✓ |
| `title` | VARCHAR(256) | 标题 | |
| `fulfillment_type` | VARCHAR(32) | 履约类型 | |
| `category_id` | VARCHAR(36) | 分类ID | ✓ |
| `cover_image_url` | VARCHAR(512) | 封面图 | |
| `image_urls` | JSON | 图片列表 | |
| `description` | TEXT | 描述 | |
| `price` | JSON | 价格对象 | |
| `stock` | INT | 库存（总） | |
| `reserved_stock` | INT | 已预留库存 | |
| `weight` | FLOAT | 重量 | |
| `shipping_fee` | DECIMAL | 固定运费 | |
| `tags` | JSON | 标签 | |
| `status` | VARCHAR(32) | 状态 | |
| `reject_reason` | VARCHAR(512) | 驳回原因 | |
| `rejected_at` | DATETIME | 驳回时间 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：
- `fulfillment_type`：SERVICE（到店服务）、PHYSICAL_GOODS（物流商品）
- `status`：PENDING_REVIEW（待审核）、ON_SALE（在售）、OFF_SHELF（下架）、REJECTED（已驳回）

#### service_packages（服务包表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 服务包ID（主键） | PK |
| `title` | VARCHAR(256) | 标题 | |
| `description` | TEXT | 描述 | |
| `cover_image_url` | VARCHAR(512) | 封面图 | |
| `image_urls` | JSON | 图片列表 | |
| `service_type` | VARCHAR(64) | 服务类目标识 | |
| `price` | JSON | 价格对象 | |
| `valid_days` | INT | 有效期（天） | |
| `total_count` | INT | 总次数 | |
| `status` | VARCHAR(32) | 状态 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.6 场所相关表

#### venues（场所表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 场所ID（主键） | PK |
| `provider_id` | VARCHAR(36) | 服务提供方ID | ✓ |
| `name` | VARCHAR(256) | 场所名称 | |
| `logo_url` | VARCHAR(512) | LOGO | |
| `cover_image_url` | VARCHAR(512) | 封面图 | |
| `image_urls` | JSON | 图片列表 | |
| `description` | TEXT | 简介 | |
| `country_code` | VARCHAR(32) | 国家编码 | ✓ |
| `province_code` | VARCHAR(32) | 省编码 | ✓ |
| `city_code` | VARCHAR(32) | 市编码 | ✓ |
| `address` | VARCHAR(512) | 地址 | |
| `lat` | FLOAT | 纬度 | |
| `lng` | FLOAT | 经度 | |
| `contact_phone` | VARCHAR(64) | 联系电话 | |
| `business_hours` | JSON | 营业时间 | |
| `publish_status` | VARCHAR(32) | 发布状态 | |
| `review_status` | VARCHAR(32) | 审核状态 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：
- `publish_status`：DRAFT（草稿）、PUBLISHED（已发布）、OFFLINE（已下架）
- `review_status`：PENDING（待审核）、APPROVED（已通过）、REJECTED（已驳回）

#### venue_services（场所服务表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 服务ID（主键） | PK |
| `venue_id` | VARCHAR(36) | 场所ID | ✓ |
| `service_type` | VARCHAR(64) | 服务类目标识 | ✓ |
| `name` | VARCHAR(256) | 服务名称 | |
| `description` | TEXT | 描述 | |
| `product_id` | VARCHAR(36) | 关联商品ID | ✓ |
| `is_enabled` | BOOLEAN | 是否启用 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### venue_schedules（场所排期表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 排期ID（主键） | PK |
| `venue_id` | VARCHAR(36) | 场所ID | ✓ |
| `service_type` | VARCHAR(64) | 服务类目标识 | ✓ |
| `booking_date` | DATE | 预约日期 | ✓ |
| `time_slot` | VARCHAR(16) | 时段 | |
| `capacity` | INT | 容量 | |
| `reserved_count` | INT | 已预约数量 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.7 管理相关表

#### admins（管理员表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 管理员ID（主键） | PK |
| `username` | VARCHAR(64) | 登录用户名 | ✓ (unique) |
| `password_hash` | VARCHAR(255) | 密码哈希 | |
| `phone` | VARCHAR(20) | 手机号 | |
| `status` | VARCHAR(16) | 状态 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### audit_logs（审计日志表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 审计ID（主键） | PK |
| `actor_type` | VARCHAR(32) | 操作者类型 | |
| `actor_id` | VARCHAR(36) | 操作者ID | ✓ |
| `action` | VARCHAR(32) | 动作 | |
| `resource_type` | VARCHAR(64) | 资源类型 | ✓ |
| `resource_id` | VARCHAR(128) | 资源ID | ✓ |
| `summary` | VARCHAR(512) | 摘要 | |
| `ip` | VARCHAR(64) | IP | |
| `user_agent` | VARCHAR(512) | UserAgent | |
| `metadata` | JSON | 元数据 | |
| `created_at` | DATETIME | 创建时间 | |

**说明**：
- 记录所有重要操作的审计日志
- `resource_id` 长度 128（可能不是 UUID）

### 3.8 其他重要表

#### dealers（经销商表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 经销商ID（主键） | PK |
| `name` | VARCHAR(256) | 经销商名称 | |
| `parent_dealer_id` | VARCHAR(36) | 上级经销商ID | ✓ |
| `status` | VARCHAR(16) | 状态 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### providers（服务提供方表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 服务提供方ID（主键） | PK |
| `name` | VARCHAR(256) | 服务提供方名称 | |
| `status` | VARCHAR(16) | 状态 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### dealer_links（经销商链接表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 链接ID（主键） | PK |
| `dealer_id` | VARCHAR(36) | 归属经销商ID | ✓ |
| `product_id` | VARCHAR(36) | 高端服务卡商品ID（可为空） | ✓ |
| `sellable_card_id` | VARCHAR(36) | 可售卡ID（可为空） | ✓ |
| `campaign` | VARCHAR(128) | 活动/批次 | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED/EXPIRED） | |
| `valid_from` | DATETIME | 生效时间 | |
| `valid_until` | DATETIME | 到期时间 | |
| `url` | VARCHAR(2048) | 投放URL | |
| `uv` | INT | 访问UV | |
| `paid_count` | INT | 支付数 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.9 退款相关表

#### refunds（退款表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 退款ID（主键） | PK |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `amount` | DECIMAL | 退款金额 | |
| `status` | VARCHAR(16) | 状态（REQUESTED/APPROVED/REJECTED/PROCESSING/SUCCESS/FAILED） | |
| `reason` | VARCHAR(512) | 原因 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.10 购物车相关表

#### carts（购物车表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 购物车ID（主键） | PK |
| `user_id` | VARCHAR(36) | 用户ID（唯一） | ✓ (unique) |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：每个用户只有一个购物车。

#### cart_items（购物车项表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 购物车项ID（主键） | PK |
| `cart_id` | VARCHAR(36) | 购物车ID | ✓ |
| `item_type` | VARCHAR(32) | 类型（PRODUCT/SERVICE_PACKAGE） | |
| `item_id` | VARCHAR(36) | 商品/服务包等业务对象ID | |
| `quantity` | INT | 数量 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：唯一约束 `(cart_id, item_type, item_id)`，避免同商品重复行。

### 3.11 服务包相关表

#### service_package_instances（服务包实例表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 卡实例ID（主键） | PK |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `order_item_id` | VARCHAR(36) | 订单明细ID | ✓ |
| `service_package_template_id` | VARCHAR(36) | 服务包模板ID | ✓ |
| `owner_id` | VARCHAR(36) | 当前持有者（裁决字段一致） | ✓ |
| `region_scope` | VARCHAR(32) | 区域范围 | |
| `tier` | VARCHAR(64) | 等级/阶梯 | |
| `valid_from` | DATETIME | 生效时间 | |
| `valid_until` | DATETIME | 到期时间 | |
| `status` | VARCHAR(16) | 状态（ACTIVE/EXPIRED/TRANSFERRED/REFUNDED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### package_services（服务包服务表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 明细ID（主键） | PK |
| `service_package_id` | VARCHAR(36) | 服务包模板ID | ✓ |
| `service_type` | VARCHAR(64) | 服务类目标识 | |
| `total_count` | INT | 次数 | |

**说明**：服务包模板包含的服务类别×次数。

### 3.12 可售卡相关表

#### sellable_cards（可售卡表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 可售卡ID（主键） | PK |
| `name` | VARCHAR(128) | 展示名 | |
| `product_id` | VARCHAR(36) | 计价商品ID（v2.1废弃） | ✓ |
| `service_package_template_id` | VARCHAR(36) | 服务包模板ID | ✓ |
| `region_level` | VARCHAR(16) | 卡片区域级别（CITY/PROVINCE/COUNTRY） | |
| `region_scope` | VARCHAR(64) | 区域范围（v1废弃） | |
| `tier` | VARCHAR(64) | 等级覆盖（v1废弃） | |
| `price_original` | DECIMAL(10,2) | 可售卡唯一售价（v2.1） | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED） | |
| `sort` | INT | 排序（越大越靠前） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：v2.1 不再依赖计价商品，可售卡自带售价。

### 3.13 分类相关表

#### service_categories（服务分类表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 服务大类ID（主键） | PK |
| `code` | VARCHAR(64) | serviceType code（唯一） | ✓ (unique) |
| `display_name` | VARCHAR(128) | 中文展示名 | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED） | |
| `sort` | INT | 排序（越大越靠前） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### product_categories（商品分类表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 分类ID（主键） | PK |
| `name` | VARCHAR(128) | 分类名称 | |
| `parent_id` | VARCHAR(36) | 父级ID | ✓ |
| `sort` | INT | 排序 | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### taxonomy_nodes（分类节点表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 节点ID（主键） | PK |
| `type` | VARCHAR(16) | 类型（VENUE/PRODUCT/CONTENT） | |
| `name` | VARCHAR(128) | 名称 | |
| `parent_id` | VARCHAR(36) | 父级ID | ✓ |
| `sort` | INT | 排序 | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.14 企业相关表

#### enterprises（企业表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 企业ID（主键） | PK |
| `name` | VARCHAR(256) | 企业名称 | ✓ |
| `country_code` | VARCHAR(32) | 国家编码 | |
| `province_code` | VARCHAR(32) | 省编码 | |
| `city_code` | VARCHAR(32) | 市编码 | |
| `source` | VARCHAR(32) | 录入来源 | |
| `first_seen_at` | DATETIME | 首次出现时间 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### user_enterprise_bindings（用户企业绑定表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 绑定ID（主键） | PK |
| `user_id` | VARCHAR(36) | 用户ID | ✓ |
| `enterprise_id` | VARCHAR(36) | 企业ID | ✓ |
| `status` | VARCHAR(16) | 状态（PENDING/APPROVED/REJECTED） | |
| `binding_time` | DATETIME | 绑定时间（提交时间） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.15 账号管理相关表

#### dealer_users（经销商用户表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 经销商后台账号ID（主键） | PK |
| `dealer_id` | VARCHAR(36) | 经销商主体ID | ✓ |
| `username` | VARCHAR(64) | 登录用户名（唯一） | ✓ (unique) |
| `password_hash` | VARCHAR(255) | 密码哈希（bcrypt） | |
| `status` | VARCHAR(16) | 状态（ACTIVE/SUSPENDED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### provider_users（服务提供方用户表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 服务提供方后台账号ID（主键） | PK |
| `provider_id` | VARCHAR(36) | 服务提供方主体ID | ✓ |
| `username` | VARCHAR(64) | 登录用户名（唯一） | ✓ (unique) |
| `password_hash` | VARCHAR(255) | 密码哈希（bcrypt） | |
| `status` | VARCHAR(16) | 状态（ACTIVE/SUSPENDED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### provider_staff（服务提供方员工表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 服务提供方员工账号ID（主键） | PK |
| `provider_id` | VARCHAR(36) | 服务提供方主体ID | ✓ |
| `username` | VARCHAR(64) | 登录用户名（唯一） | ✓ (unique) |
| `password_hash` | VARCHAR(255) | 密码哈希（bcrypt） | |
| `status` | VARCHAR(16) | 状态（ACTIVE/SUSPENDED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### 3.16 结算相关表

#### dealer_settlement_accounts（经销商结算账户表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `dealer_id` | VARCHAR(36) | 经销商ID（主键） | PK |
| `method` | VARCHAR(16) | 打款方式（BANK/ALIPAY） | |
| `account_name` | VARCHAR(128) | 收款户名/实名 | |
| `account_no` | VARCHAR(64) | 收款账号（银行卡/支付宝账号） | |
| `bank_name` | VARCHAR(128) | 开户行（BANK） | |
| `bank_branch` | VARCHAR(128) | 支行（BANK，可选） | |
| `contact_phone` | VARCHAR(32) | 联系人电话（可选） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### settlement_records（结算记录表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 结算单号（主键） | PK |
| `dealer_id` | VARCHAR(36) | 经销商ID | ✓ |
| `cycle` | VARCHAR(32) | 结算周期标识 | ✓ |
| `order_count` | INT | 订单数 | |
| `amount` | DECIMAL | 应结算金额 | |
| `status` | VARCHAR(32) | 状态（PENDING_CONFIRM/SETTLED/FROZEN） | |
| `payout_method` | VARCHAR(16) | 打款方式快照（BANK/ALIPAY） | |
| `payout_account_json` | JSON | 打款账户快照（JSON） | |
| `payout_reference` | VARCHAR(128) | 打款流水号/参考号 | |
| `payout_note` | VARCHAR(512) | 打款备注 | |
| `payout_marked_by` | VARCHAR(36) | 标记打款的管理员ID | |
| `payout_marked_at` | DATETIME | 标记打款时间 | |
| `created_at` | DATETIME | 创建时间 | |
| `settled_at` | DATETIME | 结算完成时间 | |

#### dealer_hierarchies（经销商层级表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 关系ID（主键） | PK |
| `ancestor_dealer_id` | VARCHAR(36) | 祖先经销商ID | ✓ |
| `descendant_dealer_id` | VARCHAR(36) | 后代经销商ID | ✓ |
| `depth` | INT | 深度（ancestor==descendant 为 0；直接下级为 1） | |
| `created_at` | DATETIME | 创建时间 | |

**说明**：闭包表结构，用于存储经销商层级关系。

### 3.17 通知相关表

#### notifications（通知表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 通知ID（主键） | PK |
| `sender_type` | VARCHAR(32) | 发送者类型（v1：手工发送固定 ADMIN） | |
| `sender_id` | VARCHAR(36) | 发送者ID（adminId，可空） | |
| `receiver_type` | VARCHAR(32) | 接收者类型 | |
| `receiver_id` | VARCHAR(36) | 接收者ID | ✓ |
| `title` | VARCHAR(256) | 标题 | |
| `content` | TEXT | 内容 | |
| `category` | VARCHAR(16) | 类别（SYSTEM/ACTIVITY/OPS） | |
| `meta_json` | JSON | 扩展元数据（JSON，可空） | |
| `status` | VARCHAR(16) | 状态（UNREAD/READ） | |
| `created_at` | DATETIME | 创建时间 | |
| `read_at` | DATETIME | 已读时间 | |

### 3.18 售后相关表

#### after_sale_cases（售后单表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 申请单号（主键） | PK |
| `order_id` | VARCHAR(36) | 订单ID | ✓ |
| `user_id` | VARCHAR(36) | 用户ID | ✓ |
| `type` | VARCHAR(32) | 类型（RETURN/REFUND/AFTER_SALE_SERVICE） | |
| `status` | VARCHAR(32) | 状态（SUBMITTED/UNDER_REVIEW/DECIDED/CLOSED） | |
| `amount` | DECIMAL | 金额 | |
| `reason` | VARCHAR(512) | 原因 | |
| `evidence_urls` | JSON | 举证URL列表 | |
| `decided_by` | VARCHAR(36) | 裁决人（adminId） | |
| `decision` | VARCHAR(16) | 裁决（APPROVE/REJECT） | |
| `decision_notes` | VARCHAR(1024) | 裁决备注 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：v1 不支持部分退款/部分裁决（PARTIAL），仅允许全额通过或驳回。

### 3.19 CMS 相关表

#### cms_channels（CMS 栏目表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 栏目ID（主键） | PK |
| `name` | VARCHAR(128) | 栏目名称 | |
| `sort` | INT | 排序 | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

#### cms_contents（CMS 内容表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 内容ID（主键） | PK |
| `channel_id` | VARCHAR(36) | 栏目ID（官网投放，可为空） | ✓ |
| `title` | VARCHAR(256) | 标题 | |
| `cover_image_url` | VARCHAR(512) | 封面图 | |
| `summary` | VARCHAR(512) | 摘要 | |
| `content_md` | TEXT | 正文（Markdown） | |
| `content_html` | TEXT | 正文（HTML） | |
| `status` | VARCHAR(16) | 状态（DRAFT/PUBLISHED/OFFLINE） | |
| `published_at` | DATETIME | 发布时间 | |
| `mp_status` | VARCHAR(16) | 小程序状态（DRAFT/PUBLISHED/OFFLINE） | |
| `mp_published_at` | DATETIME | 小程序发布时间 | |
| `effective_from` | DATETIME | 生效开始 | |
| `effective_until` | DATETIME | 生效结束 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：
- v3：内容中心与投放解耦，内容可先在"内容中心"创建（不挂栏目）
- v2：按渠道发布，`status/published_at` 用于官网（WEB），`mp_status/mp_published_at` 用于小程序（MINI_PROGRAM）

### 3.20 法律协议相关表

#### legal_agreements（法律协议表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 协议ID（主键） | PK |
| `code` | VARCHAR(64) | 协议唯一编码（唯一） | ✓ (unique) |
| `title` | VARCHAR(256) | 标题 | |
| `content_md` | TEXT | Markdown 内容 | |
| `content_html` | TEXT | HTML 内容 | |
| `version` | VARCHAR(32) | 版本号 | |
| `status` | VARCHAR(16) | 状态（DRAFT/PUBLISHED/OFFLINE） | |
| `published_at` | DATETIME | 发布时间 | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：v2 写侧首选 Markdown；读侧/渲染侧仍用 HTML。

### 3.21 系统配置相关表

#### system_configs（系统配置表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 配置ID（主键） | PK |
| `key` | VARCHAR(128) | 配置Key（全局唯一） | ✓ (unique) |
| `value_json` | JSON | 配置值（JSON） | |
| `description` | VARCHAR(512) | 说明 | |
| `status` | VARCHAR(16) | 状态（ENABLED/DISABLED） | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：v1 以 key/valueJson 的形式存储配置；valueJson 由使用方校验 schema。

### 3.22 资产管理相关表

#### assets（资产表）

| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| `id` | VARCHAR(36) | 资产ID（主键） | PK |
| `kind` | VARCHAR(16) | 类型（IMAGE） | ✓ |
| `sha256` | VARCHAR(64) | 内容哈希（sha256，唯一） | ✓ (unique) |
| `size_bytes` | INT | 文件大小（bytes） | |
| `mime` | VARCHAR(64) | MIME | |
| `ext` | VARCHAR(16) | 扩展名 | |
| `storage` | VARCHAR(16) | 存储（LOCAL/OSS预留） | |
| `storage_key` | TEXT | 存储 key（如 uploads/2025/12/xxx.jpg） | |
| `url` | TEXT | 对外 URL（/static/uploads/... 或 https://cdn/...） | |
| `original_filename` | VARCHAR(256) | 原文件名（可选） | |
| `created_by_actor_type` | VARCHAR(16) | 创建者类型 | |
| `created_by_actor_id` | VARCHAR(36) | 创建者ID | |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

**说明**：用于文件去重和管理，通过 sha256 唯一索引避免重复存储。

## 4. 索引设计

### 4.1 索引设计原则

1. **主键索引**：所有表都有主键，自动创建主键索引
2. **外键索引**：所有外键字段都创建索引（如 `user_id`、`order_id`）
3. **查询字段索引**：经常用于查询和筛选的字段创建索引
4. **唯一索引**：唯一约束字段创建唯一索引（如 `username`、`code`）

### 4.2 主要索引列表

#### 用户相关索引

- `users.phone`：手机号索引（用于登录查询）
- `users.openid`：微信 openid 索引（用于小程序登录）
- `users.unionid`：微信 unionid 索引（用于跨端登录）
- `user_addresses.user_id`：用户ID索引（查询用户地址）

#### 订单相关索引

- `orders.user_id`：用户ID索引（查询用户订单）
- `orders.dealer_id`：经销商ID索引（查询经销商订单）
- `orders.dealer_link_id`：经销商链接ID索引
- `order_items.order_id`：订单ID索引（查询订单明细）
- `order_items.item_id`：业务对象ID索引
- `payments.order_id`：订单ID索引（查询支付记录）

#### 权益相关索引

- `entitlements.user_id`：用户ID索引（查询用户权益）
- `entitlements.order_id`：订单ID索引（查询订单权益）
- `entitlements.owner_id`：持有者ID索引（唯一裁决字段）
- `entitlements.service_package_instance_id`：服务包实例ID索引
- `entitlement_transfers.entitlement_id`：权益ID索引
- `entitlement_transfers.from_owner_id`：转出方ID索引
- `entitlement_transfers.to_owner_id`：转入方ID索引

#### 预约相关索引

- `bookings.user_id`：用户ID索引（查询用户预约）
- `bookings.venue_id`：场所ID索引（查询场所预约）
- `bookings.entitlement_id`：权益ID索引
- `bookings.booking_date`：预约日期索引（查询某日期的预约）
- `redemption_records.entitlement_id`：权益ID索引
- `redemption_records.booking_id`：预约ID索引
- `redemption_records.user_id`：用户ID索引
- `redemption_records.venue_id`：场所ID索引

#### 商品相关索引

- `products.provider_id`：服务提供方ID索引（查询提供方商品）
- `products.category_id`：分类ID索引（查询分类商品）

#### 场所相关索引

- `venues.provider_id`：服务提供方ID索引（查询提供方场所）
- `venues.country_code`：国家编码索引（地区筛选）
- `venues.province_code`：省编码索引（地区筛选）
- `venues.city_code`：市编码索引（地区筛选）
- `venue_services.venue_id`：场所ID索引
- `venue_services.service_type`：服务类型索引
- `venue_schedules.venue_id`：场所ID索引
- `venue_schedules.service_type`：服务类型索引
- `venue_schedules.booking_date`：预约日期索引

#### 退款相关索引

- `refunds.order_id`：订单ID索引（查询订单退款记录）

#### 购物车相关索引

- `carts.user_id`：用户ID索引（唯一，每个用户一个购物车）
- `cart_items.cart_id`：购物车ID索引（查询购物车项）
- `cart_items`：唯一约束 `(cart_id, item_type, item_id)`（避免重复）

#### 服务包相关索引

- `service_package_instances.order_id`：订单ID索引
- `service_package_instances.order_item_id`：订单明细ID索引
- `service_package_instances.service_package_template_id`：服务包模板ID索引
- `service_package_instances.owner_id`：持有者ID索引
- `package_services.service_package_id`：服务包模板ID索引

#### 可售卡相关索引

- `sellable_cards.product_id`：计价商品ID索引（v2.1废弃）
- `sellable_cards.service_package_template_id`：服务包模板ID索引

#### 分类相关索引

- `service_categories.code`：服务分类编码索引（唯一）
- `product_categories.parent_id`：父级ID索引（层级查询）
- `taxonomy_nodes.parent_id`：父级ID索引（层级查询）

#### 企业相关索引

- `enterprises.name`：企业名称索引（用于搜索）
- `user_enterprise_bindings.user_id`：用户ID索引（查询用户绑定）
- `user_enterprise_bindings.enterprise_id`：企业ID索引（查询企业绑定）

#### 账号管理相关索引

- `dealer_users.dealer_id`：经销商主体ID索引
- `dealer_users.username`：用户名索引（唯一，用于登录）
- `provider_users.provider_id`：服务提供方主体ID索引
- `provider_users.username`：用户名索引（唯一，用于登录）
- `provider_staff.provider_id`：服务提供方主体ID索引
- `provider_staff.username`：用户名索引（唯一，用于登录）

#### 结算相关索引

- `settlement_records.dealer_id`：经销商ID索引（查询经销商结算记录）
- `settlement_records.cycle`：结算周期索引（查询周期结算单）
- `dealer_hierarchies.ancestor_dealer_id`：祖先经销商ID索引（层级查询）
- `dealer_hierarchies.descendant_dealer_id`：后代经销商ID索引（层级查询）

#### 通知相关索引

- `notifications.receiver_id`：接收者ID索引（查询用户通知）

#### 售后相关索引

- `after_sale_cases.order_id`：订单ID索引（查询订单售后）
- `after_sale_cases.user_id`：用户ID索引（查询用户售后）

#### CMS 相关索引

- `cms_contents.channel_id`：栏目ID索引（查询栏目内容）

#### 管理相关索引

- `admins.username`：用户名索引（唯一，用于登录）
- `audit_logs.actor_id`：操作者ID索引（查询操作记录）
- `audit_logs.resource_type`：资源类型索引
- `audit_logs.resource_id`：资源ID索引

#### 其他索引

- `dealers.parent_dealer_id`：上级经销商ID索引（层级查询）
- `dealer_links.dealer_id`：经销商ID索引
- `dealer_links.product_id`：商品ID索引
- `dealer_links.sellable_card_id`：可售卡ID索引
- `assets.sha256`：文件哈希索引（唯一，去重）
- `assets.kind`：类型索引
- `legal_agreements.code`：协议编码索引（唯一）
- `system_configs.key`：配置Key索引（唯一）

### 4.3 复合索引建议

**当前项目主要使用单列索引**，如需优化查询性能，可以考虑以下复合索引：

- `(user_id, status)`：用户订单/权益按状态查询
- `(venue_id, booking_date)`：场所预约按日期查询
- `(provider_id, status)`：服务提供方商品/场所按状态查询
- `(dealer_id, created_at)`：经销商订单按时间排序

**注意**：添加复合索引需要评估查询频率和性能收益，避免过度索引。

## 5. 数据迁移说明（Alembic）

### 5.1 Alembic 简介

**Alembic** 是 SQLAlchemy 的数据库迁移工具，用于管理数据库版本和变更。

**特点**：
- 版本控制：每次迁移都有版本号
- 可回滚：支持向前和向后迁移
- 自动生成：可以根据模型自动生成迁移脚本
- 异步支持：支持 SQLAlchemy async engine

### 5.2 配置文件

**配置文件**：`backend/alembic.ini`

**关键配置**：
```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname
```

**注意**：实际数据库 URL 在 `alembic/env.py` 中从环境变量读取。

### 5.3 常用命令

#### 初始化（首次使用）

```bash
# 如果还没有初始化，需要先初始化
cd backend
alembic init alembic
```

#### 生成迁移脚本

```bash
# 自动生成迁移脚本（推荐）
uv run alembic revision --autogenerate -m "描述信息"

# 手动创建空迁移脚本
uv run alembic revision -m "描述信息"
```

**示例**：
```bash
# 添加新表
uv run alembic revision --autogenerate -m "添加用户地址表"

# 修改字段
uv run alembic revision --autogenerate -m "订单表添加经销商字段"

# 添加索引
uv run alembic revision --autogenerate -m "用户表添加手机号索引"
```

#### 应用迁移

```bash
# 升级到最新版本
uv run alembic upgrade head

# 升级到指定版本
uv run alembic upgrade <revision_id>

# 升级一个版本
uv run alembic upgrade +1
```

#### 回滚迁移

```bash
# 回滚到上一个版本
uv run alembic downgrade -1

# 回滚到指定版本
uv run alembic downgrade <revision_id>

# 回滚所有迁移
uv run alembic downgrade base
```

#### 查看迁移历史

```bash
# 查看当前版本
uv run alembic current

# 查看迁移历史
uv run alembic history

# 查看迁移历史（详细信息）
uv run alembic history --verbose
```

### 5.4 迁移脚本结构

**迁移脚本位置**：`backend/alembic/versions/`

**文件命名**：`{revision_id}_{描述}.py`

**示例**：
```python
"""添加用户地址表

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade():
    # 升级操作
    op.create_table(
        'user_addresses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        # ... 其他字段
    )
    op.create_index('ix_user_addresses_user_id', 'user_addresses', ['user_id'])

def downgrade():
    # 回滚操作
    op.drop_index('ix_user_addresses_user_id', 'user_addresses')
    op.drop_table('user_addresses')
```

### 5.5 迁移工作流程

#### 开发新功能时

1. **修改模型**：在 `backend/app/models/` 中修改或添加模型
2. **生成迁移**：运行 `uv run alembic revision --autogenerate -m "描述"`
3. **检查迁移脚本**：查看生成的迁移脚本是否正确
4. **测试迁移**：在开发环境测试迁移
5. **提交代码**：将模型和迁移脚本一起提交

#### 部署到生产环境时

1. **备份数据库**（重要！）
2. **应用迁移**：运行 `uv run alembic upgrade head`
3. **验证**：检查数据库结构是否正确

### 5.6 注意事项

#### 1. 自动生成迁移的限制

- **不会检测**：表名、列名、索引名的重命名
- **不会检测**：某些数据类型变更
- **不会检测**：某些约束变更

**解决方法**：手动编辑迁移脚本，或手动创建迁移。

#### 2. 数据迁移

**Alembic 只管理结构变更，不管理数据迁移**。

如果需要数据迁移：
1. 在迁移脚本的 `upgrade()` 函数中添加数据迁移逻辑
2. 使用 `op.execute()` 执行 SQL
3. 或使用 SQLAlchemy 的 session 操作数据

**示例**：
```python
def upgrade():
    # 结构变更
    op.add_column('users', sa.Column('new_field', sa.String(64)))
    
    # 数据迁移
    op.execute("UPDATE users SET new_field = 'default_value' WHERE new_field IS NULL")
```

#### 3. 迁移冲突

**如果多人同时开发**：
- 可能生成相同 revision 的迁移脚本
- 需要合并迁移或调整 down_revision

**解决方法**：
1. 先拉取最新代码
2. 如果有新的迁移，先应用
3. 再生成自己的迁移

#### 4. 生产环境迁移

**生产环境迁移注意事项**：
- **必须备份**：迁移前备份数据库
- **测试迁移**：先在测试环境验证
- **评估影响**：评估迁移对业务的影响
- **准备回滚**：准备回滚方案
- **监控**：迁移后监控数据库性能

### 5.7 迁移脚本示例

#### 添加新表

```python
def upgrade():
    op.create_table(
        'user_addresses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('receiver_name', sa.String(64), nullable=False),
        sa.Column('receiver_phone', sa.String(20), nullable=False),
        sa.Column('address', sa.String(512), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_user_addresses_user_id', 'user_addresses', ['user_id'])

def downgrade():
    op.drop_index('ix_user_addresses_user_id', 'user_addresses')
    op.drop_table('user_addresses')
```

#### 添加字段

```python
def upgrade():
    op.add_column('orders', sa.Column('dealer_id', sa.String(36), nullable=True))
    op.create_index('ix_orders_dealer_id', 'orders', ['dealer_id'])

def downgrade():
    op.drop_index('ix_orders_dealer_id', 'orders')
    op.drop_column('orders', 'dealer_id')
```

#### 修改字段类型

```python
def upgrade():
    op.alter_column('users', 'phone',
                    existing_type=sa.String(11),
                    type_=sa.String(20),
                    nullable=True)

def downgrade():
    op.alter_column('users', 'phone',
                    existing_type=sa.String(20),
                    type_=sa.String(11),
                    nullable=True)
```

## 6. 数据库维护建议

### 6.1 定期维护

- **备份**：定期备份数据库（建议每天）
- **监控**：监控数据库性能和空间使用
- **优化**：定期分析慢查询，优化索引
- **清理**：清理过期数据（如审计日志）

### 6.2 性能优化

- **索引优化**：根据查询模式调整索引
- **查询优化**：避免 N+1 查询，使用 join
- **分页**：大数据量查询使用分页
- **缓存**：热点数据使用 Redis 缓存

### 6.3 安全建议

- **权限控制**：数据库用户权限最小化
- **敏感数据**：敏感字段加密存储
- **SQL 注入**：使用参数化查询（SQLAlchemy 已处理）
- **审计日志**：记录重要操作

---

**最后提醒**：
- 修改数据库结构前，先备份数据库
- 迁移脚本要经过测试再应用到生产环境
- 遇到问题可以查看 Alembic 文档：https://alembic.sqlalchemy.org/

