"""
客户管理路由（/api/v1/customers）

接口列表：
  GET    /customers              列出所有客户（分页 + 搜索）
  GET    /customers/{id}         客户详情
  POST   /customers              新建客户（staff / admin）
  PATCH  /customers/{id}         更新客户信息（staff / admin）
  DELETE /customers/{id}         软删除客户（admin）
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user, require_roles
from app.models.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.customer import (
    CustomerCreate,
    CustomerListItem,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter(prefix="/customers", tags=["客户管理"])


# -----------------------------------------------------------------------
# GET /customers
# -----------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[CustomerListItem]],
    summary="列出客户",
)
async def list_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="按姓名或手机号模糊搜索"),
    is_active: bool | None = Query(None),
) -> SuccessResponse[PaginatedResponse[CustomerListItem]]:
    q = select(User).where(
        User.role == "customer",
        User.deleted_at.is_(None),
    )
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                User.real_name.ilike(pattern),
                User.display_name.ilike(pattern),
                User.wechat_nickname.ilike(pattern),
                User.phone.ilike(pattern),
            )
        )
    if is_active is not None:
        q = q.where(User.is_active == is_active)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    customers = result.scalars().all()

    return SuccessResponse(
        data=PaginatedResponse.create(
            items=[CustomerListItem.model_validate(c) for c in customers],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


# -----------------------------------------------------------------------
# GET /customers/{customer_id}
# -----------------------------------------------------------------------


@router.get(
    "/{customer_id}",
    response_model=SuccessResponse[CustomerResponse],
    summary="客户详情",
)
async def get_customer(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[CustomerResponse]:
    customer = await _get_customer_or_404(db, customer_id)
    return SuccessResponse(data=CustomerResponse.model_validate(customer))


# -----------------------------------------------------------------------
# POST /customers
# -----------------------------------------------------------------------


@router.post(
    "",
    response_model=SuccessResponse[CustomerResponse],
    status_code=status.HTTP_201_CREATED,
    summary="新建客户",
)
async def create_customer(
    body: CustomerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[CustomerResponse]:
    # 手机号唯一性检查
    if body.phone:
        existing = await db.execute(
            select(User).where(User.phone == body.phone, User.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"手机号 {body.phone} 已被注册",
            )

    customer = User(
        role="customer",
        display_name=body.display_name,
        real_name=body.real_name,
        phone=body.phone,
        gender=body.gender,
        date_of_birth=body.date_of_birth,
        notes=body.notes,
        address=body.address,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return SuccessResponse(
        data=CustomerResponse.model_validate(customer),
        message="客户创建成功",
    )


# -----------------------------------------------------------------------
# PATCH /customers/{customer_id}
# -----------------------------------------------------------------------


@router.patch(
    "/{customer_id}",
    response_model=SuccessResponse[CustomerResponse],
    summary="更新客户信息",
)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[CustomerResponse]:
    customer = await _get_customer_or_404(db, customer_id)

    # 手机号唯一性检查（仅在修改时）
    if body.phone is not None and body.phone != customer.phone:
        existing = await db.execute(
            select(User).where(
                User.phone == body.phone,
                User.deleted_at.is_(None),
                User.id != customer_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"手机号 {body.phone} 已被注册",
            )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    await db.commit()
    await db.refresh(customer)
    return SuccessResponse(data=CustomerResponse.model_validate(customer))


# -----------------------------------------------------------------------
# DELETE /customers/{customer_id}（软删除）
# -----------------------------------------------------------------------


@router.delete(
    "/{customer_id}",
    response_model=SuccessResponse[dict],
    summary="删除客户（软删除，仅 admin）",
)
async def delete_customer(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin"))],
) -> SuccessResponse[dict]:
    from datetime import datetime, timezone

    customer = await _get_customer_or_404(db, customer_id)
    customer.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return SuccessResponse(data={}, message="客户已删除")


# -----------------------------------------------------------------------
# 内部辅助
# -----------------------------------------------------------------------


async def _get_customer_or_404(db: AsyncSession, customer_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User).where(
            User.id == customer_id,
            User.role == "customer",
            User.deleted_at.is_(None),
        )
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"客户 {customer_id} 不存在",
        )
    return customer
