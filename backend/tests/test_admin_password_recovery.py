"""One-time admin recovery must target one active admin and revoke old sessions."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reset_admin_password import sync_admin_password
from app.core.security import hash_password, verify_password


class AdminPasswordRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_updates_exact_admin_and_revokes_sessions(self):
        admin = SimpleNamespace(
            email="admin@admin.com", role="admin", is_active=True,
            restricted_port=None, password_hash="old-hash", auth_version=4,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [admin]),
            )),
            commit=AsyncMock(),
        )

        async def password_operation(function, *_args):
            return False if function is verify_password else "new-hash"

        with patch("reset_admin_password.run_password_operation", side_effect=password_operation):
            result = await sync_admin_password(db, "admin@admin.com", "newpassword123")
        self.assertIn("synchronized", result)
        self.assertEqual(admin.password_hash, "new-hash")
        self.assertEqual(admin.auth_version, 5)
        db.commit.assert_awaited_once()
        self.assertEqual(db.execute.await_count, 1)

    async def test_matching_password_is_left_unchanged(self):
        admin = SimpleNamespace(
            is_active=True, restricted_port="admin", password_hash="current-hash",
            auth_version=2,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [admin]),
            )),
            commit=AsyncMock(),
        )
        with patch("reset_admin_password.run_password_operation", new=AsyncMock(return_value=True)):
            result = await sync_admin_password(db, "admin@admin.com", "currentpassword")
        self.assertIn("already matches", result)
        self.assertEqual(admin.auth_version, 2)
        db.commit.assert_not_awaited()

    async def test_invalid_or_ambiguous_target_is_rejected(self):
        db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
        for email, password in (("", "password123"), (" admin@admin.com", "password123"),
                                ("admin@admin.com", "short")):
            with self.assertRaises(ValueError):
                await sync_admin_password(db, email, password)
        db.execute.assert_not_awaited()

        db.execute.return_value = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: []),
        )
        with self.assertRaises(RuntimeError):
            await sync_admin_password(db, "admin@admin.com", "password123")
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
