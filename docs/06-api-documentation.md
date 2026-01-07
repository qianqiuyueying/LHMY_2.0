# API 接口文档

> **说明**：这个文档介绍项目的 API 设计和使用方法，帮助前端开发者理解如何调用接口。

## 1. API 设计原则

### 1.1 统一前缀

**所有 API 接口统一使用 `/api/v1` 前缀**。

**示例**：
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/orders` - 获取订单列表
- `POST /api/v1/orders` - 创建订单

**为什么这样设计**：
- 方便版本管理（未来可能有 v2）
- 统一路由管理
- 便于 API 网关配置

### 1.2 统一响应格式

**所有接口返回统一的 JSON 格式**：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "requestId": "xxx"
}
```

**成功响应**：
```json
{
  "success": true,
  "data": {
    "id": "123",
    "name": "示例"
  },
  "error": null,
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**错误响应**：
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "UNAUTHENTICATED",
    "message": "未登录",
    "details": null
  },
  "requestId": "550e8400-e29b-41d4-a716-446655440000"
}
```

**字段说明**：
- `success`：布尔值，表示请求是否成功
- `data`：成功时的数据，失败时为 `null`
- `error`：失败时的错误信息，成功时为 `null`
  - `code`：错误码（字符串）
  - `message`：错误消息（用户可读）
  - `details`：错误详情（可选，用于调试）
- `requestId`：请求唯一标识（用于日志追踪）

**前端处理方式**：
```typescript
// 统一响应格式处理
if (response.success) {
  // 使用 response.data
} else {
  // 处理错误：response.error.code, response.error.message
}
```

### 1.3 错误码说明

**常见错误码**：

| 错误码 | HTTP 状态码 | 说明 | 处理建议 |
|--------|------------|------|---------|
| `UNAUTHENTICATED` | 401 | 未登录或 token 无效 | 跳转到登录页 |
| `FORBIDDEN` | 403 | 无权限 | 提示用户无权限 |
| `NOT_FOUND` | 404 | 资源不存在 | 提示资源不存在 |
| `INVALID_ARGUMENT` | 400 | 参数不合法 | 检查参数格式 |
| `STATE_CONFLICT` | 409 | 状态冲突 | 刷新后重试 |
| `RATE_LIMITED` | 429 | 请求过于频繁 | 稍后重试 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 | 联系技术支持 |

**错误码特点**：
- 使用大写字母和下划线（如 `UNAUTHENTICATED`）
- 语义明确，便于前端处理
- 与 HTTP 状态码配合使用

### 1.4 HTTP 方法使用

**标准 RESTful 风格**：

| 方法 | 用途 | 示例 |
|------|------|------|
| `GET` | 查询数据 | `GET /api/v1/orders` - 获取订单列表 |
| `POST` | 创建资源 | `POST /api/v1/orders` - 创建订单 |
| `PUT` | 完整更新 | `PUT /api/v1/orders/{id}` - 更新订单 |
| `PATCH` | 部分更新 | `PATCH /api/v1/orders/{id}` - 部分更新订单 |
| `DELETE` | 删除资源 | `DELETE /api/v1/orders/{id}` - 删除订单 |

**注意**：本项目主要使用 `GET` 和 `POST`，部分接口可能不完全遵循 RESTful。

## 2. 认证授权机制

### 2.1 JWT Token 认证

**认证方式**：使用 Bearer Token（JWT）。

**请求头格式**：
```
Authorization: Bearer <token>
```

