import asyncio
from app.core.database import async_session
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy import select


async def create_admin():
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.email == "admin@quotepilot.ai")
        )
        if result.scalar_one_or_none():
            print("Admin already exists")
            return

        admin = User(
            email="admin@quotepilot.ai",
            password_hash=hash_password("admin123"),
            role="admin",
            name="Administrator",
        )
        db.add(admin)
        await db.commit()
        print("Admin created: admin@quotepilot.ai / admin123")


if __name__ == "__main__":
    asyncio.run(create_admin())
