# 需求与约束（v1）

## R1. 范围（Scope）

本次仅优化“重复维护成本”：

- Web 三端：`frontend/admin`、`frontend/website`、`frontend/h5`
- 小程序端：`frontend/mini-program`

优先级（从高到低）：

1. **请求层/协议层**：统一响应体 envelope 解析、query 拼接、错误模型、Idempotency-Key/requestId 生成与注入策略（保持端侧行为不变）。
2. **纯工具层**：localStorage 安全封装、常量/类型重复收敛。
3. 业务纯逻辑（无 UI 依赖）——需要在任务中单独列出、逐个确认可共享边界。

## R2. 不变性约束（Must Not Change）

- **API 语义不变**：请求路径、method、header、body、query 以及错误处理语义保持一致。
- **用户体验不变**：
  - admin：401 清会话并跳转到登录页，且保留 `next` 参数语义不变。
  - h5：token 存储 key 与现有页面交互不变；错误提示文案映射不变。
  - website：只读 GET 行为不变；`VITE_API_BASE` 默认与现有行为一致。
  - mini-program：401/未登录跳转、toast 静默规则、`wx.request`/`wx.uploadFile` 行为不变。
- **发布与运行方式不变**：不引入新的“必须的”部署组件；允许最小构建配置调整（如 Vite 允许导入共享目录、TS paths）。

## R3. 交付验收（DoD）

每个任务至少满足：

- **可回滚**：出现问题可在 10 分钟内回滚到改动前（通过 git revert 或保留旧入口 wrapper）。
- **构建通过**：
  - `frontend/admin`: `npm run typecheck` + `npm run build`
  - `frontend/website`: `npm run typecheck` + `npm run build`
  - `frontend/h5`: `npm run typecheck` + `npm run build`
- **Smoke 通过（每端最小 1 条）**
  - admin：登录/任一列表页加载（或本地 mock 也可）
  - website：主页/列表页加载
  - h5：落地页/购买页加载
  - mini-program：启动 + 触发一次 API 调用（开发者工具）

## R4. 文档同步要求

实施过程中必须同步更新 `tasks.md`：

- 任务勾选状态
- 实现证据（文件与关键调用点）
- 若出现“不得不改变行为”的情况：必须停止并在任务里记录原因与替代方案，等待确认后再继续


