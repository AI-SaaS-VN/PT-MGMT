"""
服务记录（课次）路由（/api/v1/sessions）

接口列表：
  GET    /sessions               列出课次（可按 customer_id / therapist_id / status 过滤）
  GET    /sessions/{id}          课次详情
  POST   /sessions               创建课次（预约）
  PATCH  /sessions/{id}          更新课次信息
  POST   /sessions/{id}/complete 确认完成（销课）—— 含行锁并发控制

Phase 1 约束（architecture.md § 8.1）：
  therapist_id 必须等于对应课包的 sold_by_staff_id（应用层校验）。

并发控制（architecture.md § 8.3）：
  销课操作使用 SELECT ... FOR UPDATE 锁定课包行，
  防止并发导致 sessions_used 超出 sessions_total + sessions_gifted。
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import require_roles
from app.models.customer_package import CustomerPackage
from app.models.session_record import SessionRecord
from app.models.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.session import (
    SessionCreate,
    SessionListItem,
    SessionResponse,
    SessionUpdate,
)

router = APIRouter(prefix="/sessions", tags=["课次管理"])


# -----------------------------------------------------------------------
# GET /sessions
# -----------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[PaginatedResponse[SessionListItem]],
    summary="列出课次",
)
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
    customer_id: uuid.UUID | None = Query(None),
    therapist_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SuccessResponse[PaginatedResponse[SessionListItem]]:
    q = select(SessionRecord).where(SessionRecord.deleted_at.is_(None))
    if customer_id:
        q = q.where(SessionRecord.customer_id == customer_id)
    if therapist_id:
        q = q.where(SessionRecord.therapist_id == therapist_id)
    if status_filter:
        q = q.where(SessionRecord.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.order_by(SessionRecord.scheduled_at.desc()).offset((page - 1) * page_size).limit(page_size)
    sessions = (await db.execute(q)).scalars().all()

    return SuccessResponse(
        data=PaginatedResponse.create(
            items=[SessionListItem.model_validate(s) for s in sessions],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


# -----------------------------------------------------------------------
# GET /sessions/{session_id}
# -----------------------------------------------------------------------


@router.get(
    "/{session_id}",
    response_model=SuccessResponse[SessionResponse],
    summary="课次详情",
)
async def get_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[SessionResponse]:
    sess = await _get_session_or_404(db, session_id)
    return SuccessResponse(data=SessionResponse.model_validate(sess))


# -----------------------------------------------------------------------
# POST /sessions
# -----------------------------------------------------------------------


@router.post(
    "",
    response_model=SuccessResponse[SessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建课次（预约）",
)
async def create_session(
    body: SessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[SessionResponse]:
    # 验证课包存在
    pkg = await _get_package_or_400(db, body.package_id)

    # Phase 1 约束：therapist_id 必须等于 sold_by_staff_id
    _check_phase1_therapist(pkg, body.therapist_id)

    # 验证课包有剩余课次
    if pkg.sessions_used >= pkg.sessions_total + pkg.sessions_gifted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="课包课次已耗尽",
        )

    # 验证课包已付款
    if pkg.payment_status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"课包状态为 {pkg.payment_status}，须付款后才能预约课次",
        )

    sess = SessionRecord(
        customer_id=body.customer_id,
        package_id=body.package_id,
        therapist_id=body.therapist_id,
        scheduled_at=body.scheduled_at,
        body_areas=body.body_areas,
        session_notes=body.session_notes,
        status="scheduled",
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return SuccessResponse(
        data=SessionResponse.model_validate(sess),
        message="课次预约成功",
    )


# -----------------------------------------------------------------------
# PATCH /sessions/{session_id}
# -----------------------------------------------------------------------


@router.patch(
    "/{session_id}",
    response_model=SuccessResponse[SessionResponse],
    summary="更新课次信息",
)
async def update_session(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[SessionResponse]:
    sess = await _get_session_or_404(db, session_id)

    # 已完成的课次不可再修改（除 admin）
    if sess.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已完成的课次不可修改，如需更正请联系管理员",
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sess, field, value)

    await db.commit()
    await db.refresh(sess)
    return SuccessResponse(data=SessionResponse.model_validate(sess))


# -----------------------------------------------------------------------
# POST /sessions/{session_id}/complete  ——  销课（含并发行锁）
# -----------------------------------------------------------------------


@router.post(
    "/{session_id}/complete",
    response_model=SuccessResponse[SessionResponse],
    summary="确认完成（销课）",
    description=(
        "将课次状态置为 completed，并原子性地将对应课包的 sessions_used +1。\n\n"
        "使用 `SELECT ... FOR UPDATE` 锁定课包行，防止并发操作导致超课。"
    ),
)
async def complete_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles("admin", "staff"))],
) -> SuccessResponse[SessionResponse]:
    # Step 1: 检查课次存在且状态合法
    sess = await _get_session_or_404(db, session_id)

    if sess.status == "completed":
        # 幂等：已完成则直接返回（防止重复点击）
        return SuccessResponse(
            data=SessionResponse.model_validate(sess),
            message="课次已完成（重复请求）",
        )

    if sess.status not in ("scheduled", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"课次当前状态为 {sess.status}，无法完成",
        )

    # Step 2: SELECT ... FOR UPDATE 锁定课包行（防并发）
    pkg_result = await db.execute(
        select(CustomerPackage)
        .where(
            CustomerPackage.id == sess.package_id,
            CustomerPackage.deleted_at.is_(None),
        )
        .with_for_update()
    )
    pkg = pkg_result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="关联课包不存在")

    # Step 3: 再次验证课次未超出（加锁后的二次确认）
    if pkg.sessions_used >= pkg.sessions_total + pkg.sessions_gifted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="课包课次已耗尽，无法销课",
        )

    # Step 4: 原子更新
    now = datetime.now(tz=timezone.utc)
    pkg.sessions_used += 1
    sess.status = "completed"
    sess.completed_at = now

    await db.commit()
    await db.refresh(sess)
    return SuccessResponse(
        data=SessionResponse.model_validate(sess),
        message="销课成功",
    )


# -----------------------------------------------------------------------
# 内部辅助
# -----------------------------------------------------------------------


async def _get_session_or_404(db: AsyncSession, session_id: uuid.UUID) -> SessionRecord:
    result = await db.execute(
        select(SessionRecord).where(
            SessionRecord.id == session_id,
            SessionRecord.deleted_at.is_(None),
        )
    )
    sess = result.scalar_one_or_none()
    if sess is None:
        raise HTTPException(status_code=404, detail=f"课次 {session_id} 不存在")
    return sess


async def _get_package_or_400(db: AsyncSession, package_id: uuid.UUID) -> CustomerPackage:
    result = await db.execute(
        select(CustomerPackage).where(
            CustomerPackage.id == package_id,
            CustomerPackage.deleted_at.is_(None),
        )
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=400, detail=f"课包 {package_id} 不存在")
    return pkg


def _check_phase1_therapist(pkg: CustomerPackage, therapist_id: uuid.UUID) -> None:
    """
    Phase 1 约束：服务技师必须是销售技师。

    architecture.md § 8.1：
      Phase 1 中，"售课即服务"——哪个技师卖的课包，就由该技师提供服务。
      Phase 2 将放开此限制，支持多技师治疗方案。
    """
    if pkg.sold_by_staff_id and pkg.sold_by_staff_id != therapist_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Phase 1 约束：服务技师（{therapist_id}）须与销售技师"
                f"（{pkg.sold_by_staff_id}）一致"
            ),
        )
