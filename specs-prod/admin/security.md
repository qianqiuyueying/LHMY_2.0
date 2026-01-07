# 安全规范（Security）

## 1. 会话与认证（Session / Auth）

### 1.1 Token 形态与传递
- **传递方式**：`Authorization: Bearer <token>`
- **角色识别**：后端通过 token 解码确定 actorType（见 `facts.md#F-BE-005`）
- **前端会话**：基于 `frontend/admin/src/lib/auth`（待补充事实）

### 1.2 Token 失效与黑名单（Blacklist）
- Admin refresh/logout 将旧 token 加入 Redis blacklist（见 `facts.md#F-BE-006`）
- 解析 actor 时对 ADMIN token 做 blacklist 校验（见 `facts.md#F-BE-005`）

### 1.3 2FA（管理员可选）
- 若管理员账号绑定 phone，则登录流程进入 2FA challenge/verify（见 `facts.md#F-BE-006`）
- challenge 有 TTL（当前实现：10 分钟；见 `admin_auth.py`）

### 1.4 管理员账号与会话安全加固（TASK-P0-005）（v1 草案）
> 目标：把“生产可用的 admin 登录安全策略”固化成可验收口径，避免仅靠原型实现上线。

#### 1.4.1 初始化账号（seed admin）
- **现状**：`admin_auth.py::_ensure_admin_seed` 在 `ADMIN_INIT_USERNAME/ADMIN_INIT_PASSWORD` 有值时，会在登录请求内“若不存在则创建初始账号”。
- **生产要求（必须）**
  - **生产环境禁止自动 seed**：`app_env=production` 时，后端不得在请求路径内自动创建账号（即使 `ADMIN_INIT_*` 被误配置也不生效）。
  - **初始化投放方式（v1）**：提供**一次性初始化脚本**创建首个管理员账号；脚本必须写审计并支持回滚（你已拍板）。
  - **强制改密**：v1 不强制首登改密（若后续要启用需另行拍板）。

#### 1.4.2 密码策略（Password Policy）
- **最小要求（v1）**
  - 长度：**≥ 10**（你已拍板；现状 change-password 仅要求 ≥ 8，需要收敛）
  - 复杂度：**4 选 2**（你已拍板）：大写 / 小写 / 数字 / 特殊字符
  - 弱口令黑名单：启用最小黑名单（你已拍板）
    - v1 最小集合：`1234567890`, `12345678`, `password`, `admin123`, `qwertyuiop`
- **存储要求**：只存 `password_hash`；禁止任何日志/审计记录密码明文（现状满足）。

#### 1.4.3 登录失败锁定（Anti-Bruteforce）
- **目标**：限制撞库与短信轰炸；返回可解释错误码，不泄露“账号存在性”。
- **策略（v1 口径，你已拍板）**
  - 同一 `username` 在滚动窗口 **10 分钟** 内失败次数 **≥ 5**：进入锁定，锁定持续 **30 分钟**
  - 锁定期间：
    - `POST /admin/auth/login`：返回 429 `RATE_LIMITED`（不新增错误码）
    - `POST /admin/auth/2fa/challenge`：同样受限（避免短信轰炸）
  - **不泄露账号存在性**：对“账号不存在/密码错误/被锁定”返回同一类文案（后端可用 error.code 区分给前端动作）。
- **审计/安全日志（v1）**
  - 登录成功：必须审计（现状已做）
  - 登录失败：建议写入“安全日志”或审计（resourceType=`ADMIN_AUTH`，action=`LOGIN_FAILED` 或 `UPDATE` + metadata 标注）（TBD：拍板）

#### 1.4.4 2FA 策略（SMS 2FA）
- **触发条件（现状）**：admin 配置 `phone` 即启用 2FA。
- **生产要求（v1）**
  - 2FA 按账号可选开关：**未绑定 phone 允许登录**（你已拍板）
  - 未绑定 phone：必须提示绑定；且**高风险操作前置要求先绑定**（绑定动作需审计）
  - resend/verify 限流：必须启用（SmsCodeService 已有 RATE_LIMITED 口径；与登录锁定共同生效）

