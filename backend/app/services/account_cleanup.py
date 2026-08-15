"""Cleanup of unverified seller accounts whose verification window has expired.

Deletes seller accounts that never completed email verification and whose
verification token(s) have all expired, together with their WeChat bindings.

The operation is idempotent: re-running it finds no matching rows and is a no-op,
so it is safe to run concurrently or repeatedly.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.core.database import async_session
from app.models.user import User
from app.models.auth_token import AuthToken
from app.models.seller_wechat_account import SellerWechatAccount

logger = logging.getLogger(__name__)

# Matches VERIFICATION_TOKEN_TTL in app/api/auth.py: the window a seller is
# allowed to verify their email. An unverified seller older than this whose
# tokens have all expired is considered abandoned.
VERIFICATION_GRACE = timedelta(hours=24)

CLEANUP_INTERVAL_SECONDS = 3600


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def cleanup_expired_unverified_sellers() -> dict:
    """Delete abandoned unverified seller accounts. Returns a summary dict."""
    async with async_session() as db:
        cutoff = _now() - VERIFICATION_GRACE

        # A verification token was issued at some point for this account.
        ever_issued = (
            select(AuthToken.id)
            .where(
                AuthToken.user_id == User.id,
                AuthToken.token_type == "email_verification",
            )
            .exists()
        )
        # A still-unexpired verification token exists (window is still open).
        unexpired = (
            select(AuthToken.id)
            .where(
                AuthToken.user_id == User.id,
                AuthToken.token_type == "email_verification",
                AuthToken.expires_at > _now(),
            )
            .exists()
        )

        # Only: sellers, never verified, past the grace period, whose
        # verification flow was initiated but has no unexpired token left.
        target_query = select(User.id).where(
            User.role == "seller",
            User.email_verified_at.is_(None),
            User.created_at < cutoff,
            ever_issued,
            ~unexpired,
        )
        target_ids = (await db.execute(target_query)).scalars().all()

        if not target_ids:
            await db.commit()
            return {"deleted": 0, "wechat_deleted": 0}

        # Remove WeChat bindings explicitly so no orphan
        # seller_wechat_accounts rows remain, even if the DB FK cascade is
        # missing. (The model + schema both declare ON DELETE CASCADE, so this
        # is a safety net rather than a structural change.)
        wechat_ids = (
            await db.execute(
                select(SellerWechatAccount.id).where(
                    SellerWechatAccount.user_id.in_(target_ids)
                )
            )
        ).scalars().all()
        if wechat_ids:
            await db.execute(
                delete(SellerWechatAccount).where(
                    SellerWechatAccount.id.in_(wechat_ids)
                )
            )

        # auth_tokens / saved_products / reviews reference users.id with
        # ON DELETE CASCADE and are cleaned up by this delete.
        await db.execute(delete(User).where(User.id.in_(target_ids)))
        await db.commit()

        return {"deleted": len(target_ids), "wechat_deleted": len(wechat_ids)}
