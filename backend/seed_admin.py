import asyncio
import logging
from datetime import datetime, timezone
from app.core.config import settings, is_production
from app.core.database import async_session
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Dev-only fallbacks (clearly marked, NEVER used in production).
_DEV_ADMIN_EMAIL = "admin@localhost"
_DEV_ADMIN_PASSWORD = "devadmin123"
_DEV_TEST_PASSWORD = "devtest1234"
_DEV_TEST_ACCOUNTS = [
    {"email": "test@localhost", "password": _DEV_TEST_PASSWORD, "role": "buyer", "name": "Test Buyer", "country": "CN", "phone": "13800000001", "uid": "TESTBUYER01"},
    {"email": "seller@localhost", "password": _DEV_TEST_PASSWORD, "role": "seller", "name": "Test Seller", "country": "CN", "phone": "13800000002", "uid": "TESTSELLER1"},
    {"email": "admin@localhost", "password": _DEV_TEST_PASSWORD, "role": "admin", "name": "Test Admin", "country": "CN", "phone": None, "uid": None},
]


def _admin_credentials() -> tuple[str, str]:
    """Resolve admin email/password from env; dev falls back to dev-only creds."""
    email = settings.ADMIN_EMAIL or (_DEV_ADMIN_EMAIL if not is_production() else "")
    password = settings.ADMIN_PASSWORD or (_DEV_ADMIN_PASSWORD if not is_production() else "")
    return email, password


def _should_create_test_accounts() -> bool:
    # NEVER in production; in dev, opt-in via CREATE_TEST_ACCOUNTS=true.
    if is_production():
        return False
    return (settings.CREATE_TEST_ACCOUNTS or "").strip().lower() in ("1", "true", "yes")


async def create_admin():
    email, password = _admin_credentials()
    if not email or not password:
        logger.warning(
            "ADMIN_EMAIL/ADMIN_PASSWORD not set%s; skipping admin account creation.",
            " in production" if is_production() else "",
        )
        return

    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.email == email, User.role == "admin")
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.email_verified_at is None:
                existing.email_verified_at = datetime.now(timezone.utc)
                await db.commit()
            return

        admin = User(
            email=email,
            password_hash=hash_password(password),
            role="admin",
            name="Administrator",
            country="CN",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
        logger.warning("Admin account created: %s", email)


async def create_test_accounts():
    if not _should_create_test_accounts():
        return

    async with async_session() as db:
        for acc in _DEV_TEST_ACCOUNTS:
            result = await db.execute(
                select(User).where(User.email == acc["email"], User.role == acc["role"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                changed = False
                if existing.name != acc["name"]:
                    existing.name = acc["name"]
                    changed = True
                if acc.get("phone") and existing.phone != acc["phone"]:
                    existing.phone = acc["phone"]
                    changed = True
                if acc.get("uid") and existing.uid != acc["uid"]:
                    existing.uid = acc["uid"]
                    changed = True
                if existing.email_verified_at is None:
                    existing.email_verified_at = datetime.now(timezone.utc)
                    changed = True
                if changed:
                    logger.warning("Test account updated: %s (%s)", acc["email"], acc["role"])
                continue
            db.add(User(
                email=acc["email"],
                password_hash=hash_password(acc["password"]),
                role=acc["role"],
                name=acc["name"],
                country=acc["country"],
                phone=acc.get("phone"),
                uid=acc.get("uid"),
                email_verified_at=datetime.now(timezone.utc),
            ))
            logger.warning("Test account created: %s (%s)", acc["email"], acc["role"])
        await db.commit()


async def _main():
    await create_admin()
    await create_test_accounts()


if __name__ == "__main__":
    asyncio.run(_main())
