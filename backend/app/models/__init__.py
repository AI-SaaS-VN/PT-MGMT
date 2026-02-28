"""
ORM 模型包

导入所有模型以确保 Alembic 的 autogenerate 能发现所有表。
在 alembic/env.py 中使用 `from app.models import *` 或直接导入此包即可。

导入顺序遵循外键依赖：Base → User → StaffProfile → ... → NotificationLog
"""

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid
from app.models.coupon import Coupon
from app.models.course import Course
from app.models.customer_package import CustomerPackage
from app.models.notification_log import NotificationLog
from app.models.referral import Referral
from app.models.session_record import SessionRecord
from app.models.sms_code import SmsCode
from app.models.staff_profile import StaffProfile
from app.models.therapist_availability import TherapistAvailability
from app.models.transaction import Transaction
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "new_uuid",
    "User",
    "StaffProfile",
    "TherapistAvailability",
    "Course",
    "CustomerPackage",
    "SessionRecord",
    "Transaction",
    "Referral",
    "Coupon",
    "NotificationLog",
    "SmsCode",
]
