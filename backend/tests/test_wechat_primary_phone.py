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
             patch.object(wechat, '_set_wechat_primary_phone', AsyncMock()) as promote, \
             patch.object(wechat, '_auth_payload', return_value={'bound': True}):
            await wechat.wechat_login(wechat.WechatLoginRequest(code='code', phone_code='phone-code'), Response(), db)
            exchange.assert_awaited_once_with('phone-code')
            promote.assert_awaited_once_with(db, user, '13800000000')
            db.commit.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
