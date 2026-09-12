"""Offline registration preference and legacy-login regression tests."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from pydantic import ValidationError
from app.api import auth, wechat
from app.models.user import User


class DistributionTests(unittest.IsolatedAsyncioTestCase):
    async def test_email_registration(self):
        for role in ("seller", "buyer"):
            for value in (None, True, False):
                added = []
                db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                                     add=added.append, commit=AsyncMock(), refresh=AsyncMock())
                data = auth.RegisterRequest(email="a@example.com", password="password1", name="shop",
                                            country="CN", phone="123", role=role, supports_distribution=value)
                with patch.object(auth, "_create_token", AsyncMock(return_value="token")), patch.object(auth, "send_verification_email", AsyncMock(return_value=True)):
                    if role == "seller" and value is None:
                        with self.assertRaises(HTTPException) as error:
                            await auth.register(data, db)
                        self.assertEqual(error.exception.status_code, 422)
                        self.assertEqual(added, [])
                    else:
                        await auth.register(data, db)
                        self.assertIs(added[0].supports_distribution, value if role == "seller" else None)

    async def test_wechat_registration(self):
        for value in (True, False):
            added = []
            db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                                 add=added.append, flush=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())
            data = wechat.WechatRegisterRequest(code="c", phone_code="p", email="a@example.com",
                                               password="password1", name="shop", country="CN", supports_distribution=value)
            with patch.object(wechat, "code_to_session", AsyncMock(return_value={"openid": "test"})), patch.object(wechat, "get_phone_number", AsyncMock(return_value="123")), patch.object(wechat, "send_verification_email", AsyncMock(return_value=True)):
                await wechat.wechat_register(data, db)
            self.assertIs(added[0].supports_distribution, value)

    async def test_login_does_not_require_or_overwrite_preference(self):
        for value in (None, True, False):
            seller = SimpleNamespace(id=1, role="seller", is_active=True, password_hash="hash",
                email_verified_at=datetime.now(timezone.utc), auth_version=0, email="a@example.com",
                name="shop", store_name="shop", avatar_url=None, business_license_url=None,
                country="CN", phone=None, uid="test", supports_distribution=value)
            db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [seller]))), commit=AsyncMock())
            with patch.object(auth, "verify_password", return_value=True), patch.object(auth, "create_access_token", return_value="token"):
                response = await auth.login(auth.LoginRequest(identifier=seller.email, password="password1", role="seller"), db)
            self.assertIs(response.supports_distribution, value)
            db.commit.assert_not_awaited()
            db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(user_id=1)))
            db.get = AsyncMock(return_value=seller)
            with patch.object(wechat, "code_to_session", AsyncMock(return_value={"openid": "test"})), patch.object(wechat, "get_phone_number", AsyncMock(return_value="123")), patch.object(wechat, "create_access_token", return_value="token"):
                response = await wechat.wechat_login(wechat.WechatLoginRequest(code="c", phone_code="p"), db)
            self.assertIs(response.supports_distribution, value)
            db.commit.assert_not_awaited()

    def test_registration_strict_boolean(self):
        common = dict(email="a@example.com", password="password1", name="shop", country="CN", phone="123")
        for model, fields in ((auth.RegisterRequest, dict(**common, role="seller")),
                              (wechat.WechatRegisterRequest, dict(**common, code="c", phone_code="p"))):
            for invalid in ("false", "true", "", 0, 1):
                with self.assertRaises(ValidationError):
                    model(**fields, supports_distribution=invalid)
        with self.assertRaises(ValidationError):
            wechat.WechatRegisterRequest(**common, code="c", phone_code="p")
        wechat.WechatBindRequest(code="c", phone_code="p", identifier="a", password="b")
        self.assertTrue(User.__table__.columns.supports_distribution.nullable)


if __name__ == "__main__":
    unittest.main()
