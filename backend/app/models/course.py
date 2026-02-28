"""
课程目录模型（courses 表）

存放门店提供的所有课程/套餐模板，如：
  - "肩颈调理套餐 10 次"
  - "体验课（单次）"
  - "功能训练月卡 20 次"

客户购买课程后会生成 CustomerPackage 记录。
一个 Course 可被多个客户购买（1:N → customer_packages）。

软删除：下架课程时设置 deleted_at，已有课包不受影响。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid


class Course(Base, TimestampMixin, SoftDeleteMixin):
    """课程模板，定义课时数、价格、有效期等。"""

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 基本信息 ----
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment='课程名称，如 "肩颈调理套餐 10次"',
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    course_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="package（套餐）| single（单次）| trial（体验课）",
    )

    # ---- 课时与有效期 ----
    session_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="总课时数",
    )
    validity_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="有效天数；NULL 表示不限期",
    )

    # ---- 价格（单位：分，避免浮点精度问题）----
    price_fen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="定价（分）",
    )
    cost_per_session_fen: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="单课时成本（分）= price_fen / session_count，冗余字段便于查询",
    )

    # ---- 促销价格 ----
    promo_price_fen: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="促销价（分）；NULL 表示无促销",
    )
    promo_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promo_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- 上下架 ----
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="FALSE = 下架；客户端不展示，但已购课包不受影响",
    )

    # ---- Phase 2 预留 ----
    sop_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Phase 2: 关联 AI SOP 治疗方案模板",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
        comment="扩展元数据（JSON）",
    )

    # ---- Relationships ----
    customer_packages: Mapped[list["CustomerPackage"]] = relationship(  # type: ignore[name-defined]
        "CustomerPackage",
        back_populates="course",
        lazy="select",
    )

    __table_args__ = (
        {"comment": "课程目录，定义套餐/单次课的规格和价格"},
    )

    def __repr__(self) -> str:
        return f"<Course id={self.id} name={self.name!r}>"
