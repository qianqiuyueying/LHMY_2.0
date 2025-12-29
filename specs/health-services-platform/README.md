## 规格索引（LHMY_2.0：Admin / Website / H5 / 小程序 / 后端）

### 范围（本仓库多端统一纳入规格与事实清单）

- **纳入（全部纳入事实清单）**：`frontend/admin`、`frontend/website`、`frontend/h5`、`frontend/mini-program`、`backend`

### 目标（本轮优先级）

- **P0：可部署、可上线、上线后可用**
- **P0：兼容性与可维护性**（方便未来持续升级，不引入破坏性变更）

### 规范文档入口

- **总纲 / 兼容性原则 / 上线 DoD**：`specs/health-services-platform/design.md`
- **实施任务清单（可勾选）**：`specs/health-services-platform/tasks.md`
- **完成事实清单（可勾选，含“证据入口”）**
  - `specs/health-services-platform/facts/admin.md`
  - `specs/health-services-platform/facts/website.md`
  - `specs/health-services-platform/facts/h5.md`
  - `specs/health-services-platform/facts/mini-program.md`
  - `specs/health-services-platform/facts/backend.md`
- **原型/信息结构（占位）**：`specs/health-services-platform/prototypes/README.md`
- **后端升级需求与变更清单（v1，最小）**：`specs/health-services-platform/后端升级需求与变更清单（v1）.md`
- **发布/部署手册（单机+域名+HTTPS+Nginx，vNext）**：`ops/release/README.md`

### 使用规则（Spec-Driven）

- **先改规格，再改代码**：任何升级需求必须先写入 `tasks.md`（验收口径/影响面/兼容性约束），再进入实现。
- **实现后反写**：改动完成后必须把对应事实更新到 `facts/*.md`（文件路径/接口路径/关键函数）。
- **不做“凭感觉”优化**：事实清单未覆盖的点，默认视为风险点，升级前必须补齐事实项或明确“未覆盖/不保证”。 

### 最小可执行路径（给回归/验收）

- **H5 最小购买链路**：见 `specs/health-services-platform/facts/h5.md` 的 **“最小可执行使用路径”** 小节（从 dealer link → 下单 → 支付 → 结果页）


