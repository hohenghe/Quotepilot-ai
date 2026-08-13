"""
Minimal integration test for inquiry pagination / buyer+seller isolation / admin seller JOIN.

Run against a temporary PostgreSQL (pgvector):

    docker run -d --name quotepilot-test-db \\
      -e POSTGRES_USER=quotepilot -e POSTGRES_PASSWORD=quotepilot123 \\
      -e POSTGRES_DB=quotepilot_test -p 5433:5432 pgvector/pgvector:pg16

    TEST_DATABASE_URL=postgresql+asyncpg://quotepilot:quotepilot123@localhost:5433/quotepilot_test \\
      python tests/test_inquiry_integration.py

    docker rm -f quotepilot-test-db

Uses the project's existing SQLAlchemy models, init_db(), and JWT auth. No second
model layer. Test data uses unique emails; destroy the container afterwards.
"""
import os
import sys
import uuid
import asyncio

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
from app.models.product import Product
from app.models.seller_inquiry import SellerInquiry
from app.models.inquiry import Inquiry
from app.main import app

PASSWORD = "testpass123"
BASE = "http://test"

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


async def seed():
    suffix = uuid.uuid4().hex[:8]
    admin_email = f"admin-{suffix}@test.local"
    seller_a_email = f"seller-a-{suffix}@test.local"
    seller_b_email = f"seller-b-{suffix}@test.local"
    buyer_a_email = f"buyer-a-{suffix}@test.local"
    buyer_b_email = f"buyer-b-{suffix}@test.local"

    async with async_session() as db:
        admin = User(email=admin_email, password_hash=hash_password(PASSWORD), role="admin", name="Admin A", country="CN")
        seller_a = User(email=seller_a_email, password_hash=hash_password(PASSWORD), role="seller", name="Seller A", country="CN")
        seller_b = User(email=seller_b_email, password_hash=hash_password(PASSWORD), role="seller", name="Seller B", country="CN")
        buyer_a = User(email=buyer_a_email, password_hash=hash_password(PASSWORD), role="buyer", name="Buyer A", country="CN")
        buyer_b = User(email=buyer_b_email, password_hash=hash_password(PASSWORD), role="buyer", name="Buyer B", country="CN")
        db.add_all([admin, seller_a, seller_b, buyer_a, buyer_b])
        await db.flush()

        product_a = Product(name="Product A", sku="SKU-A", category="other", seller_id=seller_a.id)
        product_b = Product(name="Product B", sku="SKU-B", category="other", seller_id=seller_b.id)
        db.add_all([product_a, product_b])
        await db.flush()

        base_inquiry = Inquiry(raw_message="seed inquiry")
        db.add(base_inquiry)
        await db.flush()

        for i in range(60):
            db.add(SellerInquiry(
                inquiry_id=base_inquiry.id,
                buyer_id=buyer_a.id,
                seller_id=seller_a.id,
                product_id=product_a.id,
                raw_message=f"Seller A inquiry {i}",
                buyer_email=buyer_a.email,
                status="replied" if i < 10 else "pending",
                reply_body="Generated reply" if i < 10 else None,
            ))
        for i in range(3):
            db.add(SellerInquiry(
                inquiry_id=base_inquiry.id,
                buyer_id=buyer_b.id,
                seller_id=seller_b.id,
                product_id=product_b.id,
                raw_message=f"Seller B inquiry {i}",
                buyer_email=buyer_b.email,
                status="pending",
            ))
        await db.commit()

        res = await db.execute(select(SellerInquiry).where(SellerInquiry.seller_id == seller_a.id))
        seller_a_ids = [r.id for r in res.scalars().all()]
        res = await db.execute(select(SellerInquiry).where(SellerInquiry.seller_id == seller_b.id))
        seller_b_ids = [r.id for r in res.scalars().all()]

    return {
        "admin": admin_email,
        "seller_a": {"email": seller_a_email, "name": "Seller A", "inquiry_ids": seller_a_ids},
        "seller_b": {"email": seller_b_email, "name": "Seller B", "inquiry_ids": seller_b_ids},
        "buyer_a": buyer_a_email,
        "buyer_b": buyer_b_email,
        "product_a": "Product A",
        "product_b": "Product B",
    }


async def login(client, email):
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["token"]


