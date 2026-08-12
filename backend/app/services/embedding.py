import hashlib
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session
from app.core.config import settings, is_embedding_available
from app.core.retry import embedding_api_call_with_retry
from app.models.product import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EMBED] %(message)s")
logger = logging.getLogger(__name__)

_init_logged = False


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


def embedding_needs_update(product: Product) -> bool:
    if product.embedding is None:
        return True
    if product.embedding_status == "failed":
        return True
    current_text = build_product_embedding_text(
        product.name or "",
        product.category or "",
        product.description or "",
        product.technical_specs or "",
        product.certifications or "",
    )
    new_hash = compute_embedding_hash(current_text)
    if product.embedding_hash != new_hash:
        return True
    if product.embedding_model != settings.EMBEDDING_MODEL:
        return True
    return False


async def process_pending_embeddings() -> dict:
    """Process all products that need embedding. Called by background worker."""
    global _init_logged
    if not is_embedding_available():
        if not _init_logged:
            logger.warning("EMBEDDING: not configured, skipping")
            _init_logged = True
        return {"status": "unavailable", "processed": 0, "failed": 0}

    if not _init_logged:
        logger.warning("EMBEDDING API: %s model=%s",
                       settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL,
                       settings.EMBEDDING_MODEL)
        _init_logged = True

    result = {"status": "completed", "processed": 0, "failed": 0}

    async with async_session() as db:
        while True:
            query = select(Product).where(
                Product.is_active == True,
                Product.embedding_status.in_(["pending", "failed"]),
            ).limit(settings.EMBEDDING_BATCH_SIZE)

            db_result = await db.execute(query)
            products = list(db_result.scalars().all())
            if not products:
                break

            texts_to_embed: list[tuple[int, str, str]] = []
            products_to_update: list[tuple[int, str]] = []

            for p in products:
                text = build_product_embedding_text(
                    p.name or "", p.category or "", p.description or "",
                    p.technical_specs or "", p.certifications or "",
                )
                new_hash = compute_embedding_hash(text)
                if p.embedding_hash == new_hash and p.embedding_model == settings.EMBEDDING_MODEL and p.embedding is not None:
                    await db.execute(
                        update(Product).where(Product.id == p.id).values(
                            embedding_status="completed", embedded_at=datetime.now(timezone.utc)
                        )
                    )
                    continue
                texts_to_embed.append((p.id, text, new_hash))

            if not texts_to_embed:
                await db.commit()
                continue

            try:
                batch_texts = [t[1] for t in texts_to_embed]
                vectors = await embedding_api_call_with_retry(batch_texts)

                processed = 0
                failed = 0
                for (pid, _, new_hash), vec in zip(texts_to_embed, vectors):
                    if vec and len(vec) > 0:
                        await db.execute(
                            update(Product).where(Product.id == pid).values(
                                embedding=vec,
                                embedding_hash=new_hash,
                                embedding_model=settings.EMBEDDING_MODEL,
                                embedding_status="completed",
                                embedded_at=datetime.now(timezone.utc),
                            )
                        )
                        processed += 1
                    else:
                        await db.execute(
                            update(Product).where(Product.id == pid).values(
                                embedding_status="failed"
                            )
                        )
                        failed += 1

                await db.commit()
                result["processed"] += processed
                result["failed"] += failed
                logger.warning("Batch: %d ok, %d failed", processed, failed)

            except Exception as e:
                await db.rollback()
                for pid, _, _ in texts_to_embed:
                    try:
                        await db.execute(
                            update(Product).where(Product.id == pid).values(
                                embedding_status="failed"
                            )
                        )
                    except Exception:
                        pass
                await db.commit()
                result["failed"] += len(texts_to_embed)
                logger.warning("Embedding batch failed: %s", str(e)[:200])
                result["status"] = "partial"

    if result["processed"] > 0 or result["failed"] > 0:
        logger.warning("Embedding run complete: %s", result)
    return result


async def generate_query_embedding(text: str) -> list[float]:
    """Generate embedding for a single query text. Only for inquiry matching."""
    if not is_embedding_available():
        raise RuntimeError("Embedding service is not configured")

    vectors = await embedding_api_call_with_retry([text])
    if not vectors or not vectors[0]:
        raise RuntimeError("Embedding API returned empty result")
    return vectors[0]


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
    failed = await db.execute(
        select(func.count(Product.id)).where(
            Product.is_active == True, Product.embedding_status == "failed"
        )
    )
    return {
        "total": total.scalar() or 0,
        "completed": completed.scalar() or 0,
        "pending": pending.scalar() or 0,
        "failed": failed.scalar() or 0,
    }
