## 实施任务清单（可勾选）

> 说明：这是“规格 → 实现 → 回归”的最强索引。  
> 本轮先做 **事实基线**：把系统“已经是什么”写清楚（对应 `facts/*.md`），再在此基础上提出升级需求与验收标准。

### 0) 文档维护门禁（所有升级都必须遵守）

- [x] `specs/health-services-platform/README.md` 存在，并且包含本轮范围与入口索引
- [x] `specs/health-services-platform/design.md` 定义上线 DoD 与兼容性原则
- [x] 每个系统都有“完成事实清单”且包含证据入口（文件路径/接口路径/关键函数）
  - [x] `specs/health-services-platform/facts/admin.md`
  - [x] `specs/health-services-platform/facts/website.md`
  - [x] `specs/health-services-platform/facts/h5.md`
  - [x] `specs/health-services-platform/facts/mini-program.md`
  - [x] `specs/health-services-platform/facts/backend.md`
- [x] 每次升级完成后：同步更新对应 `facts/*.md` 中的事实项（新增/变化/废弃）
- [x] 每次升级完成后：在本文件追加“变更记录”（需求 → 改动点 → 风险/回滚 → 事实清单更新位置）

### 1) 系统范围确认（多端统一）

- [x] 纳入：`frontend/admin`、`frontend/website`、`frontend/h5`、`frontend/mini-program`、`backend`

### 2) P0：可部署、可上线可用（最小）

#### 2.1 后端（docker 口径）

- [x] 生产环境启动门禁存在（避免默认密钥上线）  
  证据：`backend/app/main.py` `_validate_production_settings()`
- [x] OpenAPI 兼容入口存在（`/api/v1/openapi.json`）  
  证据：`backend/app/api/v1/openapi_proxy.py`
- [x] Metrics 暴露（`/metrics`，不进入 schema）  
  证据：`backend/app/main.py` `Instrumentator().expose(... endpoint="/metrics")`

#### 2.2 H5（购买链路）

- [x] 路由与页面入口明确（落地/购买/支付结果）  
  证据：`frontend/h5/src/main.ts`
- [x] H5 下单与支付 API 调用点明确（订单创建/发起支付）  
  证据：`frontend/h5/src/pages/BuyPage.vue`

#### 2.3 小程序（使用链路）

- [x] API BaseUrl 规则明确（release 不允许默认 127）  
  证据：`frontend/mini-program/utils/config.js`
- [x] 小程序登录/绑手机调用点明确  
  证据：`frontend/mini-program/app.js`、`frontend/mini-program/pages/profile/profile.js`
- [x] 下单/支付调用点明确  
  证据：`frontend/mini-program/pages/mall/*`、`frontend/mini-program/pages/order/*`

### 3) 后续迭代（留空，等你提升级需求后再填）

> 本节是“升级需求规格”的落点：你的升级需求应写在这里。  
> 规则：每条需求必须包含【背景/问题、目标、范围(页面/接口/函数)、验收标准、兼容性约束、风险与回滚】。

#### 3.1 Admin 升级需求（含 Dealer / Provider 子系统）

- [x] **REQ-ADMIN-P0-001：未登录访问的报错体验优化（统一跳转登录 + Toast）**
  - **背景/问题**：当前未登录访问受保护路由时，报错信息直接展示在页面（error message + 页面文案重复）。
  - **目标**：未登录时统一跳转登录页，并弹一次错误提示即可（避免页面重复报错占位）。
  - **范围（候选）**：
    - 路由守卫：`frontend/admin/src/router/index.ts`
    - 登录页：`frontend/admin/src/pages/LoginPage.vue`
  - **验收标准（DoD）**：
    - [x] 未登录访问任意 `meta.role` 路由：自动跳转 `/login?next=...`
    - [x] 登录页出现一次 toast/message：内容如“请先登录”
    - [x] 登录页不再额外展示重复的页面级错误块（若已有）
    - [x] 登录成功后若 `next` 指向其他身份页面，则忽略 next 并跳转到当前身份默认首页（避免“登录成功但跳 403/无权限”）
  - **兼容性约束**：不改变现有路由路径与角色判定；仅优化提示与跳转体验。
  - **实现证据（文本）**：`frontend/admin/src/router/index.ts`、`frontend/admin/src/pages/LoginPage.vue`、`frontend/admin/src/lib/api.ts`

- [ ] **REQ-ADMIN-P1-015：登录失败次数过多时展示“可重试倒计时”**
  - **背景/问题**：当前登录失败次数过多后，只提示“登录失败/请稍后重试”，但缺少“还需等待多久”的计时信息，导致反复点击与误判。
  - **目标**：登录被锁定时明确展示剩余等待时间，并在倒计时结束后允许继续尝试登录。
  - **范围（候选）**
    - 前端：`frontend/admin/src/pages/LoginPage.vue`
    - 后端：`backend/app/api/v1/*_auth.py`（ADMIN/PROVIDER/DEALER 登录接口若共用限流逻辑需对齐返回）
  - **API 合约（建议，等待确认）**
    - 当触发“登录尝试过多”时，后端返回 429（或 400，按现状对齐）并携带 envelope error：
      - `error.code = "TOO_MANY_LOGIN_ATTEMPTS"`
      - `error.message` 为中文可读（例如“尝试次数过多，请稍后再试”）
      - `error.details.retryAfterSeconds: number`（整数，>=1）
    - 可选：同时设置 `Retry-After` header（秒），前端优先使用 `details.retryAfterSeconds`
  - **交互规则（最小）**
    - 倒计时期间：登录按钮 disabled；展示“xx 秒后可继续尝试”
    - 倒计时结束：自动恢复按钮可用；无需刷新页面
  - **验收标准（DoD）**
    - [ ] 触发锁定时，用户能明确看到剩余时间
    - [ ] 倒计时结束后无需刷新即可继续登录
  - **待确认点**
    - [ ] 该倒计时是否仅要求 **Admin 管理系统登录**，还是 Provider/Dealer 登录也要同口径？

- [ ] **REQ-ADMIN-P1-016：账号管理-创建账号“复制密码”在安卓平板可用（失败可降级手动复制）**
  - **背景/问题**：Admin「账号与身份 → 账号管理」创建新账号后点击“复制密码”，在安卓平板端出现“复制失败，请手动复制”。
  - **目标**：尽最大努力自动复制；若系统限制导致无法复制，则提供稳定的“手动复制”降级（不让用户丢失密码）。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminAccountsPage.vue`（创建账号弹窗/结果展示区）
  - **交互规则（最小）**
    - 优先使用 `navigator.clipboard.writeText`
    - 若失败（常见于 http/权限/安卓 WebView）：降级为“只读 input + 自动全选 + `document.execCommand('copy')`”尝试
    - 若仍失败：明确提示“复制失败，请长按选择后复制”，并确保密码仍可见/可选中
  - **验收标准（DoD）**
    - [ ] 在安卓平板端：点击复制后能成功复制（或明确进入可手动复制的兜底态）
    - [ ] 兜底态不丢失密码，且可一键全选（减少操作成本）
  - **实现证据（文本）**
    - `frontend/admin/src/pages/admin/AdminAccountsPage.vue`（clipboard + execCommand 兜底 + 手动复制弹窗）

- [ ] **REQ-AUTH-P1-001：管理后台登录页新增“注册”（仅 Provider/Dealer，短信验证，注册后待审核）+ 账号管理支持创建 Admin**
  - **背景/问题**：
    - 目前管理后台无自助注册入口；账号主要由 Admin 创建。
    - 平台建设期需要更高自助性：允许 Provider/Dealer 在登录页注册，但必须短信验证并进入“待审核”。
    - 同时 Admin「账号管理」需要支持创建 Admin 角色账号（同样按一次性明文密码展示口径）。
  - **目标**：
    - 登录页提供注册入口（仅 Provider/Dealer），注册必须短信验证。
    - 注册成功后账号处于 **待审核**（不可登录）；Admin 可在账号管理中“启用”即视为审核通过。
    - Admin 账号管理支持创建/重置/冻结/启用 Admin 账号。
  - **范围（页面/接口）**：
    - 前端登录页：`frontend/admin/src/pages/LoginPage.vue`
    - 前端账号管理页：`frontend/admin/src/pages/admin/AdminAccountsPage.vue`
    - 后端 Provider/Dealer 认证：`backend/app/api/v1/provider_auth.py`、`backend/app/api/v1/dealer_auth.py`
    - 后端 Admin 账号管理：`backend/app/api/v1/admin_accounts.py`
    - 短信验证码服务：`backend/app/services/sms_code_service.py`（复用，新增 scene 值）
  - **数据与状态口径**：
    - ProviderUser/DealerUser 增加状态值：`PENDING_REVIEW`（字符串枚举值；不新增表字段）
    - 注册成功后：
      - Provider：创建 `Provider` + 默认 `Venue` + `ProviderUser(status=PENDING_REVIEW)`
      - Dealer：创建 `Dealer(status=ACTIVE)` + `DealerUser(status=PENDING_REVIEW)`
  - **API 合约（v1）**
    - `POST /provider/auth/register/challenge`
      - body: `{ phone: string }`
      - 200: `{ sent: boolean, expiresInSeconds: number, resendAfterSeconds: number }`
    - `POST /provider/auth/register`
      - body: `{ username: string, password: string, providerName: string, phone: string, smsCode: string }`
      - 200: `{ submitted: true }`
    - `POST /dealer/auth/register/challenge`
      - body: `{ phone: string }`
      - 200: `{ sent: boolean, expiresInSeconds: number, resendAfterSeconds: number }`
    - `POST /dealer/auth/register`
      - body: `{ username: string, password: string, dealerName: string, phone: string, smsCode: string }`
      - 200: `{ submitted: true }`
    - 登录限制（明确提示）：
      - 当账号为 `PENDING_REVIEW`：返回 **403**，`code="ACCOUNT_PENDING_REVIEW"`，`message="账号待审核，请联系管理员启用后再登录"`
      - 当账号为 `SUSPENDED`：返回 **403**，`code="ACCOUNT_SUSPENDED"`，`message="账号已冻结"`
    - Admin 账号管理新增（最小）：
      - `GET /admin/admin-users`
      - `POST /admin/admin-users`
      - `POST /admin/admin-users/{id}/reset-password`
      - `POST /admin/admin-users/{id}/suspend`
      - `POST /admin/admin-users/{id}/activate`
  - **交互规则（v1）**
    - 登录页：增加 2 个入口按钮
      - “注册合作商”（Provider）
      - “注册经销商”（Dealer）
      - 两个入口分别打开各自的注册弹窗（不在弹窗内切换角色），字段仍为：用户名/密码/主体名称/手机号/短信验证码
    - “发送验证码”按钮遵循 `resendAfterSeconds` 倒计时
    - 注册成功：toast 提示“已提交审核”，并返回登录表单
    - 账号管理：
      - 新增“管理员”tab
      - 对 Provider/Dealer 若状态为 `PENDING_REVIEW`：主操作按钮文案显示“通过注册（启用）”，调用 activate 接口
  - **验收标准（DoD）**
    - [ ] Provider 注册：短信验证通过后创建账号，状态为 `PENDING_REVIEW`，登录会提示“待审核”且不可进入系统
    - [ ] Dealer 注册：同上
    - [ ] Admin 在账号管理中可看到 `PENDING_REVIEW` 账号并可一键启用；启用后可正常登录
    - [ ] Admin 可创建 Admin 账号并看到一次性密码（关闭后不可再次查看明文）
  - **兼容性约束**
    - 不影响既有 Admin 创建 Provider/Dealer 账号流程
    - 不引入新的外部短信供应商（沿用现有 mock 短信服务与 Redis 频控/验证码存储）
  - **风险与回滚**
    - 注册入口可能被滥用：通过短信验证码频控 + 账号待审核降低风险；如需紧急回滚，可仅前端隐藏注册入口并保留后端接口

- [ ] **REQ-ADMIN-P1-017：场所管理/审核详情抽屉“所在城市”展示城市名称**
  - **背景/问题**：Admin「供给审核→场所管理/审核」详情抽屉中“所在城市”当前展示 `CITY:xxxxx` 代码，不利于运营审核。
  - **目标**：展示城市名称（例如“北京市”），而不是 code。
  - **范围（候选）**
    - 前端：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`
    - 后端（如需）：`backend/app/api/v1/admin_venues.py`（若补充 `cityName` 字段）
  - **实现口径（v1）**
    - 优先使用详情接口返回的 `cityName` 字段（如存在）
    - 若后端未提供：前端通过“区域/城市配置”读侧接口映射 code→name（失败时兜底展示原 code）
  - **验收标准（DoD）**
    - [ ] 抽屉“所在城市”优先显示城市名称；无名称时显示 `—` 或 code（兜底）
  - **实现证据（文本）**：TBD

- [ ] **REQ-MP-P1-012：小程序首页推荐（商品/场所）由 Admin 配置控制（展示/不展示 + 列表）**
  - **背景/问题**：当前小程序首页推荐商品/场所为“直接取列表前 N 条”，无法由运营控制展示/不展示，也无法精确挑选内容。
  - **目标**：在 Admin「内容与投放 → 小程序配置中心」增加“推荐管理”页签，管理小程序端推荐商品/场所的展示开关与推荐列表（仅允许选择对外可用的已发布/上架项）。
  - **范围（候选）**
    - Admin：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`
    - Admin 菜单：`frontend/admin/src/lib/nav.ts`（菜单名去掉“（页面/入口）”）
    - 读侧接口：`backend/app/api/v1/mini_program_config.py`（新增 recommended-products/venues）
    - 管理接口：`backend/app/api/v1/admin_mini_program_config.py`
    - 小程序首页：`frontend/mini-program/pages/index/index.js`
  - **验收标准（DoD）**
    - [ ] 可分别控制“推荐商品/推荐场所”模块展示或隐藏
    - [ ] 推荐列表可排序、可添加/删除；只允许选择对外可用项（场所=PUBLISHED；商品=ON_SALE）
    - [ ] 小程序首页推荐数据改为读取新接口（不再直接取 `/products` 与 `/venues` 的前 N 条）
  - **实现证据（文本）**：TBD

- [ ] **REQ-WEBSITE-P1-007：官网投放（CMS）增加“推荐场所”页签（展示/不展示 + 列表）**
  - **背景/问题**：你已确认“官网推荐场所”不应在场所审核页发布上线；且需要在“官网投放（CMS）”内统一运营配置推荐场所的展示/不展示。
  - **目标**：在 Admin「内容与投放 → 官网投放（CMS）」增加“推荐场所”页签，支持开关与列表配置（仅 PUBLISHED）。
  - **范围（候选）**
    - 前端：`frontend/admin/src/pages/admin/AdminCmsWebsiteDeliveryPage.vue`
    - 后端：`backend/app/api/v1/admin_website_config.py`（推荐场所配置支持 enabled）
  - **验收标准（DoD）**
    - [ ] 可启用/停用官网首页推荐场所模块（停用后官网首页不展示）
    - [ ] 可维护推荐列表（仅 PUBLISHED），保存后刷新官网首页生效
  - **实现证据（文本）**：TBD

- [ ] **REQ-MP-P1-013：价格裁决口径升级（展示价=成交价；取“可命中集合”的最低价；标识来源）**
  - **现状**：后端 `app/services/pricing.py` 与小程序 `utils/price.js` 使用“优先级：活动>会员>员工>原价”裁决。
  - **需求**：小程序端根据用户身份与活动状态，计算可命中的价格集合，取最低价作为最终展示与成交价，并标识来源类型。
  - **待确认点**：
    - “活动状态”在当前数据结构中仅有 `price.activity`，无开始/结束时间；是否默认 **activity 非空即视为活动进行中**？
    - 若出现价格相等（例如 activity=member），来源标识采用何种优先级（建议：activity > member > employee > original）。
    - 是否要求 **后端成交价** 与小程序展示价严格一致（建议：以服务端为准，并将来源类型一并落单/回传）。

- [x] **REQ-DEALER-P1-001：经销商“链接/参数管理”复制链接兼容性修复**
  - **问题**：点击“复制”在部分环境（Android WebView/权限限制等）提示“复制失败，请手动复制”，且控制台无明显报错。
  - **口径**：复制实现需提供兜底：clipboard API → execCommand → 弹窗可手动复制（可长按/全选）。
  - **实现**：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`

- [x] **REQ-H5-P1-002：H5 购卡页“包含服务类别×次数”显示中文名称**
  - **问题**：H5 购卡页与介绍页展示服务包明细时，使用了服务大类 code（如 MASSAGE），用户侧不友好。
  - **口径**：使用 `GET /api/v1/service-categories` 返回的 `displayName` 映射展示；找不到映射则兜底显示 code。
  - **实现**：
    - `frontend/h5/src/pages/BuyPage.vue`
    - `frontend/h5/src/pages/LandingPage.vue`

