# Admin 生产化任务清单（可勾选）

> 规则：
> - 每条任务必须包含：**Spec 引用** → **DoD** → **实现证据**（占位也要有）→ **测试证据** → **风险/回滚**
> - 排序：高风险（资金/审核/导出/权限） > 订单核心 > 配置发布类 > 展示类

## 0. 状态图例
- [ ] 未开始
- [~] 进行中（用文字标注 in progress）
- [x] 已完成

## 1. P0 / 高风险优先（Top 10）

### [x] TASK-P0-001 生产级权限矩阵落地（覆盖所有 Admin 线路 + 后端强制门禁）
- **Spec 引用**：
  - `requirements.md#1-权限矩阵（RBAC-Matrix）——待拍板`
  - `flow-catalog.md#2-已知线路（基于现有路由与接口的最小骨架）`
  - `security.md#2-越权防护`
- **缺口**：
  - 当前前端有 role 路由门禁，但后端“动作级/路线级”权限矩阵未固化
- **DoD**：
  - `flow-catalog.md` 覆盖 `frontend/admin/src/router/index.ts` 中所有 `meta.role='ADMIN'` 页面
  - `requirements.md` 权限矩阵对每条线路给出允许角色 + 数据范围
  - 后端每条 admin API 明确依赖 `require_admin`（或等价）并补齐缺失点