**示例**：
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     http://localhost:8000/api/v1/orders
```

### 2.2 多角色隔离

**项目支持多种角色，每种角色使用独立的 JWT Secret**：

| 角色 | Token 类型 | 使用场景 | Secret 配置 |
|------|-----------|---------|------------|
| `USER` | 用户 token | 小程序、H5 用户 | `JWT_SECRET` |
| `ADMIN` | 管理员 token | 管理后台管理员 | `JWT_SECRET_ADMIN` |
| `DEALER` | 经销商 token | 管理后台经销商 | `JWT_SECRET_DEALER` |
| `PROVIDER` | 服务提供方 token | 管理后台服务提供方 | `JWT_SECRET_PROVIDER` |
| `PROVIDER_STAFF` | 服务提供方员工 token | 服务提供方员工 | `JWT_SECRET_PROVIDER` |

**为什么隔离**：
- 安全性：不同角色的 token 不能互相使用
- 权限控制：每个角色只能访问自己的接口
- 灵活性：可以独立管理每个角色的 token 过期时间

**Token 结构**（示例）：
```json
{
  "sub": "user_id_123",
  "actorType": "USER",
  "channel": "H5",
  "jti": "token_unique_id",
  "iat": 1234567890,
  "exp": 1234571490
}
```

**字段说明**：
- `sub`：用户 ID（subject）
- `actorType`：角色类型（USER/ADMIN/DEALER/PROVIDER/PROVIDER_STAFF）
- `channel`：渠道（H5/MP 等）
- `jti`：Token 唯一标识（用于黑名单）
- `iat`：签发时间（issued at）
- `exp`：过期时间（expiration）

### 2.3 Token 获取方式

#### 用户登录（USER）

**接口**：`POST /api/v1/auth/login`

**请求体**：
```json
{
  "channel": "H5",
  "phone": "13800138000",
  "smsCode": "1234"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "user_123",
      "phone": "13800138000"
    }
  }
}
```

#### 管理员登录（ADMIN）

**接口**：`POST /api/v1/admin-auth/login`

**请求体**：
```json
{
  "username": "admin",
  "password": "password123"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "admin": {
      "id": "admin_123",
      "username": "admin"
    }
  }
}
```

#### 经销商登录（DEALER）

**接口**：`POST /api/v1/dealer-auth/login`

#### 服务提供方登录（PROVIDER）

**接口**：`POST /api/v1/provider-auth/login`

### 2.4 Token 刷新

**部分接口支持 token 刷新**：

**接口**：`POST /api/v1/auth/refresh`

**请求头**：
```
Authorization: Bearer <old_token>
```

**响应**：
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### 2.5 Token 黑名单

**登出时，token 会被加入黑名单**：

**接口**：`POST /api/v1/auth/logout`

**说明**：
- 登出后，该 token 立即失效
- 使用 Redis 存储黑名单
- 即使 token 未过期，也无法使用

### 2.6 权限检查

**接口权限检查方式**：

1. **必须登录**：接口要求 `Authorization` 头，token 有效
2. **角色检查**：接口只允许特定角色访问（如 `ADMIN` 只能访问 `admin_*` 接口）
3. **数据范围**：根据角色自动限定数据范围（如经销商只能看到自己的数据）

**前端处理**：
- 401 错误：清除 token，跳转登录页
- 403 错误：提示用户无权限

## 3. 幂等性设计

### 3.1 什么是幂等性

**幂等性**：同一个请求执行多次，结果应该相同。

**示例**：
- 创建订单时，如果网络问题导致重复提交，应该只创建一个订单
- 支付时，如果重复点击，应该只支付一次

### 3.2 Idempotency-Key 机制

**使用方式**：在请求头中传递 `Idempotency-Key`。

**请求头格式**：
```
Idempotency-Key: <unique_key>
```

**示例**：
```bash
curl -X POST \
     -H "Authorization: Bearer <token>" \
     -H "Idempotency-Key: order-2024-01-01-001" \
     -H "Content-Type: application/json" \
     -d '{"items": [...]}' \
     http://localhost:8000/api/v1/orders
```

### 3.3 工作原理

1. **首次请求**：
   - 客户端生成唯一的 `Idempotency-Key`（如 UUID）
   - 服务端处理请求，将结果缓存到 Redis（24 小时）
   - 返回结果

2. **重复请求**（相同 key）：
   - 服务端检查 Redis 中是否有缓存
   - 如果有，直接返回缓存的结果（不重复处理）
   - 如果没有，正常处理请求

**缓存规则**：
- 缓存时间：24 小时
- 缓存键：`idem:{operation}:{actorType}:{actorId}:{idempotencyKey}`
- 同一用户、同一操作、同一 key 才会命中缓存

### 3.4 哪些接口需要幂等性

**需要幂等性的接口**（写操作）：
- `POST /api/v1/orders` - 创建订单
- `POST /api/v1/orders/{id}/pay` - 支付订单
- `POST /api/v1/bookings` - 创建预约
- `POST /api/v1/entitlements/{id}/redeem` - 核销权益
- `POST /api/v1/cart/add` - 添加购物车
- `POST /api/v1/ai/chat` - AI 对话
- ...（其他写操作）

**不需要幂等性的接口**（读操作）：
- `GET /api/v1/orders` - 查询订单列表
- `GET /api/v1/orders/{id}` - 查询订单详情
- ...（所有 GET 请求）

### 3.5 前端实现

**生成 Idempotency-Key**：
```typescript
import { randomUUID } from 'crypto'

// 方式 1：使用 UUID
const idempotencyKey = randomUUID()

// 方式 2：使用时间戳 + 随机数
const idempotencyKey = `order-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
```

**发送请求**：
```typescript
const response = await fetch('/api/v1/orders', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Idempotency-Key': idempotencyKey,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(orderData)
})
```

**注意事项**：
- 每个写操作都应该生成新的 `Idempotency-Key`
- 不要重复使用同一个 key（除非确实需要幂等）
- 建议使用 UUID 或时间戳 + 随机数

## 4. 完整接口清单

> **说明**：以下为项目所有 API 接口的完整列表，按模块分类。接口路径统一前缀为 `/api/v1`。

### 4.1 健康检查

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/health` | GET | 基础健康检查 | 无需登录 |
| `/api/v1/health/live` | GET | 进程存活检查 | 无需登录 |
| `/api/v1/health/ready` | GET | 就绪检查（检查 DB/Redis） | 无需登录 |

### 4.2 认证相关

#### 4.2.1 用户认证（USER）

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/auth/request-sms-code` | POST | 请求短信验证码 | 无需登录 |
| `/api/v1/auth/login` | POST | 用户登录（H5） | 无需登录 |
| `/api/v1/auth/logout` | POST | 用户登出 | USER |
| `/api/v1/auth/refresh` | POST | 刷新 token | USER |
| `/api/v1/auth/bind-enterprise` | POST | 绑定企业 | USER |
| `/api/v1/auth/enterprise-suggestions` | GET | 企业名称建议 | USER |

