import httpx
from app.core.config import settings

CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class WechatLoginError(Exception):
    pass


async def code_to_session(code: str) -> dict:
    if not settings.WECHAT_APPID or not settings.WECHAT_APP_SECRET:
        raise WechatLoginError("WeChat AppID/Secret is not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            CODE2SESSION_URL,
            params={
                "appid": settings.WECHAT_APPID,
                "secret": settings.WECHAT_APP_SECRET,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if "openid" not in data:
        raise WechatLoginError(data.get("errmsg") or "jscode2session failed")

    return data
