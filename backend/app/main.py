"""
QuotePilot AI — Backend API Server
Main application entry point.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.api.products import router as products_router
from app.api.inquiries import router as inquiries_router
from app.api.quotes import router as quotes_router
from app.api.dashboard import router as dashboard_router
from app.api.auth import router as auth_router
from app.api.seller_inquiries import router as seller_inquiries_router
from app.api.admin import router as admin_router
from app.api.saved_products import router as saved_products_router
from app.api.reviews import router as reviews_router
from app.api.files import router as files_router
from app.api.sellers import router as sellers_router
from app.api.wechat import router as wechat_router
from app.api.phones import router as phones_router
from app.api.ai import router as ai_router

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_cleanup_task: asyncio.Task | None = None


async def _embedding_worker():
    """Background worker: periodically process pending product embeddings."""
    while True:
        try:
            from app.services.embedding import process_pending_embeddings
            result = await process_pending_embeddings()
            if result["processed"] == 0 and result["failed"] == 0:
                await asyncio.sleep(30)
            else:
                await asyncio.sleep(5)
        except Exception:
            await asyncio.sleep(30)


async def _account_cleanup_worker():
    """Background worker: periodically purge abandoned unverified seller accounts."""
    from app.services.account_cleanup import (
        cleanup_expired_unverified_sellers,
        CLEANUP_INTERVAL_SECONDS,
    )
    while True:
        try:
            result = await cleanup_expired_unverified_sellers()
            if result["deleted"]:
                logger.info(
                    "Purged %s unverified seller account(s) and %s WeChat binding(s)",
                    result["deleted"],
                    result.get("wechat_deleted", 0),
                )
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        except Exception:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def _close_ai_client():
    try:
        from app.services.vision import close_ai_client
        await close_ai_client()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task
    global _cleanup_task
    await init_db()
    await _reset_stuck_embeddings()
    await _ensure_admin()
    await _ensure_test_accounts()
    _worker_task = asyncio.create_task(_embedding_worker())
    _cleanup_task = asyncio.create_task(_account_cleanup_worker())
    yield
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    await _close_ai_client()


async def _ensure_admin():
    """Auto-create the admin account on startup if it doesn't exist."""
    try:
        from seed_admin import create_admin
        await create_admin()
    except Exception:
        pass


async def _ensure_test_accounts():
    """Auto-create test accounts (seller + admin) on startup if they don't exist."""
    try:
        from seed_admin import create_test_accounts
        await create_test_accounts()
    except Exception:
        pass


async def _reset_stuck_embeddings():
    """Reset products stuck in 'processing' (from a crashed worker) back to 'pending'."""
    from sqlalchemy import text
    from app.core.database import engine
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "UPDATE products SET embedding_status='pending' "
                "WHERE embedding_status='processing' AND is_active=true"
            ))
    except Exception:
        pass


app = FastAPI(
    title="QuotePilot AI",
    description="AI-powered sales assistant for international trade",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)
app.include_router(inquiries_router)
app.include_router(quotes_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(seller_inquiries_router)
app.include_router(admin_router)
app.include_router(saved_products_router)
app.include_router(reviews_router)
app.include_router(files_router)
app.include_router(sellers_router)
app.include_router(wechat_router)
app.include_router(phones_router)
app.include_router(ai_router)


@app.get("/")
async def root():
    return {"service": "QuotePilot AI", "version": "0.1.0", "status": "running"}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/debug/llm-status")
async def llm_status():
    from app.core.config import is_llm_available, settings
    return {
        "llm_available": is_llm_available(),
        "base_url": settings.OPENAI_BASE_URL,
        "model": settings.LLM_MODEL,
        "key_configured": bool(settings.OPENAI_API_KEY),
        "key_preview": (settings.OPENAI_API_KEY[:8] + "..." + settings.OPENAI_API_KEY[-4:]) if len(settings.OPENAI_API_KEY) > 12 else "NOT SET",
    }


@app.get("/api/debug/embedding-status")
async def embedding_status():
    from app.services.embedding import get_embedding_stats
    from app.core.database import async_session
    from app.core.config import is_embedding_available, settings
    async with async_session() as db:
        stats = await get_embedding_stats(db)
    return {
        "configured": is_embedding_available(),
        "model": settings.EMBEDDING_MODEL,
        "stats": stats,
    }
