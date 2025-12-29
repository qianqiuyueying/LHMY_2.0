## 完成事实清单：微信小程序（frontend/mini-program）

> 口径：只写“事实”（已经存在的行为/代码结构），每条都给出**证据入口**（文件路径/接口路径/关键函数）。

### A) 入口与全局配置

- [x] 小程序入口为原生小程序 `App({ ... })`  
  - 证据：`frontend/mini-program/app.js`
- [x] 外链打开（web-view）存在统一承载页：当页面无法加载时展示错误态；并对“业务域名未配置导致不触发 error”的场景提供超时兜底提示  
  - 证据：`frontend/mini-program/pages/webview/webview.js`、`frontend/mini-program/pages/webview/webview.wxml`
- [x] API BaseUrl 读取规则：
  - develop/trial：允许默认 `http://127.0.0.1:8000`
  - release：不允许默认指向本地；必须显式配置 `storage.apiBaseUrl`
  - 实现侧避免依赖可选链语法，防止在部分基础库/构建配置下导致模块加载异常
  - 证据：`frontend/mini-program/utils/config.js` `getApiBaseUrl()`
- [x] 全局数据中保存 `token`、`userInfo`、`apiBaseUrl`  
  - 证据：`frontend/mini-program/app.js` `globalData`

### B) 统一请求封装（网络/鉴权/幂等/诊断信息）

- [x] 统一 API 封装存在（Promise 化、统一错误提示、支持静默模式）  
  - 证据：`frontend/mini-program/utils/api.js` `request()/get()/post()/put()/del()`（非 200 也按统一 envelope 解析，避免“请求失败 500/无信息”）
- [x] 请求头注入 `Authorization: Bearer <token>`（可选）  
  - 证据：`frontend/mini-program/utils/api.js` `needAuth` 分支
- [x] 请求头注入 `X-Request-Id`（用于端到端定位）  
  - 证据：`frontend/mini-program/utils/api.js` `genRequestId()` + header 合并
- [x] 写操作可带 `Idempotency-Key`（由调用方传入 header；工具函数生成）  
  - 证据：`frontend/mini-program/utils/api.js` `genIdempotencyKey()` + header 合并
- [x] 端侧保存最近一次 API 诊断事件到 storage：`lastApiEvent`（纯文字元数据）  
  - 证据：`frontend/mini-program/utils/api.js` `_safeSetLastApiEvent()`

### C) 登录与会话

- [x] 启动时检查 token 并验证：`GET /api/v1/users/profile`  
  - 证据：`frontend/mini-program/app.js` `checkLogin()` / `validateToken()`
- [x] 小程序登录：`POST /api/v1/mini-program/auth/login`  
  - 证据：`frontend/mini-program/app.js` `login()`
- [x] 开发环境兜底：检测“微信登录配置缺失”时使用 mock code 重试（`mock:unionid:<ts>`）  
  - 证据：`frontend/mini-program/app.js` `login()` 内 mock 分支说明

### D) 页面与接口依赖（按模块，列出关键调用点）

> 注：以下仅列出小程序侧明确出现的请求路径（可作为升级时的“关键节点清单”）。

#### D1) 首页/入口配置

- [x] 小程序入口配置：`GET /api/v1/mini-program/entries`（未登录、静默）  
  - 证据：`frontend/mini-program/pages/index/index.js`
- [x] 首页 Banner（Swiper）点击跳转统一走 `navigateByJump(jumpType, targetId)`  
  - 证据：`frontend/mini-program/utils/navigate.js`、`frontend/mini-program/pages/index/index.js`
- [x] 首页 Banner 图片加载失败时自动回退展示占位块（避免“空白但无反馈”）  
  - 证据：`frontend/mini-program/pages/index/index.wxml`、`frontend/mini-program/pages/index/index.js`
- [x] 小程序端静态图片 URL 绝对化：当 url 以 `/static/` 或 `static/` 开头时，会自动拼接 `apiBaseUrl` 形成可请求的绝对 URL（减少运营/手工粘贴导致的“图片不显示”）  
  - 证据：`frontend/mini-program/pages/index/index.js` `_absStaticUrl()`、`frontend/mini-program/pages/mall/mall.js` `_absStaticUrl()`、`frontend/mini-program/pages/aggregate/aggregate.js` `_absStaticUrl()`（SIDEBAR_GRID 图标）
- [x] 首页顶部搜索栏：已移除“区域选择”按钮（避免占位影响搜索区布局）  
  - 证据：`frontend/mini-program/pages/index/index.wxml`、`frontend/mini-program/pages/index/index.wxss`
- [x] 聚合/信息页配置：
  - `GET /api/v1/mini-program/pages/{pageId}`
  - `GET /api/v1/mini-program/collections/{collectionId}/items`
  - 证据：`frontend/mini-program/pages/aggregate/aggregate.js`、`frontend/mini-program/pages/info/info.js`

#### D2) 商城/商品

- [x] 商品分类：`GET /api/v1/product-categories`  
  - 证据：`frontend/mini-program/pages/mall/mall.js`