- **实现证据（占位）**：
  - 后端门禁补齐（/api/v1/admin/** 一刀切 require_admin）：
    - `backend/app/api/v1/after_sales.py`：`GET /admin/after-sales`、`PUT /admin/after-sales/{id}/decide`
    - `backend/app/api/v1/admin_ai.py`：`GET/PUT /admin/ai/config`、`GET /admin/ai/audit-logs`
    - `backend/app/api/v1/admin_auth.py`：`POST /admin/auth/change-password|refresh|logout`
    - `backend/app/api/v1/auth.py`：`GET /admin/enterprise-bindings`、`PUT /admin/enterprise-bindings/{id}/approve|reject`
    - `backend/app/api/v1/product_categories.py`：`GET/POST/PUT /admin/product-categories*`
    - `backend/app/api/v1/taxonomy_nodes.py`：`GET/POST/PUT /admin/taxonomy-nodes*`
    - `backend/app/api/v1/products.py`：`GET /admin/products`、`PUT /admin/products/{id}/approve|reject|off-shelf`
    - `backend/app/api/v1/admin_venues.py`：`GET /admin/venues`、`GET /admin/venues/{id}`、`POST /admin/venues/{id}/publish|reject|offline`
  - 扫描脚本（可复现缺口清单）：`scripts/admin_routes_require_admin_scan.py`
- **测试证据（占位）**：
  - 静态门禁回归：`backend/tests/test_admin_routes_require_admin_static.py`
  - 权限 DoD 护栏（集成测试）：`backend/tests/test_integration_permission_dod_cases.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_permission_dod_cases.py -q`
- **风险/回滚**：
  - 风险：权限收紧导致业务不可用
  - 回滚：按 `release.md#3-回滚步骤` 回退到上一版本；必要时引入临时 feature flag（需规格确认）

### [~] TASK-P0-002 审计日志“可查询 + 可追溯”闭环（含高风险事件覆盖率）（in progress：Batch1-结算）
- **Spec 引用**：`security.md#3-审计`、`observability.md#3-排障方式`
- **缺口**：目前已知登录/登出有审计；资金/发布/导出等覆盖情况不明
- **DoD**：
  - 明确“必审计操作清单”并与现有实现对齐
  - 提供 ADMIN 审计日志查询线路（Flow + API + 权限门槛 + 脱敏）
  - 每条高风险写操作至少产出一条审计事件，并可按 requestId 追溯
  - 定义并可验收“高风险事件覆盖率”（分母来自 `security.md#3.1.1`；分子=时间窗内每类至少 1 条业务审计）
  - 提供“未覆盖类型清单”输出方式（用于上线阻断/回归）
- **实现证据（阶段性）**：
  - 结算批次生成/标记结算：`backend/app/api/v1/admin_dealer_settlements.py`
  - 审计查询 RBAC/脱敏证据：`backend/app/api/v1/audit_logs.py`（require_admin 统一鉴权）
- **测试证据（阶段性）**：
  - `backend/tests/test_integration_admin_dealer_settlements_audit_and_idempotency.py`（结算相关审计断言）
  - `backend/tests/test_integration_admin_audit_logs_rbac_and_masking.py`（查询 401/403/脱敏）
  - `backend/tests/test_audit_coverage_report_render.py`（覆盖率脚本输出格式/分母一致性）
- **验收记录（本地可复现）**：
  - 仅运行“会写审计”的导出测试（避免其他测试 reset DB 清空审计）：
    - `RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_export_dealer_orders_csv.py -q -k test_export_requires_date_from_to_and_audited_and_csv_attachment`
  - 覆盖率脚本：
    - `uv run python scripts/audit_coverage_report.py --env-file .env --days 7 --output specs-prod/admin/evidence/audit-coverage/local-run.md`
  - 结果：`specs-prod/admin/evidence/audit-coverage/local-run.md`（当前已验证 `EXPORT_DEALER_ORDERS`=YES，覆盖率 1/6）
- **待补齐（覆盖率落地）**：
  - v1 统计口径：`observability.md#2.3`（先审计表聚合查询；后续再拍板是否上 Prometheus）
  - 验收物料：
    - SQL：`specs-prod/admin/ops/audit_coverage_7d.sql`
    - 脚本：`scripts/audit_coverage_report.py`
    - 结果记录：`specs-prod/admin/evidence/audit-coverage/`（按日落盘）
    - 本地运行留痕（示例：连接失败也落盘）：`specs-prod/admin/evidence/audit-coverage/local-run.md`
- **风险/回滚**：审计写入导致性能/容量风险；回滚为关闭审计增强项（需规格确认开关策略）

### [x] TASK-P0-003 导出能力生产化（权限门槛 + 脱敏 + 限流 + 审计 + 文件生命周期）（Batch4 完成：v1 同步直下 CSV）
- **Spec 引用**：`security.md#5-导出安全`、`observability.md#2-最小指标`
- **缺口**：导出规格缺失（字段/权限/审计/TTL/异步）
- **DoD**：
  - 盘点并列出“全部导出点”（前端按钮/后端接口）与证据（文件/函数/路由）
  - 产出并拍板 v1 导出形态（见 `api-contracts.md#10(9)`）
  - 每个导出点明确：字段白名单、脱敏规则、maxRows、必须过滤条件、速率限制
  - 每次导出必须产生审计事件（可追溯 requestId + actor + filters + rowCount）
  - 文件生命周期：
    - 若 v1 采用“同步直下不落盘”：明确 TTL=0（下载即销毁）
    - 若采用“异步落盘”：必须写清 TTL 与清理策略
- **实现证据**：
  - 后端：`backend/app/api/v1/dealer.py::export_dealer_orders_csv`（强制 dateFrom/dateTo；maxRows=5000；审计写入；直下不落盘）
  - 前端：`frontend/admin/src/pages/dealer/DealerOrdersPage.vue::exportCsv`（改为后端下载；dateFrom/dateTo 缺失时禁用）
  - 前端：`frontend/admin/src/lib/api.ts::apiDownload`（下载工具，复用 401 跳登录语义）
- **测试证据**：
  - `backend/tests/test_integration_export_dealer_orders_csv.py`
  - 运行方式：`uv run pytest backend/tests/test_integration_export_dealer_orders_csv.py -q`（需 RUN_INTEGRATION_TESTS=1）
- **风险/回滚**：
  - 风险：导出端点可能被滥用（已通过必填日期 + maxRows 限制收敛；限流策略待后续拍板加强）
  - 回滚：回退前后端改动；若紧急，可临时下线导出按钮（需记录审计与变更说明）

### [~] TASK-P0-004 经销商结算“资金级”保护（双人复核/冻结/审计/幂等证明）（in progress：Batch1-审计+幂等）
- **Spec 引用**：`api-contracts.md#5-Admin-Dealer-Settlements（经销商结算-高风险）`、`security.md#3-审计`
- **缺口**：结算标记属于资金高风险，需补齐生产级门槛（至少审计与复核策略）
- **DoD**：
  - `mark-settled` 明确权限门槛与审计字段
  - 结算生成/标记的幂等与状态机在规格中固化
  - （若需要）双人复核/冻结策略明确（不实现前先拍板）
- **实现证据（阶段性）**：
  - 后端：`backend/app/api/v1/admin_dealer_settlements.py`
    - `admin_mark_dealer_settlement_settled`：SETTLED 重复提交 → 200 幂等 no-op；FROZEN → 409 `STATE_CONFLICT`
    - `admin_generate_dealer_settlements`：同 cycle 重复 generate → 幂等返回 existing
- **测试证据（阶段性）**：
  - `backend/tests/test_integration_admin_dealer_settlements_audit_and_idempotency.py`
- **风险/回滚**：口径/资金误操作；回滚为恢复上一版本并冻结高风险入口

### [x] TASK-P0-005 管理员账号与会话安全加固（初始化账号/密码策略/2FA 策略/锁定策略）
- **Spec 引用**：`security.md#1-会话与认证`、`api-contracts.md#2-Admin-Auth（管理端认证）`
- **缺口**：初始化账号逻辑存在（开发/测试），生产策略需明确；密码策略/锁定策略未固化
- **DoD**：
  - 规格拍板：`security.md#1.4`（seed/密码/锁定/2FA/会话）
  - 生产环境：
    - 禁止请求路径内自动 seed admin（`ADMIN_INIT_*` 不生效）
    - 必须存在可用的初始化投放流程（脚本/DB/工单）与回滚步骤
  - 密码策略：
    - change-password 强制校验密码策略（长度/复杂度/弱口令）
  - 失败锁定：
    - login/2FA 相关端点受限流/锁定保护；触发后返回 429 `RATE_LIMITED`（或你拍板的业务码）
  - 2FA：
    - 策略（可选/强制/按账号）明确并实现；challenge/verify 有重发/校验限流
  - 审计：
    - 登录成功/登出/改密必须审计（现状部分已做）；失败/锁定事件是否审计按规格拍板
- **实现证据（占位）**：
  - 规格：`specs-prod/admin/security.md#1.4`、`specs-prod/admin/api-contracts.md#2.7`
  - 后端：
    - 生产禁用 seed：admin 登录路径不再创建账号：`backend/app/api/v1/admin_auth.py::_ensure_admin_seed`
    - 登录失败锁定（5次/10min/30min，429）：`backend/app/api/v1/admin_auth.py::admin_login`
    - 密码策略（≥10，4选2，弱口令黑名单）：`backend/app/services/admin_password_policy.py` + `backend/app/api/v1/admin_auth.py::admin_change_password`
    - 绑定手机号（开启2FA）：`backend/app/api/v1/admin_auth.py::admin_phone_bind_challenge/admin_phone_bind_verify`
    - 高风险门禁（未绑定 -> 403 ADMIN_PHONE_REQUIRED）：`backend/app/api/v1/deps.py::require_admin_phone_bound`（已接入结算/发货/妥投/强制取消/发布等）
  - 前端：
    - 登录提示：`frontend/admin/src/pages/LoginPage.vue`（phoneBound=false 时提示绑定）
    - 安全设置：`frontend/admin/src/pages/AccountSecurityPage.vue`（绑定手机号 UI；密码校验提示更新）
    - 统一错误处理：`frontend/admin/src/lib/error-handling.ts`（403 ADMIN_PHONE_REQUIRED 引导到安全设置）
  - 脚本（一次性初始化 + 回滚）：`scripts/admin_init_once.py`
- **测试证据**：
  - `backend/tests/test_integration_admin_auth_hardening_task_p0_005.py`
  - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_admin_auth_hardening_task_p0_005.py -q`
- **风险/回滚**：
  - 风险：策略过严导致无法登录/收不到验证码
  - 回滚：临时放宽阈值/关闭 2FA 强制（必须审计并有时限）；并提供“break-glass”账号恢复流程

### [x] TASK-P0-006 敏感信息治理（字段清单 + 脱敏统一策略 + 前端展示约束）
- **Spec 引用**：`requirements.md#R-PII-001`、`security.md#2-2-最小权限与敏感信息`
- **缺口**：部分接口已脱敏，但全局清单/一致策略未固化
- **DoD**：
  - 建立“敏感字段清单”（`requirements.md#R-PII-001.1`）并标注 List/Detail/Export 规则
  - 在 `security.md#2.3` 拍板：运单号/收货地址/结算凭证/场所电话/权益凭证 的出参口径
  - 后端：按清单落地字段白名单与脱敏（至少覆盖：订单、结算、场所）
  - 前端：展示层不展示敏感明文（即使后端返回也应兜底遮罩；但原则上后端不应返回）
  - 测试：新增断言“关键接口不返回敏感明文字段”（最小先覆盖：`/admin/orders`、`/dealer/settlements`、`/admin/venues/{id}`）
- **实现证据（占位）**：
  - 规则：`specs-prod/admin/security.md#2.3.5`（拍板口径）、`specs-prod/admin/requirements.md#R-PII-001.1`
  - 后端（脱敏/白名单）：
    - Admin 订单监管：`backend/app/api/v1/orders.py::admin_list_orders`（`trackingNoLast4` 替代 `shippingTrackingNo`）
    - Admin 订单详情（ADMIN 调用 `/orders/{id}`）：`backend/app/api/v1/orders.py::get_order_detail`（Admin 场景移除运单号明文；`shippingAddress` 输出仅省市区 + `phoneMasked`）
    - Dealer/Admin 结算列表：`backend/app/api/v1/dealer.py::list_dealer_settlements`、`backend/app/api/v1/admin_dealer_settlements.py::admin_list_dealer_settlements`（`payoutReferenceLast4` + `payoutAccount` 白名单脱敏）
    - 结算标记接口回包：`backend/app/api/v1/admin_dealer_settlements.py::admin_mark_dealer_settlement_settled`（回包仅 `payoutReferenceLast4`）
    - 场所公开端：`backend/app/api/v1/venues.py::_venue_detail_public_dto`、`backend/app/api/v1/venues.py::get_venue_detail`（移除 `contactPhone` 明文，仅 `contactPhoneMasked`）
    - 场所详情查看审计（Admin/Provider）：`backend/app/api/v1/admin_venues.py::admin_get_venue_detail`、`backend/app/api/v1/provider.py::provider_get_venue`（action=`VIEW`，不记录电话明文）
    - 权益（ADMIN）：`backend/app/api/v1/entitlements.py::list_entitlements/get_entitlement_detail`（Admin 场景移除 `qrCode/voucherCode`）
  - 前端（展示约束/类型对齐）：
    - Admin 订单监管：`frontend/admin/src/pages/admin/AdminOrdersPage.vue`、`frontend/admin/src/pages/admin/AdminOrdersByTypePage.vue`（展示 `trackingNoLast4`；不再依赖 `shippingTrackingNo`）
    - Dealer 结算记录：`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`（展示 `payoutReferenceLast4`）
    - Admin 结算：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`（不再回显 `payoutReference`）
    - Admin 权益页：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue`（不声明 `qrCode/voucherCode` 字段）
- **测试证据**：
  - `backend/tests/test_integration_pii_baseline_task_p0_006.py`
  - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_pii_baseline_task_p0_006.py -q`
- **风险/回滚**：
  - 风险：误脱敏影响运营/履约排查效率
  - 回滚：恢复字段但必须同步提高权限门槛与审计（需规格确认）

### [x] TASK-P0-007 统一错误码与前端错误处理（不靠 message）
- **Spec 引用**：`api-contracts.md#7-错误码与语义`
- **缺口**：错误码存在但前端是否一致处理未知；接口间 error.code 一致性需梳理
- **DoD**：
  - 后端：所有错误响应均为 envelope；401 统一使用 `UNAUTHENTICATED`（不出现 `UNAUTHORIZED`）
  - 后端：`/api/v1/admin/**` 端点在未登录返回 401 `UNAUTHENTICATED`；错误角色返回 403 `FORBIDDEN`
  - 后端：状态机写操作按契约区分 `STATE_CONFLICT` / `INVALID_STATE_TRANSITION`
  - 前端：形成统一错误处理模块，按 `api-contracts.md#7.3` 做动作映射（401 跳登录、403 跳 403、409 提示刷新等）
  - 前端：关键页面不再复制粘贴 catch 逻辑（最小先覆盖：结算/订单/预约/投放链接/导出/审计查询）
 - **实现证据（占位）**：
  - 后端：`backend/app/middleware/exceptions.py`（状态码兜底映射；401 -> UNAUTHENTICATED）
  - 后端测试：`backend/tests/test_exception_handler_status_code_mapping.py`
  - 前端：`frontend/admin/src/lib/error-handling.ts`（按 code 的统一动作映射）
  - 前端兼容：`frontend/admin/src/lib/api.ts`（401 + code=UNAUTHORIZED -> UNAUTHENTICATED 过渡）
  - 页面落地（示例）：`frontend/admin/src/pages/admin/AdminOrdersPage.vue`、`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`、`frontend/admin/src/pages/admin/AdminBookingsPage.vue`、`frontend/admin/src/pages/dealer/DealerLinksPage.vue`
 - **测试证据（占位）**：
  - 后端：集成测试覆盖 401/403/400/409（至少一条 admin API + 一条状态机写）
    - `backend/tests/test_integration_permission_dod_cases.py`（401/403/资源归属越权）
    - `backend/tests/test_integration_error_code_baseline_400_409.py`（400 INVALID_ARGUMENT；409 INVALID_STATE_TRANSITION）
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_error_code_baseline_400_409.py -q`
- **风险/回滚**：错误提示变化造成误导；回滚为保留旧提示但不破坏 code

### [~] TASK-P0-008 高风险接口的幂等/并发证明（文档化 + 测试化）（in progress：Batch1-结算）
- **Spec 引用**：`api-contracts.md#8-幂等约定（Baseline）`
- **缺口**：部分接口有幂等实现（结算 generate），但缺少统一规格与测试证明
- **DoD**：
  - 为每个高风险写接口写明幂等策略与冲突行为（409/200/忽略）
  - 增加对应的自动化测试覆盖并发/重复请求
- **实现证据（阶段性）**：
  - `backend/app/api/v1/admin_dealer_settlements.py::admin_mark_dealer_settlement_settled`（状态机幂等 no-op / 409）
  - `backend/app/api/v1/admin_dealer_settlements.py::admin_generate_dealer_settlements`（资源幂等：同 dealerId+cycle 不重复创建）
- **测试证据（阶段性）**：
  - `backend/tests/test_integration_admin_dealer_settlements_audit_and_idempotency.py`
- **风险/回滚**：幂等改动影响行为；回滚为恢复旧行为并在规格中标注

### [x] TASK-P0-009 Admin 可观测性基线：关键指标与 requestId 排障闭环
- **Spec 引用**：`observability.md`
- **缺口**：有 requestId/metrics 暴露，但业务级指标与高风险事件统计未固化
- **DoD**：
  - 关键高风险动作都能从 requestId 追溯到日志与审计
  - 指标仪表盘（或最小查询方式）能看到错误率/延迟/高风险操作次数
- **实现证据**：
  - requestId：`backend/app/middleware/request_id.py`（写入 `request.state.request_id` + 回传 `X-Request-Id`）
  - 请求日志：`backend/app/middleware/request_logger.py`（记录 requestId/path/method/status/cost + actor/ip/ua）
  - metrics：`backend/app/main.py`（`Instrumentator().instrument(app).expose(..., endpoint="/metrics")`）
- **测试证据**：
  - `backend/tests/test_integration_request_id_consistency_task_p0_009.py`
  - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_request_id_consistency_task_p0_009.py -q`
- **风险/回滚**：
  - 风险：日志/指标开销、包含 UA 等字段导致日志量上升
  - 回滚：降低日志级别或移除部分字段（需同步更新 `observability.md#1.1` 并记录变更）

### [~] TASK-P0-010 发布/回滚演练（含灰度与紧急回滚）（文档已齐，待环境实操留痕）
- **Spec 引用**：`release.md`、`test-plan.md`
- **缺口**：发布/回滚目前是占位，需对齐实际 CI/CD 与环境
- **DoD**：
  - 发布步骤可在目标环境执行（命令/脚本明确）
  - 至少一次回滚演练成功并记录证据（日志/截图/工单）
- **实现证据**：
  - 发布/回滚说明：`specs-prod/admin/release.md`
  - 冒烟清单：`specs-prod/admin/release-smoke.md`
  - 备份/恢复（v1）：`docker-compose.ops.yml` + `ops/backup/mysql/backup.sh`、`ops/backup/mysql/restore.sh`
  - 初始化管理员（一次性，可审计/可回滚）：`scripts/admin_init_once.py`
- **测试证据**：
  - 冒烟执行记录：`specs-prod/admin/evidence/release/YYYY-MM-DD.md`（按模板）
- **风险/回滚**：
  - 风险：演练误操作导致数据丢失/服务不可用
  - 保护：必须在预发环境执行；DB 恢复操作需审批；严格按 `release.md` 流程

## 2. 按线路生成的任务卡（全域：ADMIN/DEALER/PROVIDER）

> 规则（本节每条线路都必须覆盖，允许合并实现但不能缺）：  
> - 权限硬校验（后端）  
> - 错误码规范化（前后端一致）  
> - 审计日志（敏感操作必做）  
> - 幂等/防重复（如适用）  
> - 可观测日志字段（最小结构化）  
> - 最小测试（成功/失败/越权/边界）  
> - 发布与回滚说明（涉及 DB 变更必须写清）  
>
> 覆盖承诺：本节 flow 卡已覆盖 `frontend/admin/src/router/index.ts` 中**全部页面**（public 与非 public 均有归属）。

### [x] FLOW-AUTH-LOGIN 登录（高频）
- **范围（页面）**：`/login`（`frontend/admin/src/pages/LoginPage.vue`）
- **接口范围（至少）**：
  - `POST /api/v1/admin/auth/login`（`backend/app/api/v1/admin_auth.py`）
  - `POST /api/v1/provider/auth/login`（`backend/app/api/v1/provider_auth.py`）
  - `POST /api/v1/dealer/auth/login`（`backend/app/api/v1/dealer_auth.py`）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：登录接口为 PUBLIC；其他接口不得被未登录访问（401）
  - [x] **错误码规范化**：
    - ADMIN：401 `ADMIN_CREDENTIALS_INVALID`
    - PROVIDER/DEALER：401 `UNAUTHENTICATED`
  - [x] **审计日志**：成功登录必须记录 `LOGIN`（ADMIN/DEALER/PROVIDER 均已对齐）
  - [x] **幂等/防重复**：不要求幂等键；每次成功登录签发新 token（v1 不做互斥）
  - [x] **可观测日志字段**：失败/成功均可用 `requestId` 排查（含 ip/ua/path，见 `observability.md`）
  - [x] **最小测试**：登录失败错误码；provider/dealer 登录成功 + LOGIN 审计
  - [x] **发布与回滚**：无 DB 变更；回滚为回退前后端改动（见 `release.md`）
- **DoD（验收步骤）**
  - 未登录访问 `/admin/dashboard` → 跳转 `/login?reason=UNAUTHENTICATED&next=...`
  - 使用错误密码调用 `POST /api/v1/admin/auth/login` → 401 + `error.code=ADMIN_CREDENTIALS_INVALID`
  - 正确账号密码登录 → 200 返回 token；前端写入 session 并跳转 next 或默认首页
  - 查 `GET /api/v1/admin/audit-logs?action=LOGIN` 能看到对应登录记录（若审计要求拍板为必做）
- **实现证据占位（文件/函数/接口）**
  - 前端：`frontend/admin/src/pages/LoginPage.vue::smartLogin`
  - 后端：`backend/app/api/v1/admin_auth.py::admin_login`（及 provider/dealer 登录对应函数）
  - 接口：如上
  - 测试：`backend/tests/test_integration_flow_auth_login_refresh.py`

### [x] FLOW-AUTH-REFRESH 会话续期（高频）
- **范围（页面）**：无（由前端请求触发）
- **接口范围**：`POST /api/v1/admin/auth/refresh`（`backend/app/api/v1/admin_auth.py`）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN token 可 refresh；旧 token blacklist 生效
  - [x] **错误码规范化**：旧 token 已失效 → 401 `UNAUTHENTICATED`
  - [x] **审计日志**：v1 暂不强制记录 `REFRESH`（若需要请你在 `api-contracts.md#10` 拍板）
  - [x] **幂等/防重复**：同一旧 token 二次 refresh → 401 `UNAUTHENTICATED`
  - [x] **可观测日志字段**：requestId 可定位（见 `TASK-P0-009`）
  - [x] **最小测试**：首次 refresh 成功；重复 refresh 失败；logout 后 token 失效
  - [x] **发布与回滚**：无 DB 变更；回滚为回退后端逻辑
- **DoD（验收步骤）**
  - 登录拿到 tokenA → refresh → 返回 tokenB
  - 用 tokenA 再 refresh/访问任意 admin API → 401
  - 用 tokenB 访问 admin API → 200
- **实现证据占位**
  - 前端：`frontend/admin/src/lib/api.ts`（401 清会话跳登录策略需保持一致）
  - 后端：`backend/app/api/v1/admin_auth.py::admin_refresh`
  - 依赖：`backend/app/services/rbac.py` blacklist 校验
  - 测试：`backend/tests/test_integration_flow_auth_login_refresh.py`

### [x] FLOW-AUDIT-LOGS 审计日志查询（高风险 + 高频）（Batch7 完成）
- **范围（页面）**：`/admin/audit-logs`（`frontend/admin/src/pages/admin/AdminAuditLogsPage.vue`）
- **接口范围**：`GET /api/v1/admin/audit-logs`（`backend/app/api/v1/audit_logs.py`）
- **必须覆盖能力（勾选项）**
  - [ ] **权限硬校验（后端）**：仅 ADMIN 可查询；未登录 401
  - [ ] **错误码规范化**：dateFrom/dateTo 格式错误 → 400 `INVALID_ARGUMENT`
  - [ ] **审计日志**：metadata 出参必须兜底脱敏（password/token/smsCode/phone）
  - [ ] **幂等/防重复**：不适用（读接口）
  - [ ] **可观测日志字段**：requestId + filters 可定位问题；慢查询可识别
  - [ ] **最小测试**：分页/过滤/非法时间/未登录/非 ADMIN
  - [ ] **发布与回滚**：如需新增索引（created_at/actorType/action/resourceType），必须写清 alembic 与回滚
- **DoD（验收步骤）**
  - 未登录访问 → 401
  - ADMIN 登录后查询 → 200（分页、按 createdAt desc）
  - 传非法 dateFrom → 400 `INVALID_ARGUMENT`
  - metadata 中敏感字段不泄露（返回 "***"/脱敏）
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminAuditLogsPage.vue::load`
  - 后端：`backend/app/api/v1/audit_logs.py::admin_list_audit_logs`（鉴权改为 `Depends(require_admin)`，非 ADMIN → 403）
  - 测试：`backend/tests/test_integration_admin_audit_logs_rbac_and_masking.py`（401/403/200 + metadata 脱敏断言）

### [x] FLOW-DEALER-SETTLEMENTS 经销商结算（资金高风险）（Batch1 完成）
- **范围（页面）**：`/admin/dealer-settlements`（`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`）
- **接口范围（至少）**
  - `GET/PUT /api/v1/admin/dealer-commission`（分账规则）
  - `POST /api/v1/admin/dealer-settlements/generate`（生成，幂等）
  - `GET /api/v1/admin/dealer-settlements`（分页）
  - `POST /api/v1/admin/dealer-settlements/{id}/mark-settled`（标记结算，强审计）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；未登录 401；错误角色 403（依赖 `require_admin`）
  - [x] **错误码规范化**：cycle 格式非法/状态冲突/不存在/非法状态迁移（409）等 code 对齐 `api-contracts.md`
  - [x] **审计日志（必做）**：已覆盖 `PUT dealer-commission`/`generate`/`mark-settled` 业务审计（资金字段避免明文入审计：payoutReference 仅记录后 4 位）
  - [x] **幂等/防重复（必做）**：generate 资源幂等；mark-settled SETTLED 重复提交 → 200 幂等 no-op（不覆盖打款信息）
  - [x] **可观测日志字段**：审计 metadata 记录 cycle、created/existing、settlementId、requestId
  - [x] **前端错误态（按 code）**：403 跳转 /403；409 提示“状态已变化请刷新”；400/404 展示 message+code+requestId
  - [x] **最小测试**：generate 幂等；mark-settled 冻结冲突 409；重复提交幂等 no-op；审计入库断言
  - [x] **发布与回滚**：本批无 DB 变更；回滚为回退前后端代码变更（见 `release.md#3`）
- **DoD（验收步骤）**
  - cycle 非法 → 400 `INVALID_ARGUMENT`
  - 同 cycle 重复 generate → 不重复创建（created=0，existing>0）
  - mark-settled 对冻结单 → 409 `STATE_CONFLICT`
  - 审计日志能追溯 generate/mark-settled（若拍板为必做）
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminDealerSettlementsPage.vue`
  - 后端：
    - `backend/app/api/v1/admin_dealer_settlements.py::admin_put_dealer_commission`（分账规则更新审计）
    - `backend/app/api/v1/admin_dealer_settlements.py::admin_generate_dealer_settlements`（生成幂等 + 审计）
    - `backend/app/api/v1/admin_dealer_settlements.py::admin_mark_dealer_settlement_settled`（标记结算：幂等 no-op / 409 / 审计）
  - 测试：
    - `backend/tests/test_integration_admin_dealer_settlements_audit_and_idempotency.py`
    - 运行方式：`uv run pytest backend/tests/test_integration_admin_dealer_settlements_audit_and_idempotency.py -q`（需 RUN_INTEGRATION_TESTS=1 才会执行）

### [x] FLOW-ACCOUNT-SECURITY 修改密码（敏感）
- **范围（页面）**：`/account/security`（`frontend/admin/src/pages/AccountSecurityPage.vue`）
- **接口范围**：`POST /api/v1/*/auth/change-password`（ADMIN/PROVIDER/DEALER）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：必须登录；只能改自己的密码（不得指定他人 id）
  - [x] **错误码规范化**：旧密码错/新密码不合法 → 400 `INVALID_ARGUMENT`
  - [x] **审计日志（必做）**：ADMIN/PROVIDER/DEALER 均写入 `UPDATE` 审计（resourceType=`*_AUTH`），且不记录明文密码
  - [x] **幂等/防重复**：不适用（v1 不引入改密失败锁定；如需另起任务拍板）
  - [x] **可观测日志字段**：requestId 可追溯（见 `TASK-P0-009`）
  - [x] **最小测试**：ADMIN 策略校验；PROVIDER/DEALER ≥8；错误码与审计入库
  - [x] **发布与回滚**：无 DB 变更；回滚为回退前后端代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - 未登录调用 change-password → 401
  - 旧密码错误 → 400 `INVALID_ARGUMENT`
  - ADMIN：新密码需满足 `security.md#1.4.2`（≥10 + 4选2复杂度 + 黑名单）
  - PROVIDER/DEALER：v1 最小口径为新密码长度 ≥8（与现状后端一致）
  - 修改成功后旧密码不可再用（再次登录失败）
