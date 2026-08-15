"""
Integration tests for POST /api/products/recognize (AI is mocked — no real calls).

Run against a temporary PostgreSQL (pgvector):

    docker run -d --name quotepilot-test-db \\
      -e POSTGRES_USER=quotepilot -e POSTGRES_PASSWORD=quotepilot123 \\
      -e POSTGRES_DB=quotepilot_test -p 5433:5432 pgvector/pgvector:pg16

    TEST_DATABASE_URL=postgresql+asyncpg://quotepilot:quotepilot123@localhost:5433/quotepilot_test \\
      python tests/test_product_recognition.py

    docker rm -f quotepilot-test-db
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
from sqlalchemy import select, func

from app.core.database import init_db, async_session
from app.core.security import hash_password
from app.models.user import User
from app.models.product import Product
from app.main import app
import app.api.ai as ai_module

PASSWORD = "testpass123"
BASE = "http://test"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


async def seed():
    suffix = uuid.uuid4().hex[:8]
    email = f"seller-{suffix}@test.local"
    async with async_session() as db:
        seller = User(
            email=email, password_hash=hash_password(PASSWORD), role="seller",
            name="Seller A", country="CN",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(seller)
        await db.commit()
    return email


async def login(client, email):
    r = await client.post("/api/auth/login", json={"identifier": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["token"]


def _set_vision(result):
    async def _mock(*args, **kwargs):
        return result
    ai_module.recognize_product_image = _mock


def _set_vision_error():
    async def _mock(*args, **kwargs):
        raise RuntimeError("boom")
    ai_module.recognize_product_image = _mock


async def product_count() -> int:
    async with async_session() as db:
        return (await db.execute(select(func.count(Product.id)))).scalar() or 0


async def run():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
        email = await seed()
        token = await login(client, email)
        h = {"Authorization": f"Bearer {token}"}

        # 1. unauthenticated -> 401
        r = await client.post("/api/products/recognize",
                              files={"file": ("x.jpg", b"abc", "image/jpeg")})
        check("no token -> 401", r.status_code == 401, f"got {r.status_code}")

        # 2. non-image -> 400
        r = await client.post("/api/products/recognize",
                              files={"file": ("x.txt", b"hello", "text/plain")}, headers=h)
        check("non-image -> 400", r.status_code == 400, f"got {r.status_code}")

        # 3. oversized -> 413
        big = b"\x00" * (5 * 1024 * 1024 + 1)
        r = await client.post("/api/products/recognize",
                              files={"file": ("big.jpg", big, "image/jpeg")}, headers=h)
        check("oversized -> 413", r.status_code == 413, f"got {r.status_code}")

        # 4. normal image -> mock structured result -> 200
        before = await product_count()
        _set_vision({
            "name": "LED Panel Light", "category": "led_lighting",
            "certifications": "CE, RoHS", "moq": 100,
        })
        r = await client.post("/api/products/recognize",
                              files={"file": ("p.jpg", b"imgbytes", "image/jpeg")}, headers=h)
        check("normal -> 200", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")
        body = r.json()
        check("success true", body.get("success") is True)
        check("data.name", body.get("data", {}).get("name") == "LED Panel Light")
        check("data.category", body.get("data", {}).get("category") == "led_lighting")
        check("data.moq", body.get("data", {}).get("moq") == 100)
        check("no api key in response", "sk-" not in r.text and "api_key" not in r.text)

        # 7. no product created/modified
        after = await product_count()
        check("no product created", before == after, f"{before} -> {after}")

        # 5. AI returns all null -> safe, data all null
        _set_vision({"name": None, "category": None, "moq": None})
        r = await client.post("/api/products/recognize",
                              files={"file": ("p.jpg", b"imgbytes", "image/jpeg")}, headers=h)
        check("all-null result -> 200", r.status_code == 200, r.text[:200])
        data = r.json().get("data", {})
        check("all-null data", all(v is None for v in data.values()))

        # AI returns invalid category -> sanitized to null (via mock, provider-level)
        # (invalid category handling is covered in test_vision_unit.py)

        # 6. AI provider failure -> 502
        _set_vision_error()
        r = await client.post("/api/products/recognize",
                              files={"file": ("p.jpg", b"imgbytes", "image/jpeg")}, headers=h)
        check("provider failure -> 502", r.status_code == 502, f"got {r.status_code}")

        # 8. no seller_id/user_id accepted (endpoint only takes `file`)
        _set_vision({"name": "X"})
        r = await client.post("/api/products/recognize",
                              files={"file": ("p.jpg", b"imgbytes", "image/jpeg")},
                              data={"seller_id": "999", "user_id": "999"}, headers=h)
        check("extra seller_id ignored, still 200", r.status_code == 200, r.text[:200])


async def _main():
    await init_db()
    await run()
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