- [ ] **REQ-ADMIN-P1-018：场所审核“通过并发布”拆分（本次仅保留“通过”）**
  - **背景/问题**：当前 Admin「场所管理/审核」对待审核记录的主操作为“通过并发布”，审核与对外发布耦合。
  - **目标（分阶段）**
    - 本阶段：在该页面仅保留“通过（审核通过）”与“驳回/下线”等审核管理；不在此页执行“发布上线”。
    - 下一阶段：发布能力迁移到 Admin「内容与投放→官网投放」页面（后续你说要再细拆需求再做）。
  - **范围（本阶段）**
    - 前端：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`
    - 后端：`backend/app/api/v1/admin_venues.py`（新增/补齐“通过”接口或状态机）
  - **验收标准（DoD，本阶段）**
    - [ ] 列表对 `SUBMITTED` 记录展示按钮为“通过”（不再出现“通过并发布”）
    - [ ] 点击“通过”后：`reviewStatus` 变为 `APPROVED`，且不触发发布（`publishStatus` 不直接变为 `PUBLISHED`）
    - [ ] 发布入口不在本页（本阶段暂不实现迁移页）
  - **风险与待确认**
    - [ ] 若移除本页发布入口，系统是否仍存在其他发布路径？（避免短期无法发布导致对外不可见）
  - **实现证据（文本）**：TBD

- [x] **REQ-ADMIN-P0-002：基建联防商品能力升级：支持“到店服务 + 物流商品”**
  - **背景/问题**：当前电商侧除“到店服务/虚拟券”外，缺少可物流交付的“商品”能力；同时订单监管菜单与能力描述需要对齐。
  - **概念澄清（按当前代码语义）**：
    - **到店服务（SERVICE）**：履约为到店服务（通常与场所/排期/预约相关），属于 `PRODUCT` 体系中的一种履约类型。
    - **虚拟券（VIRTUAL_VOUCHER）**：履约为“发放券码/二维码并可核销”，是另一条订单/履约语义（当前系统中与 SERVICE 分开监管）。
    - 你已确认“虚拟券不需要保留”，因此本需求的业务目标是 **保留到店服务（SERVICE），新增物流商品，并下线虚拟券能力**（见 REQ-PLATFORM-P0-001）。
  - **目标**：电商侧支持 2 类履约：到店服务（SERVICE）+ 物流商品（PHYSICAL_GOODS/DELIVERY）；虚拟券能力下线后，订单监管菜单/筛选口径与之对齐。
  - **范围（待确认）**：
    - 后端商品模型/枚举/下单履约：`backend/app/models/*`、`backend/app/api/v1/products.py`、`backend/app/api/v1/orders.py`
    - Admin 商品监管：`frontend/admin/src/pages/admin/AdminProductsPage.vue`（及其说明文案）
    - Admin 订单监管子菜单：`frontend/admin/src/router/index.ts`（下线“虚拟券”子菜单；“商品/服务”对齐新增物流商品）
  - **验收标准（DoD，待补）**：
    - [x] Admin 商品可配置/展示物流商品的关键字段（见 REQ-ECOMMERCE-P0-001 的“物流商品 v2 规格”）
    - [x] 下单时能创建物流商品订单并进入对应状态机（见 REQ-ECOMMERCE-P0-001 的状态定义）
    - [x] 订单监管：菜单与筛选口径与“到店服务/物流商品”一致（不再出现“虚拟券”入口）
  - **兼容性约束**：对既有商品/订单 API 需保持向后兼容（新增字段/枚举值不得破坏旧端解析）。
  - **待确认点（必须）**：
    - 详见 REQ-ECOMMERCE-P0-001（物流商品 v2 规格）；若实现风险过高允许按“降级边界”回退到 v1（边界已写清）。
  - **实现证据（文本）**：
    - Admin 商品审核/监管支持 PHYSICAL_GOODS 字段展示：`frontend/admin/src/pages/admin/AdminProductsPage.vue`
    - Provider 商品/服务管理支持 PHYSICAL_GOODS 字段录入：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
    - 后端产品/订单/库存/履约：`backend/app/api/v1/products.py`、`backend/app/api/v1/orders.py`、`backend/app/services/payment_callbacks.py`、`backend/app/tasks/inventory.py`

- [x] **REQ-PLATFORM-P0-001：下线“虚拟券（VIRTUAL_VOUCHER）”能力（全端对齐）**
  - **背景/问题**：你已确认虚拟券不需要保留；当前系统存在虚拟券履约、下单与监管入口。
  - **目标**：全端侧彻底移除“虚拟券”能力（包括入口、模型枚举、下单/履约路径与相关测试），并允许清理测试数据。
  - **范围（候选）**：
    - 后端：`backend/app/models/enums.py`（若包含枚举）、`backend/app/api/v1/products.py`、`backend/app/api/v1/orders.py`、相关规则/状态机与测试
    - Admin：订单监管/商品审核相关页面与路由菜单
    - 小程序：商城/下单/商品详情展示（若存在虚拟券商品）
  - **验收标准（DoD）**：
    - [x] 系统中不再存在“虚拟券”相关的创建/审核/下单/监管入口与文案
    - [x] 后端不再接受/产出 VIRTUAL_VOUCHER 相关枚举值（接口契约对齐）
    - [x] 相关测试用例/种子数据/演示数据清理或调整后可通过
  - **实现证据（文本）**：
    - 后端枚举与接口：`backend/app/models/enums.py`、`backend/app/api/v1/orders.py`、`backend/app/api/v1/products.py`
    - 履约/权益/退款规则调整：`backend/app/services/fulfillment_routing.py`、`backend/app/services/entitlement_generation.py`、`backend/app/services/refund_service.py`
    - Admin：移除“订单监管（虚拟券）”入口与筛选：`frontend/admin/src/lib/nav.ts`、`frontend/admin/src/router/index.ts`、`frontend/admin/src/pages/admin/AdminOrdersPage.vue`
    - 小程序：订单/权益页面不再展示虚拟券：`frontend/mini-program/pages/order/order.wxml`、`frontend/mini-program/pages/entitlement/entitlement.wxml`
  - **兼容性约束（已确认）**：系统尚未上线，允许破坏性变更；若数据库中存在测试用虚拟券数据，允许全部清理。

- [x] **REQ-ECOMMERCE-P0-001：物流商品（PHYSICAL_GOODS）“更完整闭环”能力（v2 优先，必要时可降级 v1）**
  - **背景/问题**：你希望“平台型电商”一次性做得更完整；如果风险过高则接受按 v1 先上线。
  - **目标**：在保留“到店服务（SERVICE）”的同时，新增“物流商品（PHYSICAL_GOODS）”并补齐主流电商的核心能力：地址簿、库存占用/释放、发货与签收、订单查询与后台监管。
  - **异步任务队列选型（已确认）**：采用 **Celery** 承载“库存超时释放”等后台任务；`broker=RabbitMQ`（复用 `docker-compose.yml` 现有 rabbitmq），`result backend=Redis`（复用现有 redis）。
  - **v2（优先实现）规格定义**：
    - **地址簿（必须）**
      - 用户拥有“收货地址簿”，支持：新增/编辑/删除/设为默认/列表
      - 下单时可选择地址簿中的地址（并允许临时新增后直接使用）
    - **库存（主流做法：下单占用、超时释放、支付确认扣减）**
      - 创建订单时：占用库存（预占），订单处于待支付
      - 超时未支付：自动释放占用库存
      - 支付成功：确认扣减（占用转扣减），进入待发货
      - 取消/退款：按规则回补库存（v2 最小：取消未支付必回补；退款回补规则暂按“全额退款回补”）
    - **物流履约状态（v2 最小但更完整）**
      - 订单物流状态：`NOT_SHIPPED`（待发货）→ `SHIPPED`（已发货）→ `DELIVERED`（已送达/妥投）→ `RECEIVED`（用户确认收货）
      - v2 先不做第三方物流轨迹抓取；`DELIVERED` 可由供给侧/管理侧手动标记或通过未来接口扩展
    - **发货信息（必须）**
      - 录入：快递公司（carrier）+ 运单号（trackingNo）+ 发货时间（shippedAt）
    - **商品字段（物流类最小集合）**
      - `fulfillmentType=PHYSICAL_GOODS`
      - `stock`（库存）
      - `weight`（重量，可选但建议）
      - `shippingFee`（运费，v2 最小可用：固定运费；后续再升级运费模板）
      - 其余（title/description/images/price/status）沿用现有商品字段
  - **v1（降级边界，若 v2 风险过高可回退）**：
    - 仍然必须保留：**地址簿 + 库存占用/释放（超时回补） + 发货录入（carrier+trackingNo）**
    - 允许暂不做：`DELIVERED/RECEIVED` 两级状态（只做到 `SHIPPED`），以及退款回补规则细化
  - **范围（候选）**：
    - 后端：商品/订单/支付/定时任务或队列（用于超时释放库存）、数据模型迁移
    - 小程序：下单页选择收货地址、订单详情展示物流信息、地址簿管理入口
    - Admin/Provider：商品录入与审核、订单发货录入与监管筛选
  - **验收标准（DoD）**：
    - [x] 地址簿 CRUD 可用；下单可选择默认地址
    - [x] 下单占用库存，超时释放可验证（可通过测试或可重复脚本验证）
    - [x] 支付后进入待发货；录入发货信息后订单变为已发货
    - [x] Admin 订单监管可筛选到店服务/物流商品，并显示物流字段
  - **实现证据（文本）**：
    - 数据模型与迁移：`backend/app/models/user_address.py`、`backend/app/models/product.py`、`backend/app/models/order.py`、`backend/alembic/versions/c3e2f1a0b9c8_stage22_physical_goods_v2.py`
    - 枚举：`backend/app/models/enums.py`（`ProductFulfillmentType.PHYSICAL_GOODS`、`OrderFulfillmentStatus`）
    - 地址簿 API：`backend/app/api/v1/user_addresses.py`、`backend/app/api/v1/router.py`
    - 下单库存占用/地址快照：`backend/app/api/v1/orders.py`（`POST /api/v1/orders`）
    - 支付确认扣减：`backend/app/services/payment_callbacks.py`
    - 超时释放（Celery）：`backend/app/tasks/inventory.py`、`backend/app/celery_app.py`
    - 发货/妥投/收货接口：`backend/app/api/v1/orders.py`（`POST /api/v1/admin/orders/{id}/ship|deliver`、`POST /api/v1/orders/{id}/confirm-received`）、`backend/app/api/v1/provider.py`（`POST /api/v1/provider/orders/{id}/ship`）
    - Admin 订单监管筛选与发货录入：`frontend/admin/src/pages/admin/AdminOrdersPage.vue`、`frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue`
    - 小程序地址簿与下单/订单对齐：`frontend/mini-program/pages/address/address-list/address-list.js`、`frontend/mini-program/pages/address/address-edit/address-edit.js`、`frontend/mini-program/pages/mall/cart/cart.js`、`frontend/mini-program/pages/mall/product-detail/product-detail.js`、`frontend/mini-program/pages/order/order-detail/order-detail.js`

- [x] **REQ-ADMIN-P0-003：分账与结算页面易用性升级（减少手工配置）**
  - **背景/问题**：当前完成度不足，需要用户手动填写配置。
  - **目标**：升级为上线后可正确完成“健行天下业务 → 给经销商分账/结算/打款”的闭环流程（更强引导/更少手填/更安全的默认值）。
  - **范围（待定位）**：`frontend/admin/src/pages/**/Settlements*.vue`、后端结算相关接口（若涉及）。
  - **验收标准（DoD）**：
    - [x] 经销商可维护“结算账户/打款信息”（最小字段集）
    - [x] Admin 可查看结算单打款账户快照，并可标记“已打款/已结算”（记录参考号/备注）
    - [x] 结算周期输入为月份选择器（YYYY-MM）
    - [x] 后端结算单出参包含打款字段（method/account snapshot/reference/note）
  - **确认结论（你已确认）**：需要覆盖“结算账户、打款信息等字段”，并把后台提升到可上线可用的分账/结算流程。
  - **最小规格草案（按你确认，已实现 v1）**：
    - 把经销商分账比例的 `dealerOverrides(JSON)` 改为“表格编辑”：
      - 列：dealerId（可搜索选择）/ 分账比例（0~1，步进 0.01）/ 备注（可选）
      - 仍保留“默认分账比例 defaultRate（0~1）”
    - 生成结算周期输入统一使用“月份选择器（YYYY-MM）”（已实现）
    - 增加“经销商结算账户/打款信息”管理（最小字段集：method/accountName/accountNo/bankName/bankBranch/contactPhone）
    - 增加结算单“打款快照 + 标记已打款/已结算”能力
  - **实现证据（文本）**：
    - 后端模型与迁移：`backend/app/models/dealer_settlement_account.py`、`backend/app/models/settlement_record.py`、`backend/alembic/versions/e2b9c1d7a8f4_stage24_dealer_settlement_account_and_payout_fields.py`
    - Admin 结算 API：`backend/app/api/v1/admin_dealer_settlements.py`（`/admin/dealer-settlements/*`、`mark-settled`）
    - Dealer 账户/结算 API：`backend/app/api/v1/dealer.py`（`GET/PUT /dealer/settlement-account`、`GET /dealer/settlements`）
    - Admin 页面：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
    - Dealer 页面：`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`

- [x] **REQ-ADMIN-P0-004：运营工具-小程序配置中心易用性升级（减少手工配置）**
  - **背景/问题**：当前使用起来麻烦。
  - **目标**：把“配置小程序”做成可理解、可操作、可回归的流程（从页面打开就能看懂怎么配；结构化编辑、校验、预览、发布流程清晰）。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue` + 对应后端 `admin_mini_program_config` 接口。
  - **验收标准（DoD，待确认）**：
    - [ ] 配置编辑具备结构化校验与明确错误提示
    - [ ] 发布/下线操作减少手工步骤
  - **确认结论（你已确认）**：当前打开页面“完全看不懂如何操作”，需要对“配置流程本身”做整体优化。
  - **最小规格草案（按你确认，进入实现）**：
    - 提供“向导式三步”：1）内容集合 2）页面 3）首页入口（含 OPERATION=BANNER 说明）
    - entries/pages/collections 默认使用结构化编辑（表单/表格）；JSON 编辑仅作为“高级模式”入口
    - 提供“预览/校验/发布顺序”的强引导（发布前校验引用关系、必填字段、URL 合法性）
    - 提供“最小可用模板一键生成”（可直接发布后在小程序端看到效果）
  - **验收标准（DoD）**：
    - [x] 页面打开后提供清晰的“最短路径”说明与三步引导（集合→页面→入口）
    - [x] 首页入口（含 Banner）支持结构化新增/编辑/删除并保存草稿；JSON 编辑降级为高级入口
    - [x] 发布前校验入口对页面引用（避免 targetId 指向不存在 pageId）
  - **实现证据（文本）**：
    - Admin 页面：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`

- [x] **REQ-ADMIN-P0-005：官网配置-首页推荐场所选择控件升级（从输入ID到可选Select）**
  - **背景/问题**：当前只能输入场所 id，容易出错。
  - **目标**：提供可搜索/可选择的 Select（展示场所名称/城市等），并输出对应 venueId。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue` + 后端场所检索接口（复用 `/api/v1/venues` 或 admin 专用接口）。
  - **验收标准（DoD）**：
    - [x] Select 支持按关键字搜索场所（名称/地址）
    - [x] 选择项展示至少包含：场所名、城市（若可用）、ID（小字）
    - [x] 提交保存时仍仅保存 venueId（保持数据结构稳定）
  - **实现证据（文本）**：`frontend/admin/src/pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue`、`backend/app/api/v1/admin_venues.py`

- [ ] **REQ-WEBSITE-P1-001：官网首页“推荐场所”由 Admin 运营配置（不随审核自动上首页）**
  - **背景/问题**
    - 当前存在“审核通过后自动展示”的倾向，导致首页推荐不可控、无法运营排序与取舍。
    - 官网文案为“推荐场所/服务”，口径混乱（你已确认官网不应推荐商品/服务，应为“推荐场所”）。
  - **终态口径（你已确认）**
    - 官网首页推荐仅展示 Admin 明确配置的场所列表（可排序/可移除）。
    - 审核通过仅代表“可被选择”，不代表自动上首页。
    - 前台文案统一为“推荐场所”（不出现推荐服务/商品）。
  - **数据与接口（既有能力对齐）**
    - 推荐场所配置入口与保存接口复用现有实现：
      - Admin 配置：`PUT /api/v1/admin/website/home/recommended-venues`
      - 读侧（官网使用）：按现有 website config 读侧接口与页面实现为准
  - **范围（候选）**
    - 官网首页：`frontend/website/src/pages/HomePage.vue`
    - 官网场所列表/详情：`frontend/website/src/pages/VenuesPage.vue`、`VenueDetailPage.vue`
    - Admin 配置页：`frontend/admin/src/pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue`
    - 后端：`backend/app/api/v1/admin_website_config.py`（或等价模块）
  - **验收标准（DoD）**
    - [ ] 首页推荐仅展示配置列表，且与“内容中心”模块并行不互相影响
    - [ ] 新增场所并通过审核后，不会自动出现在首页推荐（除非被配置）
    - [ ] 文案为“推荐场所”，无“推荐服务/商品”
  - **实现证据（文本）**：TBD
  - **实现证据（文本）**
    - 小程序首页推荐卡片图片展示：`frontend/mini-program/pages/index/index.js`（`coverImageUrlAbs/nameDisplay/cityName`）+ `frontend/mini-program/pages/index/index.wxml`（推荐商品/场所使用 `<image>`）
    - “（默认场所）”来源定位：`backend/app/api/v1/admin_accounts.py`（创建 Provider 时同步创建默认 Venue）
    - 新创建的默认场所不再追加后缀：`backend/app/api/v1/admin_accounts.py`
    - 场所详情头图留白修复：`frontend/mini-program/pages/venue-detail/venue-detail.wxml`、`frontend/mini-program/pages/venue-detail/venue-detail.wxss`

- [ ] **REQ-WEBSITE-P1-002：官网首页推荐场所不展示/不及时更新问题修复**
  - **背景/问题**：你反馈新增场所后，场所页可见但首页推荐容器不展示（与“内容”模块对比可复现）。
  - **目标**：首页推荐展示与更新稳定可预期。
  - **范围（候选）**：`frontend/website/src/pages/HomePage.vue` + 对应后端读侧接口
  - **验收标准（DoD）**
    - [ ] 当 Admin 配置了推荐场所且场所为 `PUBLISHED` 时：首页“推荐场所”卡片必须展示该场所（至少展示名称；封面/地址缺失不应导致整卡不渲染）
    - [ ] 当 Admin 配置为空或配置的场所不可用时：首页应明确展示空态或提示（不静默失败）
    - [ ] 配置变更后刷新首页即可看到最新推荐列表（不出现“场所页可见但首页长期为空”的不一致）
  - **实现证据（文本）**：TBD

- [ ] **REQ-WEBSITE-P1-003：官网场所列表图标（封面）展示策略优化（统一容器 + cover）**
  - **终态口径（你已确认）**
    - 列表图标采用“统一容器 + `object-fit: cover`”以保证视觉一致；不要求图片严格同尺寸。
  - **范围（候选）**：`frontend/website/src/pages/VenuesPage.vue`（以及使用场所卡片的同类列表）
  - **验收标准（DoD）**
    - [ ] 不同尺寸/比例的封面在列表中视觉一致（不拉伸、不变形、裁剪可接受）
    - [ ] 空封面有占位，且占位不影响布局
  - **实现证据（文本）**：TBD

- [x] **REQ-ADMIN-P0-006：运营工具-小程序配置中心补齐 Banner/轮播图管理能力**
  - **背景/问题**：当前似乎没有首页 Banner（轮播图）管理。
  - **目标**：支持配置首页轮播图数据（图片URL/跳转/排序/启用/发布）。
  - **范围（待确认）**：后端 SystemConfig keys 与小程序首页渲染逻辑（Q4）。
  - **验收标准（DoD，待确认）**：按最小字段集与发布流程落地。
  - **实现说明（v1 最小）**：
    - Banner/轮播图数据源复用“首页入口（entries）”中的 `position=OPERATION` 项；小程序首页将其映射为 Banner 列表
  - **实现证据（文本）**：
    - Admin 配置入口：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`（entries position=OPERATION）
    - 小程序读侧渲染：`frontend/mini-program/pages/index/index.js`（将 position=OPERATION entries 转成 banners）

- [x] **REQ-ADMIN-P0-007：多角色“自助重置为指定密码”能力（各角色登录后自行改密）**
  - **背景/问题**：当前创建账号会生成随机复杂密码，不利于长期管理。
  - **目标**：各角色账号登录后可把“随机初始密码”改为“自己指定密码”（并满足最小安全规则）；Admin 仍可保留“重置为随机密码”的运维能力（已存在/合理）。
  - **范围**：后端各角色 auth 接口 + 管理端各角色个人中心/安全设置入口。
  - **验收标准（DoD，待确认）**：
    - [x] 各角色登录后提供“修改密码”入口（旧密码 + 新密码 + 确认）
    - [x] 后端校验新密码最小规则（默认：长度 ≥ 8）
    - [x] 审计日志记录（谁在何时改密）
  - **确认结论（你已确认）**：
    - Admin “重置为随机密码”是合理的运维能力（保持）
    - 目标是：账号使用者可自行改为“指定密码”
  - **实现证据（文本）**：
    - 前端入口：`frontend/admin/src/layouts/AppLayout.vue`（下拉菜单“安全设置”）、`frontend/admin/src/pages/AccountSecurityPage.vue`
    - 路由：`frontend/admin/src/router/index.ts`（`/account/security`）
    - 后端接口：`POST /api/v1/admin/auth/change-password`、`POST /api/v1/provider/auth/change-password`、`POST /api/v1/dealer/auth/change-password`
    - 审计：`backend/app/models/audit_log.py`、`backend/app/api/v1/audit_logs.py`

- [x] **REQ-ADMIN-P0-008：统一管理各端“协议/条款”能力（可配置、多类别）**
  - **背景/问题**：协议分散：provider 申请协议、H5 购买协议、小程序登录协议等可能需要统一管理。
  - **目标**：在 Admin 中提供统一的“协议管理”，支持多类别、版本、启用/发布。
  - **范围（待确认）**：后端存储载体（SystemConfig 或新表）、各端读取接口与渲染（Q6）。
  - **验收标准（DoD）**：
    - [x] Admin 可维护多类别协议：草稿/发布/下线
    - [x] 读侧提供统一接口 `GET /api/v1/legal/{code}`（仅返回已发布版本）
    - [x] H5 购买页协议入口保持兼容（`/api/v1/h5/legal/service-agreement` 仍可用）
    - [x] Provider 申请页与小程序登录提供协议入口展示
  - **确认结论（你已确认）**：最小类别至少包含 Provider 两类申请协议、H5 购买协议、小程序登录协议（即使当前小程序端未看到，也要补齐）。
  - **最小协议类别枚举（进入实现）**：
    - `PROVIDER_INFRA_APPLY`：Provider 申请开通“基建联防”协议
    - `PROVIDER_HEALTH_CARD_APPLY`：Provider 申请开通“健行天下”协议
    - `H5_BUY_AGREEMENT`：H5 购买服务包协议
    - `MP_LOGIN_AGREEMENT`：小程序用户登录服务协议
  - **最小规格草案（按你确认，进入实现）**：
    - 后端新增“协议表”（推荐新表而非 SystemConfig，便于多版本/多类别）：
      - 字段：`code`（唯一）、`title`、`contentHtml`、`version`、`status(DRAFT/PUBLISHED/OFFLINE)`、`publishedAt`
    - Admin 提供协议管理：列表/编辑/发布/下线
    - 各端读侧接口：`GET /api/v1/legal/{code}` 返回当前已发布版本（向后兼容：保留现有单点接口）
    - 各端接入点（最小）：
      - Provider 申请页：展示对应协议并要求勾选同意
      - H5 购买页：复用现有“服务协议”入口，但内容由协议中心提供
      - 小程序登录：提供“服务协议”入口（可点击查看）
  - **实现证据（文本）**：
    - 后端模型与迁移：`backend/app/models/legal_agreement.py`、`backend/alembic/versions/d1a4b0c9e2f3_stage23_legal_agreements_and_provider_infra_agreement.py`
    - Admin 管理接口：`backend/app/api/v1/admin_legal.py`
    - 读侧接口：`backend/app/api/v1/legal.py`
    - H5 兼容入口：`backend/app/api/v1/h5_config.py`（优先协议中心，兼容 SystemConfig）
    - Admin 管理页面：`frontend/admin/src/pages/admin/AdminLegalAgreementsPage.vue`、`frontend/admin/src/lib/nav.ts`、`frontend/admin/src/router/index.ts`
    - Provider 勾选协议与提交：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`、`backend/app/api/v1/provider_onboarding.py`
    - 小程序协议入口：`frontend/mini-program/pages/profile/profile.wxml`、`frontend/mini-program/pages/legal/agreement/agreement.*`

- [ ] **REQ-ADMIN-P1-001：安全设置页 2FA 卡片升级（已开启时展示手机号等必要信息）**
  - **背景/问题**：当前“安全设置”页只提供“绑定手机号（开启2FA）”表单；若已绑定手机号（即已开启 2FA），页面仍无法明确展示“已开启/绑定到哪个手机号”，认知不完整。
  - **终态口径（你已确认）**
    - 2FA 是否开启：以 Admin 是否已绑定手机号为准（`admin.phone` 非空即开启）。
    - 已开启时：展示必要信息（至少手机号脱敏）与状态；不要求一次性做“更换手机号”流程。
  - **接口与数据**
    - 需要新增读侧接口（避免前端“猜测”）：
      - `GET /api/v1/admin/auth/security` → `{ twoFaEnabled: boolean, phoneMasked?: string | null }`
    - `phoneMasked` 规则：`138****1234`（仅展示脱敏，不返回明文）
  - **范围（候选）**
    - 前端：`frontend/admin/src/pages/AccountSecurityPage.vue`
    - 后端：新增 `backend/app/api/v1/admin_security.py`（或落在 `admin_auth.py` 同命名空间）+ 挂载到 router
  - **验收标准（DoD）**
    - [ ] Admin 已绑定手机号：安全设置页显示“2FA 已开启”与手机号脱敏；不再展示绑定表单（或表单进入只读态）
    - [ ] Admin 未绑定手机号：保持现有绑定流程可用
    - [ ] 不泄露手机号明文；响应结构遵循统一 `ok(data=...)`
  - **实现证据（文本）**：TBD

- [x] **REQ-ADMIN-P2-001：登录能力未来兼容微信扫码登录（仅规格预留，不实现）**
  - **目标**：在规格中预留未来扫码登录的扩展点（不做实现，不影响当前上线）。
  - **规格预留（最小）**：
    - Admin 登录页保留“未来可扩展的第三方登录入口区域”（不影响当前账号密码登录）
    - 后端预留未来新增 `/api/v1/admin/auth/wechat-qrcode/*` 的命名空间（仅规格约定，不实现）
  - **实现证据（文本）**：`specs/health-services-platform/tasks.md`

#### 3.2 Provider 升级需求（管理端的 Provider 角色）

- [x] **REQ-PROVIDER-P0-001：工作台申请开通健行天下服务报错排障与修复**
  - **背景/问题**：申请开通时返回 `INTERNAL_ERROR`（requestId 已提供）。
  - **目标**：修复错误并提供可理解的失败原因（如配置缺失/状态不允许）。
  - **范围（候选）**：
    - 前端：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`
    - 后端：`backend/app/api/v1/provider_onboarding.py` / 相关服务（待定位）
  - **验收标准（DoD）**：
    - [x] 在同样操作路径下不再返回 500
    - [x] 若失败，返回明确业务错误码（4xx）+ message 可用于前端提示
  - **证据补充**：需要你提供复现路径（Q7）。
  - **实现证据（文本）**：`backend/app/api/v1/provider_onboarding.py`（补齐 `uuid4` 导入，避免 500）

- [x] **REQ-PROVIDER-P0-002：商品/服务能力对齐（支持“物流商品 + 到店服务”）**
  - **背景/问题**：当前 provider 商品服务页需对齐 REQ-ADMIN-P0-002。
  - **目标**：provider 侧可创建/管理两类：服务、物流商品；并与订单/履约对齐。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderProductsPage.vue` + 后端 provider products API。
  - **验收标准（DoD）**：同 REQ-ADMIN-P0-002 的最小字段/状态。
  - **实现证据（文本）**：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`、`backend/app/api/v1/provider.py`

- [x] **REQ-PROVIDER-P0-003：新增商品/服务时“标签选择”下拉为空（补齐标签管理与数据来源）**
  - **背景/问题**：标签 select 为空，不知如何添加新标签。
  - **目标**：提供标签数据来源与管理入口（至少能新增/启用/禁用）。
  - **范围（待确认）**：标签的存储与接口（SystemConfig? taxonomy? product.tags?）（Q8）。
  - **确认结论（你已确认）**：标签为**全局库**，由 Admin 统一管理，且需要**区分标签类型**（电商常见服务/产品品类）。
  - **最小规格草案（按你确认，已实现 v1）**：
    - 数据源：后端提供 `GET /api/v1/tags?type=PRODUCT|SERVICE|VENUE`（仅返回 enabled=true 且已发布口径）
    - 管理：Admin 维护全局标签库（新增/编辑/启用/停用/排序）
    - Provider 商品/服务编辑：按履约类型/对象类型过滤可选标签（不允许 provider 自造标签）
  - **验收标准（DoD）**：
    - [x] Provider 侧“标签下拉”有数据（来源为全局库）
    - [x] Admin 有标签维护入口，可启用/停用
    - [x] 标签按类型区分（PRODUCT/SERVICE/VENUE）
  - **实现证据（文本）**：
    - 读侧接口：`backend/app/api/v1/tags.py`、`backend/app/api/v1/router.py`
    - 管理接口复用 taxonomy：`backend/app/api/v1/taxonomy_nodes.py`（type 扩展为 *_TAG）
    - Admin 页面：`frontend/admin/src/pages/admin/AdminTagsPage.vue`、`frontend/admin/src/lib/nav.ts`、`frontend/admin/src/router/index.ts`
    - Provider 选择下拉：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`

- [x] **REQ-PROVIDER-P0-004：场所信息校验与地区选择能力（全中国地区可选）**
  - **背景/问题**：场所信息缺少校验；城市选择 no data；并且“选择场所”逻辑与“一个服务提供方=一个场所”认知冲突。
  - **目标**：
    - 表单必填/格式校验完善
    - 地区选择可用（全中国）
    - 明确并落地 provider 与 venue 的关系（单场所 or 多场所）
  - **范围（待确认）**：Provider 场所信息页、后端 Venue/Provider 模型与权限（Q9）。
  - **确认结论（你已确认）**：**一个 Provider 只能有一个 Venue**。
  - **最小规格草案（按你确认，已实现 v1）**：
    - 地区选择：复用 `REGION_CITIES`（至少 CITY；若需省级下拉则要求配置包含 PROVINCE）
    - 校验：名称/地址/联系电话/封面图/介绍/城市为必填；手机号/电话格式校验
    - “选择场所”口径：若单 Provider=单场所，则移除选择器并固定当前场所
  - **实现证据（文本）**：
    - 场所信息页（地区选择/校验/单场所固定）：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
    - 提交展示按钮：先保存（PUT）再提交展示（POST submit-showcase），避免提交未保存数据：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
    - 地区数据源：`backend/app/api/v1/regions.py`、`backend/app/api/v1/admin_regions.py`
    - 后端场所更新校验：`backend/app/api/v1/provider.py`（`PUT /provider/venues/{id}`、提交展示校验）

- [x] **REQ-PROVIDER-P0-005：去除/改正多处“选择场所”能力（若确认单 Provider=单场所）**
  - **背景/问题**：健行天下服务页/工作台/核销/排期容量等多处有场所选择，需与业务关系对齐。
  - **目标**：若业务确认“单 Provider=单场所”，则这些页面默认锁定当前场所，不再选择。
  - **范围（候选）**：`frontend/admin/src/pages/provider/*` 多页 + 后端 provider context（Q9）。
  - **确认结论（你已确认）**：**单 Provider=单场所**。
  - **最小规格草案（按你确认，已实现 v1）**：
    - 若确认“单 Provider=单场所”：以下页面全部移除“选择场所”，默认锁定当前场所：
      - 工作台（场所数量口径）、健行天下服务、核销、排期/容量、场所信息等
    - 若确认“多场所”：保留选择器，但必须补齐地区数据源与必填校验，且默认选中一个“主场所”
  - **实现证据（文本）**：
    - 工作台：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`（场所数量按单场所口径）
    - 健行天下服务：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`（固定场所）
    - 核销：`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`（固定场所）
    - 排期/容量：`frontend/admin/src/pages/provider/ProviderSchedulesPage.vue`（固定场所）
    - 场所信息：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`（固定场所）

#### 3.3 Dealer 升级需求

- [x] **REQ-DEALER-P0-001：链接/参数管理生成链接时增加参数校验（有效期必填）**
  - **背景/问题**：生成链接未做参数校验，有效期应必填。
  - **目标**：前端必填校验 + 后端兜底校验（避免绕过）。
  - **范围（候选）**：`frontend/admin/src/pages/dealer/DealerLinksPage.vue` + 后端 dealer links API。
  - **验收标准（DoD）**：
    - [x] 有效期为空不可提交
    - [x] 后端返回明确 400 错误码（INVALID_ARGUMENT）与 message
  - **实现证据（文本）**：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`、`backend/app/api/v1/dealer_links.py`

- [x] **REQ-DEALER-P0-002：结算记录“结算周期”输入升级为更易用组件/说明**
  - **背景/问题**：结算周期 input 使用方式不清晰。
  - **目标**：改成可选择/可解释的组件（例如：月度区间选择、或下拉选择结算周期模板）。
  - **范围（待定位）**：Dealer settlements 页面与后端筛选参数（Q10）。
  - **实现（v1 最小）**：将周期输入从自由文本升级为“月份选择器”（输出仍为 `YYYY-MM`，不改后端契约）
  - **实现证据（文本）**：`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`、`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`

#### 3.4 H5 升级需求

- [x] **REQ-H5-P0-001：H5 使用说明补齐（给出最小可执行路径）**
  - **背景/问题**：当前你没看懂怎么使用。
  - **目标**：在规格中补齐“H5 最小使用步骤”（从 dealer link 打开、下单、支付、跳转结果页等）。
  - **范围**：`specs/health-services-platform/facts/h5.md` + `README`（仅文档层面）。
  - **验收标准（DoD）**：
    - [x] 给出从 dealer link → 购买页 → 下单/支付 → 结果页的最短步骤
    - [x] 每一步给出证据入口（页面文件/接口路径）
  - **实现证据（文本）**：`specs/health-services-platform/facts/h5.md`（“最小可执行使用路径”）、`specs/health-services-platform/README.md`

- [x] **REQ-H5-P0-002：购买区域选择数据源补齐（REGION_CITIES 配置 + 省/市/全国联动）**
  - **背景/问题**：H5 购买页区域选择下拉为空；提示需要配置 `SystemConfig.key=REGION_CITIES`。
  - **目标**：能根据 sellable card 的 `regionLevel` 决定选择维度：
    - 全国：不可选（默认）
    - 省：可选省
    - 市：可选市
  - **范围（待确认）**：
    - H5：`frontend/h5/src/pages/BuyPage.vue`
    - 后端：`backend/app/api/v1/regions.py`（REGION_CITIES 数据结构约定）与配置管理入口（Admin）联动
  - **数据结构约定（建议，等待你确认）**：
    - SystemConfig.key：`REGION_CITIES`
    - value_json：
      - `version: string`：发布版本号（发布时写入）
      - `defaultCode?: string | null`：默认选中项（必须存在于“已发布且启用”的 items 中，否则读侧会置空）
      - `items: Array<{ code: string; name: string; sort: number; enabled: boolean; published: boolean }>`
    - `code` 约定前缀（供各端按维度过滤）：
      - `COUNTRY:CN`：全国（可选；仅用于展示，不参与下拉）
      - `PROVINCE:<行政区划码>`：省级（如 `PROVINCE:110000`）
      - `CITY:<行政区划码>`：市级（如 `CITY:110100`）
  - **维护与发布闭环（建议，等待你确认）**：
    - Admin 提供页面维护 items，并提供“发布/下线”动作
    - 后端提供 Admin 接口：GET/PUT（草稿）/POST publish/POST offline
  - **验收标准（DoD）**：
    - [x] 当 regionLevel=COUNTRY：展示“全国（默认）”，不出现空下拉
    - [x] 当 regionLevel=PROVINCE/CITY：下拉有数据且可选择；提交时 regionScope 正确
    - [ ] 读侧（H5/Admin/Provider 等）只展示 **enabled=true 且 published=true** 的 items；enabled=false 的城市/省在任何选择器中均不可见
  - **待确认点（Q11）**：
    - [ ] 你是否确认采用上述“Admin 页面维护并发布”的闭环？
    - [ ] 数据规模：先覆盖“已开通城市”（可随业务增长补齐），还是一次性导入“全国省/市全量”？
  - **实现证据（文本）**：`frontend/h5/src/pages/BuyPage.vue`、`backend/app/api/v1/regions.py`、`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`、`backend/app/api/v1/admin_regions.py`

- [x] **REQ-ADMIN-P1-012：服务大类管理-新增/编辑弹窗说明文字布局优化（避免不自然换行）**
  - **背景/问题**：Admin「健行天下 → 服务大类管理 → 新增服务大类」弹窗中，输入框下方“约束说明”文字出现不舒适换行。
  - **目标**：说明文字应当**在输入框下方单独一行**自然换行；弹窗宽度可适当增大；不改变字段含义与校验逻辑。
  - **范围**：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue`
  - **验收标准（DoD）**：
    - [x] code 输入框下方的说明始终独占一行区域（不会挤在同一行与输入框并排导致怪异换行）
    - [x] dialog 宽度略增（720px）后，说明文字阅读更舒适
  - **实现证据（文本）**：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue`

- [x] **REQ-H5-P1-003：H5 购卡页展示该卡“服务内容（服务大类×次数）”**
  - **背景/问题**：用户在购卡页（`/h5/buy`）无法看到该卡包含哪些服务与次数，购买决策信息缺失。
  - **目标**：购卡页展示“该卡包含服务（服务大类×次数）”列表，口径与落地页一致。
  - **范围（候选）**：
    - H5：`frontend/h5/src/pages/BuyPage.vue`
    - 后端：复用现有 `GET /api/v1/service-packages/{templateId}`（不新增字段）
  - **交互规则（最小）**：
    - [x] 在价格/商品信息区域下方增加“包含服务”区块：逐行展示 `serviceType` 与 `totalCount`
    - [x] 加载失败：展示“加载失败/重试”，不影响继续下单（但需明确提示）
  - **验收标准（DoD）**：
    - [x] 省卡/市卡/全国卡均可在购卡页看到服务列表或明确错误态
  - **实现证据（文本）**：`frontend/h5/src/pages/BuyPage.vue`（`loadServicePackage()` + 页面展示）

- [x] **REQ-H5-P1-004：H5 省卡/市卡购买区域选择体验升级（级联选择 + 模糊搜索，无“最近选择”）**
  - **背景/问题**：`CITY:*` 城市选项数量大，滚轮选择体验差；省卡/市卡维度要求不同。
  - **目标**：同时支持两种方式：A) 省/市级联选择；B) 模糊搜索；且省卡必须选到省、市卡必须选到市；不提供“最近选择”。
  - **范围**：`frontend/h5/src/pages/BuyPage.vue`
  - **规则（按你确认）**：
    - [x] regionLevel=PROVINCE：必须选择 `PROVINCE:<code>`；提供省列表与搜索过滤
    - [x] regionLevel=CITY：必须选择 `CITY:<code>`；提供“先省后市”的级联选择；同时提供搜索城市名快速定位（可直接选中市）
    - [x] 不新增“最近选择/历史选择”
  - **数据约定（沿用已实现）**：
    - `GET /api/v1/regions/cities` 返回 `items[{code,name,sort}]`
    - code 前缀：`PROVINCE:`/`CITY:`（如 `PROVINCE:110000`、`CITY:110100`）
  - **待确认点（Q-H5-REGION-001）**：
    - [x] 行政区划码映射采用 GB/T 2260 6 位码规则：`CITY:110100 -> PROVINCE:110000`（取前 2 位 + `0000`）
  - **实现证据（文本）**：`frontend/h5/src/pages/BuyPage.vue`（级联 + 搜索 + 必选校验）

- [x] **REQ-H5-P1-005：H5 信息架构重构（首页介绍页 + 经销商卖卡列表 + 带参直达购卡）**
  - **背景/问题**：
    - 现状 H5 更像“技术联调页”：依赖 query 才能看到卡信息，且投放链接使用的 `ts/nonce/sign` 受 10 分钟有效期限制，不适合长期投放。
    - 业务口径（按你确认）：**只有经销商能卖卡**；购买入口必须至少带“经销商信息 + 卡信息”，以及技术上必要参数。
  - **目标（按你确认）**：
    - [ ] `/h5` 为《健行天下》产品介绍页（不依赖参数也可阅读）
    - [ ] 若带经销商入口参数：展示“该经销商已生成投放链接的卡片列表”与基本信息；点击某卡进入购卡页
    - [ ] 若同时带“经销商 + 卡”：直接进入该经销商指定卡的购卡页
    - [ ] 购买入口必须可长期投放（不可依赖 10 分钟过期的静态签名）
    - **推荐技术契约（最小，可长期投放）**：
    - **投放 URL 统一改为使用 `dealerLinkId`**（uuid，来自后台生成的 DealerLink 记录），H5 通过后端只读接口解析：
      - 入口形态（经销商参数 + 可选卡参数）：
        - 经销商入口链接：`/h5?dealerLinkId=<ENTRY_LINK_ID>`（用于查看该经销商全部可售卡，并点选进入购卡页）
        - 指定卡直达：`/h5?dealerLinkId=<ENTRY_LINK_ID>&sellableCardId=<CARD_ID>`（直达该卡购卡页）
    - **后端新增 H5 只读接口（无需登录）**：
      - `GET /api/v1/h5/dealer-links/{dealerLinkId}`
        - 返回：`{ dealer:{id,name}, sellableCard?:{id,name,regionLevel,priceOriginal,servicePackageTemplateId}, link:{id,status,validFrom,validUntil} }`
        - 约束：仅 ENABLED 且未过期可用；否则返回 403/404（明确错误码）
      - `GET /api/v1/h5/dealer-links/{dealerLinkId}/cards`
        - 返回该 dealer 下所有“已生成投放链接且可用”的卡列表（用于经销商入口页展示）
      - `GET /api/v1/h5/dealer-links/{dealerLinkId}/cards/{sellableCardId}`
        - 返回指定卡详情（并校验该 dealer 是否有权售卖该卡）
    - **下单绑定经销商的方式（避免 10 分钟签名问题）**：
      - `POST /api/v1/orders`（H5 channel, SERVICE_PACKAGE）新增 query：`dealerLinkId`
      - 后端校验 dealerLinkId 可用，并将订单绑定到该 dealerId；同时校验“订单的 sellableCardId 属于该 dealer 已授权可售范围”（严格门禁）
    - **保留 dealerId/ts/nonce/sign 校验**：
      - 继续作为“防篡改属性”的通用能力与兼容接口（`GET /api/v1/dealer-links/verify`），但不再作为长期投放链接的必备入口参数。
  - **范围（候选）**：
    - H5：`frontend/h5/src/pages/LandingPage.vue`、`frontend/h5/src/pages/BuyPage.vue`、路由（`frontend/h5/src/main.ts`）
    - Dealer/Admin：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`、`backend/app/api/v1/dealer_links.py`
    - 后端：新增 H5 只读接口（建议放 `backend/app/api/v1/h5_config.py`）
    - 订单：`backend/app/api/v1/orders.py`（新增 dealerLinkId 校验与绑定）
  - **验收标准（DoD）**：
    - [x] 经销商入口打开 `/h5`：展示经销商名称 + 该经销商可售卡列表
    - [x] 带 `sellableCardId` 打开 `/h5`：直达该卡购卡页，且可看到服务内容与区域选择
    - [x] 无 dealerLinkId 时：仅展示产品介绍，且“立即购买”入口**不可点击**（置灰/不可见均可，最终实现以阻断为准）（前端门禁）
    - [x] `/h5/buy` 无 dealerLinkId 或 dealerLink 未绑定卡：**阻断购买页内容**（展示门禁空态），避免任何误购/误记账（前端门禁）
    - [x] 下单必须带 dealerLinkId，后端能正确绑定订单 dealerId
  - **待你确认的 2 个关键点（Q-H5-DEALERLINK-001/002）**：
    - [x] 是否确认“投放链接参数”从 `dealerId/ts/nonce/sign` **切换为** `dealerLinkId`（uuid）作为长期投放主入口？（你已确认）
    - [x] 是否确认 `POST /orders` 绑定经销商改为 **接受 `dealerLinkId`**（而不是要求携带可过期的签名参数）？（你已确认）
  - **实现证据（文本）**：
    - DealerLinks 生成 URL：`backend/app/api/v1/dealer_links.py`、`frontend/admin/src/pages/dealer/DealerLinksPage.vue`
    - H5 只读解析：`backend/app/api/v1/h5_config.py`、`frontend/h5/src/pages/LandingPage.vue`、`frontend/h5/src/pages/BuyPage.vue`
    - 下单绑定：`backend/app/api/v1/orders.py`

- [x] **REQ-H5-P1-006：H5 C 端视觉风格系统升级（仅视觉，不改信息架构/契约）**
  - **规格依据**：
    - 全局风格系统提示词（你提供）：可信赖、健康活力、现代简洁；明亮留白、信息层级清晰、圆角卡片、轻阴影、柔和渐变背景点缀；偏 iOS/微信审美；不使用外部图片素材；仅线性图标/几何占位；移动端转化优先；底部固定 CTA；加载/空/错误态统一。
    - 现有 H5 “事实与页面边界”：`specs/health-services-platform/facts/h5.md`（`/h5`、`/h5/buy`、`/h5/pay/result`）
  - **背景/问题**：
    - 当前 H5 样式偏“工程默认/技术联调”，品牌一致性弱，页面层级与 CTA 视觉不够聚焦。
  - **目标**：
    - 在不改变既有路由、门禁、接口契约、信息结构顺序的前提下，统一升级为“陆合铭云健康服务平台”C 端视觉体系（适配微信/iOS 审美，提升转化与下单体验）。
  - **范围**：
    - H5：`frontend/h5/src/style.css`、`frontend/h5/src/pages/LandingPage.vue`、`frontend/h5/src/pages/BuyPage.vue`、`frontend/h5/src/pages/PayResultPage.vue`
    - **明确不做**：不改 API、字段、交互流程与页面信息架构（以 `facts/h5.md` 为准）；不引入外部图片/摄影图；不引入微信 JS-SDK（规格未定义）
  - **设计/样式规则（最小可执行）**：
    - **配色（统一三端口径，先在 H5 落地）**：
      - 主色（teal）：用于品牌/主按钮/重点信息（建议默认值：`#14b8a6`）
      - 辅色（slate/navy）：用于标题/正文主色（建议：`#0f172a`、`#334155`）
      - 强调色（橙黄）：用于 CTA/价格/关键行动（少量使用，建议：`#f59e0b`）
      - 背景：浅灰白 + 极淡青绿渐变氛围（不使用图片）
    - **排版与间距**：
      - 标题加粗、正文常规；价格数字更大更醒目；模块间距 > 元素间距；卡片分组为主；每屏 1 个主行动按钮（底部固定 CTA）
    - **组件语言**：
      - 卡片（圆角 12–16）+ 轻阴影；标签/列表/表单区块化；按钮主次明确（主按钮实心、次按钮描边/幽灵）
      - 状态（加载/空/错误）：使用 Vant 组件时统一“简洁几何占位 + 文案”，不引入外部图片素材
    - **可访问性**：
      - 触控区 ≥ 44px；对比度充足；重要信息不只靠颜色区分
  - **验收标准（DoD）**：
    - [x] `LandingPage/BuyPage/PayResultPage` 视觉风格统一：明亮留白、圆角卡片、轻阴影、柔和渐变背景点缀
    - [x] CTA 视觉聚焦：价格数字更醒目；关键行动使用强调色但克制；底部固定 CTA 在滚动时始终可见且不遮挡内容
    - [x] 不引入任何外部图片素材；空/错/加载态符合“几何占位 + 文案”口径
    - [x] 不改变既有门禁、路由与信息架构顺序（以 `facts/h5.md` 为准）
  - **待确认点（必须先确认再改代码）**：
    - [x] **Q-H5-STYLE-001**：你说的“页面结构描述有误”，具体是以下哪一种？（按你确认）
      - [x] A) 仅你提供的提示词里对“落地页模块顺序/必含模块”的描述不适用，但现有结构（经销商卖卡列表 + FAQ/条款 + 底部 CTA）保持不变
      - [ ] B) 现有页面结构也需要调整（若选 B，需要你给出正确 IA/原型，否则本需求仅做视觉）
    - [x] **Q-H5-STYLE-002**：是否有品牌色的**固定色值**（teal/slate/强调橙黄）？
      - [x] 当前无固定色值：先使用默认值落地，并封装为 CSS 变量（后续仅需替换变量即可全站变更）
  - **实现证据（文本）**：
    - [x] H5 主题变量与基础样式：`frontend/h5/src/style.css`
    - [x] 页面适配与卡片化：`frontend/h5/src/pages/*.vue`

- [x] **REQ-H5-P1-007：H5 高级感视觉微调（高端服务卡质感增强，仅视觉）**
  - **规格依据**：
    - 你最新确认：现有页面结构不变；需要更“高级感”（高端服务卡）视觉表达；你不关心技术实现细节，由我给出默认方案落地
    - `REQ-H5-P1-006` 的风格系统与约束（不外图/不改流程/不做花哨动效）
  - **目标**：
    - 在保持“可信赖、健康活力、现代简洁”的前提下，进一步提升质感：更克制的色彩层级、更精细阴影与边框、更统一的按钮/卡片/分割线/排版节奏。
  - **范围**：
    - H5 全局与全部页面：`frontend/h5/src/style.css`、`frontend/h5/src/pages/*.vue`
  - **规则（默认执行，不再追加确认点）**：
    - **色彩层级**：正文更深、辅助更柔；强调色仅用于“关键行动/价格”局部点睛，不做大面积铺色
    - **材质**：卡片使用“细边框 + 双层轻阴影”增强层次；分割线使用 hairline（更轻更干净）
    - **按钮**：购买/提交类 CTA 使用“强调色实心”，其余主按钮保持品牌主色；次按钮为描边/幽灵
    - **避免项**：不引入纹理/摄影图/复杂插画；不做强玻璃拟态（允许轻透明但不做强 blur 视觉主导）
  - **验收标准（DoD）**：
    - [x] 所有页面卡片/按钮/分割线/字体层级一致，整体更“干净、克制、有层次”
    - [x] 购买页提交 CTA 的视觉优先级最高（更醒目但不过饱和），不影响可访问性与对比度
    - [x] 不改页面结构/路由/门禁/接口；不新增外部图片素材
  - **实现证据（文本）**：
    - [x] `frontend/h5/src/style.css`（tokens 与 Vant 变量微调）
    - [x] `frontend/h5/src/pages/BuyPage.vue`（提交 CTA 皮肤）

#### 3.5 Website 升级需求

- [x] **REQ-WEBSITE-P1-001：Header 窄屏换行问题修复（布局不换行/更合理折叠）**
  - **背景/问题**：窗口变窄时 header 内容换行，布局异常。
  - **目标**：窄屏下清晰：品牌区 + 菜单按钮；其余收进抽屉（或保持单行不挤压）。
  - **范围**：`frontend/website/src/layouts/SiteLayout.vue`
  - **验收标准（DoD）**：
    - [x] 900px 以下不出现 header 多行换行导致抖动
    - [x] 主要 CTA 仍可通过抽屉访问
  - **实现证据（文本）**：`frontend/website/src/layouts/SiteLayout.vue`

- [ ] **REQ-WEBSITE-P1-004：官网 Header 导流入口改版（移除 H5 购买按钮；小程序入口改为二维码弹窗）**
  - **背景/问题**
    - 官网 Header 当前有“进入小程序”“H5购买高端服务卡”两个按钮，且受 Admin「官网配置→导流外链」控制。
    - 你已确认：不需要“H5购买高端服务卡”功能；小程序入口希望展示二维码，方便用户扫码进入。
  - **目标**
    - 移除 Header 的 “H5购买高端服务卡” 按钮与相关交互。
    - “进入小程序”改为弹出二维码（二维码内容来源于导流外链中的 `miniProgramUrl`）。
  - **范围（候选）**
    - 官网布局/Header：`frontend/website/src/layouts/SiteLayout.vue`
    - 导流外链读取：`frontend/website/src/lib/websiteExternalLinks.ts`
  - **交互规则（v1）**
    - 点击“进入小程序”：
      - 若 `miniProgramUrl` 已配置：弹出对话框展示二维码（可复制链接为辅）
      - 若未配置：toast 提示“小程序入口未配置”
    - 不再展示/调用 `h5BuyUrl`
  - **验收标准（DoD）**
    - [ ] Header 不再出现“H5购买高端服务卡”
    - [ ] Header 的“进入小程序”变为二维码弹窗，窄屏可用、可关闭
    - [ ] 仍受 Admin 导流外链开关/配置影响（未配置时提示）
  - **实现证据（文本）**：TBD

- [ ] **REQ-WEBSITE-P1-005：官网整体响应式窄屏不裁切内容（必要时换行/滚动）**
  - **背景/问题**：窗口变窄时右侧内容会被吞掉且无横向滚动条，导致信息不可见。
  - **目标**：窄屏下内容可读、可操作，不出现“被裁切但无法滚动/换行”的状态。
  - **范围（候选）**
    - 全局布局与容器：`frontend/website/src/layouts/SiteLayout.vue`、`frontend/website/src/assets/*`（若存在全局样式）
    - 关键页面：`frontend/website/src/pages/HomePage.vue`、`frontend/website/src/pages/ContentCenterPage.vue`
  - **验收标准（DoD）**
    - [ ] 宽度缩小到 360~420px：页面不应裁切关键内容（Header/按钮/主内容区）
    - [ ] 若出现横向溢出：必须可横向滚动或通过换行避免溢出（两者选其一且一致）
  - **实现证据（文本）**：TBD

- [ ] **REQ-WEBSITE-P1-006：官网内容中心筛选栏布局优化（栏目/搜索/按钮）**
  - **背景/问题**：内容中心页面中“栏目 + 搜索 input + 搜索/重置按钮”容器布局不合理（信息密度高、对齐不佳）。
  - **目标**：筛选栏在宽屏/窄屏下均清晰对齐，按钮与输入的层级更合理。
  - **范围（候选）**：`frontend/website/src/pages/ContentCenterPage.vue`
  - **验收标准（DoD）**
    - [ ] 筛选栏在宽屏：同一行对齐，间距合理
    - [ ] 窄屏：自动换行，按钮不被挤压/裁切
  - **实现证据（文本）**：TBD

- [x] **REQ-WEBSITE-P1-008：官网场所详情页联系电话展示为明文（便于用户联系）**
  - **背景/问题**：官网场所详情页当前优先展示 `contactPhone`，缺失时回退为 `contactPhoneMasked`，导致用户看到的是脱敏号码，无法直接联系。
  - **目标**：在官网场所详情页展示**可拨打的明文联系电话**（若场所已发布且有配置）。
  - **范围（候选）**
    - 官网详情页：`frontend/website/src/pages/VenueDetailPage.vue`
    - 后端场所详情（public）：`backend/app/api/v1/venues.py::GET /api/v1/venues/{id}`
  - **规则（最小，待你确认后再实现）**
    - 列表接口 `GET /api/v1/venues`：仍仅返回 `contactPhoneMasked`（避免列表面暴露 PII）
    - 详情接口 `GET /api/v1/venues/{id}`：在返回 `contactPhoneMasked` 的同时，补充 `contactPhone` 明文（仅 PUBLISHED 场所）
  - **待确认点（必须）**
    - [ ] 是否允许 **未登录用户** 在官网详情页看到明文电话？（v1 草案：允许；否则需要定义“登录门禁/展示口径”）
  - **验收标准（DoD）**
    - [ ] 官网场所详情页：展示明文电话；不再回退展示脱敏号导致无法联系
    - [ ] 场所无电话时：展示“—/暂无”，不展示脱敏占位
  - **实现证据（文本）**：
    - 后端 public detail 出参补 `contactPhone` 明文：`backend/app/api/v1/venues.py`
    - 官网详情不再回退脱敏字段：`frontend/website/src/pages/VenueDetailPage.vue`

### 5) 变更记录（按需求）

> 规则：每次升级完成后追加（需求 → 改动点 → 风险/回滚 → 事实清单更新位置）。

- **REQ-ADMIN-P0-001**：未登录统一跳登录 + toast  
  - 改动点：路由守卫统一重定向 `/login?next=...&reason=UNAUTHENTICATED`；登录页消费 reason 并 toast；API 401 自动清 session 并跳转  
  - 风险/回滚：仅前端体验层；回滚为移除 beforeEach/401 处理  
  - 事实更新：`facts/admin.md`
- **REQ-DEALER-P0-001**：生成链接有效期必填校验  
  - 改动点：前端必填/区间校验；后端 `validUntil` 必填与区间校验  
  - 风险/回滚：仅新增校验；回滚为移除校验（不推荐）  
  - 事实更新：`facts/admin.md`、`facts/backend.md`
- **REQ-H5-P0-002**：购买区域选择数据源补齐（REGION_CITIES）  
  - 改动点：Admin 草稿/发布/下线/导入全国；H5 购买页按 regionLevel 过滤显示；各端按 CITY 前缀过滤  
  - 风险/回滚：仅新增配置与筛选；回滚为不展示下拉（不推荐）  
  - 事实更新：`facts/admin.md`、`facts/h5.md`、`facts/backend.md`
- **REQ-PLATFORM-P0-001**：彻底移除虚拟券能力  
  - 改动点：后端枚举/下单/履约/权益/退款/测试移除虚拟券；前端 Admin/小程序移除入口与文案  
  - 风险/回滚：破坏性（已确认系统未上线可接受）；回滚需恢复旧枚举与逻辑  
  - 事实更新：`facts/admin.md`、`facts/mini-program.md`、`facts/backend.md`
- **REQ-ECOMMERCE-P0-001**：物流商品 v2（地址簿+库存占用/释放+发货/签收基础）  
  - 改动点：新增地址簿 API/页面；下单预占与 Celery 超时释放；支付确认扣减；发货/妥投/确认收货；Admin 订单监管展示与发货录入  
  - 风险/回滚：涉及订单/库存字段与定时任务；回滚为禁用 PHYSICAL_GOODS 入口与迁移回滚（不推荐）  
  - 事实更新：`facts/backend.md`、`facts/admin.md`、`facts/mini-program.md`
- **REQ-WEBSITE-P1-001**：官网 header 窄屏不换行  
  - 改动点：提前触发移动端导航断点，避免桌面导航导致换行  
  - 风险/回滚：仅样式；回滚为恢复旧断点  
  - 事实更新：`facts/website.md`
- **MP-OPS-BANNER-001**：小程序首页 Banner 图片不显示/点击无跳转（运营位）  
  - 改动点：小程序端增强静态 URL 绝对化（兼容 `static/...`），Banner 取图字段容错（`iconUrl/imageUrl/snake_case`）；`navigateByJump` 对缺参/跳转失败输出 warn；Swiper 点击事件增加兜底绑定；管理端发布前校验 enabled entries 的 `jumpType/targetId` 合法性  
  - 风险/回滚：主要为容错与校验增强；回滚为移除校验/兜底，但会恢复“发布后端上静默无响应”风险  
  - 事实更新：`facts/mini-program.md`、`facts/admin.md`
  - 补充：为 Banner 图片增加 `bindload/binderror` 日志与失败占位回退（用于定位“无网络请求/无报错”的端侧现象）

- **MP-OPS-QUALITY-001（待确认是否强制）**：小程序“代码质量→代码包→组件显示”提示“启用组件需要按需注入”  
  - 现象：在 `app.json` 开启 `lazyCodeLoading: "requiredComponents"` 后，小程序启动时报错 `module '@babel/runtime/helpers/arrayWithHoles.js' is not defined`，导致首页不可用（仓库内无 `miniprogram_npm` 产物）。  
  - 处理：已回滚 `lazyCodeLoading`（保持当前可运行）；若你们后续**必须**让该代码质量项通过，需要先补齐规格与构建口径（是否引入并固化 npm 构建产物/依赖，或调整编译设置），再进入实现。  
  - 风险/回滚：该项属于“质量建议/门禁”而非业务功能；强行开启会引入构建链路变更风险。  

---

### 6) 平台级优化（vNext：上线与可运维门禁）

> 说明：本节用于下一轮“平台级优化”的规格落点。  
> 规则：先写清 **上线口径与验收**，你确认后再开始改代码/改部署。

#### 6.1 发布与部署（Release Playbook）

- [x] **REQ-PLATFORM-P0-002：发布手册与一键部署脚本（Windows/Ubuntu）**
  - **背景/问题**：目前已具备 docker compose，但缺少“可照着做就能上线”的发布手册与一键命令口径。
  - **目标**：提供可重复的上线步骤（含环境变量、迁移、回滚、验收），并在 Windows/Ubuntu 各给一个一键脚本入口。
  - **范围（候选）**：`docker-compose.yml`、`ops/release/deploy.ps1`、`ops/release/deploy.sh`、`.env.example`、`README`。
  - **验收标准（DoD）**：
    - [x] 只按手册操作即可从 0 部署到可用（含数据库迁移）
    - [x] 失败回滚路径明确（回滚策略不要求自动化，但要可操作）
    - [x] 明确区分 dev/staging/prod 的关键差异（尤其密钥/回调地址）
  - **待确认点（必须）**：
    - 你要的生产形态：**单机 docker compose** 还是 **多机/集群**？
    - 是否需要 HTTPS（域名证书）与反向代理（Nginx）？
  - **确认结论（你已确认）**：单机 docker compose；需要域名+HTTPS+Nginx 反代。
  - **实现证据（文本）**：
    - 发布手册：`ops/release/README.md`
    - 环境变量模板：`ops/release/env.example`
    - 部署脚本：`ops/release/deploy.ps1`、`ops/release/deploy.sh`、`ops/release/rollback.ps1`、`ops/release/rollback.sh`
    - Nginx HTTPS 模板：`nginx/conf.d/https.conf.example`、`docker-compose.yml`（443 映射与证书挂载）

#### 6.2 数据库迁移与初始化（DB Gate）

- [x] **REQ-PLATFORM-P0-003：数据库迁移门禁与初始化脚本**
  - **背景/问题**：已经有 Alembic migrations，但缺少“上线前必须迁移成功”的门禁与初始化口径（例如默认账号/基础字典）。
  - **目标**：提供迁移命令、初始化命令、以及启动前/启动后检查点。
  - **范围（候选）**：`backend/alembic/*`、`backend/app/main.py`、`backend/app/utils/settings.py`、`ops/*`
  - **验收标准（DoD）**：
    - [x] staging/prod 可稳定执行迁移（可重复、可回滚、可定位失败）
    - [x] 初始化项列表清晰（例如：初始 admin、基础字典、示例数据是否允许）
  - **待确认点（必须）**：
    - 是否需要“生产禁止 seed demo 数据”的硬门禁？（目前部分页面有 seed 按钮）
  - **确认结论（你已确认）**：必须加。
  - **实现证据（文本）**：
    - 迁移：`docker-compose.yml`（backend 启动时自动 `alembic upgrade head`）、`ops/migrations/migrate.ps1`、`ops/migrations/migrate.sh`
    - 生产 seed 门禁：`backend/app/api/v1/admin_dev.py`（production 403）

#### 6.3 端到端冒烟验收（Smoke Tests）

- [x] **REQ-PLATFORM-P0-004：一键冒烟验收清单（不依赖截图/日志）**
  - **背景/问题**：目前功能较多，需要一个“上线前 15 分钟跑完”的验收闭环清单。
  - **目标**：用文本步骤+接口路径，把核心链路的验收固定下来（便于交接/回归）。
  - **范围（候选）**：`specs/health-services-platform/tasks.md`（本文件）、`facts/*`。
  - **验收标准（DoD）**：
    - [x] 覆盖 H5：登录→下单→支付→结果页
    - [x] 覆盖小程序：登录→权益→预约→商城下单→订单
    - [x] 覆盖后台：协议/标签/小程序配置发布→Provider 上架/开通→Dealer 结算生成/标记打款
  - **验收步骤（15 分钟冒烟，文本）**：
    - **A. 基础设施（1 分钟）**
      - [ ] `GET /api/v1/health/live` 返回 success=true
      - [ ] `GET /api/v1/health/ready` 返回 success=true（DB/Redis 可用）
      - [ ] `GET /api/v1/openapi.json` 返回 200（兼容入口）
      - 证据：`backend/app/api/v1/health.py`、`backend/app/api/v1/openapi_proxy.py`
    - **B. Admin（3~5 分钟）**
      - [ ] 登录 Admin（`/admin/auth/login`）
      - [ ] 进入「系统与审计 → 协议/条款管理」：为 `H5_BUY_AGREEMENT` 与 `MP_LOGIN_AGREEMENT` 保存草稿并发布
      - [ ] 进入「基建联防 → 标签库（全局）」：新增一个 `SERVICE` 标签并保持 ENABLED
      - [ ] 进入「运营工具 → 小程序配置中心」：在“首页入口”新增一个快捷入口 + 一个 Banner（OPERATION），保存草稿并发布
      - 证据：`frontend/admin/src/pages/admin/AdminLegalAgreementsPage.vue`、`AdminTagsPage.vue`、`AdminMiniProgramConfigPage.vue`
    - **C. Provider（3~5 分钟）**
      - [ ] Provider 登录后进入工作台：打开基建联防/健行天下开通弹窗，勾选协议并提交（agree=true）
      - [ ] 进入「商品/服务」新增一个 SERVICE（选择刚刚创建的标签）
      - 证据：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`、`ProviderProductsPage.vue`
    - **D. H5 购买链路（3~5 分钟）**
      - [ ] 使用 dealer link 打开落地页 → 进入购买页 → 查看“服务协议”弹窗
      - [ ] 门禁验证：直接打开 `/h5/buy`（无 dealerLinkId）应展示门禁空态并阻止购买
      - [ ] 门禁验证：支付结果页点击“重新支付”若缺 dealerLinkId 应提示并回到 `/h5`
      - [ ] 发起下单：`POST /api/v1/orders`（带 Idempotency-Key）
      - [ ] 发起支付：`POST /api/v1/orders/{id}/pay`（带 Idempotency-Key）
      - 证据：`frontend/h5/src/pages/BuyPage.vue`、`backend/app/api/v1/orders.py`
    - **E. 小程序（2~3 分钟）**
      - [ ] 打开“我的”：未登录时可点击查看《服务协议》（MP_LOGIN_AGREEMENT）
      - [ ] 登录 → 权益页/订单页可正常访问
      - 证据：`frontend/mini-program/pages/profile/profile.wxml`、`frontend/mini-program/pages/legal/agreement/agreement.*`
    - **F. Dealer 结算（1~2 分钟）**
      - [ ] Dealer 侧配置结算账户：`PUT /api/v1/dealer/settlement-account`

---

### 7) 下一块业务（C：待确认后进入实现）

> 说明：你要求“按任务列表继续做”，但 C 必须先有明确入口与验收标准，否则会引入未确认需求（违背 Spec-Driven）。

- [ ] **REQ-NEXT-C-001：下一块业务（默认候选，需你二选一或给新入口）**
  - **你要我做哪一个？（只需回复 A/B/C）**
    - **A）Dealer 侧订单归属页易用性**：支持按支付状态筛选、展示 dealerLinkId/卡信息摘要、导出（若已有接口则复用）
      - 入口：Admin → Dealer → 订单归属（`frontend/admin/src/pages/dealer/DealerOrdersPage.vue` 若存在）
      - 验收：能快速定位某个投放链接的成交订单与支付状态
    - **B）H5 支付成功后的“打开小程序”体验强化**：给出更清晰的路径说明/可复制 appid+path、失败兜底更强
      - 入口：`frontend/h5/src/pages/PayResultPage.vue`
      - 验收：用户能按提示稳定找到小程序权益入口
    - **C）经销商投放链接的数据统计（UV/支付数）闭环**：H5 打开首页/购卡页时回传 uv；支付成功后回传 paidCount（不做复杂埋点，仅最小闭环）
      - 入口：`backend/app/api/v1/dealer_links.py` + H5 页面
      - 验收：DealerLinks 列表能看到 uv 与 paidCount 的变化
  - **约束**：
    - 不引入存量迁移要求（你已说明开发阶段）
    - 不新增无规格支撑的字段/接口；若必须新增，会先写最小契约并让你确认
      - [ ] Admin 生成结算单：`POST /api/v1/admin/dealer-settlements/generate`
      - [ ] Admin 标记已打款：`POST /api/v1/admin/dealer-settlements/{id}/mark-settled`
      - 证据：`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`、`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - **实现证据（文本）**：
    - 本条即为冒烟清单落点：`specs/health-services-platform/tasks.md`

#### 6.4 可观测性与运维（Observability）

- [x] **REQ-PLATFORM-P0-005：运行态可观测性补齐（指标/日志/健康探针）**
  - **背景/问题**：已有 `/metrics` 与 requestId，但缺少对“生产可运维”的统一门禁（例如 readiness、关键依赖检查）。
  - **目标**：让运维能快速判断“服务是否可用/为何不可用”，并能定位核心错误路径。
  - **范围（候选）**：`backend/app/main.py`、middleware、docker healthcheck、监控说明文档。
  - **验收标准（DoD）**：
    - [x] 至少区分 liveness/readiness（若当前仅 health，也需明确语义）
    - [x] 关键依赖（DB/Redis/RabbitMQ）异常时的表现可诊断
  - **实现证据（文本）**：
    - 健康探针：`backend/app/api/v1/health.py`（`/health/live`、`/health/ready`）
    - docker healthcheck：`docker-compose.yml`（backend→ready，nginx→live）
    - 反代头兼容：`docker-compose.yml`（uvicorn `--proxy-headers --forwarded-allow-ips=*`）、`nginx/conf.d/default.conf`

---

### 7) 上线可用性排查与修复（vNow：全端“可部署、上线可用”）

> 说明：本节来自你最新的“逐端逐页检查清单”。  
> 规则：先把问题收敛成可验收任务，再逐条实现并在 `facts/*.md` 反写证据。

#### 7.1 Website（官网）

- [x] **REQ-WEBSITE-P0-002：窄屏菜单按钮样式与可点击区域修复**
  - **背景/问题**：窄屏出现的菜单按钮风格不一致，且靠边导致按钮未完整露出/难点击。
  - **目标**：按钮与官网整体风格一致，具备合理 padding 与安全边距；不会贴边/被裁切。
  - **范围（候选）**：`frontend/website/src/layouts/SiteLayout.vue`（Header/移动端按钮区 CSS 与布局）
  - **验收标准（DoD）**：
    - [x] 1100px 以下移动端按钮不贴边，完全可见
    - [x] 按钮样式与官网一致（颜色/圆角/hover）
    - [x] 不引入 header 换行回归（与 REQ-WEBSITE-P1-001 不冲突）
  - **实现证据（文本）**：
    - `frontend/website/src/layouts/SiteLayout.vue`（移动端菜单按钮样式/安全边距）

#### 7.2 Admin（运营后台）

- [x] **REQ-ADMIN-P0-009：企业信息库“程序筛选”改为 Select（注意性能）**
  - **背景/问题**：筛选条件仍需手填编码，难用且易错。
  - **目标**：改为可搜索 Select；大数据量下不卡顿（分页/远程搜索/防抖）。
  - **范围（候选）**：`frontend/admin/src/pages/admin/*Enterprises*.vue`（企业信息库页）、后端企业字典/查询接口（若缺失需补）
  - **验收标准（DoD）**：
    - [x] Select 可搜索，默认不一次性加载全量（读侧已发布城市量级可接受）
    - [x] 选择项展示：名称 + code（小字）
    - [x] 交互不卡顿（本地搜索 + loading）
  - **实现证据（文本）**：
    - Admin 企业信息库页面：`frontend/admin/src/pages/admin/AdminEnterprisesPage.vue`（城市筛选从输入改为 Select，数据源 `/api/v1/regions/cities`）

- [x] **REQ-ADMIN-P0-010：订单监管（商品/服务）说明文案与实际功能对齐**
  - **背景/问题**：说明里“当前视图固定订单类型：PRODUCT”与当前能力不一致。
  - **目标**：说明文案与实际过滤/查询口径一致；避免误导运营。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue` 或相关订单监管页
  - **验收标准（DoD）**：
    - [x] 文案不再出现与当前功能冲突的描述
    - [x] 说明中明确 PRODUCT/SERVICE_PACKAGE 对应业务含义
  - **实现证据（文本）**：
    - Admin 订单监管视图说明：`frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue`

- [ ] **REQ-ADMIN-P1-019：订单监管（基建联防/健行天下）彻底按业务线分开 + 列表摘要字段补齐 + 详情抽屉**
  - **背景/问题**
    - 当前管理后台存在“订单监管”能力，但订单列表字段偏少，难以支持订单管理（无法快速识别“买了什么/当前履约进度”）。
    - 业务上存在两类订单：
      - **基建联防**：电商商品/服务订单（`orderType=PRODUCT`，可能包含物流履约）
      - **健行天下**：服务包购卡订单（`orderType=SERVICE_PACKAGE`，允许匿名购卡）
    - 这两类订单虽然共用表结构（`orders/order_items`），但在运营语境与关注字段上不同，页面展示必须拆分，避免混用造成误读。
  - **目标**
    - 管理后台提供 2 个明确的订单监管页面入口：
      - `基建联防 → 订单监管（商品/服务）`：仅展示 `PRODUCT`
      - `健行天下 → 订单监管（服务包）`：仅展示 `SERVICE_PACKAGE`
    - 列表增加“订单摘要”字段：**`firstItemTitle + itemsCount`**，用于快速识别（列表只负责快速识别，不承载完整明细）。
    - 提供“订单详情抽屉”：展示订单关键字段与 `order_items` 明细，物流订单在详情内展示（脱敏后的）收货地区信息。
    - 服务包匿名订单：下单时写入“联系方式快照”（至少脱敏），以便后台可追踪与管理。
  - **范围（页面/接口/模型）**
    - Admin 页面：
      - `frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue`（两个业务线复用同页，靠路由 meta 固定 orderType）
      - （可选）保留 `AdminOrdersPage.vue` 作为历史/调试页，但不作为菜单入口（避免混用）
    - Admin 列表接口：
      - `GET /api/v1/admin/orders`（返回字段补齐）
    - 订单详情接口（已存在）：
      - `GET /api/v1/orders/{id}`（Admin 可用；补齐必要字段/脱敏口径）
    - 下单接口（服务包匿名）：
      - `POST /api/v1/orders`（匿名 SERVICE_PACKAGE 必须提交 `buyerPhone`）
    - 数据模型：
      - `orders.buyer_phone`：匿名购卡时写入买家手机号快照（数据库存明文，用于后端筛选；对外返回仅脱敏）
  - **字段与脱敏规则（最小）**
    - Admin 列表（`GET /admin/orders`）新增/明确字段：
      - `itemsCount: number`：该订单包含的明细数量（按 `order_items` 聚合）
      - `firstItemTitle: string | null`：该订单用于识别的“第一条标题”（按 `order_items.title` 聚合，定义为 `MIN(title)`；仅用于识别，不承诺真实购买顺序）
      - `dealerLinkId: string | null`：投放链接 ID（用于健行天下投放追踪）
      - `buyerPhoneMasked: string | null`：若为匿名服务包订单，来自 `orders.buyer_phone` 脱敏；若为实名订单，可来自 `users.phone` 脱敏
    - Admin 详情（`GET /orders/{id}`，Admin 场景）：
      - `shippingAddress` 仅返回省/市/区 code + `phoneMasked`（不返回收货人姓名/手机号明文/详细地址）
      - 运单号不返回明文，仅 `trackingNoLast4`
  - **交互规则（最小）**
    - 列表新增“订单摘要”列：展示 `firstItemTitle`（一行）+ “共 N 项”。
    - 列表提供“详情”按钮：打开抽屉加载 `GET /orders/{id}` 并展示：
      - 订单基础信息（订单号、支付状态、金额拆分、履约状态、时间）
      - 明细列表（title/quantity/unitPrice/totalPrice 等）
      - 物流订单的（脱敏）收货地区信息
    - 物流订单补齐“标记妥投”入口（调用 `POST /api/v1/admin/orders/{id}/deliver`）
  - **验收标准（DoD）**
    - [ ] 菜单入口拆分：两个业务线各自的订单监管入口打开后只展示自己的 `orderType`
    - [ ] 列表展示新增“订单摘要（标题+数量）”，并能快速识别订单内容
    - [ ] 点“详情”能看到订单关键字段 + `order_items` 明细；物流订单详情能看到脱敏收货地区
    - [ ] 匿名服务包下单必须传 `buyerPhone`，并能在 Admin 列表中以 `buyerPhoneMasked` 呈现
    - [ ] Admin 端不泄露手机号明文、运单号明文、收货人姓名与详细地址
  - **实现证据（文本）**：TBD（完成后补齐到 `facts/admin.md`、`facts/backend.md`、`facts/h5.md`）

- [x] **REQ-ADMIN-P0-011：分账与结算页面彻底去 JSON 输入 + 文案中文化**
  - **背景/问题**：让 Admin 手填 JSON 不可用；“结算单”tab 的字段（dealerId/cycle）仍是英文显示。
  - **目标**：分账比例与结算账户等均用表单/表格交互；字段展示中文化。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - **验收标准（DoD）**：
    - [x] 分账比例配置不再手填 JSON（改为表格：经销商 + 比例）
    - [x] “结算单”tab 列名/筛选项中文化（经销商ID/结算周期）
    - [x] 性能：覆盖比例表格为按需新增（不强制加载经销商字典）
  - **实现证据（文本）**：
    - Admin 分账与结算页面：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`

- [ ] **REQ-ADMIN-P0-012：小程序配置中心（面向运营）重做：向导式配置 + 可视化预览 + 最小概念暴露（ID/JSON 隐藏到高级）**
  - **背景/问题**：功能太多太杂；仍存在大量 JSON 编辑，不符合运营使用。
  - **目标**：把“配置小程序”变成运营可理解的工作流：**像搭积木一样**完成首页与页面配置，避免要求运营理解 pageId/collectionId/JSON schema 等工程概念。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue` + 后端接口
  - **口径确认（你已确认）**：
    - 首页需要管理 **Banner（轮播）** 与 **快捷入口**。通过“快捷入口跳转到哪里”的管理，运营可创建出“推荐商品/推荐场所”等页面入口。
    - 运营对页面认知：
      - **聚合页**：包含一级/二级标签（或侧边栏），内容是“信息聚合”——可以聚合：快捷入口、信息页、其他小程序、H5 等跳转项。
      - **信息页**：类似“内容详情页/文章页”，用于展示内容详情；并可跳转到场所详情/产品详情等小程序原生页面。
  - **补充澄清（2025-12-21，来自运营规划确认）**：
    - **首页布局**：除 Banner/快捷入口外，首页其他布局默认“写死”（不纳入本次后台配置范围）。
    - **跳转口径（统一）**：入口/聚合项/信息页内链接，统一使用 `jumpType + targetId` 表达“跳转到哪里”。
      - `AGG_PAGE`：跳转到聚合页（targetId=pageId）
      - `INFO_PAGE`：跳转到信息页（targetId=pageId）
      - `WEBVIEW`：跳转到 H5（targetId=url，生产仅允许 https）
      - `MINI_PROGRAM`：跳转到其他小程序（targetId=appid|path，path 可为空）
      - `ROUTE`：跳转到**本小程序内部页面（路由页）**（targetId=path[?query]，例如 `/pages/venue-detail/venue-detail?id=xxx`）
    - **交互补充（2025-12-23，来自运营确认：ROUTE 大量需要参数；外部小程序为固定合作但会增加）**：
      - **ROUTE 的配置方式（减少手填）**：
        - 运营侧提供“**页面选择器**”（数据源：本仓库小程序 `app.json` 的 `pages[]`）来生成 `path`，不要求运营手敲路径
        - 同时提供“**参数编辑器**”（key/value 表格）生成 querystring，用于业务详情页等大量带参场景
        - 保存时仍只落 `targetId` 字符串：`/pages/xxx/xxx?key=value&k2=v2`（不改变后端契约）
      - **MINI_PROGRAM 的配置方式（减少拼字符串）**：
        - 运营侧将 `appid|path` 拆成结构化输入：`appId`（必填）+ `path`（可选）
        - 提供“已出现过的合作小程序 appId 快捷选择”（从当前草稿/已配置项中自动收集），并允许手动输入新增 appId（合作增长无需改后端）
        - 保存时仍只落 `targetId` 字符串：`appid|path`（path 为空也允许）
    - **聚合页形态（两类都需要）**：
      - **TABS_LIST（顶部标签 + 列表卡片）**：页面顶部为一级标签（可选二级，最多二级），下方为**列表状**跳转卡片，按排序展示。
      - **SIDEBAR_GRID（侧边栏 + 图标宫格）**：左侧侧边栏分类，右侧为**图标状宫格**（类似一整页快捷入口），每个图标为一个跳转项。
    - **建议配置结构（最小约束，便于实现；可后续细化）**：
      - **聚合页 `AGG_PAGE.config`**（NAV 手工维护模式）：
        - `title`: string
        - `nav.layout`: `"TABS_LIST" | "SIDEBAR_GRID"`（缺省视为 `"TABS_LIST"`）
        - `nav.groups`：
          - **TABS_LIST**：`[{ name, children: [{ name, items: [JumpItem] }] }]`（最多二级；二级可不填但结构保留）
          - **SIDEBAR_GRID**：`[{ name, items: [JumpItem] }]`（仅一级侧边栏分类；不使用 children）
        - `JumpItem`: `{ title, subtitle?, iconUrl?, jumpType, targetId, enabled, sort }`
          - `iconUrl`：可为空；支持外部 URL，或“上传到服务器后返回的 URL”（由后台存储并回传）
      - **信息页 `INFO_PAGE.config`**：
        - `title`: string
        - `blocks`: `[{ type, ... }]`
          - `type="markdown"`：`{ type:"markdown", contentMd }`（写侧编辑用）
          - `type="richText"`：`{ type:"richText", contentHtml }`（读侧渲染用，兼容既有实现；可由 Markdown 转换生成）
    - **聚合页内容来源**：以“运营手工维护列表”为主，不强绑定商品/场所；聚合项可指向：聚合页/信息页/本小程序路由页/H5/其他小程序。
    - **信息页富文本**：仅需最低程度图文，运营侧以 **Markdown** 编辑为主；发布/预览时转换为小程序可渲染的 `contentHtml`（或等价结构）。
  - **兼容性约束（vNow）**：
    - 不破坏现有小程序读侧接口：仍沿用 `MINI_PROGRAM_ENTRIES / MINI_PROGRAM_PAGES / MINI_PROGRAM_COLLECTIONS` 的读侧契约（`/api/v1/mini-program/*`）。
    - 本次升级允许在 items/config 中 **新增可选字段**（例如 jumpType/targetId），但不移除既有字段。
  - **信息架构与工作流（v2，必须落地到 UI）**：
    - **模块拆分（默认运营模式）**：
      - **首页装修**：只做 Banner 与快捷入口两块（分别独立列表与新增/编辑弹窗）；不与页面库混放。
      - **页面库**：聚合页 / 信息页独立管理（列表 + 新增/编辑），默认只暴露“运营表单”。
      - **发布与生效认知**：所有模块必须明确“草稿 vs 已发布”，并提供主按钮“保存并发布”（减少误操作）。
      - **预览**：支持“纯文本预览”（无需保存/发布即可预览当前草稿的结构与跳转）。
      - **读侧对照（排障）**：提供按钮直接查看读侧响应（`/mini-program/entries`、`/mini-program/pages/{id}`），用于确认是否已生效/是否指向同一环境。
    - **高级模式（默认隐藏）**：
      - 内容集合/JSON 编辑仅在高级模式展示；默认运营模式不加载、不展示，不干扰运营配置。
      - 高级模式切换需风险提示（避免误以为必须编辑 JSON）。
  - **验收标准（DoD）**：
    - [ ] **从零开始向导**：提供“从零配置（推荐）”流程：创建集合 → 创建页面 → 配置首页（Banner/入口）→ 一键发布
    - [x] **概念降噪**：默认不要求理解/输入 `pageId/collectionId`；由系统自动生成并展示“可读名称”，ID 仅在“高级信息”里可复制
    - [x] **首页配置可视化**：
      - [x] Banner 管理（轮播）：图片/标题/跳转（选择页面/外链/路由），支持排序/启用/预览
      - [x] 快捷入口管理：名称/图标/跳转，支持排序/启用/预览
    - [x] **页面配置可视化（按运营定义重做）**：
      - [ ] 聚合页（信息聚合）：
        - [x] 运营可维护分类与内容：
          - [x] **TABS_LIST**：维护“一级分类 → 二级分类”（可不填二级，最多二级），并在分类下维护“列表卡片（跳转项）”
          - [x] **SIDEBAR_GRID**：维护“侧边栏分类 → 图标宫格项（跳转项）”
        - [x] 跳转项结构（最小）：title/subtitle(可选)/iconUrl(可选，仅 SIDEBAR_GRID 推荐)/jumpType/targetId/enabled/sort
        - [x] 跳转项支持：聚合页/信息页/本小程序路由页（含业务详情页）/H5/其他小程序
        - [ ] 不要求运营填写 pageId；创建页面时系统生成并在高级信息中可复制
      - [ ] 信息页（内容详情页/文章页）：
        - [x] 支持“正文内容（Markdown）”与“跳转聚合（links/cards/banner）”两种用途，可同时存在
        - [x] 运营以 block 形式编辑（banner/Markdown/links/cards），每块支持增删、块内条目编辑与校验
        - [x] Markdown 在预览/发布时转换为小程序可渲染结构（例如 `contentHtml`）
        - [ ] 支持“引用数据库内容（CMS）”作为一个 block（事实更新：小程序端按 contentId 实时拉取已发布内容）
    - [ ] **强校验与友好错误**：发布前校验引用关系（入口→页面、页面→集合），错误用中文说明并定位到具体项
    - [x] **预览与回显**：保存草稿/发布/下线后，明确展示“草稿态/已发布态/发布时间/草稿更新时间”，并支持快速预览（文本预览即可）
      - [x] 页面库状态回显：列表明确展示 **未发布/已发布/已下线/草稿有变更（未发布）**，并展示 **草稿更新时间** 与 **发布时间**
      - [x] 文本预览：后台可对“首页入口/页面草稿”进行纯文本预览，便于运营核对分类结构与跳转目标
    - [x] **高级模式**：JSON 编辑仅在“高级模式”可见，默认隐藏；切换高级模式有风险提示
  - **实现证据（文本）**：
    - `frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`

- [x] **REQ-ADMIN-P0-013：区域/城市配置页性能优化 + 保存/发布结果回显修复**
  - **背景/问题**：一键导入后页面操作卡顿；保存草稿无明显变化；发布后列表 published 仍显示未发布。
  - **目标**：大数据量下交互顺滑；保存/发布后回显正确（含 published 状态与版本/更新时间等）。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`、`backend/app/api/v1/admin_regions.py`、`backend/app/api/v1/regions.py`
  - **验收标准（DoD）**：
    - [x] 导入全国省市后，搜索/编辑/保存不明显卡顿（分页/增量渲染）
    - [x] 保存草稿/发布动作有明确反馈
    - [x] 发布后读侧能读到最新版本
  - **实现证据（文本）**：
    - 后端持久化修复：`backend/app/api/v1/admin_regions.py`
    - 前端性能优化：`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`

- [x] **REQ-ADMIN-P0-014：供给侧审核页补齐“申请内容详情”查看能力**
  - **背景/问题**：审核页面无法查看 provider 提交的完整内容（仅基础信息）。
  - **目标**：审核者可查看场所/健行天下开通申请的详细字段与资料（图片/地址/城市/介绍等）。
  - **范围（候选）**：
    - Admin 场所管理/审核：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`（或详情页）
    - 健行天下开通审核：`frontend/admin/src/pages/admin/AdminProviderOnboardingHealthCardPage.vue`（若存在）
    - 后端：`backend/app/api/v1/admin_venues.py`、`backend/app/api/v1/admin_provider_onboarding.py`
  - **验收标准（DoD）**：
    - [x] 审核列表支持打开详情抽屉/弹窗（展示提交内容）
    - [x] 字段覆盖：场所名称/地址/城市/电话/封面/图集/简介/标签/状态等
  - **实现证据（文本）**：
    - 后端详情接口：`backend/app/api/v1/admin_venues.py`（`GET /api/v1/admin/venues/{id}`）
    - Admin 场所管理/审核：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`（详情抽屉）
    - 健行天下开通审核：`frontend/admin/src/pages/admin/AdminProviderHealthCardOnboardingPage.vue`（查看场所资料）

- [ ] **REQ-ADMIN-P1-002：供给审核/商品审核“驳回原因”能力补齐（可录入、可回显、可追溯）**
  - **背景/问题**：当前驳回操作体验不友好：
    - Admin 驳回时无法填写原因；
    - Provider 无法明确看到当前是“通过/驳回”，也看不到驳回原因；
    - 审核详情页也缺少结构化展示“状态与原因”。
  - **终态口径（你已确认）**
    - 驳回原因采用“覆盖式”（最新一次驳回原因覆盖旧值），不做复杂历史版本。
  - **数据模型（需要变更）**
    - Venue（场所展示资料审核）增加字段：
      - `review_status`（或复用现有 publishStatus + 额外字段；以实现为准）
      - `reject_reason`（string, 可空）
      - `rejected_at`（datetime, 可空）
    - Product（商品审核）增加字段：
      - `reject_reason`（string, 可空）
      - `rejected_at`（datetime, 可空）
  - **API 合约（需要变更/新增）**
    - Admin：
      - `POST /api/v1/admin/venues/{id}/reject` body 支持 `{ reason: string }`（必填，1~200）
      - `PUT /api/v1/admin/products/{id}/reject` body 支持 `{ reason: string }`（必填，1~200）
    - Provider：
      - Provider 场所详情与列表出参包含审核状态与驳回原因（脱敏不需要，但需中文可读）
      - Provider 商品列表/详情出参包含审核状态与驳回原因
  - **UI/UX 约束（最小）**
    - Admin 驳回必须弹窗填写原因（不能为空）
    - Provider 列表需展示状态标签：待审/已上架/已下架/已驳回（或场所：草稿/已发布/已驳回/已下线）
    - Provider 详情页展示驳回原因（醒目但不干扰编辑）
  - **范围（候选）**
    - 后端：`backend/app/models/venue.py`、`backend/app/models/product.py`、对应 alembic 迁移、`backend/app/api/v1/admin_venues.py`、`backend/app/api/v1/products.py`、`backend/app/api/v1/provider.py`
    - 前端：admin：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`、`AdminProductsPage.vue`、健行天下审核页（若存在）
    - 前端：provider：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`、`ProviderProductsPage.vue`
  - **验收标准（DoD）**
    - [ ] Admin 驳回可输入原因并成功落库；再次驳回会覆盖原因与时间
    - [ ] Provider 可在列表/详情看到状态与驳回原因
    - [ ] 审核详情“图片资料”与“状态/原因”结构清晰（见 REQ-ADMIN-P1-003）
  - **实现证据（文本）**：TBD

- [ ] **REQ-ADMIN-P1-003：供给审核详情图片资料结构优化（Logo/封面/环境服务图分组）**
  - **背景/问题**：当前审核详情中图片资料把 logo/封面/环境服务图混在一起展示，不利于审核者快速核对。
  - **目标**：按图片类型分组展示，并明确每组含义。
  - **范围（候选）**：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`、`frontend/admin/src/pages/admin/AdminProviderHealthCardOnboardingPage.vue`
  - **验收标准（DoD）**
    - [ ] Logo、封面、环境/服务图分别独立区块展示（标题 + grid）
    - [ ] 无图时展示空态文案（例如“未提交”）
  - **实现证据（文本）**：TBD

- [ ] **REQ-ADMIN-P1-017：供给审核-场所下线需填写“下线原因”（并可回显）**
  - **背景/问题**：Admin 在「供给审核 → 场所管理/审核」对场所执行“下线”时，缺少下线原因输入，追溯性差，也不利于对外解释。
  - **目标**：下线动作与驳回类似：操作时必须填原因，且原因可在详情中回看（覆盖式，无历史版本）。
  - **数据模型（建议，等待确认）**
    - Venue 增加字段：
      - `offline_reason`（string, 可空；最近一次下线原因）
      - `offlined_at`（datetime, 可空；最近一次下线时间）
  - **API 合约（建议，等待确认）**
    - `POST /api/v1/admin/venues/{id}/offline` body：`{ reason: string }`（必填，1~200）
    - Admin 场所列表/详情出参补齐：`offlineReason`、`offlinedAt`
    - Provider 场所列表/详情出参补齐：`offlineReason`、`offlinedAt`（用于 Provider 侧理解“为何下线”）
  - **UI/UX 约束（最小）**
    - Admin 点击“下线”弹窗输入原因，不能为空
    - 详情抽屉中在“状态/原因”区块展示下线原因（若存在）
  - **验收标准（DoD）**
    - [ ] Admin 下线必须填写原因，且可成功落库
    - [ ] Admin/Provider 均可在详情看到最近一次下线原因（若存在）
  - **待确认点**
    - [ ] 下线原因是否需要 Provider 可见？（默认：可见）
  - **实现证据（文本）**
    - 后端：`backend/app/models/venue.py`（`offline_reason/offlined_at`）、`backend/app/api/v1/admin_venues.py`（`POST /admin/venues/{id}/offline` body.reason）、`backend/app/api/v1/provider.py`（DTO 回显）、alembic：`backend/alembic/versions/e3f4a5b6c7d8_stage33_venue_offline_reason.py`
    - 前端：admin：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`（下线弹窗原因 + 详情回显）
    - 前端：provider：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`（下线原因回显）

- [ ] **REQ-ADMIN-P1-018：供给审核-场所审核状态反复切换后卡死（提示“状态已发生变化”但刷新无效）修复**
  - **背景/问题**：Admin 对同一场所反复执行“通过/驳回/下线”后，列表出现“待审核”但无法驳回，提示“状态已发生变化，请刷新后重试”，且多次刷新仍无法操作（通过并发布不触发）。
  - **目标**：状态机一致且可恢复：当列表显示为“可驳回”时，后端必须允许驳回；当后端不允许驳回时，前端必须明确展示为不可驳回状态并刷新到真实状态。
  - **范围（候选）**
    - 后端：`backend/app/api/v1/admin_venues.py`（审核/发布/下线状态变更规则）
    - 前端：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`（动作 enable 口径与刷新策略）
  - **验收标准（DoD）**
    - [ ] 不会出现“UI 显示待审核但后端永远拒绝驳回”的僵尸状态
    - [ ] 当确实发生并发/状态变化时，提示后可一键刷新到最新状态并恢复可操作性
  - **实现证据（文本）**
    - 后端：`backend/app/api/v1/provider.py`（`submit-showcase` 归一 `publish_status=DRAFT`）、`backend/app/api/v1/admin_venues.py`（驳回接口对 OFFLINE 待审容错并归一 publish_status）

#### 7.3 Provider（服务提供方后台）

- [x] **REQ-PROVIDER-P0-006：工作台“场所数量”卡片与单场所设计对齐**
  - **背景/问题**：仍展示场所数量 card，暗示多场所。
  - **目标**：移除或改为“当前场所”信息（不暗示多场所）。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`
  - **验收标准（DoD）**：
    - [x] 不再出现“场所数量”口径误导（改为“当前场所（单场所）”）
  - **实现证据（文本）**：
    - Provider 工作台：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`

- [x] **REQ-PROVIDER-P0-007：场所标签/商品标签/服务标签按全局标签库分别受控**
  - **背景/问题**：场所信息页选标签未按 Admin 全局标签控制。
  - **目标**：场所页只允许选 `VENUE` 标签；商品/服务页分别选 `PRODUCT/SERVICE` 标签。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`、`ProviderProductsPage.vue`、`ProviderServicesPage.vue`、`backend/app/api/v1/tags.py`
  - **验收标准（DoD）**：
    - [x] 场所标签下拉来自 `/api/v1/tags?type=VENUE`
    - [x] 商品/服务标签下拉分别来自 PRODUCT/SERVICE
  - **实现证据（文本）**：
    - 场所标签：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
    - 商品标签：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
    - 服务标签：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`

- [ ] **REQ-PROVIDER-P1-013：提交审核时校验标签仍为可用（被下线/禁用的标签禁止提交）**
  - **背景/问题**：Provider 在编辑阶段已选标签 A；之后 Admin 在全局标签库下线/禁用 A；但 Provider 仍可提交带 A 的场所/商品/服务进入审核，导致审核口径与数据一致性受损。
  - **目标**：在“提交审核”这一刻强校验：所有已选标签必须仍为可用（enabled=true 且 published=true）。否则阻断提交，并给出明确中文提示。
  - **范围（候选）**
    - 后端：Provider 提交接口（场所/商品/服务）：`backend/app/api/v1/provider.py`（或拆分模块中的 submit 路由）
    - 前端：Provider 提交时错误提示：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`、`ProviderProductsPage.vue`、`ProviderServicesPage.vue`
  - **规则（最小）**
    - 仅在“提交审核”动作校验；保存草稿/编辑不强校验（允许继续编辑以便替换标签）
    - 校验口径：标签记录需满足“全局标签库为 ENABLED”（当前模型为 `taxonomy_nodes.status=ENABLED`；不存在 published 字段）
  - **错误码（建议，等待确认）**
    - HTTP 400 + `error.code="TAG_NOT_AVAILABLE"`，`error.message="所选标签已下线或禁用，请更换后再提交"`
    - `error.details.invalidTags: Array<{ name: string }>`（便于前端展示具体是哪些）
  - **验收标准（DoD）**
    - [ ] 任意一类提交（场所/商品/服务）包含不可用标签时：提交被阻断且提示清晰
    - [ ] 替换为可用标签后可正常提交
  - **实现证据（文本）**
    - 后端：`backend/app/api/v1/provider.py`（`_assert_tags_available` + `submit-showcase`/`products` 提交审核门禁）

- [x] **REQ-PROVIDER-P1-014：上传图片前置压缩与尺寸限制（>5MB 或宽>2000px 自动处理）**
  - **背景/问题**：Provider 上传商品详情图等图片时，存在 >5MB 或超大分辨率，导致上传失败/耗时长/体验差。
  - **目标**：前端上传前自动压缩与等比缩放，尽量把图片控制在可接受范围后再上传；若压缩后仍超限，再提示用户手动处理。
  - **范围（候选）**
    - 前端上传工具：`frontend/admin/src/lib/uploads.ts`（`uploadImage` 或等价方法）
    - Provider 使用上传的位置：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`（商品封面/图集/详情图等）、其他复用上传组件的页面
  - **规则（按你描述）**
    - 触发条件：`file.size > 5MB` **或** 图片 `width > 2000px`
    - 自动处理：
      - 等比缩放到 `maxWidth=2000px`（高度等比）
      - 压缩质量 `0.75 ~ 0.85`（实现取一个固定值，建议 `0.82`）
    - 压缩后：
      - 若 `<=5MB`：自动上传
      - 若仍 `>5MB`：提示“图片仍过大，请压缩后再上传”（并不上传）
  - **兼容性约束**
    - 不改变后端上传接口契约：仍使用 `POST /api/v1/uploads/images`
    - 若浏览器/环境不支持 canvas/toBlob：降级为不压缩直接上传（由后端返回超限错误）
  - **验收标准（DoD）**
    - [x] 对超大图片：上传前自动压缩并成功上传
    - [x] 压缩后仍超限：明确提示且不进入上传流程
  - **实现证据（文本）**
    - `frontend/admin/src/lib/uploads.ts`（`uploadImage` 内部 `_compressIfNeeded`：>5MB 或宽>2000px 自动压缩/缩放）

- [x] **REQ-PROVIDER-P1-017：新增商品/服务/健行天下服务时“适用地区”下拉仅允许选择当前场所已绑定区域**
  - **背景/问题**：Provider 在新增服务/商品时，“适用地区”下拉当前展示的是全量已发布地区；但业务上你期望只能选择“场所已绑定的区域”，否则会出现超范围配置。
  - **目标**：适用地区 select 的可选项收敛到“当前场所已绑定区域”，并对基建联防/健行天下两类入口保持一致口径。
  - **范围（候选）**
    - 健行天下服务：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`
    - 基建联防商品/服务（服务型商品的 applicableRegions）：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
  - **待确认点（必须）**
    - [ ] “场所已绑定区域”口径是哪个？
      - A) 仅允许选择 **场所所在城市**（`Venue.cityCode`，单选或多选但仅 1 项）
      - B) 允许选择 **场所所在省/市**（`Venue.provinceCode/cityCode`，可二选一）
      - C) 场所有一组“可服务区域”列表（非 `cityCode`，需明确字段/接口来源）
  - **验收标准（DoD）**
    - [ ] 上述两处新增/编辑弹窗：适用地区下拉不再出现“非绑定区域”
  - **实现证据（文本）**：
    - 健行天下服务适用地区锁定为场所 cityCode：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`
    - 基建联防服务型商品适用地区锁定为场所 cityCode：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`

- [ ] **REQ-PROVIDER-P1-015：Provider 场所信息页审核/发布状态标签更显眼（按状态映射颜色）**
  - **背景/问题**：Provider「场所信息」页当前审核状态/发布状态 tag 不够显眼，难以快速区分“待审/通过/驳回/上线/下线”。
  - **目标**：按明确颜色映射展示：
    - 待审核：`warning`
    - 审核通过：`success`
    - 已驳回：`error`
    - 发布上线（PUBLISHED/ONLINE）：`success`
    - 发布下线（OFFLINE）：`warning`
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
  - **验收标准（DoD）**
    - [ ] 列表与详情的状态标签颜色符合映射，且不会出现“通过/驳回看不出来”的情况
  - **实现证据（文本）**
    - `frontend/admin/src/pages/provider/ProviderVenuesPage.vue`（`reviewTagType/publishTagType` + tag 绑定）

- [ ] **REQ-PROVIDER-P1-016：基建联防商品列表“已驳回”状态使用 error 样式**
  - **背景/问题**：Provider「商品/服务（基建联防）」列表中，“已驳回”状态样式不符合“错误/阻断”语义，不够醒目。
  - **目标**：当状态为 REJECTED 时，tag 类型为 `error`。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
  - **验收标准（DoD）**
    - [ ] “已驳回”在列表/详情中均以 error 呈现
  - **实现证据（文本）**
    - `frontend/admin/src/pages/provider/ProviderProductsPage.vue`（`statusTagType`：REJECTED -> `danger`）

- [x] **REQ-PROVIDER-P0-008：开通健行天下/基建联防前置条件与文案重写（贴合真实业务）**
  - **背景/问题**：开通前置条件需强约束（场所信息满足条件 + 同意协议）；健行天下卡片文案不符合业务描述。
  - **目标**：在 UI/流程上明确“先完善场所→同意协议→提交/开通”；健行天下说明改为“服务兑换/核销场景”。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`、`backend/app/api/v1/provider_onboarding.py`
  - **验收标准（DoD）**：
    - [x] 未满足场所信息条件时，按钮明确提示并引导去完善
    - [x] 文案准确描述：用户在 H5 购买服务包→到店兑换→provider 核销服务次数
  - **实现证据（文本）**：
    - 前端门禁与文案：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`
    - 后端门禁：`backend/app/api/v1/provider_onboarding.py`（`_assert_min_venue_info`）

- [x] **REQ-PROVIDER-P0-009：健行天下服务页表单中文化 + applicableRegions 从 JSON 升级为表单**
  - **背景/问题**：页面存在场所 select 暗示多场所；字段英文；applicableRegions(JSON) 难用。
  - **目标**：移除场所选择暗示；字段中文；地区适用范围用多选表单（省/市）。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderServicesPage.vue`、后端 services API
  - **待确认点（必须）**：
    - 核销方式 `redemptionMethod` 口径：确认“扫码 + 券码 **默认双支持**”，不再让 Provider 选择；后端需兼容历史单选数据（QR_CODE/VOUCHER_CODE）。
  - **验收标准（DoD）**：
    - [x] UI 无 JSON 输入（地区范围用表单多选）
    - [x] 字段全部中文化（label/placeholder/提示）
  - **实现证据（文本）**：
    - `frontend/admin/src/pages/provider/ProviderServicesPage.vue`

- [x] **REQ-PROVIDER-P0-010：预约管理/排期容量的服务选择升级（从输入编码到选择已有服务）**
  - **背景/问题**：当前需要输入 serviceType 编码，难用且易错。
  - **目标**：下拉选择“本 Provider 已创建的服务”，并按业务类型分类展示。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderBookingsPage.vue`、`ProviderSchedulesPage.vue`、后端提供“列出本 provider 的服务字典”接口
  - **待确认点（必须）**：
    - 预约是否拆成两页（健行天下 vs 基建联防服务）还是单页分组？我会基于现有数据结构给出最小方案再请你拍板。
  - **实现说明（vNow）**：
    - 先落地“单页分组下拉”（不拆页），确保可用性；后续如需拆页再升级信息架构。
  - **实现证据（文本）**：
    - Provider 预约管理：`frontend/admin/src/pages/provider/ProviderBookingsPage.vue`
    - Provider 排期/容量：`frontend/admin/src/pages/provider/ProviderSchedulesPage.vue`

- [x] **REQ-PROVIDER-P0-012：基建联防“服务型商品”补齐预约配置（生成 VenueService.productId 关联）**
  - **背景/问题**：独立预约流要求存在 `venue_services.product_id=product.id` 且 `booking_required=true`；但当前 Provider 创建 SERVICE 商品不会生成对应 VenueService，导致小程序无法判断/发起预约。
  - **目标**：Provider 在创建/编辑 **服务型商品**时可配置：服务类目（serviceType）、需要预约（bookingRequired）、适用区域（省/市，多选），并默认核销方式“双支持”（不让 Provider 选择）。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`、`backend/app/api/v1/provider.py`（`/provider/products`）
  - **验收标准（DoD）**：
    - [x] 创建 SERVICE 商品时要求选择 serviceType（来自服务大类字典），并自动创建/更新 `VenueService(product_id=product.id, service_type=..., booking_required=..., applicable_regions=...)`
    - [x] 无场所时禁止创建（引导先完善场所信息）
    - [x] 该配置可被小程序 `GET /api/v1/bookings/order-item-context` 解析到（venueId/serviceType）
  - **实现证据（文本）**：
    - Provider 商品页：`frontend/admin/src/pages/provider/ProviderProductsPage.vue`
    - 后端自动维护：`backend/app/api/v1/provider.py`（`POST/PUT /provider/products`）

- [x] **REQ-PROVIDER-P0-011：场所信息“所在城市”选择 no data 修复**
  - **背景/问题**：Admin 已配置区域城市，但 Provider 场所信息仍 no data。
  - **目标**：城市选择可用且体验顺畅（支持搜索/过滤）。
  - **范围（候选）**：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`、`backend/app/api/v1/regions.py`
  - **验收标准（DoD）**：
    - [x] 城市下拉有数据（CITY:*）
    - [x] 支持搜索；选中后保存成功
  - **实现证据（文本）**：
    - Provider 场所信息：`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`（cityCode 直接存储/选择 `CITY:*`）

- [ ] **REQ-PROVIDER-P1-001：Provider 全站协议门禁（平台建设期：强约束，不走“临时最小版”）**
  - **背景/问题**：当前仅在工作台开通按钮上要求勾选协议，Provider 可以直接进入其他功能页使用服务，业务上不符合“先签协议再使用能力”的要求。
  - **终态口径（你已确认）**：
    - 基建联防协议与健行天下协议的“是否可访问”判断 **仅以 acceptedAt 是否存在为准**；业务状态（SUBMITTED/APPROVED）不作为硬门禁条件。
    - **基建联防协议（infra）门禁**：
      - 未同意 `PROVIDER_INFRA_APPLY` 时：除白名单页面外，Provider 端所有页面均不可访问。
      - 白名单（可访问，方案A）：`工作台（仅用于签署协议）`、`场所信息（用于补齐开通前置条件）`、`退出登录`。
      - **安全设置页不在白名单内**（即：未同意时不能进入安全设置；仅允许退出登录）。
      - 交互约束（方案A）：工作台在未同意 infra 时 **不展示** 预约/核销/统计/跳转等业务入口，仅保留“签署协议/完善场所信息”的引导与动作。
    - **健行天下协议（health card）门禁**：
      - 未同意 `PROVIDER_HEALTH_CARD_APPLY` 时：仅限制 Provider 侧路由 `'/provider/services'`（菜单名：**健行天下服务**）不可访问（其余页面按 infra 门禁规则）。
  - **交互要求**
    - 被门禁拦截时，必须给出明确提示（中文）并引导回工作台完成签署：
      - infra：提示“需先同意《基建联防协议》后才能使用该功能”，并提供跳转工作台按钮
      - health card：提示“需先同意《健行天下协议》后才能使用健行天下服务”，并提供跳转工作台按钮
  - **数据来源（判定依据）**
    - Provider 工作台接口 `GET /api/v1/provider/onboarding` 出参字段：
      - `infraAgreementAcceptedAt`（非空视为已同意 infra 协议）
      - `agreementAcceptedAt`（非空视为已同意 health card 协议）
  - **范围（候选）**
    - 前端路由守卫：`frontend/admin/src/router/index.ts`（Provider 路由统一门禁）
    - Provider 工作台：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`（入口引导、协议弹窗）
    - Provider 读侧：`backend/app/api/v1/provider_onboarding.py`（acceptedAt 字段确保稳定返回）
  - **验收标准（DoD）**
    - [ ] 未同意 infra 协议：进入任意非白名单页面会被拦截并提示；可跳转工作台；可进入场所信息补齐前置条件；可退出登录
    - [ ] 同意 infra 协议但未同意 health card 协议：仅 `健行天下服务`被拦截，其余可用
    - [ ] 同意两份协议：所有 provider 页面按原逻辑可用（不额外增加限制）
    - [ ] 门禁不影响 Admin/Dealer 角色路由访问
  - **实现证据（文本）**：TBD
  - **实现证据（文本）**
    - 路由门禁：`frontend/admin/src/router/index.ts`（Provider onboarding 缓存 + 方案A 白名单拦截；`/provider/services` 健行天下协议门禁）
    - 侧边栏收口：`frontend/admin/src/layouts/AppLayout.vue`、`frontend/admin/src/lib/nav.ts`（未同意 infra 时仅展示工作台/场所信息；未同意 health 时隐藏健行天下服务入口）
    - 工作台收口：`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`（未同意 infra 时隐藏预约/核销等业务入口，仅保留签协议与场所信息引导）

- [ ] **REQ-PROVIDER-P1-002：Provider 图片上传重复提交修复（场所/商品：一次选图只上传一次）**
  - **背景/问题（你反馈）**
    - Provider 场所信息页上传 logo/封面/环境服务图会出现“重复上传”（看起来成功两次）。
    - Provider 商品/服务新增时上传封面图与详情图同样重复。
  - **目标**：一次选择/拖入图片只触发一次上传请求；UI 成功提示与最终列表一致。
  - **范围（候选）**
    - `frontend/admin/src/pages/provider/ProviderVenuesPage.vue`
    - `frontend/admin/src/pages/provider/ProviderProductsPage.vue`
    - 公共上传工具：`frontend/admin/src/lib/uploads`（若需）
  - **实现约束**
    - 不改变上传接口与返回结构：继续复用 `POST /api/v1/uploads/images`
    - 优先在前端处理（`el-upload` 事件触发策略与文件状态机）
  - **验收标准（DoD）**
    - [ ] 上传任意一张图：后端仅收到 1 次请求；前端仅提示 1 次成功；最终字段只新增 1 个 url
    - [ ] 多图上传（环境图/详情图）：每张图各 1 次请求；不会出现同一张图重复两次的请求
  - **实现证据（文本）**：TBD

#### 7.4 Dealer（经销商后台）

- [x] **REQ-DEALER-P0-003：Dealer 登录“响应解析错误”修复**
  - **背景/问题**：Dealer 登录时前端提示“响应解析错误”。
  - **目标**：Dealer 登录稳定可用；错误时返回统一错误结构并能被前端正确展示。
  - **范围（候选）**：`frontend/admin/src/pages/LoginPage.vue`（或 dealer 登录入口）、`frontend/admin/src/lib/api.ts`、`backend/app/api/v1/dealer_auth.py`
  - **验收标准（DoD）**：
    - [x] Dealer 登录接口返回统一响应结构（不再返回 null/非 JSON）
    - [x] 错误时 toast 可展示明确 message（不再出现“响应解析错误”泛化提示）
  - **实现证据（文本）**：
    - 后端登录接口修复：`backend/app/api/v1/dealer_auth.py`（`POST /dealer/auth/login`）

#### 7.5 H5

- [x] **REQ-H5-P0-003：购买区域选择不可用修复（依赖 REGION_CITIES 发布链路）**
  - **背景/问题**：购买区域选择仍不可用，疑似与“保存草稿/发布不生效”相关。
  - **目标**：购买页区域选择可用（省/市/全国），且提交 regionScope 正确。
  - **范围（候选）**：`frontend/h5/src/pages/BuyPage.vue`、`backend/app/api/v1/regions.py`、`backend/app/api/v1/admin_regions.py`、Admin 区域页
  - **验收标准（DoD）**：
    - [x] regionLevel=PROVINCE/CITY 时下拉可选且不空（取决于 REGION_CITIES 已发布数据）
    - [x] 选择回调兼容，能正确写入 regionScope 并通过校验
  - **实现证据（文本）**：
    - H5 购买页区域选择：`frontend/h5/src/pages/BuyPage.vue`（`onConfirmRegion` 兼容解析）

#### 7.6 小程序

- [x] **REQ-MP-P0-003：商城商品详情页底部栏布局修复（数量/购物车/购买按钮）**
  - **背景/问题**：购买按钮被挤出页面；图片占位偏移。
  - **目标**：底部操作栏布局稳定；占位图居中；适配不同屏宽。
  - **范围（候选）**：`frontend/mini-program/pages/mall/product-detail/product-detail.wxml|wxss`
  - **验收标准（DoD）**：
    - [x] 购买按钮不越界；点击区域正确
    - [x] 图片占位左右留白一致
  - **实现证据（文本）**：
    - `frontend/mini-program/pages/mall/product-detail/product-detail.wxss`

- [x] **REQ-MP-P1-005：商品详情页图片支持点击放大预览（wx.previewImage）**
  - **背景/问题**：商品详情页头图/轮播图当前仅展示，点击无法放大查看细节。
  - **目标**：点击商品头图/轮播图时，调用微信原生图片预览能力，可放大/左右滑动查看。
  - **范围（候选）**：
    - `frontend/mini-program/pages/mall/product-detail/product-detail.wxml`
    - `frontend/mini-program/pages/mall/product-detail/product-detail.js`
  - **规则（v1 最小，待你确认后再实现）**
    - 若存在 `galleryUrlsAbs`：点击任一张图 → `wx.previewImage({ current, urls: galleryUrlsAbs })`
    - 若仅有单张 `heroUrlAbs`：点击 → `wx.previewImage({ current: heroUrlAbs, urls: [heroUrlAbs] })`
  - **验收标准（DoD）**
    - [ ] 点击图片后可进入预览并可缩放查看
  - **实现证据（文本）**：
    - `frontend/mini-program/pages/mall/product-detail/product-detail.wxml`
    - `frontend/mini-program/pages/mall/product-detail/product-detail.js`

- [x] **REQ-MP-P0-004：商城立即支付 500 修复（下单/支付后端链路）**
  - **背景/问题**：点击购买-立即支付请求失败 500。
  - **目标**：小程序商城下单/支付链路可用；错误时返回明确业务错误。
  - **范围（候选）**：`frontend/mini-program/pages/mall/*`、`backend/app/api/v1/orders.py`、`backend/app/api/v1/payments.py`
  - **验收标准（DoD）**：
    - [x] 下单成功返回订单；支付接口不再 500（配置缺失返回 400，openid 缺失返回 200+FAILED）
    - [x] 小程序端能展示 failureReason（例如“未获取到openid，请重新登录后重试”）
  - **实现证据（文本）**：
    - 后端支付接口错误码/失败原因：`backend/app/api/v1/orders.py`（`POST /orders/{id}/pay`）
    - 小程序支付提示：`frontend/mini-program/pages/order/order-detail/order-detail.js`

- [x] **REQ-MP-P0-005：基建联防“服务型商品”预约能力补齐（与 Provider 设置联动）**
  - **背景/问题**：服务型商品无法预约；目前预约似乎仅权益（服务包）支持。
  - **目标**：基建联防服务商品按 Provider 的 bookingRequired 设置支持预约流程。
  - **范围（候选）**：小程序商城/预约页；后端订单/预约契约；Provider 服务配置
  - **确认结论（你已确认）**：走**独立预约流**（不复用服务包权益预约）。
  - **实现约束（vNow 最小）**：
    - 预约来源分两类：`ENTITLEMENT`（服务包权益）与 `ORDER_ITEM`（基建联防服务型商品订单明细）
    - `ORDER_ITEM` 预约必须满足：订单已支付 + 商品为 SERVICE + 存在 `venue_services.product_id=product.id` 且 `booking_required=true`
  - **实现证据（文本）**：
    - 后端：`backend/app/api/v1/bookings.py`（`GET /bookings/order-item-context`、`POST /bookings` 支持 orderId/orderItemId）
    - 小程序：`frontend/mini-program/pages/order/order-detail/order-detail.*`（去预约入口）、`frontend/mini-program/pages/booking/date-slot-select/date-slot-select.js`

- [x] **REQ-MP-P1-003：订单页类型筛选与布局优化**
  - **背景/问题**：点击类别不生效；顶部容器空白过大；布局需重做。
  - **目标**：筛选真实生效；顶部 tab 高度合理；整体布局更紧凑。
  - **范围（候选）**：`frontend/mini-program/pages/order/order.*`
  - **实现证据（文本）**：
    - `frontend/mini-program/pages/order/order.js`、`frontend/mini-program/pages/order/order.wxml`、`frontend/mini-program/pages/order/order.wxss`

- [x] **REQ-MP-P1-004：我的页用户信息与入口结构优化**
  - **背景/问题**：昵称/头像占位；绑定手机号入口位置不合理；地址新增报错无提示；地区选择不友好；协议确认交互不清晰。
  - **目标**：能获取并展示微信头像昵称（若受限则给清晰兜底）；入口重排；地址校验与错误提示；地区选择更易用；登录前协议确认弹窗明确。
  - **范围（候选）**：`frontend/mini-program/pages/profile/profile.*`、地址页 `frontend/mini-program/pages/address/*`
  - **确认结论（进入实现，vNow 最小）**：
    - “我的”页（Tab 页）顶部只展示基础信息概览（头像/昵称/手机号/身份标签），不在本页直接编辑，避免布局挤压与信息混乱。
    - 新增“个人资料”页集中维护基础信息：头像（chooseAvatar）、昵称（nickname）、手机号（只读+去绑定）、企业绑定/员工身份（只读+去绑定）。
    - “我的”页提供入口跳转“个人资料”页；原有菜单入口保留（企业绑定、权益、预约、地址、客服、协议等）。
    - 不引入新后端字段/新接口：复用现有 `/api/v1/uploads/images` 与 `PUT /api/v1/users/profile`。
    - “我的”页视觉层级（主次分明，vNow 最小）：
      - 顶部信息卡为主：头像/昵称突出；手机号/身份为次信息（字号/颜色弱化）
      - 菜单入口按功能分组（如：账户、服务、其他），每组具备清晰标题与统一留白
      - “退出登录”为危险操作：独立样式（红色/独立按钮），避免与普通入口混淆
  - **验收标准（DoD，补充）**：
    - [x] 顶部信息卡与菜单区块的圆角/阴影/间距统一，且点击区域充足
    - [x] 菜单分组后信息更清晰，不影响原入口功能与跳转
    - [x] 危险操作（退出）视觉上显著区分
  - **实现证据（文本）**：
    - 小程序我的页：`frontend/mini-program/pages/profile/profile.js`、`frontend/mini-program/pages/profile/profile.wxml`、`frontend/mini-program/pages/profile/profile.wxss`
    - 小程序个人资料页：`frontend/mini-program/pages/profile/profile-edit/profile-edit.*`
      - 微信新规：不再使用 `wx.getUserProfile` 获取头像昵称；改用“头像昵称填写能力”（官方推荐）：`chooseAvatar` + `nickname` 输入。
        - 头像：`<button open-type="chooseAvatar">` → 选择后使用 `POST /api/v1/uploads/images` 上传图片 → 回写 `PUT /api/v1/users/profile.avatar`
        - 昵称：`<input type="nickname">` → 回写 `PUT /api/v1/users/profile.nickname`
        - 约束：上传接口需允许 USER 访问；并将返回的 `/static/uploads/...` 组合为可访问的 URL 后写入 `avatar`
    - 后端返回昵称/头像 + 同步接口：`backend/app/api/v1/users.py`（`GET/PUT /api/v1/users/profile`）、`backend/app/api/v1/mini_program_auth.py`（登录响应补齐字段）

- [ ] **REQ-MP-P2-010：小程序商品/场所信息展示补齐（图片、城市、场所内商品列表与跳转）**
  - **背景/问题（你反馈）**
    - 商品列表/详情封面与详情图未展示，仍为占位图；占位图布局偏移。
    - 场所列表图标出现 `null`，城市信息展示为 `CITY:xxxxxx` 而非中文名称。
    - 场所详情页“服务列表”为空；你希望升级为“商品/服务列表”，展示该 Provider 的全部商品/服务，并可点击跳转对应商品详情。
    - 首页推荐场所/推荐商品卡片封面仍可能显示占位图（商城页无该问题），需要对齐数据字段与渲染逻辑。
    - 首页推荐场所标题后出现“（默认场所）”等非运营配置的文案；你要求先**查清来源与业务含义**（来自后端字段/前端硬编码/数据脏值），再决定是否展示、如何展示。
  - **终态口径（你已确认）**
    - 场所详情页列表展示：**该 Provider 的全部商品/服务**（不局限于 venue_services 绑定项）。
    - 官网/小程序列表图片策略：统一容器，列表用 `cover`（你已确认）。
  - **数据来源与接口**
    - 商品列表：复用 `GET /api/v1/products`，通过 `providerId` 过滤（后端已支持该参数）。
    - 场所详情：复用 `GET /api/v1/venues/{id}` 获取 `providerId`（若出参缺失则需补齐）。
    - 城市中文名：复用 `GET /api/v1/regions/cities` 构建 `code->name` 映射（仅取 CITY:*）。
  - **范围（候选）**
    - 小程序商城商品列表/详情：`frontend/mini-program/pages/mall/mall.*`、`frontend/mini-program/pages/mall/product-detail/*`
    - 小程序首页推荐卡片：`frontend/mini-program/pages/index/index.*`
    - 小程序场所列表/详情：`frontend/mini-program/pages/booking/venue-select/*`、`frontend/mini-program/pages/venue-detail/*`（或实际场所入口页）
    - 小程序公共占位组件样式：对应 wxss
  - **验收标准（DoD）**
    - [ ] 商品列表/详情展示真实图片（cover + gallery），占位只在无图/加载失败出现
    - [ ] 场所列表/首页推荐场所无 `null` 文案；城市显示为中文 name，不显示 `CITY:` code
    - [ ] 场所详情展示商品/服务列表（来自 providerId 过滤的 products），点击可跳转商品详情
    - [ ] 首页推荐场所/推荐商品封面使用真实图片（有图则不出现占位）
    - [ ] 场所详情顶部大图左右留白一致（不偏左/不偏右）
    - [ ] “（默认场所）”文案必须定位来源并给出处理策略：
      - 若为前端硬编码：移除并给出回归说明
      - 若为后端字段：补充字段语义与端侧展示规则（何时展示、展示在哪里、文案口径）
      - 若为数据脏值：读侧兜底不展示脏值，并给出写侧/数据修复建议（不必在本任务内实现）
  - **实现证据（文本）**：TBD


#### 3.6 小程序升级需求

- [x] **REQ-MP-P1-001：首页顶部搜索栏去掉区域选择按钮**
  - **范围（待定位）**：`frontend/mini-program/pages/index/index.*`
  - **验收标准（DoD）**：按钮移除后布局不塌陷，搜索仍可用。
  - **实现证据（文本）**：`frontend/mini-program/pages/index/index.wxml`、`frontend/mini-program/pages/index/index.js`、`frontend/mini-program/pages/index/index.wxss`

- [x] **REQ-MP-P1-002：权益页筛选卡片空白问题修复（无 icon 则收紧卡片尺寸/对齐）**
  - **范围（待定位）**：`frontend/mini-program/pages/entitlement/entitlement.*`
  - **验收标准（DoD）**：筛选卡片视觉不空洞，点击区域合理。
  - **实现证据（文本）**：`frontend/mini-program/pages/entitlement/entitlement.wxml`、`frontend/mini-program/pages/entitlement/entitlement.wxss`

- [ ] **REQ-MP-P2-001：首页整体布局优化（主次分明，vNow 最小）**
  - **背景/问题**：当前首页视觉层级弱、信息噪声大，用户难以快速抓住主入口与核心内容。
  - **目标**：首页信息结构清晰：主入口（搜索/运营位）优先；快捷入口其次；推荐商品/场所为内容承载；空态/错误态保持可理解。
  - **范围（候选）**：`frontend/mini-program/pages/index/index.wxml`、`index.wxss`（不改后端契约与接口）
  - **交互与信息结构约束（最小）**：
    - 顶部：搜索框（保持现有能力与跳转逻辑）
    - 运营位：Banner 轮播（保持点击跳转）
    - 快捷入口：最多两行网格（超出折叠/或仍按网格但保持一致间距）
    - 内容区：推荐商品（横滑卡片）与推荐场所（竖向列表），每个区块具备明确标题与统一留白
    - 状态区：loading/error/empty 三态保留，且不破坏主结构层级
  - **验收标准（DoD）**：
    - [ ] 视觉层级：顶部与 Banner 明显高于内容区（留白/字号/卡片样式一致）
    - [ ] 统一组件样式：卡片圆角/阴影/间距一致；标题样式统一
    - [ ] 可用性：所有按钮/卡片点击区域充足，不发生溢出/遮挡（含自定义 tabbar）
    - [ ] 不新增/不修改 API；仅 UI 结构与样式调整
  - **确认结论（进入实现）**：
    - 接受“快捷入口最多两行”（最多 8 个）
    - 当入口超过两行时，新增“更多入口”页面承载完整入口列表，并提供“更多”入口跳转

---

#### 3.7 AI 能力平台（Provider/Strategy/Gateway，v2）

- [ ] **REQ-AI-P0-001：AI 配置体系重构为 Provider + Strategy（可替换三年不重写）**
  - **背景/问题**：
    - 现状 AI 为 v1（SystemConfig `AI_CONFIG`）强绑定 OpenAI compatible：`baseUrl/apiKey/model` + 端侧 messages。
    - 需引入 DashScope（应用模式/模型模式），未来还可能接入其他 Provider，不能把模型/SDK 细节暴露到 Admin/小程序。
  - **目标**：
    - Admin：分为 Provider（技术配置）与 Strategy（业务语义）两层；Strategy 与 Provider 解耦、可切换。
    - 后端：统一 AI Gateway + Provider Adapter，屏蔽 SDK/HTTP/App/Model 差异。
    - 小程序：只传 `scene + message`，不暴露任何技术参数。
  - **规格依据（单一真相来源）**：
    - `specs/health-services-platform/ai-gateway-v2.md`
  - **范围（候选）**：
    - 后端：`backend/app/api/v1/ai.py`、新增 `app/services/ai/*`、新增 models + alembic 迁移
    - Admin：新增 Provider 管理页 / Strategy 管理页 / 绑定页；旧 AI 配置页提供迁移入口
    - 小程序：`frontend/mini-program/pages/ai-chat/*`
  - **验收标准（DoD）**：
    - [ ] Admin 不出现 “GPT/Qwen/Claude” 等模型品牌文案；不要求运营理解 model/sdk
    - [ ] Provider 支持至少：`dashscope_application` + `openapi_compatible`；且支持“连接测试”
    - [ ] Strategy 中不出现 model/apiKey/appId/endpoint；`generation_config` 为建议值，可降级忽略
    - [ ] 小程序请求改为：`POST /api/v1/ai/chat { scene, message }`；禁止端侧传 model/apiKey/temperature/tokens
    - [ ] 风控：health 场景具备“非医疗声明 + 拒绝诊断类问题”
    - [ ] 审计：AI 调用只记录元数据（scene/provider/strategy/latency/result），不落库对话内容
  - **实现证据（文本）**：TBD（完成后补齐到 `facts/backend.md`、`facts/admin.md`、`facts/mini-program.md`）

### 4) 澄清问题（需要你确认后才能进入编码实现）

> 说明：以下问题都属于“数据模型/契约/业务规则”层面的缺口；不确认会导致实现不可控或破坏兼容性。

- **Q1（对应 REQ-ADMIN-P0-002 / REQ-PROVIDER-P0-002）**：你说的“商品（支持物流）”最小规格是什么？
  - 需要确认：是否需要收货地址、物流公司/运单号、发货/签收状态、运费/重量、库存、售后退换等。
  - 以及：订单状态机最小闭环你希望到哪一步（仅下单支付？还是含发货/签收？）
- **Q2（对应 REQ-ADMIN-P0-003）**：分账与结算里“目前需要手填”的具体字段有哪些？你希望简化成什么交互（选择模板/自动计算/向导）？
- **Q3（对应 REQ-ADMIN-P0-004）**：小程序配置中心“麻烦”的具体点是哪几项（页面/集合/入口/发布流程/校验/预览）？
- **Q4（对应 REQ-ADMIN-P0-006）**：你说的首页 banner/轮播图，期望落到小程序的哪个位置/模块？目前小程序首页是否已经有承载 banner 的渲染结构？
- **Q5（对应 REQ-ADMIN-P0-007）**：重置密码的规则与边界：
  - 可重置哪些账号（Admin/Dealer/Provider/ProviderStaff）？
  - 密码强度规则（最小长度、是否必须包含数字/大小写/符号）？
  - 是否要求“下次登录强制改密”？
- **Q6（对应 REQ-ADMIN-P0-008）**：协议分类清单请你先给一个最小枚举（例如：PROVIDER_INFRA_APPLY、PROVIDER_HEALTH_CARD_APPLY、H5_BUY_AGREEMENT、MP_LOGIN_AGREEMENT…），以及每类协议要展示在哪个端的哪个页面。
- **Q7（对应 REQ-PROVIDER-P0-001）**：复现“申请开通健行天下服务 500”的路径：点了哪个按钮、是否填写了什么、发生在提交哪个步骤？（你给的 requestId 我们会用来定位后端日志/链路）
- **Q8（对应 REQ-PROVIDER-P0-003）**：你希望“标签”是全局标签库，还是每个 Provider 自己维护？标签是否需要分类型（商品标签/服务标签/场所标签）？
- **Q9（对应 REQ-PROVIDER-P0-004/005/009）**：业务规则确认：**一个 Provider 是否只能有一个 Venue？**
  - 如果是：我们会把 UI 的“选择场所”改成固定当前场所，并清理相关统计字段的口径。
  - 如果否：那“选择场所”保留，但需要把“no data 的地区选择”和校验补齐。
- **Q10（对应 REQ-DEALER-P0-002）**：Dealer 结算周期你期望的口径是“月结/周结/日结”哪一种？是否与后端 `settlement_cycle` 的实现一致？
- **Q11（对应 REQ-H5-P0-002）**：REGION_CITIES 的数据你希望由哪里维护？
  - 由 Admin 页面维护并发布？还是直接写 SystemConfig JSON（仅临时）？
  - 数据规模：需要“全国省市区全量”还是仅覆盖已开通城市？

- **Q12/Q13（对应 REQ-PLATFORM-P0-001）结论（已确认）**：
  - 系统尚未上线：选择“彻底移除虚拟券能力”，并允许清理测试数据；不需要兼容历史虚拟券订单/商品。