#### 4.2.2 管理员认证（ADMIN）

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/auth/login` | POST | 管理员登录 | 无需登录 |
| `/api/v1/admin/auth/logout` | POST | 管理员登出 | ADMIN |
| `/api/v1/admin/auth/refresh` | POST | 刷新 token | ADMIN |
| `/api/v1/admin/auth/2fa/challenge` | POST | 2FA 挑战 | ADMIN |
| `/api/v1/admin/auth/2fa/verify` | POST | 2FA 验证 | ADMIN |
| `/api/v1/admin/auth/change-password` | POST | 修改密码 | ADMIN |
| `/api/v1/admin/auth/phone-bind/challenge` | POST | 绑定手机号挑战 | ADMIN |
| `/api/v1/admin/auth/phone-bind/verify` | POST | 绑定手机号验证 | ADMIN |
| `/api/v1/admin/auth/security` | GET | 安全设置 | ADMIN |

#### 4.2.3 小程序认证

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/mini-program/auth/login` | POST | 小程序登录 | 无需登录 |
| `/api/v1/mini-program/auth/logout` | POST | 小程序登出 | USER |

#### 4.2.4 经销商认证（DEALER）

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/dealer/auth/login` | POST | 经销商登录 | 无需登录 |
| `/api/v1/dealer/auth/register/challenge` | POST | 注册挑战 | 无需登录 |
| `/api/v1/dealer/auth/register` | POST | 经销商注册 | 无需登录 |
| `/api/v1/dealer/auth/change-password` | POST | 修改密码 | DEALER |

#### 4.2.5 服务提供方认证（PROVIDER）

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/provider/auth/login` | POST | 服务提供方登录 | 无需登录 |
| `/api/v1/provider/auth/logout` | POST | 服务提供方登出 | PROVIDER |
| `/api/v1/provider/auth/refresh` | POST | 刷新 token | PROVIDER |
| `/api/v1/provider/auth/register/challenge` | POST | 注册挑战 | 无需登录 |
| `/api/v1/provider/auth/register` | POST | 服务提供方注册 | 无需登录 |
| `/api/v1/provider/auth/change-password` | POST | 修改密码 | PROVIDER |

### 4.3 用户相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/users/profile` | GET | 获取当前用户信息 | USER |
| `/api/v1/users/profile` | PATCH | 更新当前用户信息 | USER |
| `/api/v1/admin/users` | GET | 管理员获取用户列表 | ADMIN |
| `/api/v1/admin/users/{id}` | GET | 管理员获取用户详情 | ADMIN |

### 4.4 用户地址相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/user-addresses` | GET | 获取地址列表 | USER |
| `/api/v1/user-addresses` | POST | 添加地址 | USER |
| `/api/v1/user-addresses/{id}` | GET | 获取地址详情 | USER |
| `/api/v1/user-addresses/{id}` | PUT | 更新地址 | USER |
| `/api/v1/user-addresses/{id}` | DELETE | 删除地址 | USER |

### 4.5 订单相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/orders` | GET | 获取订单列表 | USER |
| `/api/v1/orders` | POST | 创建订单 | USER（需 Idempotency-Key） |
| `/api/v1/orders/{id}` | GET | 获取订单详情 | USER |
| `/api/v1/orders/{id}/pay` | POST | 支付订单 | USER（需 Idempotency-Key） |
| `/api/v1/orders/{id}/confirm-received` | POST | 确认收货 | USER |
| `/api/v1/admin/orders` | GET | 管理员获取订单列表 | ADMIN |
| `/api/v1/admin/orders/{id}/ship` | POST | 管理员发货 | ADMIN |
| `/api/v1/admin/orders/{id}/deliver` | POST | 管理员标记已送达 | ADMIN |
| `/api/v1/dealer/orders` | GET | 经销商获取订单列表 | DEALER |
| `/api/v1/dealer/orders/export` | GET | 经销商导出订单 | DEALER |

### 4.6 支付相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/payments/wechat/notify` | POST | 微信支付回调 | 无需登录（服务端调用） |

### 4.7 购物车相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/cart` | GET | 获取购物车 | USER |
| `/api/v1/cart/add` | POST | 添加商品到购物车 | USER（需 Idempotency-Key） |
| `/api/v1/cart/update` | POST | 更新购物车商品 | USER（需 Idempotency-Key） |

### 4.8 权益相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/entitlements` | GET | 获取权益列表 | USER |
| `/api/v1/entitlements/{id}` | GET | 获取权益详情 | USER |
| `/api/v1/entitlements/{id}/redeem` | POST | 核销权益 | USER（需 Idempotency-Key） |
| `/api/v1/entitlements/{id}/transfer` | POST | 转赠权益 | USER（需 Idempotency-Key） |
| `/api/v1/admin/entitlements` | GET | 管理员获取权益列表 | ADMIN |
| `/api/v1/admin/entitlements/{id}` | GET | 管理员获取权益详情 | ADMIN |
| `/api/v1/admin/entitlement-transfers` | GET | 管理员获取转赠记录 | ADMIN |

