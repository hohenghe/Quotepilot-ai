import asyncio
import logging
from app.core.database import async_session
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "1951444042@qq.com"
ADMIN_PASSWORD = "admin1234"

TEST_ACCOUNTS = [
    {"email": "test@test.com", "password": "test1234", "role": "seller", "name": "Test Seller", "country": "CN"},
    {"email": "admin@test.com", "password": "test1234", "role": "admin", "name": "Test Admin", "country": "CN"},
]


async def create_admin():
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        if result.scalar_one_or_none():
            return

        admin = User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",
            name="Administrator",
            country="CN",
        )
        db.add(admin)
        await db.commit()
        logger.warning("Admin account created: %s", ADMIN_EMAIL)


async def create_test_accounts():
    async with async_session() as db:
        for acc in TEST_ACCOUNTS:
            result = await db.execute(
                select(User).where(User.email == acc["email"])
            )
            if result.scalar_one_or_none():
                continue
            db.add(User(
                email=acc["email"],
                password_hash=hash_password(acc["password"]),
                role=acc["role"],
                name=acc["name"],
                country=acc["country"],
            ))
            logger.warning("Test account created: %s (%s)", acc["email"], acc["role"])
        await db.commit()


async def _main():
    await create_admin()
    await create_test_accounts()


if __name__ == "__main__":
    asyncio.run(_main())
