"""
客户 Schema

用于 /api/v1/customers 路由的请求体和响应体。
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    """创建客户请求体（admin / staff 在后台手动录入）。"""

    display_name: str | None = Field(None, max_length=100)
    real_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    gender: str = Field("unknown", pattern="^(male|female|unknown)$")
    date_of_birth: date | None = None
    notes: str | None = None
    address: str | None = None


class CustomerUpdate(BaseModel):
    """更新客户信息请求体（所有字段可选）。"""

    display_name: str | None = Field(None, max_length=100)
    real_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    gender: str | None = Field(None, pattern="^(male|female|unknown)$")
    date_of_birth: date | None = None
    notes: str | None = None
    address: str | None = None
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    """客户详情响应。"""

    id: uuid.UUID
    role: str
    display_name: str | None
    real_name: str | None
    phone: str | None
    gender: str
    date_of_birth: date | None
    notes: str | None
    address: str | None
    is_active: bool
    referral_code: str | None
    wechat_nickname: str | None
    first_login_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerListItem(BaseModel):
    """客户列表条目（轻量）。"""

    id: uuid.UUID
    display_name: str | None
    real_name: str | None
    phone: str | None
    gender: str
    is_active: bool
    wechat_nickname: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
