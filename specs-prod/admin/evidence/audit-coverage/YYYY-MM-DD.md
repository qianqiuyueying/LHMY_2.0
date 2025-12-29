# 审计覆盖率（v1）验收记录 - 执行失败

- 时间窗：近 7 天（since `2025-12-16T03:41:56.928031+00:00`）
- 错误：`OperationalError: (pymysql.err.OperationalError) (1045, "Access denied for user 'lhmy'@'172.18.0.1' (using password: YES)")
(Background on this error at: https://sqlalche.me/e/20/e3q8)`

## 1. 需要覆盖的分母清单（resourceType）
- `EXPORT_DEALER_ORDERS`
- `DEALER_SETTLEMENT_BATCH`
- `DEALER_SETTLEMENT`
- `ORDER`
- `DEALER_LINK`
- `BOOKING`

## 2. 处置建议
- 请在目标环境（预发/生产）配置正确的 DB 连接后重试。
- 也可使用 `specs-prod/admin/ops/audit_coverage_7d.sql` 直接在 DB 执行聚合查询并人工记录。