#### 1.4.5 会话与 Token（Admin）
- **access token TTL**：`jwt_admin_access_expire_seconds`（现状 2 小时）
- **refresh 策略（现状）**：refresh 会把旧 token jti 写入 blacklist（TTL=旧 token 剩余时间），新 token 重新签发。
- **logout 策略（现状）**：logout 同样写入 blacklist，并写审计（现状已做）。
- **并发会话（TBD）**：是否允许同一 admin 多端同时在线（当前允许）；若需“单点登录”需单独拍板与实现。

#### 1.4.6 待你确认点（进入编码前必须拍板）
> 已拍板（Batch14）：本节关闭。

## 2. 越权防护（Authorization / Anti-Privilege Escalation）

### 2.1 安全边界原则
- **后端为安全边界**：必须使用 `require_admin`（或等价）在后端强制鉴权
- 前端路由守卫仅为 UX，不可当作权限保证（见 `requirements.md#R-SEC-001`）

### 2.2 最小权限与敏感信息
- **列表接口默认脱敏**：例如用户列表 `phoneMasked`（见 `facts.md#F-BE-007`）
- **敏感字段**（示例）：手机号明文、身份证、银行卡号、支付流水号、结算凭证等
  - 需要明确：权限门槛、审计、展示/导出脱敏策略

### 2.3 敏感信息治理（PII / Secrets）（v1 草案）
> 目标：把“哪些字段算敏感、在列表/详情/导出/审计分别怎么处理”固化成可验收规则，避免各接口各写一套。

#### 2.3.1 分类与范围
- **认证/安全类 Secrets（严禁出参明文）**
  - token / authorization / password / password_hash / smsCode / otp / 2FA code
- **个人可识别信息 PII（默认脱敏）**
  - 手机号、姓名、身份证号、银行卡号、开户地址、详细地址、联系方式
- **资金/结算敏感**
  - 结算账户号（accountNo）、结算凭证号（payoutReference）、结算账户快照（payoutAccount_json）
- **履约/订单敏感**
  - 收货地址快照（shippingAddress / shipping_address_json）
  - 运单号（shippingTrackingNo）
- **权益/核销敏感（等同“可用凭证”）**
  - `qrCode`（二维码 payload 文本）、`voucherCode`（券码）

#### 2.3.2 三类出参场景规则（必须统一）
- **列表（List）**
  - 默认 **不返回明文** PII/Secrets（只返回 `*Masked` / `*Last4` / 聚合信息）
  - 例：手机号只返回 `phoneMasked` / `buyerPhoneMasked`
- **详情（Detail）**
  - 默认仍 **不返回明文** Secrets
  - PII 若业务确需展示明文，必须满足：规格明确 + 权限门槛 + 审计（TBD：是否需要“查看明文”也记审计）
- **导出（Export）**
  - 只能导出 **字段白名单**
  - 默认只允许 **脱敏字段**（手机号仅 `*Masked`）；禁止导出 token/券码/二维码payload/银行卡号明文等

#### 2.3.3 脱敏口径（v1 最小）
- **phoneMasked**：`138****1234`（前 3 后 4）
- **accountNoMasked**：仅保留后 4 位（其余 `*`）
- **trackingNoLast4**：仅保留后 4 位（其余 `*`）
- **address**：v1 不定义通用“地址脱敏算法”；若必须返回 `shippingAddress`，则其内部任何 `phone/contactPhone` 字段必须脱敏（TBD：详细地址是否允许返回）

#### 2.3.4 现状证据（已存在/已发现）
- **已做（正向）**
  - Admin 用户查询仅返回 `phoneMasked`：`backend/app/api/v1/admin_users.py::_user_list_item/_user_detail`
  - 审计日志查询对 metadata 兜底脱敏（password/token/authorization/smsCode/phone）：`backend/app/api/v1/audit_logs.py::_mask_sensitive`
  - 导出经销商订单 CSV 导出手机号为 `_mask_phone`：`backend/app/api/v1/dealer.py::export_dealer_orders_csv`
  - 经销商结算账户出参有 `accountNoMasked`：`backend/app/api/v1/dealer.py::get_dealer_settlement_account`
