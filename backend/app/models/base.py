"""
ORM 基础模块

提供：
  - Base：所有模型的声明式基类（DeclarativeBase）
  - TimestampMixin：created_at / updated_at 自动时间戳
  - SoftDeleteMixin：deleted_at 软删除支持

使用约定：
  - 所有表使用 UUID 主键，由 Python uuid.uuid4() 生成（不依赖 DB 函数）
  - 软删除查询须过滤 `.where(Model.deleted_at.is_(None))`
  - Transaction 表不继承 SoftDeleteMixin（财务记录永久保留，见 architecture.md § 2.3）
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


class TimestampMixin:
    """
    自动管理 created_at / updated_at 时间戳。

    - created_at：INSERT 时由数据库 now() 填充
    - updated_at：INSERT 和 UPDATE 时均自动更新
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    软删除支持。

    deleted_at 为 NULL 表示记录有效；非 NULL 表示已删除。
    所有读操作须附加 `.where(Model.deleted_at.is_(None))` 过滤条件。
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


def new_uuid() -> uuid.UUID:
    """生成新 UUID，供 mapped_column default 使用。"""
    return uuid.uuid4()
