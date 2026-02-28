"""
交易/付款记录模型（transactions 表）

⚠️  此表不使用软删除（无 deleted_at 列）。
    财务记录须永久保留，满足合规审计要求（见 architecture.md § 2.3）。

支持的付款方式：
  - wechat_pay：微信支付（异步回调确认）
  - bank_transfer：银行转账（管理员手动确认）
  - cash：现金（管理员手动录入）
  - coupon：优惠券抵扣

退款处理：
  创建一条 amount_fen < 0 的新记录，无需状态机流转。

并发安全：
  微信支付回调（/webhooks/wechat-pay）须使用幂等键（wx_transaction_id）
  防止重复回调导致课包状态变更两次（见 architecture.md § 3.6 支付回调处理逻辑）。
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Transaction(Base, TimestampMixin):
    """
    交易记录。

    注意：不继承 SoftDeleteMixin，财务数据永久保留。
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 关联 ----
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_packages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="确认付款的管理员（微信支付由系统自动确认）",
    )

    # ---- 金额 ----
    amount_fen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="正数=收款，负数=退款（分）",
    )

    # ---- 付款方式 ----
    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="wechat_pay | bank_transfer | cash | coupon",
    )

    # ---- 微信支付字段 ----
    wx_transaction_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        comment="微信支付流水号（回调中获得），幂等键",
    )
    wx_out_trade_no: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        comment="我方订单号（创建支付时生成）",
    )
    wx_prepay_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="微信预支付 ID（返回给前端调起支付）",
    )

    # ---- 银行转账字段 ----
    bank_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="银行流水参考号",
    )
    bank_transfer_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="银行转账日期",
    )

    # ---- 状态 ----
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | confirmed | failed | cancelled",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ---- 审计 ----
    raw_wx_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="微信支付完整回调数据（合规存档）",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Relationships ----
    customer_package: Mapped["CustomerPackage"] = relationship(  # type: ignore[name-defined]
        "CustomerPackage",
        back_populates="transactions",
    )

    # ---- 索引 ----
    __table_args__ = (
        Index("ix_transactions_customer_id", "customer_id"),
        Index("ix_transactions_status", "status"),
        {"comment": "交易/付款记录（永久保留，无软删除）"},
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} amount={self.amount_fen} "
            f"method={self.payment_method} status={self.status}>"
        )
