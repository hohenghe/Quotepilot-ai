"""Offline regression checks for WeChat-authorized phone ownership."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException, Response
from app.api import wechat
from app.models.user_phone import UserPhone


def result(value=None, records=None):
    res = Mock()
    res.scalar_one_or_none.return_value = value
    res.scalars.return_value.all.return_value = records or []
    return res


class PhoneBindingTests(unittest.IsolatedAsyncioTestCase):
    async def bind(self, original, authorized, records, owners=None):
        user = SimpleNamespace(id=1, phone=original)
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(), result(records=records)])
        db.flush = AsyncMock()
        with patch.object(wechat, '_phone_owners', AsyncMock(return_value=owners or [])):
            await wechat._bind_authorized_phone(db, user, authorized)
        return user, db

    async def test_existing_web_primary_remains_primary(self):
        primary = UserPhone(user_id=1, phone='13900000000', is_primary=True, verified=True)
        user, db = await self.bind(primary.phone, '13800000000', [primary])
        secondary = db.add.call_args.args[0]
        self.assertEqual(user.phone, primary.phone)
        self.assertTrue(primary.is_primary)
        self.assertEqual(secondary.phone, '13800000000')
        self.assertFalse(secondary.is_primary)
        self.assertTrue(secondary.verified)

    async def test_wechat_account_without_phone_gets_primary(self):
        user, db = await self.bind(None, '13800000000', [])
        primary = db.add.call_args.args[0]
        self.assertEqual(user.phone, '13800000000')
        self.assertTrue(primary.is_primary and primary.verified)

    async def test_repeat_authorization_does_not_duplicate(self):
        primary = UserPhone(user_id=1, phone='13900000000', is_primary=True, verified=True)
        secondary = UserPhone(user_id=1, phone='13800000000', is_primary=False, verified=False)
        user, db = await self.bind(primary.phone, secondary.phone, [primary, secondary])
        self.assertEqual(user.phone, primary.phone)
        self.assertTrue(primary.is_primary)
        self.assertFalse(secondary.is_primary)
        self.assertTrue(secondary.verified)
        db.add.assert_not_called()

    async def test_legacy_mirror_is_repaired_without_replacing_primary(self):
        stale = UserPhone(user_id=1, phone='13800000000', is_primary=True, verified=False)
        user, db = await self.bind('13900000000', stale.phone, [stale])
        self.assertEqual(user.phone, '13900000000')
        self.assertFalse(stale.is_primary)
        self.assertTrue(db.add.call_args.args[0].is_primary)

    async def test_other_account_phone_conflicts(self):
        owner = SimpleNamespace(id=2)
        user = SimpleNamespace(id=1, phone='13900000000')
        db = Mock()
        db.execute = AsyncMock(return_value=result())
        with patch.object(wechat, '_phone_owners', AsyncMock(return_value=[owner])):
            with self.assertRaises(HTTPException) as caught:
                await wechat._bind_authorized_phone(db, user, '13800000000')
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(user.phone, '13900000000')
        db.add.assert_not_called()

    async def test_bound_login_exchanges_phone_before_return(self):
        user = SimpleNamespace(id=1, is_active=True, role='seller', email=None)
        db = Mock()
        db.execute = AsyncMock(return_value=result(SimpleNamespace(user_id=1)))
        db.get = AsyncMock(return_value=user)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'openid'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')) as exchange, \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[])), \
             patch.object(wechat, '_bind_authorized_phone', AsyncMock()) as bind, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True}):
            await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
        exchange.assert_awaited_once_with('phone-code')
        bind.assert_awaited_once_with(db, user, '13800000000')
        db.commit.assert_awaited_once()

    async def test_bound_login_with_other_account_phone_keeps_identity(self):
        current = SimpleNamespace(id=1, is_active=True, role='seller', email=None)
        other = SimpleNamespace(id=2, password_hash='stored-hash')
        db = Mock()
        db.execute = AsyncMock(return_value=result(SimpleNamespace(user_id=1)))
        db.get = AsyncMock(return_value=current)
        db.commit = AsyncMock()
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'current'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')), \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[other])), \
             patch.object(wechat, '_bind_authorized_phone', AsyncMock()) as bind, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True, 'token': 'current-token', 'user_id': 1}):
            response = await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
        self.assertEqual(response.user_id, 1)
        self.assertIn('主手机号未更改', response.phone_binding_warning)
        bind.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_unbound_old_wechat_phone_cannot_take_over(self):
        owner = SimpleNamespace(id=2, is_active=True, role='seller', restricted_port=None,
                                password_hash=None, email=None)
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(), result(SimpleNamespace(user_id=2))])
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'new'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')), \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[owner])):
            with self.assertRaises(HTTPException) as caught:
                await wechat.wechat_login(wechat.WechatLoginRequest(code='c', phone_code='p'), Response(), db)
        self.assertEqual(caught.exception.status_code, 409)
        db.add.assert_not_called()

    async def test_existing_web_phone_offers_binding_not_registration(self):
        owner = SimpleNamespace(id=2, is_active=True, role='seller', restricted_port=None,
                                password_hash='hash', email='seller@example.com', email_verified_at=object())
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(), result()])
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'new'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')), \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[owner])):
            response = await wechat.wechat_login(
                wechat.WechatLoginRequest(code='c', phone_code='p'), Response(), db)
        self.assertFalse(response.bound)
        self.assertFalse(response.registration_available)
        self.assertTrue(response.choice_token)
        db.add.assert_not_called()

    async def test_choice_ticket_cannot_be_replaced_by_login_token(self):
        ordinary = wechat.create_access_token(1, 'seller')
        with self.assertRaises(HTTPException) as caught:
            wechat._decode_phone_choice_token(ordinary)
        self.assertEqual(caught.exception.status_code, 400)

    async def test_registration_rechecks_phone_ownership(self):
        ticket = wechat._create_phone_choice_token({'openid': 'new'}, '13800000000')
        db = Mock()
        db.execute = AsyncMock(return_value=result())
        with patch.object(wechat, '_phone_owners', AsyncMock(return_value=[SimpleNamespace(id=2)])):
            with self.assertRaises(HTTPException) as caught:
                await wechat.complete_wechat_registration(
                    wechat.WechatChoiceRequest(choice_token=ticket), db)
        self.assertEqual(caught.exception.status_code, 409)
        db.add.assert_not_called()

    async def test_explicit_binding_reuses_choice_ticket(self):
        user = SimpleNamespace(id=2, role='seller', phone='13900000000', email_verified_at=object(),
                               password_hash='hash', restricted_port=None)
        ticket = wechat._create_phone_choice_token({'openid': 'new'}, '13800000000')
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(records=[user]), result(), result()])
        db.commit = AsyncMock()
        with patch.object(wechat, 'login_locked', return_value=False, create=True), \
             patch.object(wechat, 'verify_password', return_value=True), \
             patch.object(wechat, 'run_password_operation', AsyncMock(return_value=True), create=True), \
             patch.object(wechat, 'password_needs_rehash', return_value=False, create=True), \
             patch.object(wechat, '_bind_authorized_phone', AsyncMock()) as bind, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True, 'token': 'token'}):
            response = await wechat.wechat_bind(
                wechat.WechatBindRequest(choice_token=ticket, identifier='seller@example.com', password='pw'), db)
        self.assertTrue(response.bound)
        bind.assert_awaited_once_with(db, user, '13800000000')
        db.commit.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
