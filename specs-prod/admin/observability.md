# 可观测性（Observability）

## 1. 结构化日志（Structured Logging）

### 1.1 最小字段集合（Backend）
- **requestId**：请求唯一标识（必须贯穿日志/审计/错误响应）
- **path**：请求路径
- **method**：HTTP 方法
- **statusCode**：响应码
- **latencyMs**：耗时
- **actorType/actorId**：若可解析（来自 `request.state.actor`）
- **ip/userAgent**：用于排障与审计

### 1.2 证据与注入点
- requestId 注入：`backend/app/main.py` 使用 `RequestIdMiddleware`
- 多数接口通过 `ok(..., request_id=request.state.request_id)` 回传 requestId（全局大量使用）
 - 请求日志注入：`backend/app/middleware/request_logger.py`（记录 requestId/path/method/status/cost + actor/ip/ua）

## 2. 最小指标（Metrics - Prometheus）

### 2.1 暴露方式
- `/metrics`（不进入 OpenAPI）
- 证据：`backend/app/main.py` 使用 `prometheus_fastapi_instrumentator`

### 2.2 关键指标（Baseline）
- **HTTP**：请求总量、P95/P99 延迟、错误率（4xx/5xx）
- **Auth**：登录失败率、2FA 失败率（TBD：需要事件统计落点）
- **高风险操作**：导出次数、结算标记次数、发布次数（TBD）

### 2.3 审计覆盖率与高风险操作计数（v1 草案）
> 说明：v1 先以“审计表聚合查询”作为统计口径（无需立即引入新指标上报）。若后续需要面向 Prometheus，则再拍板新增 metrics。

#### 2.3.1 覆盖率定义（Coverage）
- **分母**：`security.md#3.1.1` 中定义的“高风险事件覆盖清单”
- **分子**：在选定时间窗内（例如近 7 天），每个事件类型至少出现 1 条**业务审计记录**（非中间件兜底审计）即记为“覆盖”
- **输出**：
  - 覆盖率 = coveredTypes / totalTypes
  - 同时输出未覆盖的类型列表（用于阻断上线/回归）

#### 2.3.2 最小查询方式（SQL/思路）
> 注意：这里只给“排障/验收查询口径”，不要求立即上报到 metrics。

- **按资源类型聚合（近 N 天）**：
  - where `created_at >= now() - interval N day`
  - group by `resource_type`
  - count(*)
- **高风险事件覆盖检查（近 N 天）**：
  - 对 `security.md#3.1.1` 的每个 resourceType，检查 count 是否 > 0

#### 2.3.3 v1 高风险事件清单（与实现对齐）
- `EXPORT_DEALER_ORDERS`
- `DEALER_SETTLEMENT_BATCH`
- `DEALER_SETTLEMENT`
- `ORDER`
- `DEALER_LINK`
- `BOOKING`

## 3. 排障方式（Troubleshooting）
- **以 requestId 为主线**：从前端错误提示/接口响应拿到 requestId → 查后端结构化日志 → 关联审计日志（如有）
- **高风险操作排障**：必须能定位到 actor、资源、动作与结果（见 `security.md#3-审计`）

## 3.1 DoD（TASK-P0-009 最小验收）
- requestId：响应头 `X-Request-Id` 与 envelope `requestId` 一致（成功与失败都满足）
- 请求日志：至少包含 `request_id/path/method/status/cost_ms/actor_type/actor_id/ip/ua`（v1 不要求 JSON，但必须可 grep）
- /metrics：可访问并能抓取基础 HTTP 指标（由 `prometheus_fastapi_instrumentator` 提供）

## 3.2 测试证据
- `backend/tests/test_integration_request_id_consistency_task_p0_009.py`
- 运行方式：`RUN_INTEGRATION_TESTS=1 uv run pytest backend/tests/test_integration_request_id_consistency_task_p0_009.py -q`

## 4. 待补齐
- **前端日志**：是否上报（Sentry/埋点）与最小字段（TBD）
- **业务指标落点**：是否已有事件表/日志埋点（TBD）
 - **覆盖率展示形态**：是否需要 admin 页面展示（建议在 `/admin/audit-logs` 页增加“覆盖率卡片”），或仅用于运维/预发验收（TBD）