- **实现证据占位**
  - 前端：
    - `frontend/admin/src/pages/AccountSecurityPage.vue::validate/submit`（按角色区分最小密码长度；统一错误处理）
  - 后端：
    - `backend/app/api/v1/admin_auth.py::admin_change_password`（策略校验 + 审计）
    - `backend/app/api/v1/provider_auth.py::provider_change_password`（≥8 + 审计）
    - `backend/app/api/v1/dealer_auth.py::dealer_change_password`（≥8 + 审计）
  - 规格：
    - `specs-prod/admin/api-contracts.md#2.6/#2A.3/#2B.2`
  - 测试：
    - `backend/tests/test_integration_flow_account_security_change_password.py`

### [x] FLOW-USERS 用户查询（隐私）
- **范围（页面）**：`/admin/users`（`frontend/admin/src/pages/admin/AdminUsersPage.vue`）
- **接口范围**：`GET /api/v1/admin/users`、`GET /api/v1/admin/users/{id}`
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN（依赖 `require_admin`）
  - [x] **错误码规范化**：identity 非法 400 `INVALID_ARGUMENT`；不存在 404 `NOT_FOUND`
  - [x] **审计日志**：v1 默认不审计“查询行为”（如需另起任务拍板）
  - [x] **幂等/防重复**：不适用（读接口）
  - [x] **可观测日志字段**：requestId + query 可排障（见 `TASK-P0-009`）
  - [x] **最小测试**：phoneMasked 不泄露明文；identity 非法 400；404 NOT_FOUND（已自动化）
  - [x] **发布与回滚**：无 DB 变更；回滚为回退前后端代码变更