### 4.9 预约相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/bookings` | GET | 获取预约列表 | USER |
| `/api/v1/bookings` | POST | 创建预约 | USER（需 Idempotency-Key） |
| `/api/v1/bookings/{id}` | GET | 获取预约详情 | USER |
| `/api/v1/bookings/{id}/cancel` | POST | 取消预约 | USER |
| `/api/v1/provider/bookings` | GET | 服务提供方获取预约列表 | PROVIDER |
| `/api/v1/provider/bookings/{id}/confirm` | POST | 确认预约 | PROVIDER |
| `/api/v1/admin/redemptions` | GET | 管理员获取核销记录 | ADMIN |

### 4.10 商品相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/products` | GET | 获取商品列表 | 无需登录 |
| `/api/v1/products/{id}` | GET | 获取商品详情 | 无需登录 |
| `/api/v1/admin/products` | GET | 管理员获取商品列表 | ADMIN |
| `/api/v1/admin/products/{id}/approve` | PUT | 管理员审核通过商品 | ADMIN |
| `/api/v1/admin/products/{id}/reject` | PUT | 管理员审核拒绝商品 | ADMIN |
| `/api/v1/admin/products/{id}/off-shelf` | PUT | 管理员下架商品 | ADMIN |

### 4.11 商品分类相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/product-categories` | GET | 获取商品分类列表 | 无需登录 |
| `/api/v1/admin/product-categories` | GET | 管理员获取商品分类列表 | ADMIN |

### 4.12 服务包相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/service-packages` | GET | 获取服务包列表 | 无需登录 |
| `/api/v1/service-packages/{id}` | GET | 获取服务包详情 | 无需登录 |
| `/api/v1/admin/service-packages` | GET | 管理员获取服务包列表 | ADMIN |
| `/api/v1/admin/service-packages/{id}` | GET | 管理员获取服务包详情 | ADMIN |
| `/api/v1/admin/service-packages` | POST | 管理员创建服务包 | ADMIN |
| `/api/v1/admin/service-packages/{id}` | PUT | 管理员更新服务包 | ADMIN |
| `/api/v1/admin/service-package-pricing` | GET | 管理员获取服务包定价 | ADMIN |
| `/api/v1/admin/service-package-pricing` | PUT | 管理员更新服务包定价 | ADMIN |

### 4.13 服务分类相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/service-categories` | GET | 获取服务分类列表 | 无需登录 |
| `/api/v1/admin/service-categories` | GET | 管理员获取服务分类列表 | ADMIN |
| `/api/v1/admin/service-categories` | POST | 管理员创建服务分类 | ADMIN |
| `/api/v1/admin/service-categories/{id}` | PUT | 管理员更新服务分类 | ADMIN |
| `/api/v1/admin/service-categories/{id}/enable` | POST | 管理员启用服务分类 | ADMIN |
| `/api/v1/admin/service-categories/{id}/disable` | POST | 管理员禁用服务分类 | ADMIN |

### 4.14 可售卡相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/sellable-cards/{id}` | GET | 获取可售卡详情 | 无需登录 |
| `/api/v1/admin/sellable-cards` | GET | 管理员获取可售卡列表 | ADMIN |
| `/api/v1/admin/sellable-cards` | POST | 管理员创建可售卡 | ADMIN |
| `/api/v1/admin/sellable-cards/{id}` | PUT | 管理员更新可售卡 | ADMIN |
| `/api/v1/admin/sellable-cards/{id}/enable` | POST | 管理员启用可售卡 | ADMIN |
| `/api/v1/admin/sellable-cards/{id}/disable` | POST | 管理员禁用可售卡 | ADMIN |
| `/api/v1/dealer/sellable-cards` | GET | 经销商获取可售卡列表 | DEALER |

### 4.15 场所相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/venues` | GET | 获取场所列表 | 无需登录 |
| `/api/v1/venues/{id}` | GET | 获取场所详情 | 无需登录 |
| `/api/v1/venues/{id}/available-slots` | GET | 获取可用时段 | 无需登录 |
| `/api/v1/admin/venues` | GET | 管理员获取场所列表 | ADMIN |
| `/api/v1/admin/venues/{id}` | GET | 管理员获取场所详情 | ADMIN |
| `/api/v1/admin/venues/{id}/publish` | POST | 管理员发布场所 | ADMIN |
| `/api/v1/admin/venues/{id}/approve` | POST | 管理员审核通过场所 | ADMIN |
| `/api/v1/admin/venues/{id}/reject` | POST | 管理员审核拒绝场所 | ADMIN |
| `/api/v1/admin/venues/{id}/offline` | POST | 管理员下架场所 | ADMIN |
| `/api/v1/provider/venues` | GET | 服务提供方获取场所列表 | PROVIDER |
| `/api/v1/provider/venues/{id}` | GET | 服务提供方获取场所详情 | PROVIDER |
| `/api/v1/provider/venues/{id}` | PUT | 服务提供方更新场所 | PROVIDER |
| `/api/v1/provider/venues/{id}/submit-showcase` | POST | 服务提供方提交展示 | PROVIDER |
| `/api/v1/provider/venues/{venueId}/services` | GET | 获取场所服务列表 | PROVIDER |
| `/api/v1/provider/venues/{venueId}/services` | POST | 创建场所服务 | PROVIDER |
| `/api/v1/provider/venues/{venueId}/services/{id}` | PUT | 更新场所服务 | PROVIDER |
| `/api/v1/provider/venues/{venueId}/schedules` | GET | 获取场所排期 | PROVIDER |
| `/api/v1/provider/venues/{venueId}/schedules/batch` | PUT | 批量更新场所排期 | PROVIDER |
| `/api/v1/provider/redemptions` | GET | 服务提供方获取核销记录 | PROVIDER |

