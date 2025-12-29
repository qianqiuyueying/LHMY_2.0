-- 审计覆盖率（近 7 天）验收 SQL（MySQL）。
--
-- 规格来源（单一真相来源）：
-- - specs-prod/admin/security.md#3.1.1 高风险事件覆盖清单（v1 分母）
-- - specs-prod/admin/observability.md#2.3 审计覆盖率与高风险操作计数（v1 草案）
--
-- 用途：
-- - 以“近 7 天”窗口聚合 audit_logs.resource_type
-- - 输出：每个 resource_type 的 count，用于人工比对“分母清单是否覆盖”
--
-- 运行方式（示例）：
--   -- 注意：请在对应环境执行（预发/生产），并把结果粘贴到 specs-prod/admin/evidence/audit-coverage/ 记录文件中
--   SELECT ...
--
-- 时间窗（近 7 天）：按 created_at 口径
SET @since = DATE_SUB(NOW(), INTERVAL 7 DAY);

SELECT
  resource_type,
  COUNT(*) AS cnt
FROM audit_logs
WHERE created_at >= @since
GROUP BY resource_type
ORDER BY cnt DESC, resource_type ASC;


