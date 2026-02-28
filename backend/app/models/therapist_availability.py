"""
技师排班表（therapist_availability）

⚠️  Phase 2 预留表 —— Phase 1 建库但不启用任何业务逻辑。

Phase 1 采用"售课即服务"模式（sold_by_staff_id == therapist_id），
无需跨技师排班冲突检测。

Phase 2 启用条件（见 architecture.md § 8.1 / § 8.4）：
  - 门店引入"首席诊疗师 → 出治疗方案 → 分配专项技师"协作模式
  - 开启 feature flag 后，创建 SessionRecord 前须查此表检测冲突
"""

import uuid
from datetime import date, time

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class TherapistAvailability(Base, TimestampMixin):
    """
    技师每日可服务时段配置。

    UNIQUE(staff_id, date, start_time) 确保同一技师同一天不会有重叠的开始时间。
    """

    __tablename__ = "therapist_availability"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联 users.id（role=staff）",
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="当日日期（yyyy-mm-dd）",
    )
    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        comment="可服务开始时间（如 09:00）",
    )
    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        comment="可服务结束时间（如 18:00）",
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="TRUE=可服务；FALSE=请假/休息",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注（如请假原因）")

    __table_args__ = (
        UniqueConstraint("staff_id", "date", "start_time", name="uq_therapist_avail_slot"),
        {"comment": "Phase 2 预留：技师排班，Phase 1 不启用"},
    )

    def __repr__(self) -> str:
        return (
            f"<TherapistAvailability staff_id={self.staff_id} "
            f"date={self.date} {self.start_time}-{self.end_time}>"
        )