- **DoD（验收步骤）**
  - 返回字段不包含 phone 明文，仅 `phoneMasked`
  - identity=非法值 → 400 `INVALID_ARGUMENT`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminUsersPage.vue::load/openDetail`（错误处理统一使用 `handleApiError`）
  - 后端：`backend/app/api/v1/admin_users.py::{admin_list_users, admin_get_user}`（phoneMasked + 400/404）
  - 规格：`specs-prod/admin/api-contracts.md#3.1/#3.2`
  - 测试：`backend/tests/test_integration_admin_users.py`（含 identity 非法 400、404 NOT_FOUND、phone 不泄露）

### [x] FLOW-ORDERS 订单监管（订单核心）（Batch2 完成）
- **范围（页面）**：`/admin/orders`（`frontend/admin/src/pages/admin/AdminOrdersPage.vue`）
- **接口范围（至少）**
  - `GET /api/v1/admin/orders`
  - `POST /api/v1/admin/orders/{id}/ship`（物流发货）
  - `POST /api/v1/admin/orders/{id}/deliver`（如前端接入；现状后端存在）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN（`backend/app/api/v1/orders.py` admin 端点改为 `Depends(require_admin)`，可区分 401/403）
  - [x] **错误码规范化**：ship/deliver 状态机冲突/非法迁移分别返回 409 `STATE_CONFLICT` / `INVALID_STATE_TRANSITION`（对齐 `api-contracts.md#9B`）
  - [x] **审计日志（敏感操作必做）**：ship/deliver 写入业务审计（resourceType=ORDER，包含 before/after + requestId；trackingNo 仅记录后 4 位）
  - [x] **幂等/防重复**：按你拍板方案 A：
    - ship：已 SHIPPED 且运单一致 → 200 no-op；不一致 → 409 `INVALID_STATE_TRANSITION`
    - deliver：已 DELIVERED → 200 no-op；已 RECEIVED → 409 `INVALID_STATE_TRANSITION`
  - [x] **可观测日志字段**：审计 metadata 记录 orderId/requestId/before/after
  - [x] **前端错误态（按 code）**：`frontend/admin/src/pages/admin/AdminOrdersPage.vue` 已对齐 401/403/409/400/404
  - [x] **最小测试**：新增集成测试覆盖 ship/deliver 的成功/幂等 no-op/非法迁移 409/审计入库
  - [x] **发布与回滚**：本批无 DB 变更；回滚为回退前后端代码变更（见 `release.md#3`）
- **DoD（验收步骤）**（基于 `api-contracts.md#9B` 草案；Batch2 编码前需你拍板 9B.2/9B.3 的幂等点）
  - ADMIN 登录后调用 `GET /api/v1/admin/orders`：分页返回，字段包含 `buyerPhoneMasked`（不泄露 phone 明文）
  - `POST /api/v1/admin/orders/{id}/ship`：
    - 非物流订单 → 400 `INVALID_ARGUMENT`
    - 未支付订单 → 409 `STATE_CONFLICT`
    - 首次发货成功 → 200，`fulfillmentStatus=SHIPPED`
    - 重复提交到同一目标状态（已 SHIPPED）→ 200 幂等 no-op（或按你拍板策略）
  - `POST /api/v1/admin/orders/{id}/deliver`：
    - 未发货 → 409 `STATE_CONFLICT`
    - 首次妥投成功 → 200，`fulfillmentStatus=DELIVERED`
    - 重复提交到同一目标状态（已 DELIVERED）→ 200 幂等 no-op
  - 审计日志：ship/deliver 均可在 `/api/v1/admin/audit-logs` 查询到（resourceType=ORDER + resourceId=orderId），且包含 requestId 与 before/after 状态
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminOrdersPage.vue::{submitShip, load}`（按 code 错误态）
  - 后端：
    - `backend/app/api/v1/orders.py::admin_list_orders`
    - `backend/app/api/v1/orders.py::admin_ship_order`
    - `backend/app/api/v1/orders.py::admin_mark_delivered`
  - 测试：
    - `backend/tests/test_integration_admin_orders_ship_deliver_audit_and_idempotency.py`
    - 运行方式：`uv run pytest backend/tests/test_integration_admin_orders_ship_deliver_audit_and_idempotency.py -q`（需 RUN_INTEGRATION_TESTS=1）

### [x] FLOW-ACCOUNTS 账号管理（高风险：创建/重置/冻结/启用）
- **范围（页面）**：`/admin/accounts`（`frontend/admin/src/pages/admin/AdminAccountsPage.vue`）
- **接口范围**：`/api/v1/admin/provider-users`、`/api/v1/admin/provider-staff`、`/api/v1/admin/dealer-users` 及其 reset/suspend/activate
- **必须覆盖能力（勾选项）**
-  - [x] **权限硬校验（后端）**：仅 ADMIN；写操作额外要求 `require_admin_phone_bound`（403 `ADMIN_PHONE_REQUIRED`）
  - [x] **错误码规范化**：重复 username 409 `ALREADY_EXISTS`；不存在 404 `NOT_FOUND`
  - [x] **审计日志（必做）**：创建账号、重置密码、冻结/启用必须审计（不记录明文密码）
  - [x] **幂等/防重复**：
    - 创建：username 唯一 → 409
    - 冻结/启用：已在目标状态 → 200 幂等 no-op（不刷审计）
  - [x] **可观测日志字段**：审计 metadata 含 adminId/targetUserId/requestId/before/after
  - [x] **最小测试**：phone 绑定门禁 403；创建+冻结+幂等 no-op+启用；审计入库且 metadata 不含 `password`
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - 未绑定手机号的 ADMIN 调用任一写端点（create/reset/suspend/activate）→ 403 `ADMIN_PHONE_REQUIRED`
  - 创建账号成功返回 `password`（仅显示一次；系统不提供查询明文密码接口）
  - 冻结/启用为状态幂等：重复点击到同一目标状态 → 200 no-op
  - 可在 `/api/v1/admin/audit-logs` 查询到对应审计记录（resourceType=PROVIDER_USER/PROVIDER_STAFF/DEALER_USER），且 metadata 不包含明文密码
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminAccountsPage.vue::{saveCreate, resetPassword, toggle*Status}`（统一错误处理 `handleApiError`）
  - 后端：`backend/app/api/v1/admin_accounts.py`（写端点接入 `require_admin_phone_bound` + 审计 + 状态幂等 no-op）
  - 规格：`specs-prod/admin/api-contracts.md#9E`
  - 测试：
    - `backend/tests/test_integration_flow_accounts_admin_accounts.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_accounts_admin_accounts.py -q`