- **待治理（风险点，需拍板后落地）**
  - Admin 订单列表/详情返回 `shippingTrackingNo` 与 `shippingAddress`（可能包含详细地址/电话）：`backend/app/api/v1/orders.py::admin_list_orders`、`_order_dto`
  - 经销商结算列表返回 `payoutReference` 与 `payoutAccount`（疑似包含敏感明文）：`backend/app/api/v1/dealer.py::list_dealer_settlements`
  - 经销商结算账户返回 `contactPhone` 明文：`backend/app/api/v1/dealer.py::get_dealer_settlement_account`
  - 场所详情返回 `contactPhone` 明文（多端）：`backend/app/api/v1/admin_venues.py::_venue_detail_item`、`backend/app/api/v1/provider.py`、`backend/app/api/v1/venues.py`
  - 权益接口对 USER 返回 `qrCode/voucherCode`（可用凭证）：`backend/app/api/v1/entitlements.py::_entitlement_dto`

#### 2.3.5 待你确认点（进入编码前必须拍板）
1) **运单号 / 收货地址**
   - Admin 订单列表与详情是否允许返回 `shippingTrackingNo` 明文？还是统一改为 `trackingNoLast4`？
   - `shippingAddress`（JSON）是否允许返回详细地址/手机号？还是只返回“省市区 + 脱敏手机号”（或完全不返回）？
2) **结算信息**
   - `payoutReference` 是否允许明文展示？（建议：只返回 `payoutReferenceLast4`）
   - `payoutAccount`（JSON）字段是否必须做白名单/脱敏？
3) **场所联系信息**
   - `contactPhone`：Admin/Provider/公开端各自的展示口径是否统一为 `contactPhoneMasked`？如需明文，是否需要额外权限与审计？
4) **权益凭证**
   - `qrCode/voucherCode` 是否允许在任何 Admin 页面/接口明文出现？（建议：Admin 侧禁止出参明文，仅用于核销流程内部校验）

## 3. 审计（Audit）

### 3.1 必审计操作（Baseline）
高风险操作必须审计（资金/结算/审核发布/导出/权限/账号管理/配置发布）。

#### 3.1.1 高风险事件覆盖清单（v1 草案，作为覆盖率分母）
> 说明：本清单用于定义“覆盖率”的分母（哪些事件必须有业务审计记录）。后续新增高风险线路时必须同步补充本清单。
>
> v1 以已落地/已拍板的线路为主，避免空泛。

- **EXPORT**
  - `resourceType=EXPORT_DEALER_ORDERS`（导出经销商订单 CSV）
- **FUNDS / SETTLEMENT**
  - `resourceType=DEALER_SETTLEMENT_BATCH`（生成结算批次）
  - `resourceType=DEALER_SETTLEMENT`（标记结算单已结算/已打款）
- **FULFILLMENT / ORDER**
  - `resourceType=ORDER`（发货 ship、妥投 deliver）
- **LINKS**
  - `resourceType=DEALER_LINK`（创建投放链接、停用投放链接）
- **BOOKINGS**
  - `resourceType=BOOKING`（ADMIN 强制取消）

### 3.2 审计字段（最小集合）
- **actor**：actorType、actorId
- **action**：动作类型（LOGIN/LOGOUT/UPDATE/EXPORT/...）
- **resource**：resourceType/resourceId
- **summary**：可读摘要（不包含敏感信息）
- **request**：requestId、path、method、ip、userAgent
- **metadata**：必要元数据（必须可 JSON 序列化）

### 3.3 现状证据（已存在）
- Admin 登录/登出会写入 `AuditLog`（见 `facts.md#F-BE-006`）
- 其他高风险操作是否已审计：TBD（需在 tasks 中逐项补齐）

### 3.4 时间与时区口径（审计日志查询）（你已拍板）

