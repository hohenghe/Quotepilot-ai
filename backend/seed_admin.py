import asyncio
import logging
from app.core.database import async_session
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "1951444042@qq.com"
ADMIN_PASSWORD = "admin1234"


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


if __name__ == "__main__":
    asyncio.run(create_admin())
