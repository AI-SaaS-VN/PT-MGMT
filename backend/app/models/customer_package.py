"""
客户课包模型（customer_packages 表）

记录客户购买某门课程后形成的"课包"，追踪：
  - 课时消耗进度（sessions_used）
  - 付款状态（payment_status）
  - 销售技师（sold_by_staff_id）——Phase 1 即为服务技师
  - 转介绍关联（referral_id）

关键约束（见 architecture.md § 2.3）：
  CHECK sessions_used <= sessions_total + sessions_gifted
  （数据库层保证课时不超扣）

Phase 1 重要规则：
  sold_by_staff_id 字段同时决定了哪位技师为该客户服务。
  创建 SessionRecord 时后端须校验 therapist_id == sold_by_staff_id。
"""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid


class CustomerPackage(Base, TimestampMixin, SoftDeleteMixin):
    """客户课包，记录购买行为和课时消耗。"""

    __tablename__ = "customer_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 关联 ----
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="购买客户",
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="购买的课程模板",
    )
    sold_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment=(
            "销售该课包的技师。"
            "Phase 1: 同时决定服务技师（SessionRecord.therapist_id 须等于此值）。"
            "Phase 2: 独立于治疗方案指定的技师。"
        ),
    )
    referral_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referrals.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联转介绍记录（若通过转介绍购买）",
    )

    # ---- 购买信息 ----
    purchase_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default="CURRENT_DATE",
        comment="购买日期",
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="到期日期（由 validity_days 计算）；NULL = 不限期",
    )

    # ---- 课时追踪 ----
    sessions_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="总课时数（从 Course.session_count 复制）",
    )
    sessions_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="已消耗课时（每次销课 +1，受 CHECK 约束）",
    )
    sessions_gifted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="转介绍奖励赠送课时",
    )

    # ---- 付款信息 ----
    agreed_price_fen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="实际成交价（分），可能低于定价",
    )
    amount_paid_fen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="已实收金额（分）",
    )
    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | partial | paid | refunded",
    )
    sold_by_commission_fen: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="销售佣金（分），付款确认后计算",
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Relationships ----
    customer: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[customer_id],
        back_populates="customer_packages",
    )
    course: Mapped["Course"] = relationship(  # type: ignore[name-defined]
        "Course",
        back_populates="customer_packages",
    )
    sessions: Mapped[list["SessionRecord"]] = relationship(  # type: ignore[name-defined]
        "SessionRecord",
        back_populates="customer_package",
        lazy="select",
    )
    transactions: Mapped[list["Transaction"]] = relationship(  # type: ignore[name-defined]
        "Transaction",
        back_populates="customer_package",
        lazy="select",
    )

    # ---- 表级约束与索引 ----
    __table_args__ = (
        CheckConstraint(
            "sessions_used <= sessions_total + sessions_gifted",
            name="ck_customer_packages_sessions_not_exceeded",
        ),
        Index("ix_customer_packages_customer_status", "customer_id", "payment_status"),
        Index("ix_customer_packages_expiry", "expiry_date"),
        {"comment": "客户课包，追踪购买和课时消耗"},
    )

    def __repr__(self) -> str:
        return (
            f"<CustomerPackage id={self.id} customer_id={self.customer_id} "
            f"used={self.sessions_used}/{self.sessions_total}>"
        )
