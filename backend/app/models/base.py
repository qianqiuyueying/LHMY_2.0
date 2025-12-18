"""模型基类。

阶段2会在此基础上逐步添加具体数据模型。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
