"""
短信验证码模型（sms_codes 表）—— Phase 2 预留

Phase 1：微信小程序登录，无需短信验证码。
Phase 2：手机号注册 / 找回账号 / 管理后台登录时启用。

设计要点：
  - 每条记录对应一次发送动作，不更新旧记录（追加模式）
  - 查询时取 phone + purpose + expires_at > now() + is_used = FALSE 的最新一条
  - 验证通过后立即将 is_used 置 TRUE，防止重放攻击
  - 旧记录由定时任务定期清理（30 天以上的可删除）
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class SmsCode(Base, TimestampMixin):
    """短信验证码（Phase 2 预留）。

    Phase 1 不启用，但提前建表以便 Alembic 迁移历史一致。
    """

    __tablename__ = "sms_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)

    # ---- 接收方 ----
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="接收短信的手机号",
    )

    # ---- 验证码内容 ----
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="6 位数字验证码（存储时应哈希，Phase 2 实现时注意）",
    )
    purpose: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="login | register | reset_password | bind_phone",
    )

    # ---- 状态 ----
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="已使用则置 TRUE，防止重放攻击",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="过期时间（通常为发送时间 + 5 分钟）",
    )

    __table_args__ = (
        {"comment": "短信验证码（Phase 2 预留，Phase 1 不使用）"},
    )

    def __repr__(self) -> str:
        return (
            f"<SmsCode phone={self.phone} purpose={self.purpose} "
            f"used={self.is_used}>"
        )
