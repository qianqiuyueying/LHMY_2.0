# 发布/回滚演练记录（模板）

- 日期：YYYY-MM-DD
- 环境：DEV / STAGING / PROD
- 发布版本：
  - backend image/tag：
  - nginx image/tag：
  - 前端 admin build（如非 docker）：
- 执行人：
- 审批/变更单：

## 1. 发布前检查（Pre-flight）
- [ ] 本次变更引用的 specs 已确认（列出 tasks）
- [ ] 生产配置门禁通过（`backend/app/main.py:_validate_production_settings`）
- [ ] 若涉及 DB：已备份（备份文件名：`./backups/mysql/...sql`）

## 2. 发布步骤执行记录
> 记录实际执行的命令与关键输出（可贴关键日志片段）。

- 命令：
- 结果：

## 3. 冒烟验证（必填）
按 `specs-prod/admin/release-smoke.md` 执行，记录结果：

- 通过项：
- 失败项（如有）：
- 失败定位（requestId/日志/审计）：

## 4. 回滚演练（至少一次）
- 是否执行回滚：是/否
- 回滚原因（如执行）：
- 回滚步骤（命令）：
- 回滚验证结果：

## 5. 风险与后续动作
- 风险点：
- 后续任务卡（links）：


