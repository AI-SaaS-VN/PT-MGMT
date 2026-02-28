"""
用户模型（users 表）

存储系统内所有角色的用户：customer（客户）、staff（技师）、admin（管理员）。

角色说明：
  - customer：微信小程序用户，通过 wx.login() 注册
  - staff：技师，由 admin 在管理后台创建账号
  - admin：门店管理员，通过手机号+密码登录

关键设计：
  - openid / unionid 均可为 NULL（admin 账号无微信身份）
  - phone 可为 NULL（仅微信登录的客户初期无手机号）
  - unionid 是跨平台账号合并的关键字段（见 architecture.md § 8.2）
  - 软删除：deleted_at IS NOT NULL 表示已注销
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid


class User(Base, TimestampMixin, SoftDeleteMixin):
    """用户表，存放所有角色（客户 / 技师 / 管理员）。"""

    __tablename__ = "users"

    # ---- 主键 ----
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )

    # ---- 角色 ----
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="customer | staff | admin",
    )

    # ---- 微信身份 ----
    openid: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        comment="微信小程序 openid，同一小程序内唯一",
    )
    unionid: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        comment=(
            "微信开放平台 UnionID，跨端账号合并的关键字段。"
            "仅当小程序已绑定微信开放平台主体时才有值（见 architecture.md § 8.2）。"
        ),
    )

    # ---- 展示信息 ----
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="前端展示名称（优先取 real_name，其次 wechat_nickname）",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="头像 URL",
    )

    # ---- 邀请码 ----
    referral_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        comment="用户专属邀请码（用于转介绍）",
    )

    # ---- 微信原始信息 ----
    wechat_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wechat_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    wechat_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="通过 wx.getPhoneNumber 获取的手机号",
    )

    # ---- 真实信息（admin 手动录入）----
    real_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        comment="绑定手机号，Web 端登录凭据（Phase 2）",
    )
    gender: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="unknown",
        comment="male | female | unknown",
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注（门店内部）")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- 账号状态 ----
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ---- Phase 2 预留 ----
    ai_profile: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
        comment="Phase 2: AI 诊断画像（初始为空 JSON）",
    )

    # ---- 登录时间戳 ----
    first_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="首次登录时间（用于统计新用户）",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ---- Relationships ----
    staff_profile: Mapped["StaffProfile | None"] = relationship(  # type: ignore[name-defined]
        "StaffProfile",
        back_populates="user",
        uselist=False,
        lazy="select",
    )
    customer_packages: Mapped[list["CustomerPackage"]] = relationship(  # type: ignore[name-defined]
        "CustomerPackage",
        foreign_keys="CustomerPackage.customer_id",
        back_populates="customer",
        lazy="select",
    )

    # ---- 表级约束 ----
    __table_args__ = (
        # UniqueConstraint 已通过 unique=True 在列上定义，
        # 此处仅添加复合索引（如需）
        {"comment": "系统所有角色的用户表（客户 / 技师 / 管理员）"},
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} role={self.role} openid={self.openid}>"
