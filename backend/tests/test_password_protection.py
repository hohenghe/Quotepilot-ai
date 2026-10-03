"""Focused password and authentication abuse checks; no database required."""
import asyncio
import hashlib
import hmac
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from app.api import auth
from app.core import auth_protection, ratelimit
from app.core.security import hash_password, password_needs_rehash, verify_password


class PasswordProtectionTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        auth_protection._failures.clear()
        ratelimit._windows.clear()

    def test_argon2_random_salt_and_legacy_compatibility(self):
        first = hash_password("example-password")
        second = hash_password("example-password")
        self.assertTrue(first.startswith("$argon2id$"))
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("example-password", first))
        self.assertFalse(verify_password("wrong-password", first))
        self.assertFalse(password_needs_rehash(first))
        legacy_salt = "ab" * 16
        legacy = legacy_salt + ":" + hmac.new(legacy_salt.encode(), b"example-password", hashlib.sha256).hexdigest()
        self.assertTrue(verify_password("example-password", legacy))
        self.assertTrue(password_needs_rehash(legacy))
        self.assertFalse(verify_password("wrong-password", legacy))
        self.assertFalse(verify_password("anything", "bad-hash"))
        self.assertFalse(verify_password("anything", None))

    async def test_legacy_hash_upgrades_after_successful_login(self):
        salt = "cd" * 16
        legacy = salt + ":" + hmac.new(salt.encode(), b"password123", hashlib.sha256).hexdigest()
        user = SimpleNamespace(
            id=1, password_hash=legacy, role="buyer", restricted_port=None,
            email_verified_at=True, auth_version=0, email="buyer@example.com",
            name=None, store_name=None, supports_distribution=None,
            avatar_url=None, business_license_url=None, country="CN", phone=None, uid="ABC",
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [user]))), commit=AsyncMock())
        result = await auth.login(auth.LoginRequest(identifier=user.email, password="password123"), db)
        self.assertEqual(result.user_id, 1)
        self.assertTrue(user.password_hash.startswith("$argon2id$"))
        db.commit.assert_awaited_once()

    async def test_failed_logins_are_limited_before_database(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: []))))
        data = auth.LoginRequest(identifier="target@example.com", password="wrong-password")
        for _ in range(10):
            with self.assertRaises(HTTPException) as exc:
                await auth.login(data, db)
            self.assertEqual(exc.exception.status_code, 401)
        with self.assertRaises(HTTPException) as exc:
            await auth.login(data, db)
        self.assertEqual(exc.exception.status_code, 429)
        self.assertEqual(db.execute.await_count, 10)

    async def test_change_password_attempts_are_limited(self):
        user = SimpleNamespace(id=42, password_hash=hash_password("correct-password"))
        db = SimpleNamespace(commit=AsyncMock())
        data = auth.ChangePasswordRequest(current_password="wrong-password", new_password="different-password")
        for _ in range(10):
            with self.assertRaises(HTTPException) as exc:
                await auth.change_password(data, db, user)
            self.assertEqual(exc.exception.status_code, 400)
        with self.assertRaises(HTTPException) as exc:
            await auth.change_password(data, db, user)
        self.assertEqual(exc.exception.status_code, 429)
        db.commit.assert_not_awaited()

    def test_auth_ip_limits_and_spoofed_header(self):
        request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.9"),
                                  headers={"x-forwarded-for": "198.51.100.1", "cf-connecting-ip": "198.51.100.2"})
        from app.core.config import settings
        with patch.object(settings, "TRUSTED_PROXY_CIDRS", ""):
            self.assertEqual(ratelimit.get_client_ip(request), "203.0.113.9")
        with patch.object(settings, "TRUSTED_PROXY_CIDRS", "203.0.113.0/24"):
            self.assertEqual(ratelimit.get_client_ip(request), "198.51.100.1")
        for _ in range(20):
            self.assertFalse(auth_protection.auth_request_limited("/api/auth/login", "203.0.113.9"))
        self.assertTrue(auth_protection.auth_request_limited("/api/auth/login", "203.0.113.9"))
        self.assertFalse(auth_protection.auth_request_limited("/api/auth/login", "203.0.113.10"))

    async def test_auth_limit_runs_before_route_and_health_is_unaffected(self):
        import httpx
        from app.main import app
        ratelimit._windows.clear()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for _ in range(20):
                response = await client.post("/api/auth/login", content=b"invalid json")
                self.assertEqual(response.status_code, 422)
            response = await client.post("/api/auth/login", content=b"invalid json")
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers["retry-after"], "60")
            self.assertEqual((await client.get("/api/health")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
