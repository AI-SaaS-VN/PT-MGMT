"""初始数据库 Schema

创建所有 Phase 1 核心表及 Phase 2 预留表。
表创建顺序遵循外键依赖：先创建被引用的表，再创建引用表。

表清单：
  核心表（Phase 1 使用）：
    users                  用户（客户 / 技师 / 管理员）
    staff_profiles         技师档案（1:0..1 关联 users）
    courses                课程 / 项目定义
    customer_packages      客户课包
    sessions               服务记录（课次）
    transactions           资金流水（无软删除）
    referrals              转介绍关系
    coupons                优惠券
    notification_logs      通知发送日志

  Phase 2 预留（建表不启用）：
    therapist_availability 技师排班时段（Phase 2 预约系统）
    sms_codes              短信验证码（Phase 2 手机号登录）

迁移版本：0001
前置版本：None（初始迁移）
创建时间：2026-02-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ================================================================
    # 1. users
    # ================================================================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            server_default="customer",
            comment="customer | staff | admin",
        ),
        sa.Column(
            "openid",
            sa.String(100),
            nullable=True,
            comment="微信小程序 openid",
        ),
        sa.Column(
            "unionid",
            sa.String(100),
            nullable=True,
            comment="微信开放平台 unionid（跨平台账号合并关键字段）",
        ),
        sa.Column("phone", sa.String(20), nullable=True, comment="绑定手机号"),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("referral_code", sa.String(20), nullable=True, comment="用户专属邀请码"),
        # 微信原始信息
        sa.Column("wechat_nickname", sa.String(100), nullable=True),
        sa.Column("wechat_avatar", sa.Text(), nullable=True),
        sa.Column("wechat_phone", sa.String(20), nullable=True, comment="wx.getPhoneNumber 获取"),
        # 真实信息（admin 录入）
        sa.Column("real_name", sa.String(100), nullable=True),
        sa.Column(
            "gender",
            sa.String(10),
            nullable=False,
            server_default="unknown",
            comment="male | female | unknown",
        ),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True, comment="备注（门店内部）"),
        sa.Column("address", sa.Text(), nullable=True),
        # 账号状态
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "ai_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="AI 诊断画像（Phase 2）",
        ),
        sa.Column("first_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("openid", name="uq_users_openid"),
        sa.UniqueConstraint("unionid", name="uq_users_unionid"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
        sa.UniqueConstraint("referral_code", name="uq_users_referral_code"),
        comment="用户（客户 / 技师 / 管理员）",
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_phone", "users", ["phone"])

    # ================================================================
    # 2. staff_profiles
    # ================================================================
    op.create_table(
        "staff_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_no", sa.String(50), nullable=True, comment="工号"),
        sa.Column("specialty", sa.String(200), nullable=True, comment="专业方向"),
        sa.Column("bio", sa.Text(), nullable=True, comment="简介"),
        sa.Column(
            "sales_commission_bps",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="销售提成（基点，1bps=0.01%）",
        ),
        sa.Column(
            "session_commission_bps",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="服务提成（基点）",
        ),
        sa.Column(
            "session_flat_rate_fen",
            sa.Integer(),
            nullable=True,
            comment="服务固定提成（分）；非空时优先于 bps",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_staff_profiles_user_id", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("user_id", name="uq_staff_profiles_user_id"),
        comment="技师 / 员工档案（1:0..1 关联 users）",
    )
    op.create_index("ix_staff_profiles_user_id", "staff_profiles", ["user_id"])

    # ================================================================
    # 3. therapist_availability（Phase 2 预留）
    # ================================================================
    op.create_table(
        "therapist_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, comment="排班日期"),
        sa.Column("start_time", sa.Time(), nullable=False, comment="时段开始时间"),
        sa.Column("end_time", sa.Time(), nullable=False, comment="时段结束时间"),
        sa.Column(
            "slot_type",
            sa.String(20),
            nullable=False,
            server_default="available",
            comment="available | blocked | booked",
        ),
        sa.Column("notes", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["staff_profiles.id"],
            name="fk_therapist_avail_staff_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "staff_id", "date", "start_time", name="uq_therapist_avail_slot"
        ),
        comment="技师排班时段（Phase 2 预留，Phase 1 不启用）",
    )
    op.create_index(
        "ix_therapist_avail_staff_date", "therapist_availability", ["staff_id", "date"]
    )

    # ================================================================
    # 4. courses
    # ================================================================
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, comment="课程名称"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True, comment="课程分类"),
        sa.Column(
            "price_fen",
            sa.Integer(),
            nullable=False,
            comment="标准售价（分）",
        ),
        sa.Column(
            "sessions_included",
            sa.Integer(),
            nullable=False,
            comment="标准课次数",
        ),
        sa.Column(
            "validity_days",
            sa.Integer(),
            nullable=True,
            comment="有效期（天）；NULL 表示永不过期",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="FALSE 时不在前端展示",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="扩展属性（Phase 2）",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="课程 / 服务项目定义",
    )
    op.create_index("ix_courses_is_active", "courses", ["is_active"])
    op.create_index("ix_courses_category", "courses", ["category"])

    # ================================================================
    # 5. coupons（先于 customer_packages，因为 customer_packages 引用 coupons）
    # ================================================================
    op.create_table(
        "coupons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, comment="优惠券码（唯一）"),
        sa.Column(
            "discount_type",
            sa.String(20),
            nullable=False,
            comment="fixed_fen | percentage_bps",
        ),
        sa.Column("discount_value", sa.Integer(), nullable=False),
        sa.Column("min_order_fen", sa.Integer(), nullable=True, comment="最低消费金额（分）"),
        sa.Column("max_discount_fen", sa.Integer(), nullable=True, comment="最大抵扣金额（分）"),
        sa.Column(
            "usage_limit",
            sa.Integer(),
            nullable=True,
            comment="最大使用次数；NULL 表示不限",
        ),
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="已使用次数",
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        comment="优惠券",
    )
    op.create_index("ix_coupons_code", "coupons", ["code"])

    # ================================================================
    # 6. customer_packages
    # ================================================================
    op.create_table(
        "customer_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sold_by_staff_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="销售技师；Phase 1：therapist_id 必须等于此值（应用层校验）",
        ),
        sa.Column(
            "sessions_total",
            sa.Integer(),
            nullable=False,
            comment="购买课次数",
        ),
        sa.Column(
            "sessions_gifted",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="赠送课次数",
        ),
        sa.Column(
            "sessions_used",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="已完成课次数（行锁保护，防并发错误）",
        ),
        sa.Column(
            "price_paid_fen",
            sa.Integer(),
            nullable=False,
            comment="实际支付金额（分）",
        ),
        sa.Column(
            "payment_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | paid | refunded | partial_refunded",
        ),
        sa.Column("expiry_date", sa.Date(), nullable=True, comment="到期日；NULL 永不过期"),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name="fk_customer_packages_customer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name="fk_customer_packages_course_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sold_by_staff_id"],
            ["staff_profiles.id"],
            name="fk_customer_packages_sold_by_staff_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["coupon_id"],
            ["coupons.id"],
            name="fk_customer_packages_coupon_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "sessions_used <= sessions_total + sessions_gifted",
            name="ck_customer_packages_sessions_not_exceeded",
        ),
        comment="客户课包（购买记录）",
    )
    op.create_index(
        "ix_customer_packages_customer_status",
        "customer_packages",
        ["customer_id", "payment_status"],
    )
    op.create_index(
        "ix_customer_packages_expiry",
        "customer_packages",
        ["expiry_date", "payment_status"],
    )

    # ================================================================
    # 7. sessions（服务记录 / 课次）
    # ================================================================
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "therapist_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment=(
                "服务技师；Phase 1：须等于 customer_packages.sold_by_staff_id，"
                "应用层校验。Phase 2：可与 sold_by_staff_id 不同（多技师治疗方案）。"
            ),
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="预约服务时间",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="实际开始时间",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="实际完成时间",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="scheduled",
            comment="scheduled | in_progress | completed | cancelled | no_show",
        ),
        sa.Column(
            "body_areas",
            postgresql.ARRAY(sa.String()),
            nullable=True,
            comment="本次服务部位标签（PostgreSQL 数组）",
        ),
        sa.Column("session_notes", sa.Text(), nullable=True, comment="治疗师本次记录"),
        sa.Column(
            "ai_session_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="AI 辅助记录（Phase 2）",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name="fk_sessions_customer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["customer_packages.id"],
            name="fk_sessions_package_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["therapist_id"],
            ["staff_profiles.id"],
            name="fk_sessions_therapist_id",
            ondelete="RESTRICT",
        ),
        comment="服务记录（课次）",
    )
    op.create_index(
        "ix_sessions_customer_scheduled",
        "sessions",
        ["customer_id", "scheduled_at"],
    )
    # Phase 2 排班冲突检测用
    op.create_index(
        "ix_sessions_therapist_scheduled_status",
        "sessions",
        ["therapist_id", "scheduled_at", "status"],
    )
    op.create_index("ix_sessions_package_id", "sessions", ["package_id"])
    op.create_index("ix_sessions_status", "sessions", ["status"])

    # ================================================================
    # 8. transactions（资金流水，无软删除）
    # ================================================================
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "amount_fen",
            sa.Integer(),
            nullable=False,
            comment="金额（分）；正数=收款，负数=退款",
        ),
        sa.Column(
            "tx_type",
            sa.String(30),
            nullable=False,
            comment="purchase | refund | gift | adjustment",
        ),
        sa.Column(
            "payment_method",
            sa.String(30),
            nullable=True,
            comment="wechat_pay | cash | bank_transfer",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | success | failed | refunded",
        ),
        sa.Column(
            "wx_out_trade_no",
            sa.String(100),
            nullable=True,
            comment="我方支付单号（唯一，幂等键）",
        ),
        sa.Column(
            "wx_transaction_id",
            sa.String(100),
            nullable=True,
            comment="微信支付流水号（唯一）",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_transactions_user_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["customer_packages.id"],
            name="fk_transactions_package_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("wx_out_trade_no", name="uq_transactions_wx_out_trade_no"),
        sa.UniqueConstraint("wx_transaction_id", name="uq_transactions_wx_transaction_id"),
        comment="资金流水（无软删除，财务记录永久保留）",
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])
    op.create_index("ix_transactions_package_id", "transactions", ["package_id"])

    # ================================================================
    # 9. referrals（转介绍）
    # ================================================================
    op.create_table(
        "referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referrer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "triggered_by_package_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="触发奖励的新客户首次购买课包",
        ),
        sa.Column(
            "reward_applied_to_package_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="奖励课时加到推荐人的哪个课包",
        ),
        sa.Column(
            "reward_type",
            sa.String(30),
            nullable=False,
            server_default="gift_session",
            comment="gift_session | coupon | cash",
        ),
        sa.Column(
            "reward_value",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="奖励值；待发放时确定具体数量",
        ),
        sa.Column(
            "reward_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | awarded | expired | cancelled",
        ),
        sa.Column("reward_awarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["referrer_id"],
            ["users.id"],
            name="fk_referrals_referrer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["referee_id"],
            ["users.id"],
            name="fk_referrals_referee_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_package_id"],
            ["customer_packages.id"],
            name="fk_referrals_triggered_by_package_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reward_applied_to_package_id"],
            ["customer_packages.id"],
            name="fk_referrals_reward_applied_to_package_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("referrer_id", "referee_id", name="uq_referral_pair"),
        comment="转介绍记录，追踪推荐奖励流程",
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])
    op.create_index("ix_referrals_referee_id", "referrals", ["referee_id"])

    # ================================================================
    # 10. notification_logs
    # ================================================================
    op.create_table(
        "notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", sa.String(100), nullable=False),
        sa.Column(
            "channel",
            sa.String(20),
            nullable=False,
            server_default="subscribe_message",
        ),
        sa.Column(
            "content_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pending | sent | failed",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wx_msg_id", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name="fk_notification_logs_recipient_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_id"],
            ["users.id"],
            name="fk_notification_logs_triggered_by_id",
            ondelete="SET NULL",
        ),
        comment="通知发送日志（微信订阅消息等）",
    )
    op.create_index("ix_notification_logs_recipient_id", "notification_logs", ["recipient_id"])

    # ================================================================
    # 11. sms_codes（Phase 2 预留）
    # ================================================================
    op.create_table(
        "sms_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column(
            "purpose",
            sa.String(30),
            nullable=False,
            comment="login | register | reset_password | bind_phone",
        ),
        sa.Column(
            "is_used",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="短信验证码（Phase 2 预留，Phase 1 不使用）",
    )
    op.create_index("ix_sms_codes_phone", "sms_codes", ["phone"])


def downgrade() -> None:
    # 按依赖关系逆序删除
    op.drop_table("sms_codes")
    op.drop_table("notification_logs")
    op.drop_table("referrals")
    op.drop_table("transactions")
    op.drop_table("sessions")
    op.drop_table("customer_packages")
    op.drop_table("coupons")
    op.drop_table("courses")
    op.drop_table("therapist_availability")
    op.drop_table("staff_profiles")
    op.drop_table("users")
