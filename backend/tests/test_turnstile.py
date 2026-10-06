"""Turnstile enforcement on browser requests and the web-only guest inquiry."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_db
from app.services.turnstile import verify_turnstile


class TurnstileTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_login_does_not_require_widget(self):
        from app.api import auth

        admin = SimpleNamespace(
            id=9, email="admin@example.com", role="admin", restricted_port=None,
            password_hash="hash", email_verified_at=None, auth_version=0,
            name="Admin", store_name=None, supports_distribution=None,
            avatar_url=None, business_license_url=None, country="CN",
            phone=None, uid=None,
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [admin]),
        )))
        request = SimpleNamespace(headers={"origin": "http://localhost:3000"})
        with patch.object(auth, "login_locked", return_value=False), \
             patch.object(auth, "run_password_operation", new_callable=AsyncMock, return_value=True), \
             patch.object(auth, "password_needs_rehash", return_value=False), \
             patch.object(auth, "verify_turnstile", new_callable=AsyncMock) as challenge:
            response = await auth.login(auth.LoginRequest(
                identifier=admin.email, password="correct-password", role="admin"), db, request)
        self.assertEqual(response.role, "admin")
        self.assertTrue(response.token)
        challenge.assert_not_awaited()

    async def test_spin_environment_variable_names_are_supported(self):
        request = SimpleNamespace(headers={"origin": "http://localhost:3000"})
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"success": True, "action": "web_login", "hostname": "localhost"},
        )
        client = SimpleNamespace(post=AsyncMock(return_value=response))
        with patch.object(settings, "TURNSTILE_SECRET_KEY", ""), \
             patch.object(settings, "TURNSTILE_SECRET", "spin-secret"), \
             patch.object(settings, "TURNSTILE_ALLOWED_HOSTNAMES", ""), \
             patch.object(settings, "TURNSTILE_HOSTNAMES", "localhost"), \
             patch("app.services.turnstile.get_http_client", return_value=client):
            with self.assertRaises(HTTPException) as missing:
                await verify_turnstile(request, None, "web_login")
            self.assertEqual(missing.exception.status_code, 403)
            await verify_turnstile(request, "valid-token", "web_login")
            self.assertEqual(client.post.await_args.kwargs["json"],
                             {"secret": "spin-secret", "response": "valid-token"})

    async def test_siteverify_checks_action_hostname_and_fails_closed(self):
        request = SimpleNamespace(headers={"origin": "http://localhost:3000"})
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"success": True, "action": "web_login", "hostname": "localhost"},
        )
        client = SimpleNamespace(post=AsyncMock(return_value=response))
        with patch.object(settings, "TURNSTILE_SECRET_KEY", "test-secret"), \
             patch.object(settings, "TURNSTILE_ALLOWED_HOSTNAMES", "localhost"), \
             patch("app.services.turnstile.get_http_client", return_value=client):
            await verify_turnstile(request, "valid-token", "web_login")
            client.post.assert_awaited_once()
            self.assertEqual(client.post.await_args.kwargs["json"],
                             {"secret": "test-secret", "response": "valid-token"})

            response.json = lambda: {"success": True, "action": "web_register", "hostname": "localhost"}
            with self.assertRaises(HTTPException) as wrong_action:
                await verify_turnstile(request, "valid-token", "web_login")
            self.assertEqual(wrong_action.exception.status_code, 403)

            response.json = lambda: {"success": True, "action": "web_login", "hostname": "other.example"}
            with self.assertRaises(HTTPException) as wrong_host:
                await verify_turnstile(request, "valid-token", "web_login")
            self.assertEqual(wrong_host.exception.status_code, 403)

            response.json = lambda: {"success": True, "action": "web_login", "hostname": None}
            with self.assertRaises(HTTPException) as missing_host:
                await verify_turnstile(request, "valid-token", "web_login")
            self.assertEqual(missing_host.exception.status_code, 403)

            client.post.side_effect = httpx.ConnectError("unavailable")
            with self.assertRaises(HTTPException) as unavailable:
                await verify_turnstile(request, "valid-token", "web_login")
            self.assertEqual(unavailable.exception.status_code, 503)

    async def test_public_test_key_only_works_outside_production(self):
        request = SimpleNamespace(headers={"origin": "http://localhost:3000"})
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"success": True, "hostname": "example.com",
                          "metadata": {"result_with_testing_key": True}},
        )
        client = SimpleNamespace(post=AsyncMock(return_value=response))
        with patch.object(settings, "TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA"), \
             patch("app.services.turnstile.get_http_client", return_value=client):
            with patch.object(settings, "ENV", "development"):
                await verify_turnstile(request, "XXXX.DUMMY.TOKEN.XXXX", "web_login")
            with patch.object(settings, "ENV", "production"):
                with self.assertRaises(HTTPException) as production:
                    await verify_turnstile(request, "XXXX.DUMMY.TOKEN.XXXX", "web_login")
                self.assertEqual(production.exception.status_code, 503)

    async def test_browser_requires_token_and_mini_program_remains_compatible(self):
        web = SimpleNamespace(headers={"origin": "http://localhost:3000"})
        mini = SimpleNamespace(headers={})
        with patch.object(settings, "TURNSTILE_SECRET_KEY", "test-secret"):
            with self.assertRaises(HTTPException) as missing:
                await verify_turnstile(web, None, "web_login")
            self.assertEqual(missing.exception.status_code, 403)
            await verify_turnstile(mini, None, "web_login")
            with self.assertRaises(HTTPException) as guest_missing:
                await verify_turnstile(mini, None, "web_inquiry", require_for_all=True)
            self.assertEqual(guest_missing.exception.status_code, 403)

    async def test_http_login_and_guest_inquiry_reject_missing_browser_token(self):
        from app.main import app

        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: []),
        )))

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        try:
            with patch.object(settings, "TURNSTILE_SECRET_KEY", "test-secret"):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    login = await client.post("/api/auth/login", headers={"Origin": "http://localhost:3000"},
                                              json={"identifier": "buyer@example.com", "password": "wrong"})
                    self.assertEqual(login.status_code, 403, login.text)
                    registration = await client.post("/api/auth/register", headers={"Origin": "http://localhost:3000"},
                                                     json={"email": "new@example.com", "password": "password123",
                                                           "country": "CN", "phone": "13800000000", "role": "buyer"})
                    self.assertEqual(registration.status_code, 403, registration.text)
                    recovery = await client.post("/api/auth/forgot-password",
                                                 headers={"Origin": "http://localhost:3000"},
                                                 json={"email": "buyer@example.com"})
                    self.assertEqual(recovery.status_code, 403, recovery.text)
                    inquiry = await client.post("/api/inquiries/analyze", json={"raw_message": "test"})
                    self.assertEqual(inquiry.status_code, 403, inquiry.text)
                    siteverify = SimpleNamespace(
                        raise_for_status=lambda: None,
                        json=lambda: {"success": True, "action": "web_login", "hostname": "localhost"},
                    )
                    with patch.object(settings, "TURNSTILE_ALLOWED_HOSTNAMES", "localhost"), \
                         patch("app.services.turnstile.get_http_client", return_value=SimpleNamespace(
                             post=AsyncMock(return_value=siteverify))):
                        checked = await client.post("/api/auth/login", headers={"Origin": "http://localhost:3000"},
                                                    json={"identifier": "buyer@example.com", "password": "wrong",
                                                          "turnstile_token": "valid-token"})
                        self.assertEqual(checked.status_code, 401, checked.text)
                        self.assertEqual(db.execute.await_count, 1)
        finally:
            app.dependency_overrides.pop(get_db, None)


if __name__ == "__main__":
    unittest.main()
