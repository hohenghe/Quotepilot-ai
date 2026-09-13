"""Account provisioning and portal boundaries, offline DB mocks only."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from pydantic import ValidationError
from app.api import admin, auth
from app.core.auth import require_seller, require_buyer, require_admin
from app.core.security import verify_password
from app.core import auth as auth_dependencies


class AccountTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_token_subject_is_rejected_before_query(self):
        for payload in ({}, {'sub': None}, {'sub': []}, {'sub': 'abc'}, {'sub': '-1'}, {'sub': '0'}, {'sub': '2147483648'}, {'sub': '9' * 100}):
            db = SimpleNamespace(execute=AsyncMock())
            with patch.object(auth_dependencies, 'decode_access_token', return_value=payload):
                self.assertIsNone(await auth_dependencies.get_current_user(SimpleNamespace(credentials='token'), db))
            db.execute.assert_not_awaited()

    async def test_disabled_account_cannot_reuse_token(self):
        for active, version, accepted in ((False, 0, False), (True, 0, True), (True, 1, False)):
            user = SimpleNamespace(id=1, is_active=active, auth_version=version)
            db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: user)))
            with patch.object(auth_dependencies, 'decode_access_token', return_value={'sub': '1', 'ver': 0}):
                result = await auth_dependencies.get_current_user(SimpleNamespace(credentials='token'), db)
            self.assertIs(result, user if accepted else None)

    async def test_create_each_port(self):
        for role in ('buyer', 'seller', 'admin'):
            added = []
            db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(first=lambda: None)), add=added.append, commit=AsyncMock(), refresh=AsyncMock())
            result = await admin.create_account(admin.CreateAccountRequest(email=' Review@Test.com ', password='password1', name='Review', role=role, supports_distribution=False), db, SimpleNamespace(id=1))
            account = added[0]
            self.assertEqual(result['email'], 'review@test.com')
            self.assertEqual(account.restricted_port, role)
            self.assertIsNotNone(account.email_verified_at)
            self.assertTrue(verify_password('password1', account.password_hash))
            self.assertNotIn('password', result)
            db.commit.assert_awaited_once()

    async def test_duplicate_does_not_overwrite(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(first=lambda: (1,))), commit=AsyncMock())
        with self.assertRaises(HTTPException) as error:
            await admin.create_account(admin.CreateAccountRequest(email='review@test.com', password='password1', name='Review', role='buyer'), db, SimpleNamespace(id=1))
        self.assertEqual(error.exception.status_code, 409)
        db.commit.assert_not_awaited()

    async def test_login_matrix(self):
        for role in ('buyer', 'seller', 'admin'):
            account = SimpleNamespace(id=1, email='a@test.com', role=role, restricted_port=role, password_hash='hash', is_active=True, email_verified_at=datetime.now(timezone.utc), auth_version=0, name='test', store_name=None, supports_distribution=None, avatar_url=None, business_license_url=None, country='CN', phone=None, uid='1')
            for target in ('buyer', 'seller', 'admin', None):
                db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [account]))))
                with patch.object(auth, 'verify_password', return_value=True), patch.object(auth, 'create_access_token', return_value='token'):
                    if target == role:
                        self.assertEqual((await auth.login(auth.LoginRequest(identifier=account.email, password='password1', role=target), db)).token, 'token')
                    else:
                        with self.assertRaises(HTTPException):
                            await auth.login(auth.LoginRequest(identifier=account.email, password='password1', role=target), db)

    def test_api_boundaries_and_legacy_admin(self):
        for role, own in [('buyer', require_buyer), ('seller', require_seller), ('admin', require_admin)]:
            user = SimpleNamespace(role=role, restricted_port=role)
            self.assertIs(own(user), user)
            for guard in (require_buyer, require_seller, require_admin):
                if guard is not own:
                    with self.assertRaises(HTTPException): guard(user)
        for guard in (require_buyer, require_seller, require_admin):
            guard(SimpleNamespace(role='admin', restricted_port=None))

    def test_invalid_input(self):
        account = admin.CreateAccountRequest(email='wechat@test', password='password1', role='buyer', name='Review')
        self.assertEqual(account.email, 'wechat@test')
        for override in ({'email': ' '}, {'email': ''}, {'password': 'short'}, {'role': 'all'}, {'name': ' '}):
            values = dict(email='a@test.com', password='password1', role='buyer', name='Review')
            values.update(override)
            with self.assertRaises(ValidationError): admin.CreateAccountRequest(**values)


if __name__ == '__main__': unittest.main()
