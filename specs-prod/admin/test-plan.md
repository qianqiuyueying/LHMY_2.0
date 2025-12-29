# 最小测试计划（Test Plan）

> 目标：以尽可能小的集合覆盖“可生产”高风险能力（权限/审计/导出/资金结算/配置发布）。

## 1. 测试分层
- **后端**：pytest（`backend/tests/`）
- **前端**：TBD（当前仓库内测试体系需确认：unit/e2e/无）
- **端到端**：优先覆盖高风险操作的关键路径

## 2. 最小后端测试集合（Baseline）

### 2.1 启动门禁（生产配置）
- 覆盖：生产环境默认密钥/空配置阻断启动
- 证据入口：`backend/app/main.py:_validate_production_settings`
- 现有测试：TBD（如已存在则补链接；否则列为 tasks）

### 2.2 Admin 认证与会话
- 登录成功/失败
- 2FA challenge/verify（成功/过期/验证码错误）
- refresh 使旧 token 失效（blacklist 生效）
- logout 使 token 失效

### 2.3 RBAC 强制（后端）
- 未携带 Authorization → 401
- 携带非 ADMIN token 调 admin API → 403

### 2.4 资金/结算（高风险）
- 结算生成幂等（同 cycle 重复 generate 不产生重复记录）
- 冻结状态禁止 mark-settled（409）

### 2.5 隐私（脱敏）
- 用户列表/详情不返回 phone 明文，仅 phoneMasked

## 3. 最小前端测试集合（占位）
- 路由门禁：未登录访问 admin 路由跳转 /login
- 角色不匹配跳转 /403
- 登录/2FA 页面主题固定浅色（防止可读性回归）

## 4. 运行方式（How to Run）

### 4.1 后端
- 在 `backend/` 下运行（命令待项目统一脚本确认）
  - `pytest -q`

### 4.2 前端
- TBD（待补充：是否有 `pnpm test` / `vitest` / `cypress` 等）


