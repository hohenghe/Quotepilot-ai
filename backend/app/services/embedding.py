import hashlib
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only
from app.core.database import async_session
from app.core.config import settings, is_embedding_available
from app.core.retry import embedding_api_call_with_retry
from app.models.product import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EMBED] %(message)s")
logger = logging.getLogger(__name__)

_init_logged = False

# Lightweight in-memory cache for query embeddings (repeated identical queries
# don't re-hit the embedding API). Bounded, FIFO eviction; keyed by model+dim+text.
_query_embedding_cache: dict[str, list[float]] = {}
_QUERY_EMBEDDING_CACHE_MAX = 256


def build_product_embedding_text(
    name: str = "",
    category: str = "",
    description: str = "",
    technical_specs: str = "",
    certifications: str = "",
) -> str:
    parts = [name, category]
    if description:
        parts.append(description)
    if technical_specs:
        parts.append(technical_specs)
    if certifications:
        parts.append(certifications)
    return " | ".join(p for p in parts if p)


def compute_embedding_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _product_embedding_text(p: Product) -> str:
    return build_product_embedding_text(
        p.name or "", p.category or "", p.description or "",
        p.technical_specs or "", p.certifications or "",
    )


async def _recheck_product(db: AsyncSession, product_id: int) -> int | None:
    """Check active membership without loading product text, images or vectors."""
    result = await db.execute(
        select(Product.id).where(Product.id == product_id, Product.is_active == True)
    )
    return result.scalar_one_or_none()


