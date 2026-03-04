"""
FastAPI 依赖注入

提供：
  - get_db()：数据库 AsyncSession（来自 core/database.py）
  - get_current_user()：从 Bearer Token 解析当前用户（返回 ORM User 对象）
  - require_roles()：角色权限守卫工厂函数

用法示例：
    from app.deps import get_db, get_current_user, require_roles

    # 任意登录用户
    async def my_route(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ): ...

    # 仅 admin / staff 可访问
    async def admin_route(
        current_user: User = Depends(require_roles("admin", "staff")),
    ): ...
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

# Bearer 令牌提取器（auto_error=True：缺少 Authorization 头直接 401）
_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    从 Authorization: Bearer <token> 中解析并验证当前用户。

    验证步骤：
      1. 解码 JWT，获取 sub（user_id）和 type
      2. 确认 type == "access"（拒绝 refresh token 直接访问）
      3. 查数据库，确认用户存在且未被软删除

    Raises:
        HTTP 401：token 无效、过期、类型错误，或用户不存在
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    # 仅接受 access token
    if payload.get("type") != "access":
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # 查询用户（同时过滤软删除），eagerly load staff_profile so
    # create_access_token can include staff_id without triggering a lazy SELECT.
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

    return user


def require_roles(*roles: str):
    """
    角色权限守卫工厂函数。

    Args:
        *roles: 允许访问的角色列表，如 require_roles("admin", "staff")

    Returns:
        FastAPI 依赖函数，验证当前用户角色，不符合则返回 HTTP 403

    Example:
        @router.get("/admin-only")
        async def admin_route(
            current_user: User = Depends(require_roles("admin")),
        ): ...
    """
    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"此操作需要以下角色之一：{', '.join(roles)}",
            )
        return current_user

    return _check
