"""
客户课包 Schema

用于 /api/v1/packages 路由的请求体和响应体。
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class PackageCreate(BaseModel):
    """创建课包（销售课程给客户）请求体。"""

    customer_id: uuid.UUID
    course_id: uuid.UUID
    sold_by_staff_id: uuid.UUID | None = Field(
        None,
        description="销售技师 ID；Phase 1 中 session 的 therapist_id 必须等于此值",
    )
    sessions_total: int = Field(..., gt=0, description="购买课次数")
    sessions_gifted: int = Field(0, ge=0, description="赠送课次数")
    price_paid_fen: int = Field(..., ge=0, description="实际支付金额（分）")
    payment_status: str = Field(
        "pending",
        pattern="^(pending|paid|refunded|partial_refunded)$",
    )
    expiry_date: date | None = Field(None, description="到期日；NULL 永不过期")
    coupon_id: uuid.UUID | None = None
    notes: str | None = None


class PackageUpdate(BaseModel):
    """更新课包请求体（仅允许修改运营字段）。"""

    payment_status: str | None = Field(
        None,
        pattern="^(pending|paid|refunded|partial_refunded)$",
    )
    sessions_gifted: int | None = Field(None, ge=0)
    expiry_date: date | None = None
    notes: str | None = None


class PackageResponse(BaseModel):
    """课包详情响应。"""

    id: uuid.UUID
    customer_id: uuid.UUID
    course_id: uuid.UUID
    sold_by_staff_id: uuid.UUID | None
    sessions_total: int
    sessions_gifted: int
    sessions_used: int
    sessions_remaining: int = Field(description="剩余可用课次（计算字段）")
    price_paid_fen: int
    payment_status: str
    expiry_date: date | None
    coupon_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_remaining(self) -> "PackageResponse":
        self.sessions_remaining = (
            self.sessions_total + self.sessions_gifted - self.sessions_used
        )
        return self


class PackageListItem(BaseModel):
    """课包列表条目（轻量）。"""

    id: uuid.UUID
    customer_id: uuid.UUID
    course_id: uuid.UUID
    sold_by_staff_id: uuid.UUID | None
    sessions_total: int
    sessions_gifted: int
    sessions_used: int
    payment_status: str
    expiry_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}
