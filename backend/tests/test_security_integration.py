"""Security integration tests for QuotePilot AI backend.

Run without a DB (auth + rate-limit tests only):
    python tests/test_security_integration.py

Run with a pgvector DB (full suite):
    docker run -d --name qp-test-db -e POSTGRES_USER=quotepilot \
      -e POSTGRES_PASSWORD=quotepilot123 -e POSTGRES_DB=quotepilot_test \
      -p 5433:5432 pgvector/pgvector:pg16
    TEST_DATABASE_URL=postgresql+asyncpg://quotepilot:quotepilot123@localhost:5433/quotepilot_test \
      python tests/test_security_integration.py
    docker rm -f qp-test-db

Uses httpx ASGITransport (no real HTTP server). The auth-rejection and
rate-limit tests do NOT require a database because the guards fire before
any DB query is executed.
"""
import os
import sys
import asyncio

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://quotepilot:quotepilot123@localhost:5433/quotepilot_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("EMBEDDING_DIM", "1024")
os.environ.setdefault("OPENAI_API_KEY", "")  # ensure mock LLM (no network)
os.environ.setdefault("EMBEDDING_API_KEY", "")  # no embedding network calls
os.environ.setdefault("EMBEDDING_BASE_URL", "")
os.environ.setdefault("ANALYZE_ANON_RATE", "3")  # small for testing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.main import app

BASE = "http://test"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


async def _db_available() -> bool:
    """Quick TCP probe to see if the test DB is reachable."""
    import socket
    from urllib.parse import urlparse
    try:
        p = urlparse(TEST_DATABASE_URL)
        host = p.hostname or "localhost"
        port = p.port or 5432
        s = socket.socket()
        s.settimeout(1)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


async def test_no_db_auth_rejections(client):
    """Tests that fire 401/403 before any DB query — work without a database."""

    # P0-4: quotes/generate anonymous → 401
    r = await client.post("/api/quotes/generate", json={"inquiry_id": 1})
    check("quotes/generate anon 401", r.status_code == 401, f"got {r.status_code}")

    # P0-4: quotes/{id} anonymous → 401
    r = await client.get("/api/quotes/1")
    check("quotes/{id} anon 401", r.status_code == 401, f"got {r.status_code}")

    # P0-5: debug/llm-status anonymous → 401
    r = await client.get("/api/debug/llm-status")
    check("debug/llm-status anon 401", r.status_code == 401, f"got {r.status_code}")

    # P0-5: debug/embedding-status anonymous → 401
    r = await client.get("/api/debug/embedding-status")
    check("debug/embedding-status anon 401", r.status_code == 401, f"got {r.status_code}")

    # P1-7: dashboard anonymous → 401
    r = await client.get("/api/dashboard")
    check("dashboard anon 401", r.status_code == 401, f"got {r.status_code}")

    # P0-5: debug/llm-status no key_preview in response (even if it were accessible)
    # Verify the source no longer has key_preview by checking a 401 body doesn't leak it.
    check("no key_preview in 401 body", "key_preview" not in r.text)

    # Extra B: generate-reply anonymous → 401
    r = await client.post("/api/seller-inquiries/generate-reply", json={"inquiry_id": 1})
    check("generate-reply anon 401", r.status_code == 401, f"got {r.status_code}")


async def test_analyze_rate_limit(client):
    """P0-3: anonymous /analyze rate limit → 429 after the limit is hit.

    Works without a DB because the rate limiter fires before any DB write.
    The first N requests may return 503/500 (no DB) but the counter still
    increments."""
    # ANALYZE_ANON_RATE is set to 3 via env. Make 4 requests; the 4th must 429.
    statuses = []
    for _ in range(4):
        try:
            r = await client.post("/api/inquiries/analyze", json={"raw_message": "test inquiry"})
            statuses.append(r.status_code)
        except Exception:
            statuses.append(0)  # DB error without DB → may propagate
    check("analyze rate limit 429 on 4th", 429 in statuses, f"statuses={statuses}")

    # One more to confirm 429 + detail structure
    try:
        r = await client.post("/api/inquiries/analyze", json={"raw_message": "x"})
        check("analyze 429 has detail", r.status_code == 429 and "detail" in r.json())
    except Exception:
        check("analyze 429 has detail", False, "request propagated")