> 目标：避免“服务器/容器时区不一致”导致审计时间展示偏移；同时让日期筛选符合运营侧的北京时间自然日直觉。

- **全站契约**：见 `specs/health-services-platform/time-and-timezone.md`
- **存储层（DB）**：统一按 **UTC** 存储（MySQL `DATETIME` 视为“UTC 的无时区时间”）
- **API 出参（`/api/v1/admin/audit-logs`）**
  - `createdAt`：统一输出为 **UTC** 的 ISO 8601 字符串，且必须带 `Z`（例如 `2026-01-07T12:34:56Z`）
- **API 入参（筛选）**
  - `dateFrom/dateTo`：前端传 `YYYY-MM-DD`（来自管理端日期选择器）
  - 后端解释口径：按 **北京时间（UTC+8）自然日** 解释并转换为 UTC 再查询
    - `dateFrom` → 北京时间当日 00:00:00（含）→ 转 UTC
    - `dateTo` → 北京时间当日 23:59:59（含）；实现上建议用“次日 00:00:00（不含）”以 `<` 查询表达
- **前端展示（Admin 审计日志页）**
  - 列表“时间”统一展示为北京时间（UTC+8），不直接裸显示后端 `createdAt` 原文

## 4. 输入校验与注入防护
- **参数校验**：必须在 Pydantic/业务逻辑中明确校验（例如 cycle 格式、rate 0~1、URL 必须 http(s)）
- **JSON 校验**：配置类接口应确保 JSON 可序列化（见 `admin_website_config.py` 的 `_ensure_json_serializable`）

## 5. 导出安全（Export Safety）——占位
### 5.1 目标与原则（Baseline）
- **后端为安全边界**：生产导出必须由后端端点执行并受 RBAC/数据范围约束；禁止仅靠前端本地导出作为“生产导出”能力
- **最小化数据**：导出字段必须显式列白名单；默认只允许脱敏字段（如手机号仅 `phoneMasked`）
- **可追溯**：每次导出必须产出审计事件（actor/resource/filters/rows/requestId）
- **可控**：必须有最大行数、速率限制与失败可解释的错误码

### 5.2 导出类型（v1 最小）
- **类型 A：后端同步生成并直接下载（推荐 v1）**
  - 不落盘：导出内容直接以 `Content-Disposition: attachment` 返回
  - **文件生命周期**：不存储文件，即“下载即销毁”（TTL=0）
  - 适用：行数可控（例如 <= 5k/10k），生成耗时可控（例如 < 10s）
- **类型 B：后端异步导出（vNext，需单独拍板）**
  - 生成任务 + 文件对象（S3/本地）+ TTL 清理 + 下载鉴权

### 5.3 必备控制项（必须全有）
- **权限门槛**：导出端点必须鉴权（ADMIN/DEALER/PROVIDER）；并强制数据范围（例如 DEALER 仅导出本 dealer 订单）
- **字段与脱敏**：明确字段白名单；PII 仅导出脱敏形式；禁止导出 token/验证码/银行卡号明文等
- **最大行数**：必须设置 `maxRows`（默认 5000；可按场景调整）；超限返回 400 `INVALID_ARGUMENT`
- **过滤约束**：高风险导出必须要求至少一个“收敛过滤条件”（如 dateFrom/dateTo）避免全量导出
- **限流**：按 actor 维度限制导出频率（例如 5 次/分钟），超限返回 429 `RATE_LIMITED`（若现状无 429 统一机制，则先用 400/409 占位，需拍板）
- **审计**：action 建议为 `UPDATE` 或新增 `EXPORT`（若不新增枚举则先用 UPDATE，需在 `api-contracts.md` 拍板）
  - metadata 最小字段：`requestId`, `exportType`, `filters`, `rowCount`, `fields`

### 5.4 现状与改造入口（证据）
- 前端存在本地 CSV 导出：`frontend/admin/src/pages/dealer/DealerOrdersPage.vue::exportCsv`
- 后端暂无专用导出端点：需按 `api-contracts.md` 固化后新增/改造


