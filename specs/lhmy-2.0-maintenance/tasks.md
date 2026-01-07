# 任务清单（可勾选）

> 约束：本清单服务于“代码去重/可维护性优化”，必须遵守 `requirements.md` 的不变性约束与 DoD。

## [ ] FE-DEDUPE-BASE 基础去重基线（只读分析）

- **目标**：建立重复点清单与迁移路径，避免“边改边发现”导致扩散。
- **产出**
  - [ ] 重复模块清单（API/auth/storage/error/query/idempotency 等）
  - [ ] 每端“行为不变”验收点清单
  - [ ] 风险点与回滚策略
- **实现证据**：TBD

## [ ] FE-DEDUPE-SHARED-ALIAS 引入共享目录与 alias（不改业务逻辑）

- **范围**
  - [ ] `frontend/shared/` 新增共享代码目录（仅 TS 纯逻辑，不含 UI）
  - [ ] `frontend/admin`/`frontend/website`/`frontend/h5`：补齐 Vite/TS 配置以允许导入共享目录
- **不变性**：仅配置变更，不改页面逻辑
- **实现证据**：TBD

### 实现证据（进行中）

- **变更文件**
  - `frontend/admin/vite.config.ts`（新增 `@shared` alias）
  - `frontend/website/vite.config.ts`（新增 `@shared` alias + `server.fs.allow`）
  - `frontend/h5/vite.config.ts`（新增 `@shared` alias + `server.fs.allow`）
  - `nginx/Dockerfile`（website 构建阶段复制 `frontend/shared/`，确保容器内 `vue-tsc` 可解析 `@shared/*`）
  - `frontend/admin/tsconfig.app.json`（新增 TS paths）
  - `frontend/website/tsconfig.app.json`（新增 TS paths）
  - `frontend/h5/tsconfig.app.json`（新增 TS paths）
  - `frontend/shared/http/envelope.ts`
  - `frontend/shared/http/query.ts`
  - `frontend/shared/http/json.ts`
  - `frontend/shared/http/base.ts`
  - `frontend/shared/http/idempotency.ts`
- **回滚方式**
  - 直接 `git revert` 本任务相关提交即可（配置与新增文件均可安全回滚）

## [ ] FE-DEDUPE-API-CORE Web 三端请求层核心去重（保持各端行为不变）

- **目标**：提取 `envelope/query/idempotency/errors` 到 `frontend/shared/`，各端 `src/lib/api.ts` 保持对外 API 不变（wrapper 迁移）。
- **范围（至少）**
  - [ ] `envelope`：统一响应体解析与错误提取
  - [ ] `query`：query 拼接工具
  - [ ] `id`：`newIdempotencyKey()` 生成（保持既有行为：优先 `crypto.randomUUID()`）
  - [ ] `safe`：最小安全工具（如 readJsonSafe）
- **实现证据**：TBD

### 实现证据（进行中）

- **变更文件**
  - `frontend/admin/src/lib/api.ts`（复用 `@shared/http/*`，并把 401 跳转/错误解析内部收敛为私有 helper）
  - `frontend/website/src/lib/api.ts`（复用 `@shared/http/query`，并把 url/json/校验内部收敛为私有 helper）
  - `frontend/h5/src/lib/api.ts`（复用 `@shared/http/*`，并把 headers/401/错误构造内部收敛为私有 helper）
- **回滚方式**
  - 保持各端 `src/lib/api.ts` 对外 API 不变；回滚时直接 `git revert` 或恢复旧实现即可

## [ ] FE-DEDUPE-STORAGE Web 端存储工具去重（localStorage 安全封装）

- **目标**：收敛 try/catch 版 localStorage 读写，避免各端各写一套。
- **范围**
  - `frontend/shared/storage/localStorage.ts`
  - `frontend/admin/src/lib/auth.ts`（admin 端直接引用 shared localStorage，删掉无意义的转发层）
  - `frontend/admin/src/lib/theme.ts`（主题存取改用 shared localStorage wrapper，避免直接 storage 异常）
  - `frontend/admin/src/layouts/AppLayout.vue`（侧边栏折叠状态存取改用 shared localStorage wrapper）
  - `frontend/h5/src/lib/api.ts`（token 存取逻辑不变，仅改为调用 shared）
- **实现证据（进行中）**
  - 变更文件：
    - `frontend/shared/storage/localStorage.ts`
    - 删除：`frontend/admin/src/lib/storage.ts`
    - `frontend/admin/src/lib/auth.ts`
    - `frontend/admin/src/lib/theme.ts`
    - `frontend/admin/src/layouts/AppLayout.vue`
    - `frontend/h5/src/lib/api.ts`
  - 回滚方式：
    - `git revert` 本任务提交；或把 admin/auth.ts 与 h5 的 token 操作改回原实现

