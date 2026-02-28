"""
优惠券模型（coupons 表）

优惠券可来自：
  - 转介绍奖励（referral_id 非 NULL）
  - 管理员手动发放（customer_id 非 NULL，定向发放）
  - 通用券（customer_id 为 NULL，任何人可用）

折扣类型：
  - fixed_fen：固定减免金额（分），如满 1000 减 100
  - percentage_bps：百分比折扣（基点），如 9000 bps = 90折（即打九折）
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class Coupon(Base, TimestampMixin):
    """优惠券，无软删除（通过 is_used / valid_until 管理生命周期）。"""

    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 券码 ----
    code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        comment='优惠券唯一码，如 "REF-ABCD"',
    )

    # ---- 定向发放 ----
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="指定客户；NULL = 通用券（任何人可用）",
    )
    referral_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("referrals.id", ondelete="SET NULL"),
        nullable=True,
        comment="来源转介绍记录（若为转介绍奖励）",
    )

    # ---- 折扣规则 ----
    discount_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="fixed_fen（固定减免分）| percentage_bps（百分比基点）",
    )
    discount_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="折扣值（配合 discount_type 解读）",
    )
    min_purchase_fen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="最低消费门槛（分）；0 = 无门槛",
    )

    # ---- 有效期 ----
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- 使用状态 ----
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_on_package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_packages.id", ondelete="SET NULL"),
        nullable=True,
        comment="使用在哪个课包上",
    )

    __table_args__ = (
        {"comment": "优惠券，支持转介绍奖励和手动发放"},
    )

    def __repr__(self) -> str:
        return f"<Coupon code={self.code!r} is_used={self.is_used}>"
