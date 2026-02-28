"""
预约/销课记录模型（sessions 表）

注意：文件名使用 session_record.py 以避免与 SQLAlchemy 的 Session 概念冲突。
ORM 类名为 SessionRecord，数据库表名为 sessions。

状态流转（见 architecture.md § 4.1）：
  pending → confirmed → completed
  pending/confirmed → cancelled
  confirmed → no_show

Phase 1 关键约束（应用层强制，非 DB 约束）：
  therapist_id 必须等于 customer_package.sold_by_staff_id。
  这确保"售课即服务"规则，见 architecture.md § 8.1。
  Phase 2 升级时放开此限制，therapist_id 由治疗方案独立指定。

并发安全（见 architecture.md § 8.3）：
  complete_session() 操作须使用 SELECT ... FOR UPDATE 行锁：
    1. 锁定 sessions 行（幂等检查）
    2. 锁定 customer_packages 行（sessions_used += 1）
  保证并发销课不产生账目错误。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid


class SessionRecord(Base, TimestampMixin, SoftDeleteMixin):
    """
    预约与销课记录。

    数据库表名为 `sessions`（符合 ERD），类名 SessionRecord 避免命名冲突。
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 关联 ----
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="预约客户",
    )
    customer_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_packages.id", ondelete="RESTRICT"),
        nullable=False,
        comment="消耗的课包",
    )
    therapist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment=(
            "服务技师。"
            "Phase 1: 须等于 customer_packages.sold_by_staff_id（应用层校验）。"
            "Phase 2: 可由治疗方案独立指定（见 architecture.md § 8.4）。"
        ),
    )

    # ---- 时间信息 ----
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="客户预约时间",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="管理员确认时间",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="实际完成时间（销课触发时记录）",
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        server_default="60",
        comment="服务时长（分钟）",
    )

    # ---- 状态 ----
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | confirmed | completed | cancelled | no_show",
    )

    # ---- 服务内容 ----
    session_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment='服务类型，如 "颈椎", "腰椎"',
    )
    body_areas: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="涉及部位（PostgreSQL 数组），如 ['颈椎', '肩部']",
    )

    # ---- 佣金 ----
    therapist_commission_fen: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="技师服务佣金（分），销课完成时计算",
    )
    commission_settled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="佣金是否已结算",
    )

    # ---- 临床记录 ----
    clinical_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="技师治疗笔记（内部可见）",
    )
    cancel_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="取消原因",
    )

    # ---- Phase 2 预留 ----
    ai_session_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
        comment="Phase 2: AI 诊断 / SOP 数据",
    )

    # ---- Relationships ----
    customer: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[customer_id],
    )
    therapist: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[therapist_id],
    )
    customer_package: Mapped["CustomerPackage"] = relationship(  # type: ignore[name-defined]
        "CustomerPackage",
        back_populates="sessions",
    )

    # ---- 索引 ----
    __table_args__ = (
        Index("ix_sessions_customer_id", "customer_id"),
        Index("ix_sessions_therapist_id", "therapist_id"),
        Index("ix_sessions_scheduled_at", "scheduled_at"),
        Index("ix_sessions_status", "status"),
        Index(
            "ix_sessions_therapist_scheduled_status",
            "therapist_id", "scheduled_at", "status",
            comment="排班冲突检测查询使用（Phase 2）",
        ),
        {"comment": "预约与销课记录"},
    )

    def __repr__(self) -> str:
        return (
            f"<SessionRecord id={self.id} status={self.status} "
            f"scheduled_at={self.scheduled_at}>"
        )