### [x] FLOW-REVIEW-VENUES 场所审核（发布/驳回/下线，高风险）
- **范围（页面）**：`/admin/venues`（`frontend/admin/src/pages/admin/AdminVenuesPage.vue`）
- **接口范围**：`POST /api/v1/admin/venues/{id}/publish|reject|offline` + 列表/详情
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；写操作要求 `require_admin_phone_bound`（403 `ADMIN_PHONE_REQUIRED`）
  - [x] **错误码规范化**：不存在 404 `NOT_FOUND`；未登录 401 `UNAUTHENTICATED`
  - [x] **审计日志（必做）**：
    - publish/reject/offline：非 no-op 时写审计（含 before/after + requestId）
    - 详情查看（含联系方式）：写 `VIEW` 审计（metadata 不记录电话明文）
  - [x] **幂等/防重复（必做）**：同目标状态重复提交 → 200 no-op（不刷审计）
  - [x] **状态机冲突码**：非法迁移 → 409 `INVALID_STATE_TRANSITION`（DRAFT->OFFLINE、PUBLISHED->DRAFT）
  - [x] **可观测日志字段**：审计 metadata 含 requestId/before/after
  - [x] **最小测试**：publish/offline 重复提交 no-op 且审计只写一次
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - DRAFT 场所：
    - publish → 200，publishStatus=PUBLISHED；重复 publish → 200 no-op
  - PUBLISHED 场所：
    - offline → 200，publishStatus=OFFLINE；重复 offline → 200 no-op
  - 审计：publish/offline 仅首次写审计；可在 `/api/v1/admin/audit-logs` 中按 resourceType=VENUE/resourceId 查询到
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminVenuesPage.vue`（错误处理统一 `handleApiError`）
  - 后端：`backend/app/api/v1/admin_venues.py`（no-op + before/after 审计）
  - 规格：`specs-prod/admin/api-contracts.md#9F`
  - 测试：
    - `backend/tests/test_integration_flow_review_venues_publish_offline_idempotency_and_audit.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_review_venues_publish_offline_idempotency_and_audit.py -q`

### [x] FLOW-PUBLISH-WEBSITE 官网配置发布（中风险：线上影响）
- **范围（页面）**：`/admin/website/*` 多页
- **接口范围**：`PUT /api/v1/admin/website/*`（SEO/导航/维护模式/外链/页脚/推荐等）
- **必须覆盖能力（勾选项）**：同上（重点：版本号/version、审计、回滚）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：所有 PUT 配置发布接口使用 `require_admin_phone_bound`；未绑定手机号 → 403 `ADMIN_PHONE_REQUIRED`
  - [x] **错误码规范化**：参数校验失败 → 400 `INVALID_ARGUMENT`；未登录 401；无权限 403（含 phone bound）
  - [x] **审计日志（必做）**：配置发布写审计（resourceType=`WEBSITE_CONFIG`，resourceId=配置 key；no-op 不刷审计）
  - [x] **幂等/防重复（最小）**：除 `version` 外字段不变 → 200 no-op（version 不推进、不写审计）
  - [x] **前端错误态（按 code）**：配置页统一使用 `handleApiError`
  - [x] **最小测试**：403 phone bound 门禁 + 审计只写一次 + no-op 不重复写审计
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - ADMIN 登录进入任一 `/admin/website/*` 页面，GET 能加载配置
  - 未绑定手机号的 ADMIN 点“保存”：返回 403 `ADMIN_PHONE_REQUIRED`，前端引导去绑定
  - 绑定手机号的 ADMIN 点“保存”：返回 200，`version` 被推进；审计日志可按 resourceType=`WEBSITE_CONFIG` + key 查询到 1 条 UPDATE
  - 对同一配置重复保存相同内容：返回 200 no-op，`version` 不变，审计不重复
- **实现证据占位**
  - 前端：
    - `frontend/admin/src/pages/admin/AdminWebsiteSiteSeoPage.vue`
    - `frontend/admin/src/pages/admin/AdminWebsiteNavControlPage.vue`
    - `frontend/admin/src/pages/admin/AdminWebsiteMaintenanceModePage.vue`
    - `frontend/admin/src/pages/admin/AdminWebsiteExternalLinksPage.vue`
    - `frontend/admin/src/pages/admin/AdminWebsiteFooterConfigPage.vue`
    - `frontend/admin/src/pages/admin/AdminWebsiteHomeRecommendedVenuesPage.vue`
  - 后端：`backend/app/api/v1/admin_website_config.py`（PUT：phone bound + no-op + 审计）
  - 规格：`specs-prod/admin/api-contracts.md#6`
  - 测试：
    - `backend/tests/test_integration_flow_publish_website_config.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_publish_website_config.py -q`

### [x] FLOW-PUBLISH-CMS CMS 内容发布/下线（高风险：线上内容）
- **范围（页面）**：`/admin/cms`（`frontend/admin/src/pages/admin/AdminCmsPage.vue`）
- **接口范围**：`POST /api/v1/admin/cms/contents/{id}/publish|offline`（含 scope=WEB/MINI_PROGRAM）+ 内容 CRUD
- **必须覆盖能力（勾选项）**：同上（审计/幂等/测试/回滚，scope 边界）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：publish/offline 使用 `require_admin_phone_bound`（未绑定手机号 → 403 `ADMIN_PHONE_REQUIRED`）
  - [x] **错误码规范化**：非法状态迁移 → 409 `INVALID_STATE_TRANSITION`；NOT_FOUND/400/401/403 口径与平台一致
  - [x] **审计日志（必做）**：publish/offline 非 no-op 写审计（resourceType=`CMS_CONTENT`，含 scope + before/after + requestId）
  - [x] **幂等/防重复（必做）**：同目标状态重复提交 → 200 no-op（不刷审计）
  - [x] **前端错误态（按 code）**：`AdminCmsPage.vue` 统一 `handleApiError`
  - [x] **最小测试**：门禁 403、publish/offline no-op、非法迁移 409、审计只写一次
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - WEB：
    - DRAFT 内容 publish → 200；重复 publish → 200 no-op；审计 PUBLISH 仅 1 条
    - PUBLISHED 内容 offline → 200；重复 offline → 200 no-op；审计 OFFLINE 仅 1 条
    - DRAFT 内容 offline → 409 `INVALID_STATE_TRANSITION`
  - MINI_PROGRAM：同上（以 `mpStatus` 为准）
  - 未绑定手机号的 ADMIN 执行 publish/offline：403 `ADMIN_PHONE_REQUIRED`，前端引导绑定
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminCmsPage.vue`（统一 `handleApiError`）
  - 后端：`backend/app/api/v1/cms.py`（publish/offline：phone bound + 幂等 no-op + 409 + 审计）
  - 规格：`specs-prod/admin/api-contracts.md#9G`
  - 测试：
    - `backend/tests/test_integration_flow_publish_cms.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_publish_cms.py -q`

### [x] FLOW-PUBLISH-MINI-PROGRAM 小程序配置发布/下线（高风险：渠道配置）
- **范围（页面）**：`/admin/mini-program`（`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`）
- **接口范围**：`/api/v1/admin/mini-program/*`（entries/pages/collections 的 PUT + publish/offline）
- **必须覆盖能力（勾选项）**：同上（版本 bump、审计、并发、回滚）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：publish/offline 使用 `require_admin_phone_bound`；未绑定手机号 → 403 `ADMIN_PHONE_REQUIRED`
  - [x] **错误码规范化**：参数校验失败 400 `INVALID_ARGUMENT`；NOT_FOUND/401/403 口径一致
  - [x] **审计日志（必做）**：publish/offline 非 no-op 写审计（resourceType=`MINI_PROGRAM_CONFIG`，resourceId=ENTRIES/PAGES:{id}/COLLECTIONS:{id}）
  - [x] **幂等/防重复（必做）**：同目标状态重复提交 → 200 no-op（version 不推进、不刷审计）
  - [x] **版本推进**：仅在 publish/offline 真实变更时推进 version
  - [x] **前端错误态（按 code）**：`AdminMiniProgramConfigPage.vue` 使用 `handleApiError`
  - [x] **最小测试**：phone bound 门禁 + publish/offline 幂等 + 审计只写一次
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - 未绑定手机号的 ADMIN 调用 publish/offline：403 `ADMIN_PHONE_REQUIRED`，前端引导绑定
  - Entries：
    - publish：首次推进 version + 写 1 条 PUBLISH 审计；重复 publish：200 no-op（version 不变、审计不重复）
    - offline：首次推进 version + 写 1 条 OFFLINE 审计；重复 offline：200 no-op
  - Pages / Collections：publish/offline 同上（resourceId 按 `{id}` 区分）
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminMiniProgramConfigPage.vue`
  - 后端：`backend/app/api/v1/admin_mini_program_config.py`
  - 规格：`specs-prod/admin/api-contracts.md#9H`
  - 测试：
    - `backend/tests/test_integration_flow_publish_mini_program_config.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_publish_mini_program_config.py -q`

### [x] FLOW-REGIONS-CITIES 城市配置发布/下线/导入（高风险：全局基础数据）
- **范围（页面）**：`/admin/regions/cities`（`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`）
- **接口范围**：`PUT /api/v1/admin/regions/cities` + `POST publish|offline|import-cn`
- **必须覆盖能力（勾选项）**：同上（导入 replace=true 的破坏性与回滚必须写清）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：publish/offline/import 使用 `require_admin_phone_bound`（未绑定手机号 → 403 `ADMIN_PHONE_REQUIRED`）
  - [x] **错误码规范化**：参数校验失败 400 `INVALID_ARGUMENT`；gb2260 缺失等内部错误 500 `INTERNAL_ERROR`
  - [x] **审计日志（必做）**：publish/offline/import 非 no-op 写审计（resourceType=`REGION_CITIES`，resourceId=`REGION_CITIES`）
  - [x] **幂等/防重复（必做）**：publish/offline 同目标状态重复提交 → 200 no-op（version 不推进、不刷审计）
  - [x] **导入破坏性与回滚**：import-cn 默认 replace=true（覆盖草稿）；回滚口径写进契约（见 `api-contracts.md#9I.5`）
  - [x] **前端错误态（按 code）**：`AdminRegionCitiesPage.vue` 统一 `handleApiError`
  - [x] **最小测试**：phone bound 门禁 + publish/offline 幂等 + import no-op + 审计只写一次
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - 未绑定手机号的 ADMIN 调用 publish/offline/import：403 `ADMIN_PHONE_REQUIRED`，前端引导绑定
  - publish：首次推进 version + 写 1 条 PUBLISH 审计；重复 publish：200 no-op（version 不变、审计不重复）
  - offline：首次推进 version + 写 1 条 OFFLINE 审计；重复 offline：200 no-op
  - import-cn：首次写 1 条 UPDATE 审计；重复 import-cn（replace=true 且无变更）：200 no-op（审计不重复）
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminRegionCitiesPage.vue`
  - 后端：`backend/app/api/v1/admin_regions.py`
  - 规格：`specs-prod/admin/api-contracts.md#9I`
  - 测试：
    - `backend/tests/test_integration_flow_regions_cities.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_regions_cities.py -q`

