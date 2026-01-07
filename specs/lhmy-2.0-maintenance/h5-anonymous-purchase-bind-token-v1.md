## 规格：H5 匿名购卡 + bind_token 跨端绑定（v1）

### 1. 规格来源与不可更改共识

本规格**直接来源于用户在 2026-01-07 提供的“全局设计共识（不可更改）”**，用于约束本仓库接下来的实现与改造范围。

#### 1.1 H5 端（不可更改）

- **H5 不建立用户登录态**
- **H5 不使用微信登录**
- **H5 不识别小程序用户身份**
- **H5 不维护用户会话、token、账号体系**
- **购卡与用户归属解耦**
- **购卡仅生成「未绑定卡（UNBOUND）」**
- **购卡阶段不绑定小程序用户**
- **H5 页面不提供“个人购卡列表”**
- **资产找回责任不在匿名用户**
  - 匿名用户丢失页面 ≠ 系统异常
  - 购卡资产可通过 dealer / admin 找回

#### 1.2 小程序端（不可更改）

- 小程序负责所有「人相关」行为：登录/卡绑定/卡激活/卡使用/卡赠送
- 小程序需支持：
  - 通过 `bind_token` 打开并绑定
  - 小程序内「绑定卡」入口（兜底）
- 绑定行为规则：
  - 仅允许 `UNBOUND -> BOUND`
  - 幂等（重复提交不应产生副作用）
  - 已绑定卡不可再次绑定

#### 1.3 Dealer / Admin（不可更改）

- Dealer 后台至少支持：
  - 查看售出的订单 / 卡
  - 为订单重新生成 `bind_token`
  - 将绑定链接发送给用户
- Admin 后台至少支持：
  - 通过支付流水 / 订单号查询卡
  - 手动生成绑定入口（兜底）
- 不需要处理历史脏数据（当前为开发阶段）

#### 1.4 唯一跨端桥梁：bind_token（不可更改）

- `bind_token` 由后端生成
- 可重复使用（在未绑定前）
- 有有效期
- 绑定成功后失效
- 不依赖前端 localStorage / cookie / session

### 2. H5 改造范围（只做这些）

H5 只负责：
- 展示商品
- 下单
- 支付
- 展示“去小程序绑定”的入口

支付完成页必须提供：
- 明确提示：卡尚未绑定
- 一个跳转小程序的绑定入口（携带 `bind_token`）
- 文案提示：可稍后通过经销商找回

H5 不实现：
- 登录
- 购卡记录列表
- 用户中心
- 绑定逻辑

### 2.1 后端支撑接口（v1 最小契约）

> 说明：H5 不维护登录态，因此需要提供“按订单号读取 bind_token”的只读接口。

#### 2.1.1 `GET /api/v1/h5/orders/{orderId}/bind-token`

用途：
- H5 支付完成页展示“卡尚未绑定”与“去小程序绑定入口”

鉴权：
- **无需登录**（匿名可调用）

响应（200）：
- `orderId`: string
- `cardId`: string（v1：等同 orderId）
- `cardStatus`: `"UNBOUND" | "BOUND" | null`
- `bindToken`: string | null（若支付回调尚未发卡或 token 已失效则为 null）
- `expiresAt`: string | null（ISO 时间；bindToken 为空时为 null）

错误：
- 404 `NOT_FOUND`：订单不存在

#### 2.1.0（新增）微信内一键拉起所需：`GET /api/v1/h5/wechat/jssdk-config`

用途：
- H5 在微信内使用 `wx.config` 初始化 JS-SDK，使 `wx-open-launch-weapp` 可一键拉起小程序

鉴权：
- 无需登录（匿名可调用）

请求：
- Query `url`: string（当前页面 URL，**不含 hash**，例如 `location.href.split('#')[0]`）

响应（200）：
- `appId`: string（公众号 appid）
- `timestamp`: number
- `nonceStr`: string
- `signature`: string（sha1 签名）

依赖配置（env）：
- `WECHAT_H5_APPID`
- `WECHAT_H5_SECRET`

#### 2.1.2 `POST /api/v1/orders`（H5 购卡：允许匿名）

用途：
- H5 创建购卡订单（v1：一单一张卡）

鉴权：
- 当 `orderType=SERVICE_PACKAGE` 时：**允许不带 Authorization**（匿名）

约束（v1）：
- `orderType=SERVICE_PACKAGE` 且 `items.length=1` 且 `items[0].quantity=1`
- 必须携带 `dealerLinkId`（query）

响应：
- 沿用现有订单 DTO（最小需要 `id` 作为 orderId）

#### 2.1.3 `POST /api/v1/orders/{id}/pay`（H5 购卡：微信 H5 MWEB）

用途：
- H5 发起支付（v1：微信 H5/MWEB，不依赖 openid）

鉴权：
- 对 SERVICE_PACKAGE：允许匿名