async def process_pending_embeddings() -> dict:
    """Process products whose embedding_status is 'pending'.
    Products marked 'failed' are NOT auto-retried; they require explicit reset
    (content change, model change, or admin action)."""
    global _init_logged
    if not is_embedding_available():
        if not _init_logged:
            logger.warning("EMBEDDING: not configured, skipping")
            _init_logged = True
        return {"status": "unavailable", "processed": 0, "failed": 0}

    if not _init_logged:
        logger.warning("EMBEDDING API: %s model=%s dim=%s",
                       settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL,
                       settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM)
        _init_logged = True

    result = {"status": "completed", "processed": 0, "failed": 0}

    async with async_session() as db:
        # Only claim 'pending' products — never auto-retry 'failed'.
        query = (
            select(Product, Product.embedding.is_not(None).label("has_embedding"))
            .options(load_only(
                Product.id, Product.name, Product.category, Product.description,
                Product.technical_specs, Product.certifications,
                Product.embedding_hash, Product.embedding_model,
            ))
            .where(Product.is_active == True, Product.embedding_status == "pending")
            .order_by(Product.id)
            .limit(settings.EMBEDDING_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        db_result = await db.execute(query)
        rows = db_result.all()
        products = [p for p, _ in rows]
        has_embedding = {p.id: present for p, present in rows}

        if not products:
            return result

        # Row locks make the claim exclusive across API processes. Release them
        # before the slow network call so product edits remain responsive.
        claimed_ids = [p.id for p in products]
        await db.execute(
            update(Product).where(Product.id.in_(claimed_ids)).values(
                embedding_status="processing"
            )
        )
        await db.commit()

        # Build text + hash for each
        tasks = []
        for p in products:
            text = _product_embedding_text(p)
            new_hash = compute_embedding_hash(text)
            # Skip if hash+model already matches and embedding exists
            if (
                has_embedding[p.id]
                and p.embedding_hash == new_hash
                and p.embedding_model == settings.EMBEDDING_MODEL
            ):
                await db.execute(
                    update(Product).where(
                        Product.id == p.id, Product.is_active == True,
                        Product.embedding_status == "processing",
                    ).values(
                        embedding_status="completed", embedded_at=datetime.now(timezone.utc)
                    )
                )
                continue
            tasks.append((p.id, text, new_hash))

        await db.commit()

        if not tasks:
            return result

        # Send batch to API
        try:
            batch_texts = [t[1] for t in tasks]
            vectors = await embedding_api_call_with_retry(batch_texts)
            if len(vectors) != len(tasks):
                raise ValueError("Embedding API returned a different number of vectors")

            # Validate dimension
            if vectors and vectors[0]:
                actual_dim = len(vectors[0])
                if actual_dim != settings.EMBEDDING_DIM:
                    logger.warning(
                        "EMBEDDING dimension mismatch: got %d, config %d. Marking batch failed.",
                        actual_dim, settings.EMBEDDING_DIM,
                    )
                    failed_ids = [pid for pid, _, _ in tasks]
                    failed_result = await db.execute(
                        update(Product).where(
                            Product.id.in_(failed_ids), Product.is_active == True,
                            Product.embedding_status == "processing",
                        ).values(
                            embedding_status="failed",
                            embedding_error=f"dimension mismatch: got {actual_dim}, expected {settings.EMBEDDING_DIM}",
                        )
                    )
                    await db.commit()
                    result["failed"] += failed_result.rowcount or 0
                    result["status"] = "partial"
                    return result

            processed = 0
            failed = 0
            for (pid, _, new_hash), vec in zip(tasks, vectors):
                # A concurrent edit moves the row back to pending; a delete
                # moves it to skipped. Neither may receive this stale vector.
                guard = (Product.id == pid, Product.is_active == True,
                         Product.embedding_status == "processing")
                if vec and len(vec) == settings.EMBEDDING_DIM:
                    write_result = await db.execute(
                        update(Product).where(*guard).values(
                            embedding=vec,
                            embedding_hash=new_hash,
                            embedding_model=settings.EMBEDDING_MODEL,
                            embedding_status="completed",
                            embedding_retry_count=0,
                            embedding_error=None,
                            embedded_at=datetime.now(timezone.utc),
                        )
                    )
                    processed += write_result.rowcount or 0
                else:
                    write_result = await db.execute(
                        update(Product).where(*guard).values(
                            embedding_status="failed",
                            embedding_error="empty or wrong-dimension vector",
                        )
                    )
                    failed += write_result.rowcount or 0

            await db.commit()
            result["processed"] += processed
            result["failed"] += failed
            if failed:
                result["status"] = "partial"
            logger.warning("EMBEDDING batch: %d ok, %d failed", processed, failed)

        except Exception as e:
            await db.rollback()
            # Permanent failure after all retries → mark failed, DON'T auto-retry
            failed_result = await db.execute(
                update(Product).where(
                    Product.id.in_([pid for pid, _, _ in tasks]),
                    Product.is_active == True,
                    Product.embedding_status == "processing",
                ).values(
                    embedding_status="failed",
                    embedding_error=str(e)[:500],
                )
            )
            await db.commit()
            result["failed"] += failed_result.rowcount or 0
            result["status"] = "partial"
            logger.warning("EMBEDDING batch permanently failed: %s", str(e)[:200])

    if result["processed"] > 0 or result["failed"] > 0:
        logger.warning("EMBEDDING run: %s", result)
    return result


async def generate_query_embedding(text: str, max_retries: int | None = None) -> list[float]:
    """Generate embedding for a single query text. Only for inquiry matching.

    max_retries overrides settings.EMBEDDING_MAX_RETRIES so the synchronous
    /analyze path can use a smaller value than the background worker."""
    if not is_embedding_available():
        raise RuntimeError("Embedding service is not configured")

    cache_key = f"{settings.EMBEDDING_MODEL}|{settings.EMBEDDING_DIM}|{text}"
    cached = _query_embedding_cache.get(cache_key)
    if cached is not None:
        return cached

    vectors = await embedding_api_call_with_retry([text], max_retries=max_retries)
    if not vectors or not vectors[0]:
        raise RuntimeError("Embedding API returned empty result")
    if len(vectors[0]) != settings.EMBEDDING_DIM:
        raise RuntimeError(
            f"Embedding dimension mismatch: got {len(vectors[0])}, expected {settings.EMBEDDING_DIM}"
        )
    vec = vectors[0]

    if len(_query_embedding_cache) >= _QUERY_EMBEDDING_CACHE_MAX:
        _query_embedding_cache.pop(next(iter(_query_embedding_cache)))
    _query_embedding_cache[cache_key] = vec
    return vec


async def get_embedding_stats(db: AsyncSession) -> dict:
    from sqlalchemy import func
    total = await db.execute(select(func.count(Product.id)).where(Product.is_active == True))
    completed = await db.execute(
        select(func.count(Product.id)).where(
            Product.is_active == True, Product.embedding_status == "completed"
        )
    )
    pending = await db.execute(
        select(func.count(Product.id)).where(
            Product.is_active == True, Product.embedding_status == "pending"
        )
    )
    processing = await db.execute(
        select(func.count(Product.id)).where(
            Product.is_active == True, Product.embedding_status == "processing"
        )
    )
    failed = await db.execute(
        select(func.count(Product.id)).where(
            Product.is_active == True, Product.embedding_status == "failed"
        )
    )
    return {
        "total": total.scalar() or 0,
        "completed": completed.scalar() or 0,
        "pending": pending.scalar() or 0,
        "processing": processing.scalar() or 0,
        "failed": failed.scalar() or 0,
    }
