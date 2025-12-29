# 发布冒烟清单（Release Smoke Checklist）

> 目标：用最小步骤验证“可生产高风险能力”不回归（权限/审计/导出/资金/配置发布）。
> 规则：每次发布必须执行，并将结果记录到 `specs-prod/admin/evidence/release/YYYY-MM-DD.md`。

## 0. 前置
- 已完成 `release.md#2.1` 的部署
- 已知 Admin 账号可登录（生产环境用初始化脚本创建首个管理员：`scripts/admin_init_once.py`）

## 1. 后端连通性
- [ ] `GET /api/v1/health/ready` 返回 success=true
- [ ] `GET /metrics` 可访问（Prometheus 可抓取）

## 2. 认证与门禁
- [ ] 未登录访问 `GET /api/v1/admin/users` → 401 `UNAUTHENTICATED`
- [ ] ADMIN 登录成功（必要时走 2FA）
- [ ] 未绑定手机号的 ADMIN：
  - [ ] 高风险操作（例如结算 generate）→ 403 `ADMIN_PHONE_REQUIRED`（引导绑定）
  - [ ] 在 `/account/security` 完成绑定后，高风险操作可继续

## 3. 高风险流程抽样（v1 最小）
> 只要求验证“至少 1 条路径闭环”，不要求全量覆盖（全量覆盖由各 FLOW 任务卡负责）。

- [ ] **导出（DEALER 订单导出）**
  - dateFrom/dateTo 必填，不填返回 400 `INVALID_ARGUMENT`
  - 正确日期范围：返回 CSV 下载；审计表存在 `resourceType=EXPORT_DEALER_ORDERS`
- [ ] **订单监管（ADMIN 发货/妥投）**
  - 发货/妥投可执行（或在无数据时记录“环境无样本”）
  - 审计表存在 `resourceType=ORDER`
- [ ] **场所审核（发布/下线）**
  - 可执行（或无样本则记录）
  - 审计表存在 `resourceType=VENUE`

## 4. 审计可追溯
- [ ] 任一高风险操作返回中包含 requestId
- [ ] 在 `GET /api/v1/admin/audit-logs` 中可按 `requestId` 关联到对应审计记录