### 4.16 服务提供方相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/provider/workbench/stats` | GET | 工作台统计 | PROVIDER |
| `/api/v1/provider/products` | GET | 获取商品列表 | PROVIDER |
| `/api/v1/provider/products` | POST | 创建商品 | PROVIDER |
| `/api/v1/provider/products/{id}` | PUT | 更新商品 | PROVIDER |
| `/api/v1/provider/orders` | GET | 获取订单列表 | PROVIDER |
| `/api/v1/provider/orders/{id}/ship` | POST | 发货 | PROVIDER |
| `/api/v1/provider/onboarding` | GET | 获取入驻信息 | PROVIDER |
| `/api/v1/provider/onboarding/infra/open` | POST | 开通基础设施 | PROVIDER |
| `/api/v1/provider/onboarding/health-card/submit` | POST | 提交健康证 | PROVIDER |
| `/api/v1/admin/provider-onboarding/health-card` | GET | 管理员获取健康证审核 | ADMIN |
| `/api/v1/admin/provider-onboarding/{providerId}/health-card/decide` | PUT | 管理员决定健康证审核 | ADMIN |

### 4.17 经销商相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/dealer/orders` | GET | 获取订单列表 | DEALER |
| `/api/v1/dealer/orders/export` | GET | 导出订单 | DEALER |
| `/api/v1/dealer/settlements` | GET | 获取结算记录 | DEALER |
| `/api/v1/dealer/settlement-account` | GET | 获取结算账户 | DEALER |
| `/api/v1/dealer/settlement-account` | PUT | 更新结算账户 | DEALER |
| `/api/v1/dealer-links` | GET | 获取经销商链接列表 | DEALER/ADMIN |
| `/api/v1/dealer-links` | POST | 创建经销商链接 | DEALER/ADMIN（需 Idempotency-Key） |
| `/api/v1/dealer-links/{id}/disable` | POST | 禁用经销商链接 | DEALER/ADMIN |
| `/api/v1/dealer-links/verify` | GET | 验证经销商链接 | 无需登录 |
| `/api/v1/admin/dealer-commission` | GET | 管理员获取经销商佣金设置 | ADMIN |
| `/api/v1/admin/dealer-commission` | PUT | 管理员更新经销商佣金设置 | ADMIN |
| `/api/v1/admin/dealer-settlements/generate` | POST | 管理员生成结算单 | ADMIN |
| `/api/v1/admin/dealer-settlements` | GET | 管理员获取结算单列表 | ADMIN |
| `/api/v1/admin/dealer-settlements/{id}/mark-settled` | POST | 管理员标记已结算 | ADMIN |

### 4.18 企业相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/enterprises` | GET | 管理员获取企业列表 | ADMIN |
| `/api/v1/admin/enterprises/{id}` | GET | 管理员获取企业详情 | ADMIN |

### 4.19 账号管理相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/admin-users` | GET | 管理员获取管理员账号列表 | ADMIN |
| `/api/v1/admin/admin-users` | POST | 管理员创建管理员账号 | ADMIN |
| `/api/v1/admin/admin-users/{id}/reset-password` | POST | 重置管理员密码 | ADMIN |
| `/api/v1/admin/admin-users/{id}/suspend` | POST | 暂停管理员账号 | ADMIN |
| `/api/v1/admin/admin-users/{id}/activate` | POST | 激活管理员账号 | ADMIN |
| `/api/v1/admin/provider-users` | GET | 管理员获取服务提供方账号列表 | ADMIN |
| `/api/v1/admin/provider-users` | POST | 管理员创建服务提供方账号 | ADMIN |
| `/api/v1/admin/provider-users/{id}/reset-password` | POST | 重置服务提供方密码 | ADMIN |
| `/api/v1/admin/provider-users/{id}/suspend` | POST | 暂停服务提供方账号 | ADMIN |
| `/api/v1/admin/provider-users/{id}/activate` | POST | 激活服务提供方账号 | ADMIN |
| `/api/v1/admin/provider-staff` | GET | 管理员获取服务提供方员工列表 | ADMIN |
| `/api/v1/admin/provider-staff` | POST | 管理员创建服务提供方员工 | ADMIN |
| `/api/v1/admin/provider-staff/{id}/reset-password` | POST | 重置服务提供方员工密码 | ADMIN |
| `/api/v1/admin/provider-staff/{id}/suspend` | POST | 暂停服务提供方员工账号 | ADMIN |
| `/api/v1/admin/provider-staff/{id}/activate` | POST | 激活服务提供方员工账号 | ADMIN |
| `/api/v1/admin/dealer-users` | GET | 管理员获取经销商账号列表 | ADMIN |
| `/api/v1/admin/dealer-users` | POST | 管理员创建经销商账号 | ADMIN |
| `/api/v1/admin/dealer-users/{id}/reset-password` | POST | 重置经销商密码 | ADMIN |
| `/api/v1/admin/dealer-users/{id}/suspend` | POST | 暂停经销商账号 | ADMIN |
| `/api/v1/admin/dealer-users/{id}/activate` | POST | 激活经销商账号 | ADMIN |