### [x] FLOW-NOTIFICATIONS-SEND 通知发送（敏感：触达/成本）
- **范围（页面）**：`/admin/notifications/send`
- **接口范围**：`POST /api/v1/admin/notifications/send` + receivers 列表
- **必须覆盖能力（勾选项）**：同上（审计必做、限流/防重复策略需拍板）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：接入 `require_admin_phone_bound`；未绑定手机号 → 403 `ADMIN_PHONE_REQUIRED`
  - [x] **幂等/防重复（必做）**：强制 `Idempotency-Key`；重复提交同 key → 200 幂等复放（不重复 fan-out）
  - [x] **限流（必做）**：每 Admin 20 次 / 10 分钟，超出 → 429 `RATE_LIMITED`
  - [x] **容量上限（必做）**：targetsCount 单次最多 5000，超出 → 400 `INVALID_ARGUMENT`
  - [x] **审计日志（必做）**：发送写审计（resourceType=`NOTIFICATION_SEND`），metadata 不记录正文/不记录全量收件人明细
  - [x] **前端错误态（按 code）**：前端统一 `handleApiError`（含 403 phone required 引导绑定）
  - [x] **最小测试**：403/400/429/幂等复放覆盖
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - 未绑定手机号：调用发送 → 403 `ADMIN_PHONE_REQUIRED`
  - 缺少 `Idempotency-Key`：400 `INVALID_ARGUMENT`
  - 同 key 重复提交：200 幂等复放；通知与审计不重复
  - 连续发送超过阈值：429 `RATE_LIMITED`
  - TARGETED targetsCount>5000：400 `INVALID_ARGUMENT`
- **实现证据**
  - 前端：`frontend/admin/src/pages/admin/AdminNotificationsSendPage.vue`
  - 后端：`backend/app/api/v1/admin_notifications.py`
  - 规格：`specs-prod/admin/api-contracts.md#9J`
  - 测试：
    - `backend/tests/test_integration_flow_notifications_send.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_notifications_send.py -q`

### [x] FLOW-DEALER-LINKS 经销商链接管理（高频：生成/停用链接）（Batch3 完成）
- **范围（页面）**：`/dealer/links`（`frontend/admin/src/pages/dealer/DealerLinksPage.vue`）
- **接口范围**：`GET/POST /api/v1/dealer-links`、`POST /api/v1/dealer-links/{id}/disable`
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：DEALER/ADMIN 二选一；未登录 401；DEALER 数据范围强制限定 dealerId（现状实现）
  - [x] **错误码规范化**：Idempotency-Key 缺失 400 `INVALID_ARGUMENT`；dateFrom/dateTo 400；NOT_FOUND/403 口径与实现对齐（见 `api-contracts.md#9C`）
  - [x] **审计日志（必做）**：create/disable 写入业务审计（resourceType=DEALER_LINK，含 requestId + before/after；no-op 不刷）
  - [x] **幂等/防重复（必做）**：**已强制** `Idempotency-Key`；重复请求 200 幂等 no-op；disable 幂等 no-op
  - [x] **可观测日志字段**：审计 metadata 记录 dealerId/dealerLinkId/sellableCardId/requestId
  - [x] **前端错误态（按 code）**：`frontend/admin/src/pages/dealer/DealerLinksPage.vue` 已对齐 401/403/409/400/404
  - [x] **最小测试**：新增集成测试覆盖 create 幂等、缺 header 400、disable 幂等、审计入库断言
  - [x] **发布与回滚**：本批无 DB 变更；回滚为回退前后端代码变更（见 `release.md#3`）
- **DoD（验收步骤）**（以 `api-contracts.md#9C` 为准；Batch3 编码前需拍板 #10(8)）
  - DEALER 登录访问列表：仅返回本 dealer 的链接（不得通过 query 绕过）
  - `POST /dealer-links`：
    - `validUntil` 缺失/非法 → 400 `INVALID_ARGUMENT`
    - 指定不可用 sellableCardId → 400/403（按契约）
    - 重复提交（同 Idempotency-Key）→ 200 幂等 no-op（如你拍板强制 Idempotency-Key）
  - `POST /dealer-links/{id}/disable`：
    - 越权停用他人链接 → 403
    - 停用已 DISABLED/EXPIRED → 200 幂等 no-op
  - 审计日志：create/disable 可在 `/api/v1/admin/audit-logs` 查询到（resourceType=DEALER_LINK + resourceId）
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/dealer/DealerLinksPage.vue`（按 code 错误态；create 携带 idempotencyKey）
  - 后端：`backend/app/api/v1/dealer_links.py`（强制 Idempotency-Key + 幂等复放 + 业务审计）
  - 测试：
    - `backend/tests/test_integration_dealer_links_idempotency_and_audit.py`
    - 运行方式：`uv run pytest backend/tests/test_integration_dealer_links_idempotency_and_audit.py -q`（需 RUN_INTEGRATION_TESTS=1）

### [x] FLOW-PROVIDER-REDEEM 场所核销（高风险：扣减次数）
- **范围（页面）**：`/provider/redeem`（`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`）
- **接口范围**：`POST /api/v1/entitlements/{id}/redeem`（要求 `Idempotency-Key`）
- **必须覆盖能力（勾选项）**：同上（幂等必做、归属校验必做、审计必做）
- **必须覆盖能力（勾选项）**
  - [x] **幂等/防重复（必做）**：强制 `Idempotency-Key`；同 key 重放 200 幂等复放（不重复扣减/不重复写核销记录）
  - [x] **归属校验（必做）**：PROVIDER/PROVIDER_STAFF 需满足 `Venue.provider_id==providerId`；否则 403 `FORBIDDEN`
  - [x] **审计日志（必做）**：核销成功写 `AuditLog`（action=`UPDATE`，resourceType=`ENTITLEMENT_REDEEM`，resourceId=`{entitlementId}`；幂等复放不重复写）
  - [x] **错误码**：v1 先保持现状错误码（不收敛，避免破坏兼容；见 `api-contracts.md#9K`）
  - [x] **响应字段**：成功响应包含 `remainingCount` + `entitlementStatus`
  - [x] **最小测试**：核销成功写审计 + 幂等复放不重复写审计 + 响应字段断言
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码变更（见 `release.md`）
- **DoD（验收步骤）**
  - 使用相同 `Idempotency-Key` 重复调用：返回相同 `redemptionRecordId`，且 `AuditLog(resourceType=ENTITLEMENT_REDEEM, resourceId={entitlementId})` 仅 1 条
  - 成功响应包含 `remainingCount` 与 `entitlementStatus`
- **实现证据**
  - 前端：`frontend/admin/src/pages/provider/ProviderRedeemPage.vue`
  - 后端：`backend/app/api/v1/entitlements.py::redeem_entitlement`
  - 规格：`specs-prod/admin/api-contracts.md#9K`
  - 测试：
    - `backend/tests/test_integration_flow_provider_redeem_entitlement.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_provider_redeem_entitlement.py -q`

### [x] FLOW-ADMIN-DASHBOARD 仪表盘（高频：运营入口）
- **范围（页面）**：`/admin/dashboard`（`frontend/admin/src/pages/admin/AdminDashboardPage.vue`）
- **接口范围**：`GET /api/v1/admin/dashboard/summary`（`backend/app/api/v1/admin_dashboard.py`）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；未登录 401；错误角色 403
  - [x] **错误码规范化**：`range` 非法 → 400 `INVALID_ARGUMENT`（不走 FastAPI 默认 422）
  - [x] **审计日志**：默认不审计读（v1）
  - [x] **幂等/防重复**：不适用（读）
  - [x] **可观测日志字段**：requestId + range + 返回耗时（由 request logger 统一提供；range 作为 query 可在 access log 侧定位）
  - [x] **最小测试**：成功/未登录/错误角色/非法 range=400
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码提交（见 `release.md#3`）
- **DoD（验收步骤）**
  - ADMIN 登录访问页面与接口 → 200
  - DEALER/PROVIDER token 调用接口 → 403（或 401，但必须拒绝）
- **规格草案入口（已对齐）**：`specs-prod/admin/api-contracts.md#9L`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminDashboardPage.vue::load`
  - 后端：`backend/app/api/v1/admin_dashboard.py`（对应 handler）
  - 测试：
    - `backend/tests/test_integration_flow_admin_dashboard_summary.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_dashboard_summary.py -q`

### [x] FLOW-ADMIN-ENTERPRISE 企业与绑定审核（高风险：企业身份）
- **范围（页面）**
  - `/admin/enterprise-bindings`（`frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue`）
  - `/admin/enterprises`（`frontend/admin/src/pages/admin/AdminEnterprisesPage.vue`）
- **接口范围（至少）**
  - `GET /api/v1/admin/enterprise-bindings`
  - `PUT /api/v1/admin/enterprise-bindings/{id}/approve`
  - `PUT /api/v1/admin/enterprise-bindings/{id}/reject`
  - `GET /api/v1/admin/enterprises`
  - `GET /api/v1/admin/enterprises/{id}`
  - `PUT /api/v1/admin/enterprises/{id}`
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN（写操作额外 phone bound 门禁）
  - [x] **错误码规范化**：不存在/状态冲突/参数错（非法迁移 409 `INVALID_STATE_TRANSITION`）
  - [x] **审计日志（必做）**：approve/reject/更新企业信息必审计（no-op 不刷审计）
  - [x] **幂等/防重复**：按统一口径（同目标状态重复提交=200 no-op；非法流转=409）
  - [x] **可观测日志字段**：requestId + bindingId/enterpriseId（audit metadata 含这些字段）
  - [x] **最小测试**：门禁/幂等 no-op/非法迁移 409/审计写入
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码提交（见 `release.md#3`）
- **规格入口**：`specs-prod/admin/api-contracts.md#9M`
- **DoD（验收步骤）**（以 `api-contracts.md#9M` 为准）
  - ADMIN 可分页查询绑定申请（手机号仅 masked）
  - approve/reject 满足幂等口径与错误码口径（200 no-op / 409 invalid transition）
  - 编辑企业名称写审计且仅允许改 name
