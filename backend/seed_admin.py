import asyncio
import logging
from datetime import datetime, timezone
from app.core.database import async_session
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "1951444042@qq.com"
ADMIN_PASSWORD = "admin1234"

TEST_ACCOUNTS = [
    {"email": "test@test.com", "password": "test1234", "role": "buyer", "name": "Test Buyer", "country": "CN", "phone": "13800000001", "uid": "TESTBUYER01"},
    {"email": "seller@test.com", "password": "test1234", "role": "seller", "name": "Test Seller", "country": "CN", "phone": "13800000002", "uid": "TESTSELLER1"},
    {"email": "admin@test.com", "password": "test1234", "role": "admin", "name": "Test Admin", "country": "CN", "phone": None, "uid": None},
]


async def create_admin():
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.email == ADMIN_EMAIL, User.role == "admin")
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.email_verified_at is None:
                existing.email_verified_at = datetime.now(timezone.utc)
                await db.commit()
            return

        admin = User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",
            name="Administrator",
            country="CN",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
        logger.warning("Admin account created: %s", ADMIN_EMAIL)


async def create_test_accounts():
    async with async_session() as db:
        for acc in TEST_ACCOUNTS:
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