async def run():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
        data = await seed()

        # --- Seller pagination ---
        token_a = await login(client, data["seller_a"]["email"])
        h = {"Authorization": f"Bearer {token_a}"}
        r = await client.get("/api/seller-inquiries/received?page=1&page_size=50", headers=h)
        page1 = r.json()
        check("seller p1 status 200", r.status_code == 200)
        check("seller p1 len==50", len(page1["items"]) == 50, f"got {len(page1['items'])}")
        check("seller total>=60", page1["total"] >= 60, f"total={page1['total']}")
        check("seller p1 has_next true", page1["has_next"] is True)

        r2 = await client.get("/api/seller-inquiries/received?page=2&page_size=50", headers=h)
        page2 = r2.json()
        check("seller p2 len==10", len(page2["items"]) == 10, f"got {len(page2['items'])}")
        check("seller p2 has_next false", page2["has_next"] is False)

        ids = [i["id"] for i in page1["items"]] + [i["id"] for i in page2["items"]]
        check("seller no duplicate ids across pages", len(ids) == len(set(ids)),
              f"{len(ids)} items, {len(set(ids))} unique")

        # --- Seller isolation ---
        token_b = await login(client, data["seller_b"]["email"])
        hb = {"Authorization": f"Bearer {token_b}"}
        rb = await client.get("/api/seller-inquiries/received?page=1&page_size=100", headers=hb)
        sb_ids = set(i["id"] for i in rb.json()["items"])
        sa_ids = set(data["seller_a"]["inquiry_ids"])
        check("seller B sees own inquiries", sb_ids == set(data["seller_b"]["inquiry_ids"]))
        check("seller B sees no seller A", sb_ids.isdisjoint(sa_ids))

        # --- Buyer inquiries + isolation ---
        token_ba = await login(client, data["buyer_a"])
        rba = await client.get("/api/inquiries/buyer?page=1&page_size=100", headers={"Authorization": f"Bearer {token_ba}"})
        ba_ids = set(i["id"] for i in rba.json()["items"])
        check("buyer A sees own 60 inquiries", ba_ids == sa_ids, f"got {len(ba_ids)}")
        check("buyer A sees no seller B inquiries", ba_ids.isdisjoint(set(data["seller_b"]["inquiry_ids"])))

        token_bb = await login(client, data["buyer_b"])
        rbb = await client.get("/api/inquiries/buyer?page=1&page_size=100", headers={"Authorization": f"Bearer {token_bb}"})
        bb_ids = set(i["id"] for i in rbb.json()["items"])
        check("buyer B sees own 3 inquiries", bb_ids == set(data["seller_b"]["inquiry_ids"]))
        check("buyer B sees no buyer A", bb_ids.isdisjoint(sa_ids))

        # --- Admin product seller JOIN ---
        token_admin = await login(client, data["admin"])
        rp = await client.get("/api/products/admin/all?page=1&page_size=100", headers={"Authorization": f"Bearer {token_admin}"})
        prods = {p["name"]: p for p in rp.json()["items"]}
        check("admin sees product A", data["product_a"] in prods)
        check("admin sees product B", data["product_b"] in prods)
        check("product A seller_name == Seller A",
              prods.get(data["product_a"], {}).get("seller_name") == "Seller A")
        check("product B seller_name == Seller B",
              prods.get(data["product_b"], {}).get("seller_name") == "Seller B")

        # --- Unauthorized ---
        r = await client.get("/api/inquiries/buyer")
        check("no token buyer endpoint 401", r.status_code == 401, f"got {r.status_code}")
        r = await client.get("/api/inquiries/buyer", headers={"Authorization": f"Bearer {token_b}"})
        check("seller JWT buyer endpoint 403", r.status_code == 403, f"got {r.status_code}")
        r = await client.get("/api/seller-inquiries/received", headers={"Authorization": f"Bearer {token_ba}"})
        check("buyer JWT seller endpoint 403", r.status_code == 403, f"got {r.status_code}")
        r = await client.get("/api/products/admin/all", headers={"Authorization": f"Bearer {token_ba}"})
        check("buyer JWT admin endpoint 403", r.status_code == 403, f"got {r.status_code}")


async def _main():
    await init_db()
    await run()
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)


def main():
    print("Using DATABASE_URL =", TEST_DATABASE_URL)
    try:
        asyncio.run(_main())
    except Exception as e:
        print(f"\nFATAL: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
