import asyncio
import time

import httpx
from app.core.config import settings

CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
PHONE_NUMBER_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"

_access_token: str | None = None
_access_token_expires_at = 0.0
_access_token_lock = asyncio.Lock()


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


async def _get_access_token() -> str:
    """Return a cached app access token for WeChat's phone-number API."""
    global _access_token, _access_token_expires_at
    if _access_token and time.monotonic() < _access_token_expires_at:
        return _access_token

    async with _access_token_lock:
        if _access_token and time.monotonic() < _access_token_expires_at:
            return _access_token
        if not settings.WECHAT_APPID or not settings.WECHAT_APP_SECRET:
            raise WechatLoginError("WeChat AppID/Secret is not configured")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                ACCESS_TOKEN_URL,
                params={
                    "grant_type": "client_credential",
                    "appid": settings.WECHAT_APPID,
                    "secret": settings.WECHAT_APP_SECRET,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        token = data.get("access_token")
        if not token:
            raise WechatLoginError(data.get("errmsg") or "failed to obtain WeChat access token")
        _access_token = str(token)
        _access_token_expires_at = time.monotonic() + max(int(data.get("expires_in", 7200)) - 60, 60)
        return _access_token


async def get_phone_number(phone_code: str) -> str:
    """Verify user-approved phone authorization and return its mobile number."""
    if not phone_code:
        raise WechatLoginError("WeChat phone authorization was not granted")

    token = await _get_access_token()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            PHONE_NUMBER_URL,
            params={"access_token": token},
            json={"code": phone_code},
        )
        resp.raise_for_status()
        data = resp.json()

    phone = (data.get("phone_info") or {}).get("purePhoneNumber")
    if not phone:
        raise WechatLoginError(data.get("errmsg") or "failed to obtain WeChat phone number")
    return str(phone)
