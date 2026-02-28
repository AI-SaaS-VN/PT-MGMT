"""
认证相关 Schema（对应 architecture.md § 3.6 认证接口）

微信小程序登录流程：
  1. 客户端调用 wx.login() 获取 code
  2. 客户端 POST /api/v1/auth/wx-login，携带 code 与可选的 referral_code
  3. 服务端返回 access_token / refresh_token 及用户基本信息

Token 刷新流程（Phase 2）：
  POST /api/v1/auth/refresh，携带 refresh_token → 返回新的 access_token
"""

import uuid

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------
# 请求体
# -----------------------------------------------------------------------


class WxLoginRequest(BaseModel):
    """微信小程序登录请求体。"""

    code: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="wx.login() 返回的临时登录凭证，有效期 5 分钟",
    )
    referral_code: str | None = Field(
        None,
        max_length=20,
        description="邀请码（可选）；若为新用户且提供有效邀请码，触发转介绍奖励逻辑",
    )


class TokenRefreshRequest(BaseModel):
    """刷新 Access Token 请求体（Phase 2）。"""

    refresh_token: str = Field(..., description="有效的 Refresh Token")


# -----------------------------------------------------------------------
# 响应体
# -----------------------------------------------------------------------


class UserInfo(BaseModel):
    """登录成功后返回的用户基本信息。"""

    id: uuid.UUID = Field(..., description="用户 UUID")
    role: str = Field(..., description="customer | staff | admin")
    phone: str | None = Field(None, description="手机号（未绑定时为 null）")
    display_name: str | None = Field(None, description="展示名称")
    avatar_url: str | None = Field(None, description="头像 URL（可能为空）")
    is_new_user: bool = Field(False, description="首次注册时为 true，可用于引导页跳转")

    model_config = {"from_attributes": True}


class WxLoginResponse(BaseModel):
    """微信登录成功响应数据（嵌套在 SuccessResponse.data 中）。"""

    access_token: str = Field(..., description="JWT Access Token，有效期 24 小时")
    refresh_token: str = Field(..., description="JWT Refresh Token，有效期 7 天")
    token_type: str = Field("Bearer", description="固定值 Bearer")
    user: UserInfo


class TokenRefreshResponse(BaseModel):
    """Token 刷新成功响应数据（Phase 2）。"""

    access_token: str = Field(..., description="新的 JWT Access Token")
    token_type: str = Field("Bearer")
