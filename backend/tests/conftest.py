"""pytest 配置。

说明：确保在任意工作目录执行 pytest 时，都能正确导入 backend/app 下的包。
"""

from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
