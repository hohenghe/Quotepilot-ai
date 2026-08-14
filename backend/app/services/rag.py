import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import is_embedding_available
from app.services.embedding import generate_query_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [RAG] %(message)s")
logger = logging.getLogger(__name__)

_rag_logged = False


def _keyword_score(query: str, product: dict[str, Any]) -> float:
    query_lower = query.lower()
    keywords = list(dict.fromkeys(
        kw for kw in query_lower.replace(",", " ").replace(".", " ").replace("/", " ").split()
        if len(kw) >= 2
    ))
    name = (product.get("name") or "").lower()
    category = (product.get("category") or "").lower().replace("_", " ")
    desc = (product.get("description") or "").lower()
    specs = (product.get("technical_specs") or "").lower()
    certs = (product.get("certifications") or "").lower()

    score = 0.0
    for kw in keywords:
        if kw in name:
            score += 0.5
        if kw in category:
            score += 0.25
        if kw in desc:
            score += 0.15
        if kw in specs:
            score += 0.1
        if kw in certs:
            score += 0.05
    return min(score, 1.0)


async def search_products_hybrid(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    candidate_limit: int = 50,
) -> list[dict[str, Any]]:
    """Hybrid search: pgvector cosine similarity + keyword reranking."""
    global _rag_logged
    use_vector = is_embedding_available()

    if use_vector:
        if not _rag_logged:
            logger.warning("SEARCH MODE: vector + keyword on DB")
            _rag_logged = True

        try:
            query_vec = await generate_query_embedding(query)
        except Exception as e:
            logger.warning("Query embedding failed, falling back to keyword-only: %s", str(e)[:200])
            use_vector = False
            # Return a special indicator
    else:
        if not _rag_logged:
            logger.warning("SEARCH MODE: keyword-only on DB")
            _rag_logged = True

    if use_vector and query_vec:
        # pgvector cosine distance search: <=> returns cosine distance
        # Convert to parameter array format
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        sql = text(f"""
            SELECT id, name, sku, category, description, technical_specs, certifications,
                   moq, unit_price, price_range_low, price_range_high, pricing, lead_time_days,
                   seller_id, embedding_status,
                   1 - (embedding <=> :vec ::vector) AS vector_score
            FROM products
            WHERE is_active = true AND embedding_status = 'completed'
            ORDER BY embedding <=> :vec ::vector
            LIMIT :limit
        """)
        result = await db.execute(sql, {"vec": vec_str, "limit": candidate_limit})
        rows = result.fetchall()
    else:
        rows = []

    # Build product dicts from vector search results OR from keyword-only fallback
    if rows:
        candidates = []
        for row in rows:
            d = {
                "id": row.id,
                "name": row.name,
                "sku": row.sku,
                "category": row.category,
                "description": row.description,
                "technical_specs": row.technical_specs,
                "certifications": row.certifications,
                "moq": row.moq,
                "unit_price": row.unit_price,
                "price_range_low": row.price_range_low,
                "price_range_high": row.price_range_high,
                "pricing": row.pricing,
                "lead_time_days": row.lead_time_days,
                "seller_id": row.seller_id,
                "_vector_score": float(row.vector_score) if hasattr(row, "vector_score") else 0.5,
            }
            candidates.append(d)
    else:
        # Keyword-only fallback: load all active products
        from sqlalchemy import select
        from app.models.product import Product
        result = await db.execute(
            select(Product).where(Product.is_active == True).limit(candidate_limit * 2)
        )
        all_products = list(result.scalars().all())
        candidates = [
            {
                "id": p.id, "name": p.name, "sku": p.sku, "category": p.category,
                "description": p.description, "technical_specs": p.technical_specs,
                "certifications": p.certifications, "moq": p.moq,
                "unit_price": p.unit_price, "price_range_low": p.price_range_low,
                "price_range_high": p.price_range_high, "pricing": p.pricing,
                "lead_time_days": p.lead_time_days, "seller_id": p.seller_id,
                "_vector_score": 0.5,
            }
            for p in all_products
        ]

    # Hybrid scoring: combine vector + keyword
    scored = []
    vector_weight = 0.6 if use_vector else 0.0
    for p in candidates:
        vs = p.get("_vector_score", 0.5)
        ks = _keyword_score(query, p)
        combined = vector_weight * vs + (1 - vector_weight) * ks
        scored.append((p, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    results = [(p, s) for p, s in scored[:top_k] if s > 0]

    if results:
        logger.warning("RESULTS: %d matched (scores: %s)",
                       len(results), ", ".join(f"{s:.2f}" for _, s in results[:5]))

    return [
        {
            "product_id": p["id"],
            "product_name": p["name"],
            "seller_id": p.get("seller_id"),
            "sku": p.get("sku"),
            "match_score": round(s, 3),
            "match_reason": "",
            "moq": p.get("moq"),
            "unit_price": p.get("unit_price"),
            "price_range_low": p.get("price_range_low"),
            "price_range_high": p.get("price_range_high"),
            "pricing": p.get("pricing"),
            "lead_time_days": p.get("lead_time_days"),
            "certifications": p.get("certifications"),
            "technical_specs": p.get("technical_specs"),
        }
        for p, s in results
    ]