## [ ] FE-DEDUPE-AUTH-ACTOR Web 端身份类型与判定工具去重（ActorType）

- **目标**：把 `ActorType` 与 `isAdmin/isProvider/isDealer` 收敛到 shared，避免在多端分叉维护。
- **范围**
  - `frontend/shared/auth/actor.ts`
  - `frontend/admin/src/lib/auth.ts`（对外 API 保持不变，仅改为复用 shared 并转导出）
- **实现证据（进行中）**
  - 变更文件：
    - `frontend/shared/auth/actor.ts`
    - `frontend/admin/src/lib/auth.ts`
  - 回滚方式：
    - `git revert` 本任务提交；或将 admin/auth.ts 的类型与判定函数恢复为原地实现

## [ ] FE-DEDUPE-MP-API 小程序请求层对齐（仅对齐协议语义，不强行共享构建产物）

- **目标**：保持小程序行为不变，但与 Web 端对齐：Envelope、header 注入规则、错误对象字段语义一致。
- **实现证据**：TBD

## 证据记录区（模板）

当任务完成时，在对应任务下方补充：

- **变更文件**：`path` 列表
- **关键调用点**：`path::function/line`（可选）
- **回滚方式**：一句话
- **Smoke**：执行方式与结果

## [ ] FE-CLEANUP-SCAFFOLD 清理脚手架示例与未引用资源（让代码更像人维护）

- **目标**：删除默认脚手架残留（示例组件/未引用资源），降低噪音与误导。
- **范围**
  - 删除 `HelloWorld.vue`（admin/website/h5）
  - 删除未引用 `src/assets/vue.svg`（admin/website/h5）
- **实现证据（已完成）**
  - 变更文件：
    - 删除：`frontend/admin/src/components/HelloWorld.vue`
    - 删除：`frontend/website/src/components/HelloWorld.vue`
    - 删除：`frontend/h5/src/components/HelloWorld.vue`
    - 删除：`frontend/admin/src/assets/vue.svg`
    - 删除：`frontend/website/src/assets/vue.svg`
    - 删除：`frontend/h5/src/assets/vue.svg`
  - 回滚方式：
    - `git revert` 本任务提交；或从 git 历史恢复上述文件
  - Typecheck：
    - `frontend/admin`: `npm run typecheck` ✅
    - `frontend/website`: `npm run typecheck` ✅
    - `frontend/h5`: `npm run typecheck` ✅

## [ ] ADMIN-CLEANUP-INLINE-ONEOFF admin 清理单用途 lib 文件（减少跳转）

- **目标**：把“仅被单页引用、且仅包含副作用初始化”的 lib 文件内联到使用点，减少文件数量与跨文件跳转成本。
- **实现证据（已完成）**
  - 变更文件：
    - 修改：`frontend/admin/src/pages/admin/AdminDashboardPage.vue`（内联 ECharts minimal setup）
    - 删除：`frontend/admin/src/lib/echarts.ts`
  - 回滚方式：
    - `git revert` 本任务提交；或恢复 `lib/echarts.ts` 并改回 `import '../../lib/echarts'`
  - Typecheck：
    - `frontend/admin`: `npm run typecheck` ✅

## [ ] ADMIN-IA-SIDEBAR admin 侧边栏信息架构调整（业务线/全局能力对齐；不改路由与权限）

- **背景/问题**：现有侧边栏分组存在“业务线与全局能力混放”的体验问题（如：企业相关入口混入“用户与身份”；标签库/场所审核等全局能力被归入单一业务线；健行天下开通审核/分账结算归属不清；运营工具与官网配置边界模糊）。
- **目标**：按公司三大业务线（**基建联防 / 健行天下 / 职健行动**）+ “全局能力”重新分组与命名，让入口更符合业务语义与未来扩展。
- **排序规则（必须）**
  - **组内存在明显业务流程**：按业务流程排序（如：模板/配置 → 订单监管 → 履约/售后/审计）。
  - **组内无明显业务流程**：按 `path` 字典序排序（可重复、可验证）。
- **不变性（必须）**
  - 仅调整侧边栏 **分组/命名/顺序**；不改路由 path、不改权限门禁、不改页面功能。
  - 所有现有页面仍可通过原路径访问，跳转与接口调用行为不变。
