"""
JWT 安全模块

提供：
  - create_access_token(user)  → 24 小时有效的访问令牌
  - create_refresh_token(user) → 7 天有效的刷新令牌
  - decode_token(token)        → 验证并解码令牌，返回 payload
  - hash_password / verify_password → bcrypt 密码哈希（admin 登录用）

JWT Payload 结构（对应 architecture.md § 3.2）：
    {
        "sub": "usr_uuid",
        "role": "customer|staff|admin",
        "phone": "13800138000" | null,
        "wx_openid": "o..." | null,
        "wx_unionid": "o..." | null,    # 跨平台账号合并关键字段
        "staff_id": "uuid" | null,      # 仅 role=staff 时有值
        "type": "access|refresh",
        "iat": timestamp,
        "exp": timestamp,
    }
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import inspect as sa_inspect

from app.core.config import settings

# bcrypt 上下文，用于 admin 账号密码哈希
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------------------------------------------------------
# Token 创建
# -----------------------------------------------------------------------

def _build_payload(user: "User", token_type: str, expires_delta: timedelta) -> dict:  # type: ignore[name-defined]
    """构建 JWT payload（内部辅助函数）。"""
    now = datetime.now(tz=timezone.utc)
    # Read staff_profile only if already loaded in the ORM identity map.
    # Accessing the relationship directly triggers a lazy SELECT which raises
    # MissingGreenlet inside an async session.
    staff_id = None
    loaded_profile = sa_inspect(user).dict.get("staff_profile")
    if loaded_profile is not None:
        staff_id = str(loaded_profile.id)

    return {
        "sub": str(user.id),
        "role": user.role,
        "phone": user.phone,
        "wx_openid": user.openid,
        "wx_unionid": user.unionid,   # None if mini-program not bound to Open Platform
        "staff_id": staff_id,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }


def create_access_token(user: "User") -> str:  # type: ignore[name-defined]
    """
    创建 Access Token（默认有效期 24 小时）。

    Args:
        user: ORM User 实例（须已从数据库加载）

    Returns:
        签名后的 JWT 字符串
    """
    payload = _build_payload(
        user,
        token_type="access",
        expires_delta=timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS),
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user: "User") -> str:  # type: ignore[name-defined]
    """
    创建 Refresh Token（默认有效期 7 天）。

    Args:
        user: ORM User 实例

    Returns:
        签名后的 JWT 字符串
    """
    payload = _build_payload(
        user,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    解码并验证 JWT。

    Args:
        token: 原始 JWT 字符串

    Returns:
        解码后的 payload 字典

    Raises:
        JWTError: 令牌无效、过期或签名错误
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# -----------------------------------------------------------------------
# 密码哈希（admin 账号用）
# -----------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """返回 bcrypt 哈希后的密码字符串。"""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配。"""
    return _pwd_context.verify(plain, hashed)
