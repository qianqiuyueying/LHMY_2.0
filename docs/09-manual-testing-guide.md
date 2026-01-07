# 健康服务平台 - 手动测试指南

> **版本**: v2.0  
> **更新日期**: 2026-01-06  
> **适用范围**: 完整功能回归测试、上线前验收测试

## 目录

1. [测试环境准备](#1-测试环境准备)
2. [基础设施测试](#2-基础设施测试)
3. [认证授权测试](#3-认证授权测试)
4. [H5 购买链路测试](#4-h5-购买链路测试)
5. [小程序使用链路测试](#5-小程序使用链路测试)
6. [管理后台功能测试](#6-管理后台功能测试)
7. [API 接口测试](#7-api-接口测试)
8. [边界与异常测试](#8-边界与异常测试)
9. [性能与稳定性测试](#9-性能与稳定性测试)
10. [测试检查清单](#10-测试检查清单)

---

## 1. 测试环境准备

### 1.1 环境要求

- **后端服务**: Docker Compose 环境已启动
- **数据库**: MySQL 8.0（已初始化表结构）
- **缓存**: Redis 7
- **消息队列**: RabbitMQ 3
- **前端访问**: 
  - Admin: `http://localhost/admin` 或生产域名
  - H5: `http://localhost/h5` 或生产域名
  - Website: `http://localhost` 或生产域名
  - 小程序: 需配置微信开发者工具

### 1.2 测试账号准备

#### Admin 管理员账号
- 账号: `admin@example.com`（或实际管理员账号）
- 密码: （从环境变量或数据库获取）

#### Dealer 经销商账号
- 账号: `dealer@example.com`
- 密码: （需先创建）

#### Provider 服务提供方账号
- 账号: `provider@example.com`
- 密码: （需先创建）

#### 普通用户账号
- 手机号: `13800138000`（用于 H5 购买测试）
- 短信验证码: （实时获取）

### 1.3 测试工具

- **API 测试**: Postman / curl / Swagger UI (`http://localhost:8000/docs`)
- **浏览器**: Chrome / Edge（最新版）
- **小程序**: 微信开发者工具
- **数据库工具**: MySQL Workbench / DBeaver

---

## 2. 基础设施测试

### 2.1 健康检查接口

#### 2.1.1 Liveness 探针
```bash
# 测试进程存活
curl http://localhost:8000/api/v1/health/live
```

**预期结果**:
- HTTP 200
- 响应: `{"success": true, "data": {...}}`

#### 2.1.2 Readiness 探针
```bash
# 测试依赖可用性（DB/Redis）
curl http://localhost:8000/api/v1/health/ready
```

**预期结果**:
- HTTP 200
- 响应包含数据库和 Redis 连接状态

**测试步骤**:
1. ✅ 正常状态：返回 200
2. ✅ 数据库断开：停止 MySQL 容器，应返回 503 或错误信息
3. ✅ Redis 断开：停止 Redis 容器，应返回 503 或错误信息

### 2.2 OpenAPI 文档

```bash
# 访问 OpenAPI JSON
curl http://localhost:8000/api/v1/openapi.json

# 访问 Swagger UI
浏览器打开: http://localhost:8000/docs
```

**预期结果**:
- OpenAPI JSON 可正常访问
- Swagger UI 页面正常加载，显示所有接口

### 2.3 Metrics 监控

```bash
# Prometheus metrics
curl http://localhost:8000/metrics
```

**预期结果**:
- 返回 Prometheus 格式的指标数据
- 包含 HTTP 请求相关指标

### 2.4 Docker 容器健康检查

```bash
# 检查容器状态
docker ps

# 检查容器健康状态
docker inspect lhmy_backend | grep -A 10 Health
docker inspect lhmy_nginx | grep -A 10 Health
```

**预期结果**:
- 所有容器状态为 `healthy`
- 健康检查间隔为 10 秒

---

## 3. 认证授权测试

### 3.1 Admin 管理员登录

#### 3.1.1 正常登录
**接口**: `POST /api/v1/admin/auth/login`

**请求**:
```json
{
  "username": "admin@example.com",
  "password": "your_password"
}
```

**预期结果**:
- HTTP 200
- 返回 `token`、`actorType: "ADMIN"`、`actorUsername`
- 前端 localStorage 保存 token

#### 3.1.2 错误密码
**请求**: 使用错误密码

**预期结果**:
- HTTP 401
- 错误信息: "用户名或密码错误"

#### 3.1.3 登录失败次数限制
**测试步骤**:
1. 连续输入错误密码 5 次
2. 观察是否触发锁定机制

**预期结果**:
- 达到限制后返回 429 或错误提示
- 包含 `retryAfterSeconds`（如已实现）

### 3.2 Dealer 经销商登录

**接口**: `POST /api/v1/dealer/auth/login`

**测试步骤**: 同 Admin 登录流程

**预期结果**:
- 返回 `actorType: "DEALER"`

### 3.3 Provider 服务提供方登录

**接口**: `POST /api/v1/provider/auth/login`

**测试步骤**: 同 Admin 登录流程

**预期结果**:
- 返回 `actorType: "PROVIDER"`

### 3.4 小程序登录

**接口**: `POST /api/v1/mini-program/auth/login`

**请求**:
```json
{
  "code": "微信小程序 code"
}
```

**测试步骤**:
1. 在微信开发者工具中打开小程序
2. 触发登录流程
3. 检查 token 是否保存

**预期结果**:
- 返回 token 和用户信息
- 小程序全局数据保存 token

### 3.5 H5 登录（短信验证码）

**接口**: 
- `POST /api/v1/auth/request-sms-code`（获取验证码）
- `POST /api/v1/auth/login`（登录）

**测试步骤**:
1. 输入手机号，请求验证码
2. 输入验证码，完成登录

**预期结果**:
- 验证码发送成功
- 登录成功，返回 token

### 3.6 Token 刷新

**接口**: `POST /api/v1/admin/auth/refresh`（以 Admin 为例）

**请求**:
```json
{
  "refreshToken": "your_refresh_token"
}
```

**预期结果**:
- 返回新的 access token

### 3.7 权限验证

#### 3.7.1 未登录访问受保护接口
**测试步骤**:
1. 不携带 Authorization header
2. 访问需要登录的接口

**预期结果**:
- HTTP 401
- 错误信息: "UNAUTHENTICATED"

#### 3.7.2 跨角色访问
**测试步骤**:
1. 使用 Dealer token
2. 访问 Admin 专用接口

**预期结果**:
- HTTP 403
- 错误信息: "FORBIDDEN"

#### 3.7.3 前端路由守卫
**测试步骤**:
1. 未登录访问 `/admin/*` 路由
2. 使用 Dealer 账号访问 `/admin/*` 路由

**预期结果**:
- 自动跳转到 `/login?next=...`
- 登录页显示提示信息

---

## 4. H5 购买链路测试

> **参考**: `specs/health-services-platform/facts/h5.md` 的"最小可执行使用路径"

### 4.1 前置条件

#### 4.1.1 创建经销商投放链接
**接口**: `POST /api/v1/dealer-links`（需 Dealer 登录）

**请求**:
```json
{
  "sellableCardId": 1,
  "validUntil": "2026-12-31T23:59:59Z"
}
```

**预期结果**:
- 返回 `dealerLinkId`
- 返回入口 URL: `/h5?dealerLinkId=...`

#### 4.1.2 创建可售卡（Admin）
**接口**: `POST /api/v1/admin/sellable-cards`（需 Admin 登录）

**请求**:
```json
{
  "name": "测试健康卡",
  "servicePackageTemplateId": 1,
  "regionLevel": "CITY",
  "price": 10000,
  "status": "ENABLED"
}
```

### 4.2 落地页测试

#### 4.2.1 通过经销商链接访问
**URL**: `/h5?dealerLinkId={dealerLinkId}`

**测试步骤**:
1. 打开落地页
2. 检查是否显示经销商信息
3. 检查是否显示可售卡列表

**预期结果**:
- 页面正常加载
- 显示经销商名称
- 显示可售卡列表（卡片摘要：服务类别×次数）

#### 4.2.2 直达购卡页
**URL**: `/h5?dealerLinkId={dealerLinkId}&sellableCardId={sellableCardId}`

**预期结果**:
- 自动跳转到 `/h5/buy?dealerLinkId=...&sellableCardId=...`

#### 4.2.3 无经销商链接访问
**URL**: `/h5`

**预期结果**:
- "立即购买"按钮不可点击（置灰）
- 提示: "请通过经销商投放链接购买"

### 4.3 购买页测试

#### 4.3.1 页面加载
**URL**: `/h5/buy?dealerLinkId={dealerLinkId}&sellableCardId={sellableCardId}`

**测试步骤**:
1. 检查卡片信息是否正确显示
2. 检查服务内容展示（服务大类 × 次数）
3. 检查价格显示

**预期结果**:
- 卡片详情正确
- 服务内容清晰展示
- 价格正确

#### 4.3.2 区域选择（省/市卡）
**测试步骤**:
1. 选择省份
2. 选择城市
3. 测试搜索功能

**预期结果**:
- 省/市级联选择正常
- 搜索功能可用
- 省卡必须选到省，市卡必须选到市

#### 4.3.3 短信验证码
**接口**: `POST /api/v1/auth/request-sms-code`

**请求**:
```json
{
  "phone": "13800138000",
  "scene": "H5_BUY"
}
```

**测试步骤**:
1. 输入手机号
2. 点击"获取验证码"
3. 检查是否收到短信
4. 测试倒计时功能

**预期结果**:
- 验证码发送成功
- 按钮显示倒计时（60 秒）
- 倒计时期间不可重复点击

#### 4.3.4 服务协议
**测试步骤**:
1. 点击"服务协议"链接
2. 检查协议内容是否正确加载

**预期结果**:
- 协议弹窗正常显示
- 内容来自 `GET /api/v1/h5/legal/service-agreement`

#### 4.3.5 提交订单
**接口**: `POST /api/v1/orders`

**请求**:
```json
{
  "orderType": "SERVICE_PACKAGE",
  "items": [
    {
      "sellableCardId": 1,
      "quantity": 1
    }
  ],
  "regionId": 1
}
```

**Headers**:
- `Idempotency-Key: {uuid}`
- `Authorization: Bearer {token}`

**Query**:
- `dealerLinkId={dealerLinkId}`

**测试步骤**:
1. 填写手机号、验证码
2. 选择区域（如需要）
3. 勾选服务协议
4. 点击"立即购买"
5. 检查订单创建结果

**预期结果**:
- 订单创建成功
- 返回订单 ID
- 自动跳转到支付流程

#### 4.3.6 幂等性测试
**测试步骤**:
1. 使用相同的 `Idempotency-Key` 重复提交

**预期结果**:
- 返回相同的订单 ID（不重复创建）

### 4.4 支付流程测试

#### 4.4.1 发起支付
**接口**: `POST /api/v1/orders/{orderId}/pay`

**请求**:
```json
{
  "paymentMethod": "WECHAT"
}
```

**Headers**:
- `Idempotency-Key: {uuid}`

**测试步骤**:
1. 创建订单后自动发起支付
2. 检查支付参数是否正确

**预期结果**:
- 返回微信支付参数（如 `prepayId`）
- 前端调用微信支付 SDK

#### 4.4.2 支付成功
**测试步骤**:
1. 完成支付（测试环境可使用沙箱）
2. 检查订单状态更新

**预期结果**:
- 订单状态变为 `PAID`
- 跳转到支付结果页

#### 4.4.3 支付失败
**测试步骤**:
1. 取消支付或支付失败
2. 检查错误处理

**预期结果**:
- 显示错误提示
- 可重试支付

### 4.5 支付结果页测试

#### 4.5.1 支付成功页面
**URL**: `/h5/pay/result?status=success&dealerLinkId=...`

**测试步骤**:
1. 检查成功提示
2. 检查"打开小程序查看权益"提示
3. 测试小程序跳转（如已配置）

**预期结果**:
- 显示支付成功信息
- 提供小程序入口提示

#### 4.5.2 支付失败页面
**URL**: `/h5/pay/result?status=failed&reason=...`

**预期结果**:
- 显示失败原因
- 提供重试支付入口

---

## 5. 小程序使用链路测试

> **参考**: `specs/health-services-platform/facts/mini-program.md`

### 5.1 小程序启动

#### 5.1.1 首次启动
**测试步骤**:
1. 打开微信开发者工具
2. 加载小程序
3. 检查登录流程

**预期结果**:
- 自动触发登录
- Token 保存成功
- 跳转到首页

#### 5.1.2 Token 验证
**测试步骤**:
1. 启动时检查已有 token
2. 调用 `GET /api/v1/users/profile` 验证

**预期结果**:
- Token 有效：直接进入首页
- Token 无效：重新登录

### 5.2 首页测试

#### 5.2.1 入口配置加载
**接口**: `GET /api/v1/mini-program/entries`

**测试步骤**:
1. 检查 Banner 是否显示
2. 检查入口列表是否正确

**预期结果**:
- Banner 图片正常加载
- 入口列表正确显示
- 点击跳转正常

#### 5.2.2 推荐场所
**接口**: `GET /api/v1/mini-program/home/recommended-venues`

**预期结果**:
- 推荐场所列表正确显示

#### 5.2.3 推荐商品
**接口**: `GET /api/v1/mini-program/home/recommended-products`

**预期结果**:
- 推荐商品列表正确显示

### 5.3 商城功能测试

#### 5.3.1 商品分类
**接口**: `GET /api/v1/product-categories`

**测试步骤**:
1. 进入商城页
2. 检查分类列表

**预期结果**:
- 分类列表正确显示
- 点击分类可筛选商品

#### 5.3.2 商品列表
**接口**: `GET /api/v1/products`

**测试步骤**:
1. 检查商品列表加载
2. 测试分页功能
3. 测试筛选功能

**预期结果**:
- 商品列表正常显示
- 分页加载正常
- 筛选功能正常

#### 5.3.3 商品详情
**接口**: `GET /api/v1/products/{productId}`

**测试步骤**:
1. 点击商品进入详情页
2. 检查商品信息
3. 测试加入购物车

**预期结果**:
- 商品详情正确显示
- 可以加入购物车

### 5.4 购物车测试

#### 5.4.1 添加商品
**接口**: `POST /api/v1/cart/items`

**测试步骤**:
1. 在商品详情页点击"加入购物车"
2. 检查购物车数量更新

**预期结果**:
- 商品成功加入购物车
- 购物车角标更新

#### 5.4.2 购物车列表
**接口**: `GET /api/v1/cart`

**测试步骤**:
1. 进入购物车页面
2. 检查商品列表
3. 测试修改数量
4. 测试删除商品

**预期结果**:
- 购物车商品正确显示
- 可以修改数量
- 可以删除商品

#### 5.4.3 结算下单
**接口**: `POST /api/v1/orders`

**测试步骤**:
1. 选择商品
2. 点击"结算"
3. 填写收货地址
4. 提交订单

**预期结果**:
- 订单创建成功
- 跳转到订单详情页

### 5.5 订单管理测试

#### 5.5.1 订单列表
**接口**: `GET /api/v1/orders`

**测试步骤**:
1. 进入订单列表页
2. 检查订单状态筛选
3. 测试分页加载

**预期结果**:
- 订单列表正确显示
- 状态筛选正常
- 分页加载正常

#### 5.5.2 订单详情
**接口**: `GET /api/v1/orders/{orderId}`

**测试步骤**:
1. 点击订单进入详情
2. 检查订单信息
3. 测试支付功能

**预期结果**:
- 订单详情正确显示
- 可以发起支付

#### 5.5.3 订单支付
**接口**: `POST /api/v1/orders/{orderId}/pay`

**测试步骤**:
1. 在订单详情页点击"支付"
2. 调用微信支付
3. 完成支付

**预期结果**:
- 支付参数正确
- 微信支付正常调用
- 支付成功后订单状态更新

### 5.6 权益使用测试

#### 5.6.1 权益列表
**接口**: `GET /api/v1/entitlements`

**测试步骤**:
1. 进入"我的权益"页面
2. 检查权益列表

**预期结果**:
- 权益列表正确显示
- 显示剩余次数

#### 5.6.2 预约服务
**接口**: `POST /api/v1/bookings`

**测试步骤**:
1. 选择权益
2. 选择服务提供方
3. 选择时间
4. 提交预约

**预期结果**:
- 预约创建成功
- 权益次数扣减

#### 5.6.3 核销权益
**接口**: `POST /api/v1/redemptions`

**测试步骤**:
1. 在服务提供方处
2. 扫描二维码或输入码
3. 核销权益

**预期结果**:
- 核销成功
- 权益次数扣减

---

## 6. 管理后台功能测试

> **参考**: `specs/health-services-platform/facts/admin.md`

### 6.1 Admin 管理功能

#### 6.1.1 工作台
**接口**: `GET /api/v1/admin/dashboard/stats`

**测试步骤**:
1. 登录 Admin 账号
2. 进入工作台
3. 检查统计数据

**预期结果**:
- 统计数据正确显示
- 图表正常渲染

#### 6.1.2 可售卡管理
**接口**: 
- `GET /api/v1/admin/sellable-cards`
- `POST /api/v1/admin/sellable-cards`
- `PUT /api/v1/admin/sellable-cards/{id}`
- `POST /api/v1/admin/sellable-cards/{id}/enable`
- `POST /api/v1/admin/sellable-cards/{id}/disable`

**测试步骤**:
1. 创建可售卡
2. 编辑可售卡
3. 启用/禁用可售卡
4. 检查列表显示

**预期结果**:
- CRUD 操作正常
- 状态变更生效

#### 6.1.3 服务包定价管理
**接口**:
- `GET /api/v1/admin/service-package-pricing`
- `PUT /api/v1/admin/service-package-pricing`
- `POST /api/v1/admin/service-package-pricing/publish`
- `POST /api/v1/admin/service-package-pricing/offline`

**测试步骤**:
1. 配置服务包定价
2. 发布定价
3. 下架定价

**预期结果**:
- 定价配置正确
- 发布/下架状态正确

#### 6.1.4 场所管理
**接口**:
- `GET /api/v1/admin/venues`
- `POST /api/v1/admin/venues/{id}/publish`
- `POST /api/v1/admin/venues/{id}/reject`
- `POST /api/v1/admin/venues/{id}/offline`

**测试步骤**:
1. 查看场所列表
2. 审核场所（通过/拒绝）
3. 下架场所

**预期结果**:
- 审核流程正常
- 状态更新正确

#### 6.1.5 用户管理
**接口**:
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{id}`

**测试步骤**:
1. 查看用户列表
2. 查看用户详情
3. 测试筛选功能

**预期结果**:
- 用户列表正确显示
- 用户详情完整

#### 6.1.6 订单管理
**接口**:
- `GET /api/v1/admin/orders`
- `POST /api/v1/admin/orders/{id}/ship`
- `POST /api/v1/admin/orders/{id}/deliver`

**测试步骤**:
1. 查看订单列表
2. 发货操作
3. 标记已送达

**预期结果**:
- 订单列表正确
- 发货流程正常

#### 6.1.7 经销商结算管理
**接口**:
- `GET /api/v1/admin/dealer-commission`
- `PUT /api/v1/admin/dealer-commission`
- `GET /api/v1/admin/dealer-settlements`
- `POST /api/v1/admin/dealer-settlements/{id}/mark-paid`

**测试步骤**:
1. 配置分账比例
2. 生成结算单
3. 标记已打款

**预期结果**:
- 分账配置正确
- 结算单生成正确

#### 6.1.8 通知管理
**接口**:
- `GET /api/v1/admin/notifications`
- `POST /api/v1/admin/notifications`
- `GET /api/v1/admin/notification-receivers`

**测试步骤**:
1. 创建通知
2. 选择接收者
3. 发送通知

**预期结果**:
- 通知创建成功
- 接收者收到通知

#### 6.1.9 审计日志
**接口**: `GET /api/v1/admin/audit-logs`

**测试步骤**:
1. 查看审计日志列表
2. 测试筛选功能
3. 检查日志详情

**预期结果**:
- 日志记录完整
- 筛选功能正常

### 6.2 Dealer 经销商功能

#### 6.2.1 投放链接管理
**接口**:
- `GET /api/v1/dealer-links`
- `POST /api/v1/dealer-links`
- `POST /api/v1/dealer-links/{id}/disable`

**测试步骤**:
1. 创建投放链接
2. 查看链接列表
3. 禁用链接

**预期结果**:
- 链接创建成功
- 链接 URL 正确
- 禁用生效

#### 6.2.2 订单归属
**接口**: `GET /api/v1/dealer/orders`

**测试步骤**:
1. 查看订单列表
2. 按支付状态筛选
3. 按投放链接筛选
4. 导出 CSV

**预期结果**:
- 订单列表正确
- 筛选功能正常
- CSV 导出成功

#### 6.2.3 结算账户管理
**接口**:
- `GET /api/v1/dealer/settlement-account`
- `PUT /api/v1/dealer/settlement-account`

**测试步骤**:
1. 查看结算账户信息
2. 更新打款信息

**预期结果**:
- 账户信息正确显示
- 更新成功

### 6.3 Provider 服务提供方功能

#### 6.3.1 工作台
**测试步骤**:
1. 登录 Provider 账号
2. 查看工作台数据

**预期结果**:
- 统计数据正确

#### 6.3.2 商品管理
**接口**:
- `GET /api/v1/provider/products`
- `POST /api/v1/provider/products`
- `PUT /api/v1/provider/products/{id}`

**测试步骤**:
1. 创建商品
2. 编辑商品
3. 提交审核

**预期结果**:
- 商品创建成功
- 审核流程正常

#### 6.3.3 场所管理
**接口**:
- `GET /api/v1/provider/venues`
- `POST /api/v1/provider/venues/{id}/submit-showcase`

**测试步骤**:
1. 查看场所列表
2. 提交展示申请

**预期结果**:
- 申请提交成功

#### 6.3.4 服务配置
**接口**: `POST /api/v1/provider/venues/{venueId}/services`

**测试步骤**:
1. 配置场所服务
2. 设置服务参数

**预期结果**:
- 服务配置成功

#### 6.3.5 预约管理
**接口**:
- `GET /api/v1/provider/bookings`
- `PUT /api/v1/bookings/{id}/confirm`
- `POST /api/v1/provider/bookings/{id}/cancel`

**测试步骤**:
1. 查看预约列表
2. 确认预约
3. 取消预约

**预期结果**:
- 预约管理正常

#### 6.3.6 排班管理
**接口**: `POST /api/v1/provider/venues/{venueId}/schedules/batch`

**测试步骤**:
1. 批量设置排班
2. 检查排班显示

**预期结果**:
- 排班设置成功
- 排班显示正确

#### 6.3.7 核销管理
**接口**: `POST /api/v1/provider/redemptions`

**测试步骤**:
1. 扫描权益码
2. 核销权益

**预期结果**:
- 核销成功
- 权益次数扣减

---

## 7. API 接口测试

### 7.1 接口分类测试

#### 7.1.1 认证相关接口
- [ ] Admin 登录/登出/刷新
- [ ] Dealer 登录/登出/刷新
- [ ] Provider 登录/登出/刷新
- [ ] 小程序登录
- [ ] H5 短信登录
- [ ] 修改密码

#### 7.1.2 用户相关接口
- [ ] 获取用户信息
- [ ] 更新用户信息
- [ ] 用户地址管理（CRUD）

#### 7.1.3 商品相关接口
- [ ] 商品列表/详情
- [ ] 商品分类
- [ ] 购物车操作

#### 7.1.4 订单相关接口
- [ ] 创建订单
- [ ] 订单列表/详情
- [ ] 支付订单
- [ ] 确认收货

#### 7.1.5 权益相关接口
- [ ] 权益列表
- [ ] 权益详情
- [ ] 权益转移

#### 7.1.6 预约相关接口
- [ ] 创建预约
- [ ] 预约列表
- [ ] 确认/取消预约

#### 7.1.7 配置相关接口
- [ ] 小程序配置
- [ ] H5 配置
- [ ] 官网配置
- [ ] 区域配置

### 7.2 接口规范测试

#### 7.2.1 请求格式
- [ ] Content-Type: `application/json`
- [ ] Authorization header 格式正确
- [ ] Idempotency-Key header（写操作）

#### 7.2.2 响应格式
- [ ] 成功响应: `{"success": true, "data": {...}}`
- [ ] 错误响应: `{"success": false, "error": {...}}`
- [ ] 错误码规范（UNAUTHENTICATED, FORBIDDEN 等）

#### 7.2.3 分页参数
- [ ] `page`、`pageSize` 参数
- [ ] 响应包含 `total`、`page`、`pageSize`

#### 7.2.4 幂等性
- [ ] 写操作支持 Idempotency-Key
- [ ] 相同 Key 重复请求返回相同结果

### 7.3 接口性能测试

#### 7.3.1 响应时间
- [ ] 列表接口 < 500ms
- [ ] 详情接口 < 300ms
- [ ] 写操作 < 1000ms

#### 7.3.2 并发测试
- [ ] 100 并发请求
- [ ] 检查错误率
- [ ] 检查响应时间

---

## 8. 边界与异常测试

### 8.1 输入验证

#### 8.1.1 必填字段
**测试步骤**:
1. 不填写必填字段提交
2. 检查错误提示

**预期结果**:
- HTTP 400
- 错误信息明确

#### 8.1.2 字段格式
**测试步骤**:
1. 输入错误格式（如邮箱、手机号）
2. 输入超长字符串
3. 输入特殊字符

**预期结果**:
- 格式验证正确
- 长度限制生效

#### 8.1.3 数值范围
**测试步骤**:
1. 输入负数价格
2. 输入超大数值
3. 输入小数位数超限

**预期结果**:
- 范围验证正确

### 8.2 业务规则验证

#### 8.2.1 库存检查
**测试步骤**:
1. 购买超出库存的商品
2. 并发购买同一商品

**预期结果**:
- 库存不足时拒绝
- 并发控制正确

#### 8.2.2 状态流转
**测试步骤**:
1. 尝试非法状态变更（如已支付订单再次支付）
2. 检查状态机规则

**预期结果**:
- 状态流转正确
- 非法操作被拒绝

#### 8.2.3 权限边界
**测试步骤**:
1. 尝试访问其他用户的资源
2. 尝试跨角色操作

**预期结果**:
- 权限检查正确
- 返回 403

### 8.3 异常场景

#### 8.3.1 网络异常
**测试步骤**:
1. 模拟网络超时
2. 模拟网络断开

**预期结果**:
- 错误提示友好
- 可重试机制

#### 8.3.2 服务异常
**测试步骤**:
1. 停止数据库服务
2. 停止 Redis 服务
3. 检查错误处理

**预期结果**:
- 错误信息明确
- 服务降级（如已实现）

#### 8.3.3 数据一致性
**测试步骤**:
1. 并发操作同一资源
2. 检查数据一致性

**预期结果**:
- 数据一致
- 无脏数据

---

## 9. 性能与稳定性测试

### 9.1 负载测试

#### 9.1.1 接口压力测试
**工具**: Apache Bench / JMeter

**测试场景**:
- 健康检查接口: 1000 请求/秒
- 列表接口: 100 请求/秒
- 详情接口: 200 请求/秒

**预期结果**:
- 响应时间 < 1s
- 错误率 < 1%

#### 9.1.2 数据库压力测试
**测试步骤**:
1. 模拟大量并发查询
2. 检查数据库性能

**预期结果**:
- 查询响应正常
- 无死锁

### 9.2 稳定性测试

#### 9.2.1 长时间运行
**测试步骤**:
1. 系统运行 24 小时
2. 检查内存泄漏
3. 检查错误日志

**预期结果**:
- 无内存泄漏
- 错误率稳定

#### 9.2.2 容器重启
**测试步骤**:
1. 重启后端容器
2. 检查服务恢复

**预期结果**:
- 服务正常恢复
- 数据不丢失

---

## 10. 测试检查清单

### 10.1 功能完整性

- [ ] **基础设施**
  - [ ] 健康检查接口正常
  - [ ] OpenAPI 文档可访问
  - [ ] Metrics 正常
  - [ ] Docker 容器健康

- [ ] **认证授权**
  - [ ] 各角色登录正常
  - [ ] Token 刷新正常
  - [ ] 权限验证正确
  - [ ] 路由守卫正常

- [ ] **H5 购买链路**
  - [ ] 落地页正常
  - [ ] 购买页正常
  - [ ] 订单创建成功
  - [ ] 支付流程正常
  - [ ] 支付结果页正常

- [ ] **小程序使用链路**
  - [ ] 登录正常
  - [ ] 首页正常
  - [ ] 商城功能正常
  - [ ] 订单管理正常
  - [ ] 权益使用正常

- [ ] **管理后台**
  - [ ] Admin 功能完整
  - [ ] Dealer 功能完整
  - [ ] Provider 功能完整

### 10.2 接口测试

- [ ] 所有接口可访问
- [ ] 请求/响应格式正确
- [ ] 错误处理正确
- [ ] 幂等性正确
- [ ] 分页功能正常

### 10.3 边界测试

- [ ] 输入验证正确
- [ ] 业务规则正确
- [ ] 异常场景处理正确
- [ ] 数据一致性正确

### 10.4 性能测试

- [ ] 响应时间符合要求
- [ ] 并发处理正常
- [ ] 稳定性良好

### 10.5 文档与日志

- [ ] API 文档完整
- [ ] 错误日志清晰
- [ ] 审计日志完整

---

## 附录

### A. 测试数据准备脚本

```bash
# 创建测试账号（需在数据库中执行）
# Admin: admin@example.com / password123
# Dealer: dealer@example.com / password123
# Provider: provider@example.com / password123
```

### B. 常用测试命令

```bash
# 健康检查
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready

# 获取 OpenAPI 文档
curl http://localhost:8000/api/v1/openapi.json

# Admin 登录
curl -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"password123"}'

# 查看容器日志
docker logs lhmy_backend
docker logs lhmy_nginx
```

### C. 测试环境配置

- **后端地址**: `http://localhost:8000`
- **前端地址**: `http://localhost`（通过 Nginx）
- **数据库**: `localhost:3306`
- **Redis**: `localhost:6379`

### D. 问题反馈

如发现测试问题，请记录：
1. 测试步骤
2. 预期结果
3. 实际结果
4. 错误日志
5. 环境信息

---

**文档版本**: v1.0  
**最后更新**: 2026-01-06  
**维护者**: 开发团队