- **实现证据（进行中）**
  - 变更文件：
    - `frontend/admin/src/lib/nav.ts`（重构 `getAdminNavGroups()`：新增“职健行动/供给审核/内容与投放/官网配置”等；`标签库（全局）` 归入“系统与审计”；`分账与结算` 归入“健行天下”；组间顺序调整为 `仪表盘 → 账号与身份 → 基建联防 → 职健行动 → 健行天下 → 供给审核 → 内容与投放 → 官网配置 → 系统与审计`）
  - 回滚方式：
    - `git revert` 本任务提交；或恢复 `frontend/admin/src/lib/nav.ts` 的 `getAdminNavGroups()` 原分组定义

## [ ] ADMIN-CMS-AUTHORING admin CMS 内容生产/投放体验增强（上传图片插入 Markdown + cmsContent 选择器）

- **规格依据**
  - `specs/health-services-platform/cms-v2-mini-program-content-center.md`（6.4 Admin 写侧/投放体验）
- **目标**
  - CMS 内容编辑：支持“上传图片 → 自动插入 Markdown 图片语法”，减少运营操作成本。
  - 小程序配置中心：INFO_PAGE 的 `cmsContent` 选择器支持按栏目筛选与关键词检索，便于选中正确内容。
  - CMS 内容列表：支持按投放端（官网/小程序）筛选视图，降低“同一列表混杂两端状态/按钮”的认知成本。
  - CMS IA：拆分为「内容中心（编辑/生产） / 官网投放（栏目+发布） / 小程序投放（发布）」三入口，强分工（平台未上线可大胆调整）。
- **不变性（必须）**
  - 不新增后端接口：复用 `POST /api/v1/uploads/images` 与现有 CMS API。
  - 不改变 CMS 内容数据结构与发布机制（仍按 `WEB` / `MINI_PROGRAM` 分开发布）。
- **实现证据**：TBD

## [ ] ADMIN-ASSETS-LIBRARY 资产库 v1（图片）：统一管理/检索/复用 + 上传去重（sha256）+ 存储抽象（LOCAL→OSS）

- **规格依据**：`specs/health-services-platform/assets-library-v1.md`
- **目标**
  - 上传图片写入资产库，并按 sha256 去重（重复上传返回同一 url）
  - Admin 资产列表：可检索/分页，供 CMS 选择复用
  - 封装 StorageProvider：本地落盘为默认实现，为未来 OSS/图床预留
- **实现证据**：TBD

## [ ] ADMIN-CLEANUP-DEPS admin 依赖精简（仅删除“无引用依赖”，不改功能）

- **目标**：避免依赖列表膨胀；仅在确认“无引用”时删除依赖，确保不影响现有功能。
- **扫描结论（当前）**
  - `frontend/admin/package.json` 中的 `dependencies` / `devDependencies` **均有引用点**，暂无可安全删除项：
    - `markdown-it`：`AdminMiniProgramConfigPage.vue`
    - `vue-echarts` / `echarts`：`AdminDashboardPage.vue`
    - `@playwright/test`：`tests/e2e/*` + `playwright.config.ts`
    - `element-plus` / `@element-plus/icons-vue` / `vue-router`：多处页面与布局
- **回归**
  - `frontend/admin`: `npm run build` ✅（同时包含 `vue-tsc -b`）

## [ ] ADMIN-AUDIT-ORPHANS admin 孤儿文件扫描（只读审计）

- **目标**：用可重复的脚本验证“是否存在未被路由引用的 pages”，避免误删/漏删。
- **实现证据（已完成）**
  - 脚本：`scripts/maintenance/find_orphans_admin.mjs`
  - 结果：
    - `admin pages total: 51`
    - `referenced by router: 51`
    - `orphans: none`

## [ ] ADMIN-DEDUPE-PAGERESP admin 统一分页响应类型（纯类型去重）

- **目标**：消除大量页面内重复的 `type PageResp<T> = { items; page; pageSize; total }`，让后期维护只改一处。
- **不变性**：纯 TypeScript 类型变更，不影响运行逻辑。
- **实现证据（已完成）**
  - 新增：`frontend/admin/src/lib/pagination.ts`
  - 替换：`frontend/admin/src/pages/**` 共 26 个页面移除本地 `PageResp<T>` 定义，改为 `import type { PageResp } from '../../lib/pagination'`
  - 回归：
    - `frontend/admin`: `npm run typecheck` ✅
    - `frontend/admin`: `npm run build` ✅

## [ ] H5-AUDIT-ORPHANS h5 孤儿文件审计（只读）

