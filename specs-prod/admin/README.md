# Admin 生产规格（唯一真相）

## 1. 范围（Scope）
- **目标系统**：管理系统（`frontend/admin`）+ 其依赖的后端 Admin API（`backend/app/api/v1/admin_*.py` 等）
- **目标**：将当前“原型态 Admin”升级为“可生产”——重点覆盖权限、审计、导出、资金/结算、发布/回滚、可观测性与最小测试集合
- **非目标（本规格不承诺）**：
  - 未在 `specs-prod/admin/` 明确描述的功能、字段、接口与流程
  - 像素级 UI 还原（但必须保持信息结构、顺序与用户流）

## 2. 真相来源（Source of Truth）
- **唯一真相来源**：`specs-prod/admin/`（本目录）
- 旧规格目录 `specs/health-services-platform/`：**仅可参考，不具约束力**
- **变更规则**：任何代码/接口/字段/流程变更，必须先更新本目录对应条目并由“规格拍板人（用户）”确认

## 3. 最小 DoD 标准（Definition of Done - Baseline）
对每个迭代任务（见 `tasks.md`）最小 DoD：
- **规格**：任务引用了本目录下明确条目（标题锚点/章节号），且无冲突
- **实现**：代码变更可追溯（文件路径 + 关键函数/接口 + commit/PR 链接）
- **测试**：至少覆盖 `test-plan.md` 规定的最小测试集合（或任务自带更严格要求）
- **可观测性**：关键路径有结构化日志字段（见 `observability.md`），错误可定位
- **安全**：符合 `security.md` 的会话/越权/审计/敏感信息要求
- **回滚**：提供可执行回滚步骤（见 `release.md`）与风险说明

## 4. 如何验收（Acceptance）
- **静态验收**（无需跑环境）：
  - `facts.md` 中列出的事实都有代码证据（路径/接口/函数，必要时行号）
  - `api-contracts.md` 中接口契约可与代码对齐（路由、字段、错误码、幂等）
  - `requirements.md` 权限矩阵覆盖所有 Admin 线路（见 `flow-catalog.md`）
- **动态验收**（跑环境）：
  - 按 `test-plan.md` 跑最小测试集合通过
  - 按 `release.md` 的“灰度/回滚”流程演练成功