### 4.20 地区相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/regions/cities` | GET | 获取城市列表 | 无需登录 |
| `/api/v1/admin/regions` | GET | 管理员获取地区列表 | ADMIN |

### 4.21 分类节点相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/taxonomy-nodes` | GET | 获取分类节点列表 | 无需登录 |

### 4.22 标签相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/tags` | GET | 获取标签列表 | 无需登录 |

### 4.23 法律协议相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/legal/agreements/{code}` | GET | 获取协议内容 | 无需登录 |
| `/api/v1/admin/legal/agreements` | GET | 管理员获取协议列表 | ADMIN |
| `/api/v1/admin/legal/agreements/{code}` | GET | 管理员获取协议详情 | ADMIN |
| `/api/v1/admin/legal/agreements/{code}` | PUT | 管理员更新协议 | ADMIN |
| `/api/v1/admin/legal/agreements/{code}/publish` | POST | 管理员发布协议 | ADMIN |
| `/api/v1/admin/legal/agreements/{code}/offline` | POST | 管理员下架协议 | ADMIN |

### 4.24 CMS 内容管理相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/mini-program/cms/channels` | GET | 小程序获取栏目列表 | 无需登录 |
| `/api/v1/mini-program/cms/contents` | GET | 小程序获取内容列表 | 无需登录 |
| `/api/v1/mini-program/cms/contents/{id}` | GET | 小程序获取内容详情 | 无需登录 |
| `/api/v1/website/cms/channels` | GET | 官网获取栏目列表 | 无需登录 |
| `/api/v1/website/cms/contents` | GET | 官网获取内容列表 | 无需登录 |
| `/api/v1/website/cms/contents/{id}` | GET | 官网获取内容详情 | 无需登录 |
| `/api/v1/admin/cms/channels` | GET | 管理员获取栏目列表 | ADMIN |
| `/api/v1/admin/cms/channels` | POST | 管理员创建栏目 | ADMIN |
| `/api/v1/admin/cms/channels/{id}` | PUT | 管理员更新栏目 | ADMIN |
| `/api/v1/admin/cms/contents` | GET | 管理员获取内容列表 | ADMIN |
| `/api/v1/admin/cms/contents` | POST | 管理员创建内容 | ADMIN |
| `/api/v1/admin/cms/contents/{id}` | GET | 管理员获取内容详情 | ADMIN |
| `/api/v1/admin/cms/contents/{id}` | PUT | 管理员更新内容 | ADMIN |
| `/api/v1/admin/cms/contents/{id}/publish` | POST | 管理员发布内容 | ADMIN |
| `/api/v1/admin/cms/contents/{id}/offline` | POST | 管理员下架内容 | ADMIN |

### 4.25 小程序配置相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/mini-program/home/recommended-venues` | GET | 获取首页推荐场所 | 无需登录 |
| `/api/v1/mini-program/home/recommended-products` | GET | 获取首页推荐商品 | 无需登录 |
| `/api/v1/mini-program/entries` | GET | 获取入口列表 | 无需登录 |
| `/api/v1/mini-program/pages/{id}` | GET | 获取页面详情 | 无需登录 |
| `/api/v1/mini-program/collections/{id}/items` | GET | 获取集合商品列表 | 无需登录 |
| `/api/v1/admin/mini-program/home/recommended-venues` | GET | 管理员获取首页推荐场所 | ADMIN |
| `/api/v1/admin/mini-program/home/recommended-venues` | PUT | 管理员更新首页推荐场所 | ADMIN |
| `/api/v1/admin/mini-program/home/recommended-products` | GET | 管理员获取首页推荐商品 | ADMIN |
| `/api/v1/admin/mini-program/home/recommended-products` | PUT | 管理员更新首页推荐商品 | ADMIN |
| `/api/v1/admin/mini-program/entries` | GET | 管理员获取入口列表 | ADMIN |
| `/api/v1/admin/mini-program/entries` | PUT | 管理员更新入口列表 | ADMIN |
| `/api/v1/admin/mini-program/entries/publish` | POST | 管理员发布入口 | ADMIN |
| `/api/v1/admin/mini-program/entries/offline` | POST | 管理员下架入口 | ADMIN |
| `/api/v1/admin/mini-program/pages` | GET | 管理员获取页面列表 | ADMIN |
| `/api/v1/admin/mini-program/pages/{id}` | PUT | 管理员更新页面 | ADMIN |
| `/api/v1/admin/mini-program/pages/{id}/publish` | POST | 管理员发布页面 | ADMIN |
| `/api/v1/admin/mini-program/pages/{id}/offline` | POST | 管理员下架页面 | ADMIN |
| `/api/v1/admin/mini-program/collections` | GET | 管理员获取集合列表 | ADMIN |
| `/api/v1/admin/mini-program/collections/{id}` | PUT | 管理员更新集合 | ADMIN |
| `/api/v1/admin/mini-program/collections/{id}/publish` | POST | 管理员发布集合 | ADMIN |
| `/api/v1/admin/mini-program/collections/{id}/offline` | POST | 管理员下架集合 | ADMIN |

