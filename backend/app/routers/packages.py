"""
客户课包路由（/api/v1/packages）

接口列表：
  GET    /packages               列出课包（可按 customer_id / payment_status 过滤）
  GET    /packages/{id}          课包详情
  POST   /packages               创建课包（销售）
  PATCH  /packages/{id}          更新课包（补录信息 / 修改状态）
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import get_current_user, require_roles
from app.models.course import Course
from app.models.customer_package import CustomerPackage
from app.models.staff_profile import StaffProfile
from app.models.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.package import (
    PackageCreate,
    PackageListItem,
    PackageResponse,
    PackageUpdate,
)

router = APIRouter(prefix="/packages", tags=["课包管理"])


# -----------------------------------------------------------------------
# GET /packages
# -----------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[PackageListItem]],
    summary="列出课包",
)
async def list_packages(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
    customer_id: uuid.UUID | None = Query(None),
    payment_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SuccessResponse[PaginatedResponse[PackageListItem]]:
    q = select(CustomerPackage).where(CustomerPackage.deleted_at.is_(None))
    if customer_id:
        q = q.where(CustomerPackage.customer_id == customer_id)
    if payment_status:
        q = q.where(CustomerPackage.payment_status == payment_status)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.order_by(CustomerPackage.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    packages = (await db.execute(q)).scalars().all()

    return SuccessResponse(
        data=PaginatedResponse.create(
            items=[PackageListItem.model_validate(p) for p in packages],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


# -----------------------------------------------------------------------
# GET /packages/{package_id}
# -----------------------------------------------------------------------


@router.get(
    "/{package_id}",
    response_model=SuccessResponse[PackageResponse],
    summary="课包详情",
)
async def get_package(
    package_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[PackageResponse]:
    pkg = await _get_package_or_404(db, package_id)
    return SuccessResponse(data=PackageResponse.model_validate(pkg))


# -----------------------------------------------------------------------
# POST /packages
# -----------------------------------------------------------------------


@router.post(
    "",
    response_model=SuccessResponse[PackageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建课包（销售）",
)
async def create_package(
    body: PackageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[PackageResponse]:
    # 验证客户存在
    customer = await db.get(User, body.customer_id)
    if not customer or customer.deleted_at or customer.role != "customer":
        raise HTTPException(status_code=404, detail="客户不存在")

    # 验证课程存在且有效
    course = await db.get(Course, body.course_id)
    if not course or course.deleted_at or not course.is_active:
        raise HTTPException(status_code=404, detail="课程不存在或已下架")

    # 验证销售技师存在
    if body.sold_by_staff_id:
        staff = await db.get(StaffProfile, body.sold_by_staff_id)
        if not staff or staff.deleted_at:
            raise HTTPException(status_code=404, detail="技师档案不存在")

    pkg = CustomerPackage(
        customer_id=body.customer_id,
        course_id=body.course_id,
        sold_by_staff_id=body.sold_by_staff_id,
        sessions_total=body.sessions_total,
        sessions_gifted=body.sessions_gifted,
        price_paid_fen=body.price_paid_fen,
        payment_status=body.payment_status,
        expiry_date=body.expiry_date,
        coupon_id=body.coupon_id,
        notes=body.notes,
    )
    db.add(pkg)
    await db.commit()
    return SuccessResponse(
        data=PackageResponse.model_validate(pkg),
        message="课包创建成功",
    )


# -----------------------------------------------------------------------
# PATCH /packages/{package_id}
# -----------------------------------------------------------------------


@router.patch(
    "/{package_id}",
    response_model=SuccessResponse[PackageResponse],
    summary="更新课包",
)
async def update_package(
    package_id: uuid.UUID,
    body: PackageUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[PackageResponse]:
    pkg = await _get_package_or_404(db, package_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pkg, field, value)

    await db.commit()
    return SuccessResponse(data=PackageResponse.model_validate(pkg))


# -----------------------------------------------------------------------
# 内部辅助
# -----------------------------------------------------------------------


async def _get_package_or_404(db: AsyncSession, package_id: uuid.UUID) -> CustomerPackage:
    result = await db.execute(
        select(CustomerPackage).where(
            CustomerPackage.id == package_id,
            CustomerPackage.deleted_at.is_(None),
        )
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail=f"课包 {package_id} 不存在")
    return pkg
