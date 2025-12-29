#!/usr/bin/env bash
set -euo pipefail

# 生产备份策略（v1 最小可执行）：
# - 使用 mysqldump 生成逻辑备份文件
# - 备份文件存储到挂载目录（默认 /backups）
#
# 依赖环境变量（与 backend/app/utils/settings.py 保持一致）：
# - MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE
#
# 可选：
# - BACKUP_DIR：输出目录（默认 /backups）

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MYSQL_HOST="${MYSQL_HOST:-mysql}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-lhmy}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
MYSQL_DATABASE="${MYSQL_DATABASE:-lhmy}"

mkdir -p "${BACKUP_DIR}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
file="${BACKUP_DIR}/${MYSQL_DATABASE}_${ts}.sql"

echo "Backing up '${MYSQL_DATABASE}' to '${file}' ..."

mysqldump \
  --host="${MYSQL_HOST}" \
  --port="${MYSQL_PORT}" \
  --user="${MYSQL_USER}" \
  --password="${MYSQL_PASSWORD}" \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  "${MYSQL_DATABASE}" > "${file}"

echo "Backup completed: ${file}"