### 4.26 官网配置相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/website/home/recommended-venues` | GET | 获取首页推荐场所 | 无需登录 |
| `/api/v1/website/footer/config` | GET | 获取页脚配置 | 无需登录 |
| `/api/v1/website/external-links` | GET | 获取外部链接 | 无需登录 |
| `/api/v1/website/site-seo` | GET | 获取 SEO 配置 | 无需登录 |
| `/api/v1/website/nav-control` | GET | 获取导航控制 | 无需登录 |
| `/api/v1/website/maintenance-mode` | GET | 获取维护模式 | 无需登录 |
| `/api/v1/admin/website/home/recommended-venues` | GET | 管理员获取首页推荐场所 | ADMIN |
| `/api/v1/admin/website/home/recommended-venues` | PUT | 管理员更新首页推荐场所 | ADMIN |
| `/api/v1/admin/website/footer-config` | GET | 管理员获取页脚配置 | ADMIN |
| `/api/v1/admin/website/footer-config` | PUT | 管理员更新页脚配置 | ADMIN |
| `/api/v1/admin/website/external-links` | GET | 管理员获取外部链接 | ADMIN |
| `/api/v1/admin/website/external-links` | PUT | 管理员更新外部链接 | ADMIN |
| `/api/v1/admin/website/site-seo` | GET | 管理员获取 SEO 配置 | ADMIN |
| `/api/v1/admin/website/site-seo` | PUT | 管理员更新 SEO 配置 | ADMIN |
| `/api/v1/admin/website/nav-control` | GET | 管理员获取导航控制 | ADMIN |
| `/api/v1/admin/website/nav-control` | PUT | 管理员更新导航控制 | ADMIN |
| `/api/v1/admin/website/maintenance-mode` | GET | 管理员获取维护模式 | ADMIN |
| `/api/v1/admin/website/maintenance-mode` | PUT | 管理员更新维护模式 | ADMIN |

### 4.27 H5 配置相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/h5/landing/faq-terms` | GET | 获取落地页 FAQ 条款 | 无需登录 |
| `/api/v1/h5/legal/service-agreement` | GET | 获取服务协议 | 无需登录 |
| `/api/v1/h5/mini-program/launch` | GET | 获取小程序启动参数 | 无需登录 |
| `/api/v1/h5/dealer-links/{dealerLinkId}` | GET | 获取经销商链接信息 | 无需登录 |
| `/api/v1/h5/dealer-links/{dealerLinkId}/cards/{sellableCardId}` | GET | 获取可售卡详情 | 无需登录 |
| `/api/v1/h5/dealer-links/{dealerLinkId}/cards` | GET | 获取可售卡列表 | 无需登录 |

### 4.28 AI 相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/ai/chat` | POST | AI 对话 | USER（需 Idempotency-Key） |
| `/api/v1/admin/ai/config` | GET | 管理员获取 AI 配置 | ADMIN |
| `/api/v1/admin/ai/config` | PUT | 管理员更新 AI 配置 | ADMIN |

### 4.29 通知相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/notifications` | GET | 管理员获取通知列表 | ADMIN |
| `/api/v1/admin/notifications` | POST | 管理员创建通知 | ADMIN（需 Idempotency-Key） |
| `/api/v1/admin/notification-receivers` | GET | 管理员获取通知接收者列表 | ADMIN |
| `/api/v1/dealer/notifications` | GET | 经销商获取通知列表 | DEALER |
| `/api/v1/provider/notifications` | GET | 服务提供方获取通知列表 | PROVIDER |

### 4.30 售后相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/after-sales/cases` | GET | 获取售后单列表 | USER |
| `/api/v1/after-sales/cases` | POST | 创建售后单 | USER |
| `/api/v1/after-sales/cases/{id}` | GET | 获取售后单详情 | USER |
| `/api/v1/admin/after-sales/cases` | GET | 管理员获取售后单列表 | ADMIN |
| `/api/v1/admin/after-sales/cases/{id}/approve` | POST | 管理员审核通过售后单 | ADMIN |
| `/api/v1/admin/after-sales/cases/{id}/reject` | POST | 管理员审核拒绝售后单 | ADMIN |

### 4.31 审计日志相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/audit-logs` | GET | 管理员获取审计日志 | ADMIN |

### 4.32 资产管理相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/assets` | GET | 管理员获取资产列表 | ADMIN |

### 4.33 管理后台工作台相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/dashboard/stats` | GET | 管理员获取工作台统计 | ADMIN |

### 4.34 开发工具相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/admin/dev/tools` | GET | 管理员获取开发工具 | ADMIN |

### 4.35 文件上传相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/uploads/images` | POST | 上传图片 | USER/ADMIN |

### 4.36 OpenAPI 代理相关

| 接口 | 方法 | 说明 | 角色 |
|------|------|------|------|
| `/api/v1/openapi/proxy` | POST | OpenAPI 代理 | ADMIN |

