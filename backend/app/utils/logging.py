"""日志配置。

任务要求：请求日志。
这里提供基础 logging 配置，避免引入额外依赖。
"""

from __future__ import annotations

import logging


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
