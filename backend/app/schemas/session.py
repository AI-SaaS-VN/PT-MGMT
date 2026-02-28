"""
服务记录（课次）Schema

用于 /api/v1/sessions 路由的请求体和响应体。

Phase 1 约束（architecture.md § 8.1）：
  therapist_id 必须等于 customer_packages.sold_by_staff_id，
  由路由层在创建和更新时校验。
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """预约 / 创建课次请求体。"""

    customer_id: uuid.UUID
    package_id: uuid.UUID
    therapist_id: uuid.UUID = Field(
        ...,
        description="服务技师；Phase 1 须等于课包的 sold_by_staff_id",
    )
    scheduled_at: datetime = Field(..., description="预约服务时间（含时区）")
    body_areas: list[str] | None = Field(None, description="本次服务部位标签")
    session_notes: str | None = None


class SessionUpdate(BaseModel):
    """更新课次请求体（所有字段可选）。"""

    scheduled_at: datetime | None = None
    status: str | None = Field(
        None,
        pattern="^(scheduled|in_progress|completed|cancelled|no_show)$",
    )
    started_at: datetime | None = None
    body_areas: list[str] | None = None
    session_notes: str | None = None


class SessionResponse(BaseModel):
    """课次详情响应。"""

    id: uuid.UUID
    customer_id: uuid.UUID
    package_id: uuid.UUID
    therapist_id: uuid.UUID
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    status: str
    body_areas: list[str] | None
    session_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    """课次列表条目（轻量）。"""

    id: uuid.UUID
    customer_id: uuid.UUID
    package_id: uuid.UUID
    therapist_id: uuid.UUID
    scheduled_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