- **结论（当前）**
  - 路由入口在 `frontend/h5/src/main.ts`，pages 通过显式 import 注册，无孤儿 pages。
  - `frontend/h5/src/components`、`frontend/h5/src/assets` 均未被源码引用。

## [ ] H5-CLEANUP-EMPTY-DIRS h5 清理空目录（不影响功能）

- **目标**：删除未引用且为空的目录，减少维护噪音。
- **实现证据（已完成）**
  - 删除：
    - `frontend/h5/src/components/`（空目录，0 引用）
    - `frontend/h5/src/assets/`（空目录，0 引用）
  - 回归：
    - `frontend/h5`: `npm run typecheck` ✅
    - `frontend/h5`: `npm run build` ✅

## [ ] MP-CLEANUP-UNUSED-ASSETS 小程序清理未引用资源（不影响功能）

- **目标**：只删除确认 0 引用的静态资源，避免误删导致页面样式/图标缺失。
- **实现证据（已完成）**
  - 删除：
    - `frontend/mini-program/icons/arrow-down.png`（全仓 0 引用）
  - 复核：
    - grep `arrow-down.png`：0 命中 ✅

## [ ] BACKEND-DEDUPE-EXTRACT-BEARER 后端统一 Authorization Bearer 解析（去重，不改行为）

- **目标**：消除 `_extract_bearer_token` 的复制粘贴，统一到单一实现源，降低后续维护成本。
- **实现口径（保持不变）**
  - header 缺失/格式不对：抛 `HTTPException(401)`，detail 为 `{code: "UNAUTHENTICATED", message: "未登录"}`
  - `Bearer` 大小写不敏感
  - token 需要 `strip()`
- **实现证据（已完成）**
  - 新增：
    - `backend/app/utils/auth_header.py`：`extract_bearer_token()`
  - 迁移（删除本地 `def _extract_bearer_token`，改为 `from app.utils.auth_header import extract_bearer_token as _extract_bearer_token`）：
    - `backend/app/api/v1/admin_auth.py`
    - `backend/app/api/v1/auth.py`
    - `backend/app/api/v1/deps.py`
    - `backend/app/api/v1/admin_ai.py`
    - `backend/app/services/provider_auth_context.py`
    - `backend/app/api/v1/after_sales.py`
    - `backend/app/api/v1/bookings.py`
    - `backend/app/api/v1/dealer.py`
    - `backend/app/api/v1/cart.py`
    - `backend/app/api/v1/entitlements.py`
    - `backend/app/api/v1/admin_venues.py`
    - `backend/app/api/v1/orders.py`
    - `backend/app/api/v1/products.py`
    - `backend/app/api/v1/taxonomy_nodes.py`
    - `backend/app/api/v1/product_categories.py`
    - `backend/app/api/v1/dealer_links.py`
    - `backend/app/api/v1/users.py`
    - `backend/app/api/v1/dealer_auth.py`
    - `backend/app/api/v1/provider_auth.py`
    - `backend/app/api/v1/ai.py`
  - 复核：
    - `backend/app/api/v1` 内 grep `def _extract_bearer_token`：0 命中 ✅
    - `python -m compileall backend/app -q` ✅

## [ ] BACKEND-DEDUPE-ISO 后端统一 datetime -> ISO 字符串（去重，不改行为）

- **目标**：消除 `_iso(dt)` 的复制粘贴，统一到单一实现源，降低后续维护成本。
- **实现口径（已升级：全站时间契约）（你已拍板）**
  - 全站契约：`specs/health-services-platform/time-and-timezone.md`
  - `dt is None`：返回 `None`
  - 否则：输出 **UTC ISO 8601 且带 `Z`**（例如 `2026-01-07T12:34:56Z`）
- **实现证据（已完成）**
  - 新增：
    - `backend/app/utils/datetime_iso.py`：`iso(dt: datetime | None) -> str | None`
  - 迁移（删除本地 `def _iso`，改为 `from app.utils.datetime_iso import iso as _iso`）：
    - `backend/app/api/v1/admin_accounts.py`
    - `backend/app/api/v1/admin_dealer_settlements.py`
    - `backend/app/api/v1/admin_legal.py`
    - `backend/app/api/v1/admin_mini_program_config.py`
    - `backend/app/api/v1/admin_provider_onboarding.py`
    - `backend/app/api/v1/admin_sellable_cards.py`
    - `backend/app/api/v1/admin_service_categories.py`
    - `backend/app/api/v1/admin_service_packages.py`
    - `backend/app/api/v1/cms.py`
    - `backend/app/api/v1/dealer_sellable_cards.py`
    - `backend/app/api/v1/h5_config.py`
    - `backend/app/api/v1/provider.py`
    - `backend/app/api/v1/provider_onboarding.py`
    - `backend/app/api/v1/sellable_cards.py`
    - `backend/app/api/v1/service_categories.py`
  - 复核：
    - `backend/app/api/v1` 内 grep `def _iso`：0 命中 ✅
    - `python -m compileall backend/app -q` ✅