**注意**：
- 所有接口路径统一前缀为 `/api/v1`
- 需要 Idempotency-Key 的接口已在说明中标注
- 角色说明：USER（用户）、ADMIN（管理员）、DEALER（经销商）、PROVIDER（服务提供方）
- 实际接口参数和响应格式请查看 Swagger UI（`/docs`）或 OpenAPI JSON（`/openapi.json`）

## 5. OpenAPI/Swagger 使用说明

### 5.1 访问 Swagger UI

**本地开发环境**：
```
http://localhost:8000/docs
```

**生产环境**（如果启用）：
```
https://your-domain.com/docs
```

**ReDoc 文档**（替代 UI）：
```
http://localhost:8000/redoc
```

### 5.2 使用 Swagger UI

**功能**：
1. **查看所有接口**：左侧列表显示所有接口，按标签分组
2. **查看接口详情**：点击接口名称，查看请求参数、响应格式
3. **测试接口**：直接在页面上测试接口（需要先登录获取 token）

**测试步骤**：
1. 打开 Swagger UI
2. 找到登录接口（如 `/api/v1/auth/login`）
3. 点击 "Try it out"
4. 填写参数，点击 "Execute"
5. 复制返回的 `token`
6. 点击页面右上角的 "Authorize" 按钮
7. 输入 `Bearer <token>`，点击 "Authorize"
8. 现在可以测试需要登录的接口了

### 5.3 查看 OpenAPI JSON

**OpenAPI 规范 JSON**：
```
http://localhost:8000/openapi.json
```

**用途**：
- 导入到 Postman、Insomnia 等工具
- 生成客户端 SDK
- 查看完整的 API 规范

### 5.4 接口标签（Tags）

**接口按功能分组**：
- `auth` - 认证相关
- `orders` - 订单相关
- `payments` - 支付相关
- `entitlements` - 权益相关
- `bookings` - 预约相关
- `users` - 用户相关
- `products` - 商品相关
- `venues` - 场所相关
- `cart` - 购物车相关
- `admin-*` - 管理后台相关
- `dealer-*` - 经销商相关
- `provider-*` - 服务提供方相关

### 5.5 接口文档说明

**每个接口包含**：
- **描述**：接口用途说明
- **参数**：请求参数（路径参数、查询参数、请求体）
- **响应**：响应格式（成功、失败）
- **错误码**：可能的错误码
- **认证**：是否需要登录，需要什么角色

### 5.6 使用建议

**开发时**：
- 先看 Swagger UI 了解接口
- 在 Swagger UI 中测试接口
- 参考响应格式编写前端代码

**调试时**：
- 使用 Swagger UI 快速测试接口
- 查看请求/响应详情
- 验证参数格式

**文档时**：
- 导出 OpenAPI JSON
- 生成 API 文档
- 分享给前端团队

## 6. 常见问题

### Q: 为什么有些接口返回 401，但我已经传了 token？

A: 可能的原因：
1. Token 已过期（检查 `exp` 字段）
2. Token 格式错误（应该是 `Bearer <token>`）
3. Token 被加入黑名单（已登出）
4. Token 类型不匹配（如用 USER token 访问 ADMIN 接口）

### Q: 如何知道接口是否需要 Idempotency-Key？

A: 
1. 看接口文档（Swagger UI）
2. 看接口说明（通常写操作需要）
3. 如果缺少会返回 400 错误："缺少 Idempotency-Key"

### Q: Idempotency-Key 可以重复使用吗？

A: 不建议。每个写操作应该生成新的 key。重复使用同一个 key 会导致：
- 如果第一次请求成功，后续请求会直接返回第一次的结果
- 如果第一次请求失败，后续请求会重复处理

### Q: 如何生成 Idempotency-Key？

A: 推荐使用 UUID：
```typescript
import { randomUUID } from 'crypto'
const idempotencyKey = randomUUID()
```

或者使用时间戳 + 随机数：
```typescript
const idempotencyKey = `order-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
```

### Q: 错误响应中的 details 字段有什么用？

A: `details` 字段包含详细的错误信息，主要用于：
- 调试：开发时查看详细错误
- 参数验证：显示哪些参数不合法
- 业务错误：显示具体的业务错误原因

**注意**：生产环境可能不返回 `details`，避免泄露敏感信息。

### Q: requestId 有什么用？

A: `requestId` 用于：
- **日志追踪**：在日志中搜索 `requestId`，找到完整的请求链路
- **问题排查**：遇到问题时，提供 `requestId` 给后端排查
- **调试**：前端可以在控制台打印 `requestId`，方便调试

### Q: 如何知道接口需要什么角色？

A: 
1. 看接口路径：`admin_*` 需要 ADMIN，`provider_*` 需要 PROVIDER
2. 看 Swagger UI：接口文档会说明需要的角色
3. 看错误信息：403 错误表示无权限

### Q: 可以同时使用多个角色的 token 吗？

A: 不可以。每个请求只能使用一个 token，根据 token 类型确定角色。如果需要切换角色，需要重新登录获取对应角色的 token。

---

**最后提醒**：
- 开发时优先查看 Swagger UI（`/docs`）
- 遇到问题先看错误码和错误消息
- 不确定的地方可以问后端开发或查看代码