- **实现证据占位**
  - 后端：`backend/app/api/v1/auth.py`（enterprise-bindings approve/reject 路由证据入口）
  - 后端：`backend/app/api/v1/admin_enterprises.py`
  - 前端：
    - `frontend/admin/src/pages/admin/AdminEnterpriseBindingsPage.vue::{load,approve,reject}`
    - `frontend/admin/src/pages/admin/AdminEnterprisesPage.vue::{load,openDetail,saveEdit}`
  - 测试：
    - `backend/tests/test_integration_flow_admin_enterprise_bindings_and_enterprises.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_enterprise_bindings_and_enterprises.py -q`

### [x] FLOW-ADMIN-AFTER-SALES 售后审核（高风险：退款/争议）
- **范围（页面）**：`/admin/after-sales`（`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue`）
- **接口范围**：`GET /api/v1/admin/after-sales`、`PUT /api/v1/admin/after-sales/{id}/decide`（`backend/app/api/v1/after_sales.py`）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN（写操作额外 phone bound 门禁）
  - [x] **错误码规范化**：非法迁移/冲突按 409 `INVALID_STATE_TRANSITION`；退款失败保持 `REFUND_NOT_ALLOWED`（409）
  - [x] **审计日志（必做）**：decide 写业务审计（resourceType=AFTER_SALES，action=UPDATE；no-op 不刷）
  - [x] **幂等/防重复**：同 decision 重复提交=200 no-op；冲突 decision=409 `INVALID_STATE_TRANSITION`
  - [x] **可观测日志字段**：requestId + afterSaleId/orderId/userId/decision（见审计 metadata）
  - [x] **最小测试**：门禁/幂等 no-op/冲突 409/审计写入/REFUND_NOT_ALLOWED 保持现状
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码提交（见 `release.md#3`）
- **规格入口**：`specs-prod/admin/api-contracts.md#9N`
- **DoD（验收步骤）**（以 `api-contracts.md#9N` 为准）
  - ADMIN 可查询列表（筛选+分页）且字段齐全
  - decide：未绑定手机号 403；已绑定正常裁决 200 并写审计
  - decide：重复同一 decision 200 no-op；冲突 decision 409 `INVALID_STATE_TRANSITION`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminAfterSalesPage.vue::{load,decide}`
  - 后端：`backend/app/api/v1/after_sales.py`（`PUT /admin/after-sales/{id}/decide`）
  - 测试：
    - `backend/tests/test_integration_flow_admin_after_sales_decide.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_after_sales_decide.py -q`

### [x] FLOW-ADMIN-ENTITLEMENTS 权益/核销/转赠（高风险：权益状态）
- **范围（页面）**：`/admin/entitlements`（`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue`）
- **接口范围（至少）**
  - `GET /api/v1/entitlements`（权益列表）
  - `GET /api/v1/admin/redemptions`（核销记录）
  - `GET /api/v1/admin/entitlement-transfers`（转赠记录）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：`/admin/*` 仅 ADMIN；`/entitlements` 仅允许 ADMIN/USER（DEALER/PROVIDER 等有效 token 必须 403）
  - [x] **错误码规范化**：未携带/无效 token → 401 `UNAUTHENTICATED`；角色不允许 → 403 `FORBIDDEN`
  - [x] **审计日志**：读默认不审计；若加入“导出/敏感明文访问”必须审计（本 flow 预留）
  - [x] **幂等/防重复**：不适用（读）
  - [x] **可观测日志字段**：requestId + filter 条件（查询侧）
  - [x] **最小测试**：/entitlements 的 401/403 + Admin list/detail 禁止 qrCode/voucherCode 护栏
  - [x] **发布与回滚**：无 DB 变更；回滚为回退代码提交（见 `release.md#3`）
- **规格入口**：`specs-prod/admin/api-contracts.md#9O`
- **DoD（验收步骤）**
  - ADMIN 访问三类列表均成功
  - 非 ADMIN token 调用任一 `/api/v1/admin/*` → 403/401（必须拒绝）
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminEntitlementsPage.vue::{loadEntitlements,loadRedemptions,loadTransfers}`
  - 后端：`backend/app/api/v1/entitlements.py`、`backend/app/api/v1/admin_redemptions.py`、`backend/app/api/v1/admin_entitlement_transfers.py`
  - 测试：
    - `backend/tests/test_integration_flow_admin_entitlements_readonly_and_pii.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_entitlements_readonly_and_pii.py -q`

### [x] FLOW-ADMIN-SERVICE-PACKAGES 服务包模板管理（高频：配置类）
- **范围（页面）**：`/admin/service-packages`（`frontend/admin/src/pages/admin/AdminServicePackagesPage.vue`）
- **接口范围**：`GET /api/v1/admin/service-packages`、`GET /api/v1/admin/service-packages/{id}`、`POST /api/v1/admin/service-packages`、`PUT /api/v1/admin/service-packages/{id}`（`backend/app/api/v1/admin_service_packages.py`）
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；POST/PUT 写操作启用 `require_admin_phone_bound`
  - [x] **错误码规范化**：401/403/400/404/409（字段校验收敛 400，避免 422 漂移）
  - [x] **审计日志（敏感操作必做）**：POST/PUT（非 no-op）必审计；幂等复放不重复写；no-op 不写
  - [x] **幂等/防重复**：POST 强制 `Idempotency-Key`（24h 重放复放首次结果，含失败结果）
  - [x] **可观测日志字段**：templateId/requestId/changedFields（审计 metadata）
  - [x] **最小测试**：phone bound 403；POST 缺 key 400；POST 幂等复放；PUT no-op 不写审计；PUT locked 冲突 409；审计入库断言
  - [x] **发布与回滚**：无 DB 迁移；回滚为回退代码提交（见 `release.md#3`）
- **规格入口（已拍板）**：`specs-prod/admin/api-contracts.md#9Q`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminServicePackagesPage.vue::{load,openEdit,save}`
  - 后端：`backend/app/api/v1/admin_service_packages.py::{admin_list_service_packages,admin_get_service_package_detail,admin_create_service_package,admin_update_service_package}`
  - 测试：
    - `backend/tests/test_integration_flow_admin_service_packages_crud_idempotency_and_audit.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_service_packages_crud_idempotency_and_audit.py -q`

### [x] FLOW-ADMIN-SERVICE-CATEGORIES 服务分类（启停用，敏感）
- **范围（页面）**：`/admin/service-categories`（`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue`）
- **接口范围**：`GET/POST /api/v1/admin/service-categories`、`PUT /api/v1/admin/service-categories/{id}`、`POST /api/v1/admin/service-categories/{id}/enable|disable`
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；POST/PUT/enable/disable 一律启用 `require_admin_phone_bound`
  - [x] **错误码规范化**：401/403/400/404/409（请求体校验收敛 400；code 冲突码收敛为 409 `STATE_CONFLICT`）
  - [x] **审计日志（敏感操作必做）**：POST/PUT/enable/disable（非 no-op）必审计；no-op 不写
  - [x] **状态幂等**：enable/disable 已在目标状态 → 200 no-op（不写审计）
  - [x] **可观测日志字段**：categoryId/requestId/changedFields（审计 metadata）
  - [x] **最小测试**：门禁 403；422→400；冲突码收敛；enable/disable no-op 不审计；审计入库断言
  - [x] **发布与回滚**：无 DB 迁移；回滚为回退代码提交（见 `release.md#3`）
- **规格入口（已拍板）**：`specs-prod/admin/api-contracts.md#9R`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminServiceCategoriesPage.vue::{load,save,enable,disable}`
  - 后端：`backend/app/api/v1/admin_service_categories.py`
  - 测试：
    - `backend/tests/test_integration_flow_admin_service_categories_enable_disable_audit.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_service_categories_enable_disable_audit.py -q`

### [x] FLOW-ADMIN-SELLABLE-CARDS 可售卡（启停用，敏感：影响下单入口）
- **范围（页面）**：`/admin/sellable-cards`（`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue`）
- **接口范围**：`GET/POST /api/v1/admin/sellable-cards`、`PUT /api/v1/admin/sellable-cards/{id}`、`POST /api/v1/admin/sellable-cards/{id}/enable|disable`
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；POST/PUT/enable/disable 一律启用 `require_admin_phone_bound`
  - [x] **错误码规范化**：401/403/400/404/409（请求体校验收敛 400，避免 422 漂移）
  - [x] **审计日志（敏感操作必做）**：POST/PUT/enable/disable（非 no-op）必审计；no-op 不写
  - [x] **状态幂等**：enable/disable 已在目标状态 → 200 no-op（不写审计）
  - [x] **可观测日志字段**：sellableCardId/requestId/changedFields（审计 metadata）
  - [x] **最小测试**：门禁 403；422→400；enable/disable no-op 不审计；模板引用校验；审计入库断言
  - [x] **发布与回滚**：无 DB 迁移；回滚为回退代码提交（见 `release.md#3`）
- **规格入口（已拍板）**：`specs-prod/admin/api-contracts.md#9S`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminSellableCardsPage.vue::{load,save,enable,disable}`
  - 后端：`backend/app/api/v1/admin_sellable_cards.py`
  - 测试：
    - `backend/tests/test_integration_flow_admin_sellable_cards_enable_disable_audit.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_sellable_cards_enable_disable_audit.py -q`

### [ ] FLOW-ADMIN-TAGS 标签/类目树（配置类，影响筛选）
- **范围（页面）**：`/admin/tags`（`frontend/admin/src/pages/admin/AdminTagsPage.vue`）
- **接口范围**：`GET/POST /api/v1/admin/taxonomy-nodes`、`PUT /api/v1/admin/taxonomy-nodes/{id}`（`backend/app/api/v1/taxonomy_nodes.py`）
- **必须覆盖能力（勾选项）**：权限/错误码/审计（创建/更新）/测试/回滚
- **DoD（验收步骤）**：TBD
- **实现证据占位**：`backend/app/api/v1/taxonomy_nodes.py`

### [x] FLOW-ADMIN-AI AI 配置与审计（敏感：配置影响）
- **范围（页面）**：`/admin/ai`（`frontend/admin/src/pages/admin/AdminAiConfigPage.vue`）
- **接口范围（至少）**
  - `GET /api/v1/admin/ai/config`
  - `PUT /api/v1/admin/ai/config`
  - `GET /api/v1/admin/ai/audit-logs`
- **必须覆盖能力（勾选项）**
  - [x] **权限硬校验（后端）**：仅 ADMIN；PUT 额外要求 phone bound
  - [x] **错误码规范化**：401/403/400（字段范围非法收敛 400，避免 422 漂移）
  - [x] **审计日志（敏感操作必做）**：PUT 配置变更必审计；幂等复放不重复写；no-op 不写审计
  - [x] **幂等（PUT 策略）**：强制 `Idempotency-Key`（你已拍板方案 A）
  - [x] **敏感信息**：`apiKey` 不得在响应/审计 metadata 明文出现（仅 `apiKeyMasked` / `apiKeyUpdated`）
  - [x] **最小测试**：门禁 403、缺 key 400、字段范围 400、no-op 不 bump、不审计、变更审计一次 + 幂等复放护栏
  - [x] **回滚**：无 DB 迁移；回滚为回退代码提交（见 `release.md#3`）
- **规格入口（已拍板）**：`specs-prod/admin/api-contracts.md#9P`
- **实现证据占位**
  - 前端：`frontend/admin/src/pages/admin/AdminAiConfigPage.vue::{load,save}`
  - 后端：`backend/app/api/v1/admin_ai.py::{admin_get_ai_config,admin_put_ai_config,admin_list_ai_audit_logs}`
  - 测试：
    - `backend/tests/test_integration_flow_admin_ai_config_and_audit.py`
    - 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_flow_admin_ai_config_and_audit.py -q`

### [ ] FLOW-ADMIN-PROVIDER-ONBOARDING 平台审核 Provider 开通（敏感：准入）
- **范围（页面）**：`/admin/provider-onboarding/health-card`（`frontend/admin/src/pages/admin/AdminProviderHealthCardOnboardingPage.vue`）
- **接口范围**：`GET /api/v1/admin/provider-onboarding/health-card`、`PUT /api/v1/admin/provider-onboarding/{providerId}/health-card/decide`
- **必须覆盖能力（勾选项）**：权限/错误码/审计（decide 必做）/状态幂等/测试/回滚
- **DoD（验收步骤）**：TBD
- **实现证据占位**：`backend/app/api/v1/admin_provider_onboarding.py`

### [x] FLOW-ADMIN-BOOKINGS 平台预约监管（敏感：强制取消）（Batch5 完成）
- **范围（页面）**：`/admin/bookings`（`frontend/admin/src/pages/admin/AdminBookingsPage.vue`）
- **接口范围（至少）**
  - 列表：**必须提供** `GET /api/v1/admin/bookings`（admin 只读监管接口；你已拍板）
  - 强制取消：`DELETE /api/v1/admin/bookings/{id}`（要求 `Idempotency-Key` + reason）
- **必须覆盖能力（勾选项）**：权限/错误码/审计（强制取消必做）/幂等必做/测试/回滚
- **DoD（验收步骤，你已拍板）**
  - ADMIN 登录调用 `GET /api/v1/admin/bookings`：分页返回，字段齐全（见 `api-contracts.md#9A-平台预约监管（Admin Bookings）`）
  - `status/serviceType/keyword/dateFrom/dateTo/venueId/providerId` 任一组合过滤可用
  - 非 ADMIN 调用返回 403；未登录返回 401；非法日期返回 400（包含 `error.code=INVALID_ARGUMENT`）
  - 默认排序符合口径：`bookingDate DESC, createdAt DESC`（bookingDate 新的在前）
- **实现证据**
  - 前端：
    - `frontend/admin/src/pages/admin/AdminBookingsPage.vue::load`（改用 `GET /api/v1/admin/bookings`）
    - `frontend/admin/src/pages/admin/AdminBookingsPage.vue::cancelBooking`（强制取消）
  - 后端：
    - `backend/app/api/v1/bookings.py::admin_list_bookings`（`GET /api/v1/admin/bookings`）
    - `backend/app/api/v1/bookings.py::admin_cancel_booking`（`DELETE /api/v1/admin/bookings/{id}`：强制 `Idempotency-Key`；已 CANCELLED=200 no-op；已 COMPLETED=409）
  - 测试：
    - `backend/tests/test_integration_admin_bookings_list.py`
    - `backend/tests/test_integration_admin_cancel_booking_idempotency_and_audit.py`
    - 运行方式：`uv run pytest backend/tests/test_integration_admin_bookings_list.py -q`（需 RUN_INTEGRATION_TESTS=1）

### [ ] FLOW-DEALER-CORE 经销商核心（全部页面覆盖）
- **范围（页面）**
  - `/dealer/dashboard`（`frontend/admin/src/pages/dealer/DealerDashboardPage.vue`）
  - `/dealer/orders`（`frontend/admin/src/pages/dealer/DealerOrdersPage.vue`）
  - `/dealer/settlements`（`frontend/admin/src/pages/dealer/DealerSettlementsPage.vue`）
  - `/dealer/notifications`（`frontend/admin/src/pages/dealer/DealerNotificationsPage.vue`）
  - `/dealer/links`（已由 `FLOW-DEALER-LINKS` 覆盖；本 flow 负责其余 4 页）
- **接口范围（至少）**
  - `GET /api/v1/dealer/orders`
  - `GET/PUT /api/v1/dealer/settlement-account`、`GET /api/v1/dealer/settlements`
  - `GET /api/v1/dealer/notifications`、`POST /api/v1/dealer/notifications/{id}/read`
- **必须覆盖能力（勾选项）**：权限/错误码/审计（结算账户变更、已读通知）/幂等（read、put）/测试/回滚
- **DoD（验收步骤）**：TBD
- **实现证据占位**：`backend/app/api/v1/dealer.py`、`backend/app/api/v1/dealer_notifications.py`、`backend/app/api/v1/dealer_links.py`

### [ ] FLOW-PROVIDER-CORE 服务提供方核心（全部页面覆盖，除核销已单列）
- **范围（页面）**
  - `/provider/workbench`（`frontend/admin/src/pages/provider/ProviderWorkbenchPage.vue`）
  - `/provider/venues`（`frontend/admin/src/pages/provider/ProviderVenuesPage.vue`）
  - `/provider/products`（`frontend/admin/src/pages/provider/ProviderProductsPage.vue`）
  - `/provider/services`（`frontend/admin/src/pages/provider/ProviderServicesPage.vue`）
  - `/provider/schedules`（`frontend/admin/src/pages/provider/ProviderSchedulesPage.vue`）
  - `/provider/bookings`（`frontend/admin/src/pages/provider/ProviderBookingsPage.vue`）
  - `/provider/redemptions`（`frontend/admin/src/pages/provider/ProviderRedemptionsPage.vue`）
  - `/provider/notifications`（`frontend/admin/src/pages/provider/ProviderNotificationsPage.vue`）
  - `/provider/redeem`（已由 `FLOW-PROVIDER-REDEEM` 覆盖；本 flow 负责其余 8 页）
- **接口范围（至少）**
  - Onboarding：`GET /api/v1/provider/onboarding`、`POST /api/v1/provider/onboarding/infra/open`、`POST /api/v1/provider/onboarding/health-card/submit`
  - 场所：`GET/PUT /api/v1/provider/venues*`、`POST /api/v1/provider/venues/{id}/submit-showcase`
  - 商品：`GET/POST/PUT /api/v1/provider/products*`
  - 服务：`POST/PUT /api/v1/provider/venues/{venueId}/services*`
  - 排期：`PUT /api/v1/provider/venues/{venueId}/schedules/batch`
  - 预约：`GET /api/v1/provider/bookings`、`POST /api/v1/provider/bookings/{id}/cancel`、`PUT /api/v1/bookings/{id}/confirm`（幂等键）
  - 通知：`GET /api/v1/provider/notifications`、`POST /api/v1/provider/notifications/{id}/read`
  - 核销记录：`GET /api/v1/provider/redemptions`
- **必须覆盖能力（勾选项）**
  - [ ] **权限硬校验（后端）**：providerId 数据范围裁决（venue/product/order 等不得越权）
  - [ ] **错误码规范化**：未开通健康卡/状态冲突/不存在/参数错
  - [ ] **审计日志（敏感操作必做，你已拍板全列）**：
    - submit-showcase
    - 产品状态变更（上架/下架/提交审核等）
    - 排期批量（schedules batch）
    - 预约 confirm & cancel
  - [ ] **幂等/防重复（如适用）**：confirm/取消/批量更新需定义幂等策略（含 Idempotency-Key）
  - [ ] **可观测日志字段**：providerId/venueId/productId/requestId
  - [ ] **最小测试**：成功/失败/越权/边界（pageSize、批量长度、重复请求）
  - [ ] **发布与回滚**：如引入索引/约束/状态机变更，必须写清 DB 迁移与回滚
- **DoD（验收步骤）**：TBD（按每子模块补齐）
- **实现证据占位**
  - 后端：`backend/app/api/v1/provider.py`、`backend/app/api/v1/provider_onboarding.py`、`backend/app/api/v1/provider_notifications.py`、`backend/app/api/v1/bookings.py`
  - 前端：对应 provider 页面调用点（TBD：补函数名/调用点）

## 3. DoD 证据记录区（模板）
> 当任务完成时，把证据补充到对应任务下方，并在此处追加索引。

- **证据索引占位**：TBD