响应（200）：
- `orderId`: string
- `paymentStatus`: `"PENDING" | "FAILED" | ...`
- `wechatH5Url`: string（当 `paymentStatus=PENDING` 时返回，H5 跳转该 URL 完成支付）

### 3. 数据模型约束（不可擅改）

#### 3.1 Card

Card 必须具备：
- `id`
- `status`（`UNBOUND` / `BOUND`）
- `owner_user_id`（nullable）

#### 3.2 BindToken

BindToken 必须具备：
- `token`
- `card_id`
- `expires_at`
- `used_at`（nullable）

有效期：
- 由后端生成并写入 `expires_at`
- 通过环境变量 `BIND_TOKEN_EXPIRE_SECONDS` 控制
- v1 默认：24 小时（86400 秒）

### 4. 行为边界（不可更改）

- 不要为了“用户体验”引入隐式绑定
- 不要为了“省一步操作”破坏身份边界
- 不要假设用户会一次性完成流程
- 不要引入“浏览器状态 = 资产归属”的设计

### 5. 本次实现需要补齐/确认的关键口径（阻塞项）

> 说明：以下问题若不明确，会导致实现时被迫“自行设计”，从而违反你给的边界。

1) **H5 支付方式与后端契约（已确认）**
- **支付方式**：微信 H5（MWEB）
- **约束**：不使用微信登录，不依赖 `openid`
- **契约期望（v1）**：后端下单后返回/提供 MWEB 所需参数（例如 `mweb_url` 或跳转 URL）；H5 仅负责跳转与展示结果，不维护 token。

2) **“支付成功”触发点（已确认）**
- **发卡时机**：以支付回调确认成功为准（生成 UNBOUND Card + bind_token）

3) **购买数量（已确认）**
- **v1 强制只买 1 张**（前端限制 + 后端校验）

4) **卡/权益处理（已确认）**
- **支付成功**：生成 **UNBOUND Card（含权益）**
- **绑定成功**：才将卡与权益归属到小程序用户（更新 `owner_user_id`，并完成权益归属迁移/落库）

补充口径（v1 已确认）：
- 支付成功后生成权益时，`Entitlement.owner_id`（以及兼容字段 `Entitlement.user_id`）**临时写入 `Card.id`**
- 绑定成功后，才将上述字段迁移为小程序 `User.id`
- 同步迁移 `ServicePackageInstance.owner_id`：从 `Card.id` -> `User.id`

订单与卡的关联（v1 已确认）：
- **一单一张卡**
- **Card.id = Order.id**（支付成功后，以订单号作为卡号生成 UNBOUND Card）

5) **bind_token 策略（已确认）**
- **滚动策略**：生成新 token 时作废旧 token（仅限 `Card.status=UNBOUND`）
- **失效**：绑定成功后 token 失效（`used_at` 置值 + 不可再用）

6) **绑定路径与拉起方式（已确认）**
- **小程序路径**：`pages/card/bind-by-token?token=...`
- **H5 拉起方式**：H5 在微信内，通过 `wx-open-launch-weapp` 拉起

### 6. 小程序绑定接口（v1 最小契约）

#### 6.1 `POST /api/v1/mini-program/cards/bind-by-token`

鉴权：
- 必须携带小程序 `Authorization: Bearer <token>`（channel=MINI_PROGRAM）

请求体：
- `token`: string（bind_token）

行为：
- 校验 bind_token 存在、未过期、未使用/未作废
- 仅允许 `Card.status: UNBOUND -> BOUND`
- 幂等：
  - 若卡已绑定且 `owner_user_id == 当前用户`：返回 200（no-op）
  - 若卡已绑定但归属他人：返回 409
- 绑定成功后：
  - `Card.owner_user_id = 当前用户`
  - `Card.status = BOUND`
  - `BindToken.used_at` 置值（失效）
  - 迁移权益/实例归属：`Entitlement.owner_id/user_id`、`ServicePackageInstance.owner_id` 从 `cardId` -> `userId`

响应（200）：
- `cardId`: string
- `status`: `"BOUND"`
- `alreadyBound`: boolean

### 7. Dealer/Admin 兜底接口（v1 最小契约）

#### 7.1 `POST /api/v1/dealer/orders/{orderId}/bind-token/regenerate`

用途：
- Dealer / Admin 为订单重新生成绑定凭证，并发送给用户（兜底）

鉴权：
- Dealer token 或 Admin token

约束：
- 仅限已支付订单
- 仅限 `Card.status=UNBOUND`
- 生成新 token 时作废旧 token（滚动）

响应（200）：
- `orderId`: string
- `cardId`: string（v1：等同 orderId）
- `bindToken`: string
- `expiresAt`: string（ISO）
- `miniProgramPath`: string（例如 `pages/card/bind-by-token?token=...`）