## [ ] BACKEND-INVENTORY-TYPING 修复库存任务类型标注（不改行为）

- **问题**：SQLAlchemy `scalars(...).all()` 的类型推导为 `Sequence[T]`，与代码中显式标注的 `list[T]` 不兼容，触发类型检查错误。
- **修复方式（不改运行逻辑）**
  - 将 `.all()` 的结果显式 `list(...)` 化以满足 `list[T]` 标注。
  - 对 Celery 的 `connect` / `.s()` 使用 `cast(Any, ...)`，仅消除静态类型误报。
- **涉及文件**
  - `backend/app/tasks/inventory.py`
- **回归**
  - `python -m compileall backend/app -q` ✅

## [ ] BACKEND-DEALER-LINKS-IDEM-TYPING 修复 dealer_links 幂等 actor_type 类型（不改行为）

- **问题**：`IdempotencyService.get/set` 形参 `actor_type` 类型为 `IdemActorType`（Literal union），但 `dealer_links.py` 传入的是 `str`，触发类型检查错误。
- **修复方式（不改运行逻辑）**
  - 在调用 `get/set` 时对 `actor_type` 使用 `cast(IdemActorType, ...)`，保持实际字符串值不变，仅修正静态类型。
- **涉及文件**
  - `backend/app/api/v1/dealer_links.py`
- **回归**
  - `python -m compileall backend/app -q` ✅

## [ ] BACKEND-DEALER-ORDERS-TYPING 修复 dealer orders 预取明细变量遮蔽导致的类型错误（不改行为）

- **问题**：同一函数内复用变量名 `items`（既用于 `OrderItem` 查询结果，又用于响应 `items: list[dict]`），导致类型系统将 `OrderItem` 序列误判为 `list[dict]`。
- **修复方式（不改运行逻辑）**
  - 将订单明细查询结果变量改名为 `order_items`，并使用独立的 `item_map_typed: dict[str, list[OrderItem]]` 构建映射，避免遮蔽/误推导。
- **涉及文件**
  - `backend/app/api/v1/dealer.py`
- **回归**
  - `python -m compileall backend/app -q` ✅

## [x] BACKEND-LEGAL-MD-TILDE 协议/条款 Markdown 删除线（~~text~~）渲染支持

- **规格依据**
  - `specs/health-services-platform/tasks.md` -> `REQ-ADMIN-P0-008`
- **问题**
  - Provider 工作台“开通基建联防/健行天下”弹窗协议预览中，`~~删除线~~` 无法正确渲染（多为直接显示 `~~` 文本）。
- **根因**
  - 协议/条款的 Markdown→HTML 转换（`admin_legal.py:_markdown_to_safe_html`）未启用 `pymdownx.tilde` 扩展。
- **修复方式（不改接口契约）**
  - 在 Markdown 扩展中加入 `pymdownx.tilde`，生成 `<del>` 标签；`bleach` 已允许 `del` 标签，无需额外放开。
- **涉及文件**
  - `backend/app/api/v1/admin_legal.py`
- **回归**
  - 在管理端 `协议/条款管理` 中重新保存并发布相关协议（例如 `PROVIDER_INFRA_APPLY` / `PROVIDER_HEALTH_CARD_APPLY`），再到 Provider 工作台打开协议预览确认删除线生效。

## [ ] BACKEND-PAYMENTS-WECHAT-VERIFY-TYPING 修复微信支付验签公钥类型收窄（不改行为）

- **问题**：`cert.public_key()` 静态类型可能为多种公钥类型（含无 `verify` 的 X25519/X448），导致类型检查在 `pub.verify(...)` 处报“需要传入 2/3 个位置参数”等错误。
- **修复方式（不改运行逻辑）**
  - 对公钥做 `isinstance` 收窄：
    - RSA：按微信支付 v3 规范使用 `PKCS1v15 + SHA256` 验签
    - ECC：兜底使用 `ECDSA(SHA256)`
    - 其他类型：视为配置错误，返回 500 `INTERNAL_ERROR`
- **涉及文件**
  - `backend/app/api/v1/payments.py`
- **回归**
  - `python -m compileall backend/app -q` ✅


