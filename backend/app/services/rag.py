"""
RAG (Retrieval-Augmented Generation) service — retrieves relevant products
from the knowledge base using vector similarity search.

MVP: uses deterministic scoring based on keyword overlap and embedding similarity.
Future: Replace with pgvector cosine similarity search.

Extension point:
    async def pgvector_search(embedding: list[float], top_k: int, db):
        result = await db.execute(
            text("SELECT product_id, 1 - (embedding <=> :embedding) AS similarity FROM product_vectors ORDER BY similarity DESC LIMIT :k"),
            {"embedding": embedding, "k": top_k}
        )
        return result.fetchall()
"""
from typing import Any
from app.services.embedding import generate_embedding


async def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def search_products(
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
) -> list[tuple[dict[str, Any], float]]:
    """
    Search products by query using mock embedding similarity.

    Args:
        query: The search/inquiry text
        products: List of product dicts with at least 'name', 'category', 'description' keys
        top_k: Number of top results to return

    Returns:
        List of (product_dict, similarity_score) sorted by score descending
    """
    query_vec = await generate_embedding(query)
    results = []

    for p in products:
        product_text = f"{p.get('name', '')} {p.get('category', '')} {p.get('description', '')} {p.get('technical_specs', '')}"
        product_vec = await generate_embedding(product_text)
        sim = await cosine_similarity(query_vec, product_vec)
        results.append((p, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def _keyword_match_score(query: str, product: dict[str, Any]) -> float:
    """Simple keyword-based relevance score as supplement."""
    query_lower = query.lower()
    score = 0.0

    name = (product.get("name") or "").lower()
    category = (product.get("category") or "").lower()
    desc = (product.get("description") or "").lower()
    specs = (product.get("technical_specs") or "").lower()
    certs = (product.get("certifications") or "").lower()

    keywords = query_lower.replace(",", " ").replace(".", " ").split()
    for kw in keywords:
        if len(kw) < 3:
            continue
        if kw in name:
            score += 0.3
        if kw in category:
            score += 0.2
        if kw in desc:
            score += 0.1
        if kw in specs:
            score += 0.15
        if kw in certs:
            score += 0.1

    return min(score, 1.0)


async def search_products_hybrid(
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
    vector_weight: float = 0.7,
) -> list[tuple[dict[str, Any], float]]:
    """
    Hybrid search combining vector similarity and keyword matching.
    """
    query_vec = await generate_embedding(query)
    results = []

    for p in products:
        product_text = f"{p.get('name', '')} {p.get('category', '')} {p.get('description', '')} {p.get('technical_specs', '')}"
        product_vec = await generate_embedding(product_text)
        vs = (await cosine_similarity(query_vec, product_vec) + 1) / 2
        ks = _keyword_match_score(query, p)
        combined = vector_weight * vs + (1 - vector_weight) * ks
        results.append((p, combined))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]
