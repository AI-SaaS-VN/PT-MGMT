"""
微信 API 客户端（异步）

目前封装：
  - code2session()：小程序 wx.login() 换取 openid + session_key + unionid

为什么用 httpx 而不是 wechatpy：
  wechatpy 是同步库，在 FastAPI 异步场景下会阻塞事件循环。
  jscode2session 只是一个简单的 GET 请求，直接用 httpx 更轻量。
  wechatpy 在后续微信支付、订阅消息等场景中仍会使用（在 Celery Worker 中）。

微信 API 文档：
  https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/user-login/code2Session.html
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WeChatAPIError(Exception):
    """微信 API 返回业务错误（errcode != 0）。"""

    def __init__(self, errcode: int, errmsg: str) -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeChat API error {errcode}: {errmsg}")


async def code2session(code: str) -> dict:
    """
    调用微信 jscode2session 接口，将小程序 code 换取用户身份信息。

    Args:
        code: 小程序 wx.login() 返回的临时登录凭证

    Returns:
        包含以下字段的字典：
            - openid (str)：用户在该小程序的唯一标识
            - session_key (str)：会话密钥（服务端保存，不传给客户端）
            - unionid (str | None)：微信开放平台 UnionID。
              ⚠️ 仅当小程序已关联微信开放平台账号时才返回，否则为 None。
              上线前务必在 open.weixin.qq.com 完成"小程序关联"，否则跨端账号
              合并（architecture.md § 8.2）无法正常工作。

    Raises:
        WeChatAPIError: 微信接口返回 errcode（如 40029 无效 code）
        httpx.HTTPError: 网络超时或 HTTP 错误
    """
    url = f"{settings.WECHAT_API_BASE_URL}/sns/jscode2session"
    params = {
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data: dict = response.json()

    # 微信 API 在 HTTP 200 时通过 errcode 字段标记业务错误
    if "errcode" in data and data["errcode"] != 0:
        errcode = data["errcode"]
        errmsg = data.get("errmsg", "unknown error")
        logger.warning("WeChat code2session failed: errcode=%s errmsg=%s", errcode, errmsg)
        raise WeChatAPIError(errcode=errcode, errmsg=errmsg)

    # unionid 在响应中可能不存在（小程序未绑定开放平台）
    return {
        "openid": data["openid"],
        "session_key": data["session_key"],
        "unionid": data.get("unionid"),  # None if not bound to Open Platform
    }