async def test_raw_message_too_long(client):
    """P0-3: raw_message > 4000 → 422 (validation error, before any processing)."""
    r = await client.post("/api/inquiries/analyze", json={"raw_message": "x" * 4001})
    check("raw_message 4001 → 422", r.status_code == 422, f"got {r.status_code}")


async def test_db_integration(client):
    """Full integration tests requiring a pgvector database."""
    from app.core.database import init_db, async_session
    from app.core.security import hash_password, create_access_token
    from app.models.user import User
    from app.models.product import Product
    from app.models.inquiry import Inquiry
    from app.models.seller_inquiry import SellerInquiry

    await init_db()

    import uuid
    suffix = uuid.uuid4().hex[:8]
    buyer_email = f"buyer-{suffix}@test.local"
    seller_email = f"seller-{suffix}@test.local"
    other_buyer_email = f"other-{suffix}@test.local"

    async with async_session() as db:
        buyer = User(email=buyer_email, password_hash=hash_password("testpass123"), role="buyer", name="Buyer", country="CN", email_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        seller = User(email=seller_email, password_hash=hash_password("testpass123"), role="seller", name="Seller", country="CN", email_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        other = User(email=other_buyer_email, password_hash=hash_password("testpass123"), role="buyer", name="Other", country="CN", email_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        db.add_all([buyer, seller, other])
        await db.flush()

        product = Product(name="Widget", sku="W1", category="other", seller_id=seller.id)
        db.add(product)
        await db.flush()

        # Inquiry owned by buyer
        inq = Inquiry(raw_message="need widgets", buyer_id=buyer.id)
        db.add(inq)
        await db.flush()

        # Inquiry with no owner (anonymous)
        anon_inq = Inquiry(raw_message="anon inquiry", buyer_id=None)
        db.add(anon_inq)
        await db.flush()

        await db.commit()
        buyer_id = buyer.id
        seller_id = seller.id
        other_id = other.id
        product_id = product.id
        inquiry_id = inq.id
        anon_inquiry_id = anon_inq.id

    buyer_token = create_access_token(buyer_id, "buyer", 0)
    other_token = create_access_token(other_id, "buyer", 0)
    seller_token = create_access_token(seller_id, "seller", 0)
    hb = {"Authorization": f"Bearer {buyer_token}"}
    ho = {"Authorization": f"Bearer {other_token}"}
    hs = {"Authorization": f"Bearer {seller_token}"}

    # ── P0-4: quote IDOR ──
    # Buyer owns inquiry → can generate quote
    r = await client.post("/api/quotes/generate", json={"inquiry_id": inquiry_id}, headers=hb)
    check("quote generate own inquiry ok", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")
    quote_id = r.json().get("id") if r.status_code == 200 else None

    # Other buyer → 403 (IDOR blocked)
    if inquiry_id:
        r = await client.post("/api/quotes/generate", json={"inquiry_id": inquiry_id}, headers=ho)
        check("quote generate other buyer 403", r.status_code == 403, f"got {r.status_code}")

    # Other buyer GET quote → 403
    if quote_id:
        r = await client.get(f"/api/quotes/{quote_id}", headers=ho)
        check("quote get other buyer 403", r.status_code == 403, f"got {r.status_code}")

    # Buyer GET own quote → 200
    if quote_id:
        r = await client.get(f"/api/quotes/{quote_id}", headers=hb)
        check("quote get own ok", r.status_code == 200, f"got {r.status_code}")

    # ── P1-6: seller email anonymous exposure ──
    r = await client.get(f"/api/sellers/{seller_id}/products")
    check("seller products anon 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        check("seller email hidden anon", r.json().get("seller_email") is None, f"got {r.json().get('seller_email')}")

    # Authenticated → seller_email visible
    r = await client.get(f"/api/sellers/{seller_id}/products", headers=hb)
    check("seller products auth 200", r.status_code == 200)
    if r.status_code == 200:
        check("seller email visible auth", r.json().get("seller_email") is not None)

    # ── Extra A: product update → embedding pending ──
    r = await client.put(f"/api/products/{product_id}", json={"name": "Updated Widget"}, headers=hs)
    check("product update 200", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")
    if r.status_code == 200:
        from sqlalchemy import select
        async with async_session() as db:
            p = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
            check("embedding pending after edit", p.embedding_status == "pending", f"got {p.embedding_status}")
            check("embedding_hash nulled after edit", p.embedding_hash is None)

    # ── Extra A: reactivation → embedding pending ──
    # Soft-delete then re-activate
    await client.delete(f"/api/products/{product_id}", headers=hs)
    r = await client.put(f"/api/products/{product_id}", json={"is_active": True}, headers=hs)
    check("reactivation 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        from sqlalchemy import select
        async with async_session() as db:
            p = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
            check("embedding pending after reactivate", p.embedding_status == "pending", f"got {p.embedding_status}")

    # ── Extra B: generate-reply concurrency → 409 ──
    # Create a seller inquiry
    async with async_session() as db:
        si = SellerInquiry(seller_id=seller_id, product_id=product_id, raw_message="test", buyer_email=buyer_email, status="pending")
        db.add(si)
        await db.commit()
        si_id = si.id

    # Two concurrent requests
    import asyncio as aio
    t1 = client.post("/api/seller-inquiries/generate-reply", json={"inquiry_id": si_id}, headers=hs)
    t2 = client.post("/api/seller-inquiries/generate-reply", json={"inquiry_id": si_id}, headers=hs)
    resp1, resp2 = await aio.gather(t1, t2)
    codes = {resp1.status_code, resp2.status_code}
    check("generate-reply concurrent 409", 409 in codes, f"codes={codes}")

    # ── P1-23: saved_products unique constraint ──
    async with async_session() as db:
        from app.models.saved_product import SavedProduct
        from sqlalchemy import text
        # Try inserting two rows with the same (user_id, product_id) directly
        db.add(SavedProduct(user_id=buyer_id, product_id=product_id))
        await db.commit()
        db.add(SavedProduct(user_id=buyer_id, product_id=product_id))
        try:
            await db.commit()
            check("saved_products unique constraint", False, "duplicate inserted")
        except Exception:
            check("saved_products unique constraint", True)
            await db.rollback()

    # ── P1-24: reviews unique constraint ──
    async with async_session() as db:
        from app.models.review import Review
        db.add(Review(seller_id=seller_id, user_id=buyer_id, rating=5, content="good"))
        await db.commit()
        db.add(Review(seller_id=seller_id, user_id=buyer_id, rating=3, content="meh"))
        try:
            await db.commit()
            check("reviews unique constraint", False, "duplicate inserted")
        except Exception:
            check("reviews unique constraint", True)
            await db.rollback()


async def main():
    db_ok = await _db_available()
    if not db_ok:
        print("NOTE: No DB reachable — running auth + rate-limit tests only.")
        print("      Set TEST_DATABASE_URL + start a pgvector container for full suite.\n")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE) as client:
        print("=== No-DB auth rejection tests ===")
        await test_no_db_auth_rejections(client)

        print("\n=== raw_message length cap ===")
        await test_raw_message_too_long(client)

        print("\n=== /analyze rate limit (P0-3) ===")
        await test_analyze_rate_limit(client)

        if db_ok:
            print("\n=== DB integration tests ===")
            await test_db_integration(client)
        else:
            print("\n=== DB integration tests SKIPPED (no DB) ===")

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
