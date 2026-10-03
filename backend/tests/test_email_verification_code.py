"""Email verification code contract using a temporary in-memory database."""
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api import admin, auth
from app.core.database import get_db
from app.core.security import generate_token, hash_token
from app.models.auth_token import AuthToken
from app.models.user import User
from app.services import email
from app.services.email_verification import issue_email_code
from app.services.email_verification import CODE_LIFETIME


class EmailCodeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(User.__table__.create)
            await conn.run_sync(AuthToken.__table__.create)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            user = User(email="buyer@example.com", role="buyer", country="CN", is_active=True)
            db.add(user)
            await db.commit()
            self.user_id = user.id

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_code_is_six_digits_and_email_has_no_link(self):
        with patch("app.services.email_verification.generate_email_code", return_value="042731"):
            async with self.sessions() as db:
                code = await issue_email_code(db, self.user_id)
                await db.commit()
                stored = (await db.execute(select(AuthToken))).scalar_one()
        self.assertEqual(code, "042731")
        self.assertTrue(re.fullmatch(r"[0-9]{6}", code))
        self.assertNotEqual(stored.token_hash, code)
        self.assertEqual(CODE_LIFETIME, timedelta(minutes=5))
        with patch.object(email, "_send_transactional_email", AsyncMock(return_value=True)) as send:
            self.assertTrue(await email.send_verification_email("buyer@example.com", code))
            body = " ".join(str(arg) for arg in send.call_args.args)
            self.assertIn(code, body)
            self.assertNotIn("/verify-email?token=", body)

    async def test_wrong_code_count_success_and_replay(self):
        with patch("app.services.email_verification.generate_email_code", return_value="042731"):
            async with self.sessions() as db:
                await issue_email_code(db, self.user_id)
                await db.commit()
                with self.assertRaises(HTTPException) as error:
                    await auth.verify_email(auth.VerifyEmailRequest(email="buyer@example.com", code="111111"), db)
                self.assertEqual(error.exception.status_code, 400)
                stored = (await db.execute(select(AuthToken))).scalar_one()
                self.assertEqual(stored.failed_attempts, 1)
                result = await auth.verify_email(auth.VerifyEmailRequest(email="BUYER@example.com", code="042731"), db)
                self.assertTrue(result["success"])
                db.expire_all()
                user = await db.get(User, self.user_id)
                self.assertIsNotNone(user.email_verified_at)
                with self.assertRaises(HTTPException):
                    await auth.verify_email(auth.VerifyEmailRequest(email=user.email, code="042731"), db)

    async def test_five_failures_block_code_and_expiry(self):
        with patch("app.services.email_verification.generate_email_code", return_value="042731"):
            async with self.sessions() as db:
                await issue_email_code(db, self.user_id)
                await db.commit()
                for _ in range(5):
                    with self.assertRaises(HTTPException):
                        await auth.verify_email(auth.VerifyEmailRequest(email="buyer@example.com", code="111111"), db)
                with self.assertRaises(HTTPException):
                    await auth.verify_email(auth.VerifyEmailRequest(email="buyer@example.com", code="042731"), db)
                stored = (await db.execute(select(AuthToken))).scalar_one()
                self.assertEqual(stored.failed_attempts, 5)
                stored.failed_attempts = 0
                stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await db.commit()
                with self.assertRaises(HTTPException):
                    await auth.verify_email(auth.VerifyEmailRequest(email="buyer@example.com", code="042731"), db)

    async def test_existing_link_still_works_until_expiry(self):
        raw = generate_token()
        async with self.sessions() as db:
            db.add(AuthToken(user_id=self.user_id, token_hash=hash_token(raw),
                             token_type="email_verification",
                             expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
            await db.commit()
            result = await auth.verify_email(auth.VerifyEmailRequest(token=raw), db)
            self.assertTrue(result["success"])

    async def test_resend_replaces_previous_code(self):
        with patch("app.services.email_verification.generate_email_code", return_value="042731"):
            async with self.sessions() as db:
                await issue_email_code(db, self.user_id)
                await db.commit()
                previous = (await db.execute(select(AuthToken))).scalar_one()
                previous.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
                await db.commit()
        with patch("app.services.email_verification.generate_email_code", return_value="654321"), \
             patch.object(auth, "send_verification_email", AsyncMock(return_value=True)) as send:
            async with self.sessions() as db:
                result = await auth.resend_verification(
                    auth.ResendVerificationRequest(email="buyer@example.com"), db,
                )
                self.assertTrue(result["success"])
                send.assert_awaited_once_with("buyer@example.com", "654321")
                with self.assertRaises(HTTPException):
                    await auth.verify_email(auth.VerifyEmailRequest(email="buyer@example.com", code="042731"), db)
                self.assertTrue((await auth.verify_email(
                    auth.VerifyEmailRequest(email="buyer@example.com", code="654321"), db,
                ))["success"])

    async def test_admin_delivery_sends_unstored_six_digit_code(self):
        with patch.object(admin, "send_verification_email", AsyncMock(return_value=True)) as send:
            async with self.sessions() as db:
                response = await admin.test_verification_email(
                    admin.TestEmailRequest(email="buyer@example.com"),
                    await db.get(User, self.user_id), db,
                )
                self.assertTrue(response["success"])
                code = send.await_args.args[1]
                self.assertRegex(code, r"^[0-9]{6}$")
                with self.assertRaises(HTTPException):
                    await auth.verify_email(auth.VerifyEmailRequest(email="buyer@example.com", code=code), db)

    async def test_http_register_verify_then_login(self):
        from app.main import app

        async def override_db():
            async with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        try:
            with patch.object(auth, "send_verification_email", AsyncMock(return_value=True)) as send:
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    registered = await client.post("/api/auth/register", json={
                        "email": "new@example.com", "password": "testpass123",
                        "name": "New Buyer", "country": "CN", "phone": "13800000000", "role": "buyer",
                    })
                    self.assertEqual(registered.status_code, 200, registered.text)
                    code = send.await_args.args[1]
                    self.assertRegex(code, r"^[0-9]{6}$")
                    before = await client.post("/api/auth/login", json={
                        "identifier": "new@example.com", "password": "testpass123", "role": "buyer",
                    })
                    self.assertEqual(before.status_code, 403)
                    verified = await client.post("/api/auth/verify-email", json={
                        "email": "new@example.com", "code": code,
                    })
                    self.assertEqual(verified.status_code, 200, verified.text)
                    login = await client.post("/api/auth/login", json={
                        "identifier": "new@example.com", "password": "testpass123", "role": "buyer",
                    })
                    self.assertEqual(login.status_code, 200, login.text)
                    self.assertTrue(login.json()["token"])
        finally:
            app.dependency_overrides.pop(get_db, None)


if __name__ == "__main__":
    unittest.main()
