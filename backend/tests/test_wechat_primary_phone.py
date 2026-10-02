"""Offline regression checks for WeChat-authorized primary phone promotion."""
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


class PrimaryPhoneTests(unittest.IsolatedAsyncioTestCase):
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
             patch.object(wechat, '_set_wechat_primary_phone', AsyncMock()) as promote, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True, 'token': 'current-token', 'user_id': 1}):
            response = await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
        self.assertEqual(response.user_id, 1)
        self.assertIn('主手机号未更改', response.phone_binding_warning)
        promote.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_unbound_phone_only_account_reuses_existing_user(self):
        owner = SimpleNamespace(id=2, phone='13800000000', is_active=True, role='seller',
                                restricted_port=None, password_hash=None, email=None)
        old_binding = SimpleNamespace(user_id=2, openid='old-openid', unionid=None)
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(), result(old_binding)])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'new-openid'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')), \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[owner])), \
             patch.object(wechat, '_set_wechat_primary_phone', AsyncMock()) as promote, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True, 'token': 'owner-token', 'user_id': 2}):
            response = await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
        self.assertEqual(response.user_id, 2)
        self.assertEqual(old_binding.openid, 'new-openid')
        promote.assert_awaited_once_with(db, owner, '13800000000')
        db.add.assert_not_called()
        db.commit.assert_awaited_once()

    async def test_unbound_password_account_requires_password(self):
        owner = SimpleNamespace(id=2, phone='13800000000', is_active=True, role='seller',
                                restricted_port=None, password_hash='stored-hash')
        db = Mock()
        db.execute = AsyncMock(return_value=result())
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'new-openid'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')), \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[owner])):
            with self.assertRaises(HTTPException) as caught:
                await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn('账号密码登录并绑定微信', caught.exception.detail)
        db.add.assert_not_called()

    async def test_unbound_password_account_with_old_wechat_uses_password_login(self):
        owner = SimpleNamespace(id=2, is_active=True, role='seller', restricted_port=None,
                                password_hash='stored-hash')
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(), result(SimpleNamespace(user_id=2))])
        with patch.object(wechat, 'code_to_session', AsyncMock(return_value={'openid': 'new-openid'})), \
             patch.object(wechat, 'get_phone_number', AsyncMock(return_value='13800000000')), \
             patch.object(wechat, '_phone_owners', AsyncMock(return_value=[owner])):
            with self.assertRaises(HTTPException) as caught:
                await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
        self.assertIn('请使用账号密码登录', caught.exception.detail)
        self.assertNotIn('并绑定微信', caught.exception.detail)
        db.add.assert_not_called()

    async def promote(self, old, target, records):
        user = SimpleNamespace(id=1, phone=old)
        db = Mock()
        db.execute = AsyncMock(side_effect=[result(), result(), result(target), result(records=records)])
        db.flush = AsyncMock()
        await wechat._set_wechat_primary_phone(db, user, '13800000000')
        return user, db

    async def test_promote_additional_and_preserve_old(self):
        old = UserPhone(user_id=1, phone='13900000000', is_primary=True, verified=True)
        target = UserPhone(user_id=1, phone='13800000000', is_primary=False, verified=False)
        user, db = await self.promote(old.phone, target, [old, target])
        self.assertFalse(old.is_primary)
        self.assertTrue(target.is_primary)
        self.assertTrue(target.verified)
        self.assertIsNotNone(target.verified_at)
        self.assertEqual(user.phone, target.phone)
        db.add.assert_not_called()

    async def test_missing_record_created(self):
        user, db = await self.promote('13800000000', None, [])
        record = db.add.call_args.args[0]
        self.assertEqual(record.phone, user.phone)
        self.assertTrue(record.is_primary and record.verified)

    async def test_repeat_does_not_duplicate(self):
        target = UserPhone(user_id=1, phone='13800000000', is_primary=True, verified=True)
        _, db = await self.promote(target.phone, target, [target])
        db.add.assert_not_called()
        self.assertTrue(target.is_primary)

    async def test_other_account_conflicts(self):
        for legacy, target in [(2, None), (None, UserPhone(user_id=2, phone='13800000000'))]:
            db = Mock()
            db.execute = AsyncMock(side_effect=[result(), result(legacy), result(target)])
            user = SimpleNamespace(id=1, phone='13900000000')
            with self.assertRaises(HTTPException) as caught:
                await wechat._set_wechat_primary_phone(db, user, '13800000000')
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
             patch.object(wechat, '_set_wechat_primary_phone', AsyncMock()) as promote, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True}):
            await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
            exchange.assert_awaited_once_with('phone-code')
            promote.assert_awaited_once_with(db, user, '13800000000')
            db.commit.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