- [x] 商品列表：`GET /api/v1/products`  
  - 证据：`frontend/mini-program/pages/mall/mall.js`、`frontend/mini-program/pages/index/index.js`
- [x] 商品详情：`GET /api/v1/products/{productId}`  
  - 证据：`frontend/mini-program/pages/mall/product-detail/product-detail.js`

#### D3) 订单与支付

- [x] 创建订单：`POST /api/v1/orders`（Header: `Idempotency-Key`）  
  - 证据：`frontend/mini-program/pages/mall/cart/cart.js`、`frontend/mini-program/pages/mall/product-detail/product-detail.js`
- [x] 订单列表：`GET /api/v1/orders`  
  - 证据：`frontend/mini-program/pages/order/order.js`
- [x] 订单详情：`GET /api/v1/orders/{orderId}`  
  - 证据：`frontend/mini-program/pages/order/order-detail/order-detail.js`
- [x] 发起支付：`POST /api/v1/orders/{orderId}/pay`（Header: `Idempotency-Key`）并调用 `wx.requestPayment()`  
  - 证据：`frontend/mini-program/pages/order/order-detail/order-detail.js`
 - [x] 物流商品：确认收货：`POST /api/v1/orders/{orderId}/confirm-received`  
   - 证据：`frontend/mini-program/pages/order/order-detail/order-detail.js`

#### D4) 权益与预约

- [x] 权益列表：`GET /api/v1/entitlements`  
  - 证据：`frontend/mini-program/pages/entitlement/entitlement.js`
- [x] 权益详情：`GET /api/v1/entitlements/{id}`  
  - 证据：`frontend/mini-program/pages/entitlement/entitlement-detail/entitlement-detail.js`
- [x] 预约列表：`GET /api/v1/bookings`；取消：`DELETE /api/v1/bookings/{id}`  
  - 证据：`frontend/mini-program/pages/booking/booking.js`
- [x] 创建预约：`POST /api/v1/bookings`（Header: `Idempotency-Key`）  
  - 证据：`frontend/mini-program/pages/booking/date-slot-select/date-slot-select.js`
- [x] 独立预约（基建联防服务型商品）：先解析上下文，再创建预约  
  - `GET /api/v1/bookings/order-item-context?orderId=...&orderItemId=...`  
  - 证据：`frontend/mini-program/pages/order/order-detail/order-detail.js`、`frontend/mini-program/pages/booking/date-slot-select/date-slot-select.js`
- [x] 场所选择：`GET /api/v1/venues`（可带筛选参数）  
  - 证据：`frontend/mini-program/pages/booking/venue-select/venue-select.js`
- [x] 可预约时段：`GET /api/v1/venues/{venueId}/available-slots`  
  - 证据：`frontend/mini-program/pages/booking/date-slot-select/date-slot-select.js`

#### D5) 场所

- [x] 场所列表：`GET /api/v1/venues`  
  - 证据：`frontend/mini-program/pages/index/index.js`
- [x] 场所详情：`GET /api/v1/venues/{venueId}`  
  - 证据：`frontend/mini-program/pages/venue-detail/venue-detail.js`

#### D6) 地区/企业绑定/客服支持

- [x] 地区城市配置：`GET /api/v1/regions/cities`  
  - 证据：`frontend/mini-program/pages/index/index.js`
- [x] 收货地址簿：
  - 列表：`GET /api/v1/user/addresses`
  - 新增：`POST /api/v1/user/addresses`
  - 编辑：`PUT /api/v1/user/addresses/{id}`
  - 删除：`DELETE /api/v1/user/addresses/{id}`
  - 设默认：`POST /api/v1/user/addresses/{id}/set-default`
  - 证据：`frontend/mini-program/pages/address/address-list/address-list.js`、`frontend/mini-program/pages/address/address-edit/address-edit.js`、`frontend/mini-program/pages/profile/profile.js`
- [x] 我的资料：`GET /api/v1/users/profile`  
  - 证据：`frontend/mini-program/pages/profile/profile.js`
- [x] 发送短信（绑手机场景）：`POST /api/v1/auth/request-sms-code`（scene=`MP_BIND_PHONE`）  
  - 证据：`frontend/mini-program/pages/profile/profile.js`
- [x] 绑手机：`POST /api/v1/mini-program/auth/bind-phone`  
  - 证据：`frontend/mini-program/pages/profile/profile.js`
- [x] 企业绑定：`POST /api/v1/auth/bind-enterprise`（需要 `enterpriseName` + `cityCode`；选择建议时可带 `enterpriseId`）  
  - 证据：`frontend/mini-program/pages/profile/enterprise-bind/enterprise-bind.js`、`enterprise-bind.wxml`
- [x] FAQ/条款复用 H5：`GET /api/v1/h5/landing/faq-terms`  
  - 证据：`frontend/mini-program/pages/support/support.js`

#### D7) AI 对话

- [x] AI chat：`POST /api/v1/ai/chat`（Header: `Idempotency-Key`）  
  - 证据：`frontend/mini-program/pages/ai-chat/ai-chat.js`


