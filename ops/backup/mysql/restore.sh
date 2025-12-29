#!/usr/bin/env bash
set -euo pipefail

# 生产备份恢复（v1 最小可执行）：
# - 将指定 sql 文件导入到目标数据库
#
# 依赖环境变量：
# - MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE
# - BACKUP_FILE：要恢复的文件路径（容器内路径，通常位于 /backups/...）

MYSQL_HOST="${MYSQL_HOST:-mysql}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-lhmy}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DATABASE="${MYSQL_DATABASE:-lhmy}"
BACKUP_FILE="${BACKUP_FILE:-}"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "BACKUP_FILE is required" >&2
  exit 2
fi
if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}" >&2
  exit 2
fi

echo "Restoring '${MYSQL_DATABASE}' from '${BACKUP_FILE}' ..."

mysql \
  --host="${MYSQL_HOST}" \
  --port="${MYSQL_PORT}" \
  --user="${MYSQL_USER}" \
  --password="${MYSQL_PASSWORD}" \
  "${MYSQL_DATABASE}" < "${BACKUP_FILE}"

echo "Restore completed."

