"""
技师档案模型（staff_profiles 表）

每个 role=staff 的 User 可以有一条 staff_profile，记录：
  - 专长技能
  - 入职日期 / 合同类型
  - 佣金比例或固定金额

佣金计算规则（见 architecture.md § 3.6）：
  - sales_commission_bps：销售佣金（基点 1/10000）
    例：2000 bps = 20%
  - session_commission_bps：课时服务佣金（基点）
  - session_flat_rate_fen：固定课时佣金（分）
  当 session_flat_rate_fen 非 NULL 时，优先使用固定金额，忽略 bps。
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid


class StaffProfile(Base, TimestampMixin, SoftDeleteMixin):
    """技师档案表，与 users 表 1:0..1 关联。"""

    __tablename__ = "staff_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 关联用户（唯一，保证 1:0..1 关系）----
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="关联 users.id，一个用户只能有一份技师档案",
    )

    # ---- 专业信息 ----
    specialty: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment='专长技能，逗号分隔，如 "骶髂关节, 颈椎"',
    )
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="full_time | part_time",
    )

    # ---- 佣金设置 ----
    sales_commission_bps: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="销售佣金（基点，1/10000）。例：2000 = 20%",
    )
    session_commission_bps: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="课时服务佣金（基点）。与 session_flat_rate_fen 二选一",
    )
    session_flat_rate_fen: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="课时固定佣金（分）。非 NULL 时优先于 session_commission_bps",
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Relationships ----
    user: Mapped["User"] = relationship("User", back_populates="staff_profile")  # type: ignore[name-defined]

    __table_args__ = (
        {"comment": "技师档案表，记录专长和佣金信息"},
    )

    def __repr__(self) -> str:
        return f"<StaffProfile id={self.id} user_id={self.user_id}>"
