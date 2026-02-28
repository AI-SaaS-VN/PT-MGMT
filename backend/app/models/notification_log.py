"""
通知发送日志模型（notification_logs 表）

记录每条发出的微信订阅消息（Phase 2 可扩展为 SMS / Email / Web Push）。

trigger_type 说明：
  - manual_blast：管理员手动群发
  - session_reminder：课程提醒（Celery 定时）
  - package_expiry：课包即将到期提醒
  - referral_reward：转介绍奖励到账通知
  - promotion：促销活动推送
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class NotificationLog(Base, TimestampMixin):
    """通知发送日志，无软删除。"""

    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 接收方 ----
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="触发此通知的管理员；NULL = 系统自动触发",
    )

    # ---- 消息内容 ----
    template_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="微信订阅消息模板 ID",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="subscribe_message",
        comment="subscribe_message | sms（Phase 2）| email（Phase 2）",
    )
    content_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="发送时的完整消息体快照（审计留存）",
    )

    # ---- 发送状态 ----
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | sent | failed",
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wx_msg_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="微信返回的消息 ID",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- 触发来源 ----
    trigger_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "manual_blast | session_reminder | package_expiry | "
            "referral_reward | promotion"
        ),
    )

    __table_args__ = (
        {"comment": "通知发送日志（微信订阅消息等）"},
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog recipient={self.recipient_id} "
            f"status={self.status} type={self.trigger_type}>"
        )
