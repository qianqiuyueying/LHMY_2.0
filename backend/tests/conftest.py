"""pytest 配置。

说明：确保在任意工作目录执行 pytest 时，都能正确导入 backend/app 下的包。
"""

from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# 集成测试在本地/Windows 上常以“宿主机连接 docker 暴露端口”方式运行。
# 若不显式设置，settings 默认会使用 docker compose service name（mysql/redis），导致本地解析失败。
# 这里用 setdefault：CI/容器环境可通过环境变量覆盖，不影响部署形态。
os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")
os.environ.setdefault("REDIS_PORT", "6379")
