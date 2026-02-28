"""
转介绍记录模型（referrals 表）

追踪"老客户推荐新客户"的奖励流程：
  1. 新客户注册时携带 referral_code → 创建 PENDING 状态的 referral
  2. 新客户完成首次付款 → 微信回调触发 → reward_status = 'awarded'，推荐人加赠课时
  3. 超过 expiry_date 未购课 → Celery 每日检查 → reward_status = 'expired'

约束：
  UNIQUE(referrer_id, referee_id)：同一对推荐关系只能存在一次
  （每位客户只能被推荐一次）
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Referral(Base, TimestampMixin):
    """转介绍记录，无软删除（仅通过 reward_status 管理生命周期）。"""

    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 参与方 ----
    referrer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="推荐人（老客户）",
    )
    referee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="被推荐人（新客户），每人只能被推荐一次",
    )

    # ---- 触发课包 ----
    triggered_by_package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_packages.id", ondelete="SET NULL"),
        nullable=True,
        comment="触发奖励的新客户首次购买课包",
    )
    reward_applied_to_package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_packages.id", ondelete="SET NULL"),
        nullable=True,
        comment="奖励课时加到推荐人的哪个课包",
    )

    # ---- 奖励信息 ----
    reward_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="gift_session",
        comment="gift_session | coupon | cash",
    )
    reward_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="奖励值：课时数（gift_session）或优惠券面额/分（coupon/cash）；待发放时确定具体数量",
    )
    reward_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | awarded | expired | cancelled",
    )
    reward_awarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="到期日；到期前未购课则变为 expired（Celery 每日检查）",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("referrer_id", "referee_id", name="uq_referral_pair"),
        {"comment": "转介绍记录，追踪推荐奖励流程"},
    )

    def __repr__(self) -> str:
        return (
            f"<Referral referrer={self.referrer_id} referee={self.referee_id} "
            f"status={self.reward_status}>"
        )
