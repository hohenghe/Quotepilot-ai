"""One-time admin password recovery using the service's existing environment.

Run inside the backend service: python reset_admin_password.py --execute
The password is read from ADMIN_PASSWORD, never from argv or stdin.
"""

import argparse
import asyncio

from sqlalchemy import func, select

from app.core.auth_protection import run_password_operation
from app.core.config import settings
from app.core.database import async_session
from app.core.security import hash_password, verify_password
from app.models.user import User


async def sync_admin_password(db, email: str, password: str) -> str:
    if not email or email != email.strip() or "@" not in email:
        raise ValueError("ADMIN_EMAIL must be a valid email without surrounding spaces")
    if not password or len(password) < 8:
        raise ValueError("ADMIN_PASSWORD must contain at least 8 characters")

    result = await db.execute(select(User).where(
        func.lower(User.email) == email.lower(), User.role == "admin",
    ))
    accounts = result.scalars().all()
    if len(accounts) != 1:
        raise RuntimeError(f"Expected exactly one admin account for ADMIN_EMAIL; found {len(accounts)}")

    admin = accounts[0]
    if not admin.is_active or admin.restricted_port not in (None, "admin"):
        raise RuntimeError("Admin account is inactive or restricted to another portal")
    if await run_password_operation(verify_password, password, admin.password_hash):
        return "Admin password already matches ADMIN_PASSWORD; no change made."

    admin.password_hash = await run_password_operation(hash_password, password)
    admin.auth_version = (admin.auth_version or 0) + 1
    await db.commit()
    return "Admin password synchronized with ADMIN_PASSWORD; existing sessions revoked."


async def _main() -> None:
    async with async_session() as db:
        print(await sync_admin_password(db, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="apply the one-time password update")
    args = parser.parse_args()
    if not args.execute:
        parser.error("No change made. Pass --execute to update the configured admin account.")
    asyncio.run(_main())
