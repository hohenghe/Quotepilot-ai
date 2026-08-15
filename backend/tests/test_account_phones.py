"""
Integration tests for account security (change-password) and phone management.

Run against a temporary PostgreSQL (pgvector):

    docker run -d --name quotepilot-test-db \\
      -e POSTGRES_USER=quotepilot -e POSTGRES_PASSWORD=quotepilot123 \\
      -e POSTGRES_DB=quotepilot_test -p 5433:5432 pgvector/pgvector:pg16

    TEST_DATABASE_URL=postgresql+asyncpg://quotepilot:quotepilot123@localhost:5433/quotepilot_test \\
      python tests/test_account_phones.py

    docker rm -f quotepilot-test-db

Uses the project's existing SQLAlchemy models, init_db(), and JWT auth.
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://quotepilot:quotepilot123@localhost:5433/quotepilot_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("EMBEDDING_DIM", "1024")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select

from app.core.database import init_db, async_session
from app.core.security import hash_password
from app.models.user import User
from app.models.user_phone import UserPhone
from app.main import app

PASSWORD = "testpass123"
BASE = "http://test"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


async def seed():
    suffix = uuid.uuid4().hex[:8]
    email_a = f"seller-a-{suffix}@test.local"
    email_b = f"seller-b-{suffix}@test.local"
    phone_a = f"1390000{suffix[:4]}"
    phone_b = f"1390001{suffix[:4]}"

    async with async_session() as db:
        seller_a = User(
            email=email_a, password_hash=hash_password(PASSWORD), role="seller",
            name="Seller A", country="CN", phone=phone_a,
            email_verified_at=datetime.now(timezone.utc),
        )
        seller_b = User(
            email=email_b, password_hash=hash_password(PASSWORD), role="seller",
            name="Seller B", country="CN", phone=phone_b,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add_all([seller_a, seller_b])
        await db.flush()

        primary_a = UserPhone(user_id=seller_a.id, phone=phone_a, is_primary=True, verified=True)
        primary_b = UserPhone(user_id=seller_b.id, phone=phone_b, is_primary=True, verified=True)
        db.add_all([primary_a, primary_b])
        await db.commit()
        await db.refresh(primary_a)
        await db.refresh(primary_b)

        return {
            "email_a": email_a,
            "email_b": email_b,
            "phone_a": phone_a,
            "phone_b": phone_b,
            "user_a_id": seller_a.id,
            "user_b_id": seller_b.id,
            "primary_a_id": primary_a.id,
            "primary_b_id": primary_b.id,
        }


async def login(client, email, password=PASSWORD):
    r = await client.post("/api/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["token"]


async def run():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
        data = await seed()

        # ── Password change ──────────────────────────────────────────────
        token = await login(client, data["email_a"])
        h = {"Authorization": f"Bearer {token}"}

        # same password -> reject
        r = await client.post("/api/auth/change-password", json={
            "current_password": PASSWORD, "new_password": PASSWORD,
        }, headers=h)
        check("change-password same password 400", r.status_code == 400, r.text[:120])

        # wrong current -> reject
        r = await client.post("/api/auth/change-password", json={
            "current_password": "wrongpass", "new_password": "newpass123",
        }, headers=h)
        check("change-password wrong current 400", r.status_code == 400, r.text[:120])

        # short new -> reject
        r = await client.post("/api/auth/change-password", json={
            "current_password": PASSWORD, "new_password": "12345",
        }, headers=h)
        check("change-password short new 400", r.status_code == 400, r.text[:120])

        # correct -> success, returns new token
        r = await client.post("/api/auth/change-password", json={
            "current_password": PASSWORD, "new_password": "brandnew123",
        }, headers=h)
        check("change-password success 200", r.status_code == 200, r.text[:120])
        body = r.json()
        check("change-password returns new token", bool(body.get("token")))
        check("change-password no password_hash in response", "password" not in body and "hash" not in body)

        # old JWT invalidated, new JWT works
        r_old = await client.get("/api/auth/me", headers=h)
        check("old JWT invalid after change", r_old.status_code == 401, f"got {r_old.status_code}")

        h_new = {"Authorization": f"Bearer {body['token']}"}
        r_me = await client.get("/api/auth/me", headers=h_new)
        check("new JWT valid", r_me.status_code == 200, f"got {r_me.status_code}")

        # ── Phone management ─────────────────────────────────────────────
        token_a = await login(client, data["email_a"], "brandnew123")
        ha = {"Authorization": f"Bearer {token_a}"}
        token_b = await login(client, data["email_b"])
        hb = {"Authorization": f"Bearer {token_b}"}

        # PUT /me must not change phone
        r = await client.put("/api/auth/me", json={"phone": "13800000000"}, headers=ha)
        check("PUT /me phone ignored", r.status_code == 200)
        check("PUT /me phone unchanged", r.json().get("phone") == data["phone_a"], f"got {r.json().get('phone')}")

        r = await client.get("/api/auth/me", headers=ha)
        check("GET /me still returns primary phone", r.json().get("phone") == data["phone_a"])

        # GET /phones lists primary
        r = await client.get("/api/auth/phones", headers=ha)
        check("GET phones 200", r.status_code == 200)
        phones = r.json()
        check("GET phones has primary", any(p["is_primary"] and p["phone"] == data["phone_a"] for p in phones))

        # primary phone cannot be deleted
        r = await client.delete(f"/api/auth/phones/{data['primary_a_id']}", headers=ha)
        check("delete primary 400", r.status_code == 400, r.text[:120])

        # add additional phone
        add_phone = f"1391{uuid.uuid4().hex[:7]}"
        r = await client.post("/api/auth/phones", json={"phone": add_phone}, headers=ha)
        check("add additional phone 200", r.status_code == 200, r.text[:120])
        added_id = r.json().get("id")
        check("additional phone unverified", r.json().get("verified") is False)

        # user B cannot delete user A's additional phone
        r = await client.delete(f"/api/auth/phones/{added_id}", headers=hb)
        check("cannot delete other user phone 404", r.status_code == 404, r.text[:120])

        # user A deletes own additional phone
        r = await client.delete(f"/api/auth/phones/{added_id}", headers=ha)
        check("delete own additional 200", r.status_code == 200, r.text[:120])

        # ── Cascade: deleting user removes user_phones ────────────────────
        async with async_session() as db:
            u = await db.get(User, data["user_a_id"])
            await db.delete(u)
            await db.commit()
            remaining = (await db.execute(
                select(UserPhone).where(UserPhone.user_id == data["user_a_id"])
            )).scalars().all()
        check("user_phones cascade on user delete", len(remaining) == 0, f"remaining {len(remaining)}")


async def _main():
    await init_db()
    # Idempotency: run init_db again; backfill must not duplicate rows.
    await init_db()
    await run()
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
