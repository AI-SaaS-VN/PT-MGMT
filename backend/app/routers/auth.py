"""
认证路由（/api/v1/auth）

实现接口：
  POST /api/v1/auth/wx-login   微信小程序一键登录
  POST /api/v1/auth/refresh    刷新 Access Token（Phase 2）

微信登录完整流程（对应 architecture.md § 8.2 UnionID 策略）：

  ① 客户端 wx.login() → code
  ② 服务端 code2session(code) → openid + unionid（可能为 None）
  ③ UnionID 查找策略（unionid first）：
       - 若 unionid 非空 → SELECT * FROM users WHERE unionid = ?
         - 找到 + openid 不同 → 更新 openid（同一自然人，更换小程序实例）
         - 找到              → 正常登录
       - 若 unionid 为空 或 unionid 未找到 → SELECT * FROM users WHERE openid = ?
         - 找到              → 正常登录（未来可能需要补填 unionid）
         - 未找到            → 创建新用户（is_new_user=True）
  ④ 处理 referral_code（新用户且邀请码有效时，创建 Referral 记录）
  ⑤ 更新 last_login_at
  ⑥ 生成 access_token + refresh_token
  ⑦ 返回标准 SuccessResponse
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.wechat import WeChatAPIError, code2session
from app.models.referral import Referral
from app.models.user import User
from app.schemas.auth import (
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserInfo,
    WxLoginRequest,
    WxLoginResponse,
)
from app.schemas.common import SuccessResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


# -----------------------------------------------------------------------
# POST /auth/wx-login
# -----------------------------------------------------------------------


@router.post(
    "/wx-login",
    response_model=SuccessResponse[WxLoginResponse],
    summary="微信小程序登录",
    description=(
        "使用微信 wx.login() 返回的 code 进行一键登录或注册。\n\n"
        "首次登录时自动创建用户（is_new_user=true）；\n"
        "后续登录返回现有用户信息并刷新 last_login_at。"
    ),
)
async def wx_login(
    body: WxLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[WxLoginResponse]:
    # ---- Step 1: 调用微信 code2session 接口 ----
    try:
        wx_data = await code2session(body.code)
    except WeChatAPIError as exc:
        logger.warning("wx_login code2session failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"微信登录失败：{exc.errmsg}（errcode={exc.errcode}）",
        )

    openid: str = wx_data["openid"]
    unionid: str | None = wx_data["unionid"]  # None if not bound to Open Platform

    # ---- Step 2: UnionID first 策略查找用户 ----
    user: User | None = None
    is_new_user = False

    if unionid:
        # 2a. 优先用 unionid 查找（跨平台账号合并的关键）
        result = await db.execute(
            select(User)
            .options(selectinload(User.staff_profile))
            .where(
                User.unionid == unionid,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if user and user.openid != openid:
            # 同一自然人在不同小程序实例登录，更新 openid（architecture.md § 8.2）
            logger.info(
                "Updating openid for user %s: %s → %s",
                user.id,
                user.openid,
                openid,
            )
            user.openid = openid

    if user is None:
        # 2b. unionid 为空 或 unionid 未匹配 → 用 openid 查找
        result = await db.execute(
            select(User)
            .options(selectinload(User.staff_profile))
            .where(
                User.openid == openid,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if user and unionid and user.unionid is None:
            # 小程序后来绑定了开放平台，补填 unionid
            logger.info("Filling unionid for user %s", user.id)
            user.unionid = unionid

    # ---- Step 3: 未找到用户 → 创建新用户 ----
    if user is None:
        is_new_user = True
        user = User(
            openid=openid,
            unionid=unionid,
            role="customer",
            first_login_at=datetime.now(tz=timezone.utc),
        )
        db.add(user)
        # flush 以获取 user.id（用于后续 referral 记录）
        await db.flush()
        logger.info("New user created: id=%s openid=%s", user.id, openid)

    # ---- Step 4: 处理 referral_code（仅新用户） ----
    if is_new_user and body.referral_code:
        await _handle_referral(db, referee=user, referral_code=body.referral_code)

    # ---- Step 5: 更新 last_login_at ----
    user.last_login_at = datetime.now(tz=timezone.utc)

    # ---- Step 6: 生成令牌 ----
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # ---- Step 7: 提交事务 ----
    await db.commit()
    # refresh 防止 commit 后属性过期触发隐式 lazy-load（MissingGreenlet）
    await db.refresh(user)

    return SuccessResponse(
        data=WxLoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            user=UserInfo(
                id=user.id,
                role=user.role,
                phone=user.phone,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                is_new_user=is_new_user,
            ),
        ),
        message="登录成功",
    )


async def _handle_referral(
    db: AsyncSession,
    referee: User,
    referral_code: str,
) -> None:
    """
    处理转介绍逻辑（新用户注册时）。

    查找 referral_code 对应的推荐人（referral_code 存在 staff_profiles 或 users 扩展字段，
    Phase 1 简化实现：referral_code 直接使用用户的短 ID 或指定字段）。

    注意：
      - Phase 1 中 referral_code 对应用户的 referral_code 字段（User 模型已预留）
      - 奖励发放由 Celery 任务异步处理（Phase 2），此处仅创建 pending 状态的 Referral 记录
      - 若推荐人不存在或已失效，静默忽略（不影响用户注册流程）
    """
    # 查找推荐人
    result = await db.execute(
        select(User).where(
            User.referral_code == referral_code,
            User.deleted_at.is_(None),
        )
    )
    referrer = result.scalar_one_or_none()

    if referrer is None:
        logger.warning(
            "Invalid referral_code '%s' for new user %s, skipping",
            referral_code,
            referee.id,
        )
        return

    if referrer.id == referee.id:
        # 防止自我推荐
        logger.warning("Self-referral attempt by user %s, skipping", referee.id)
        return

    # 检查是否已存在推荐关系（理论上新用户不会有，防御性检查）
    existing = await db.execute(
        select(Referral).where(
            Referral.referrer_id == referrer.id,
            Referral.referee_id == referee.id,
        )
    )
    if existing.scalar_one_or_none():
        return

    referral = Referral(
        referrer_id=referrer.id,
        referee_id=referee.id,
        reward_status="pending",
    )
    db.add(referral)
    logger.info(
        "Referral created: referrer=%s referee=%s", referrer.id, referee.id
    )


# -----------------------------------------------------------------------
# POST /auth/refresh（Phase 2 预留）
# -----------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=SuccessResponse[TokenRefreshResponse],
    summary="刷新 Access Token（Phase 2）",
    description="使用有效的 Refresh Token 换取新的 Access Token。",
)
async def refresh_token(
    body: TokenRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[TokenRefreshResponse]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或已过期的 Refresh Token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise credentials_exception

    result = await db.execute(
        select(User)
        .options(selectinload(User.staff_profile))
        .where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    new_access_token = create_access_token(user)
    return SuccessResponse(
        data=TokenRefreshResponse(access_token=new_access_token),
        message="Token 刷新成功",
    )
