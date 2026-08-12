"""
RAG (Retrieval-Augmented Generation) service — retrieves relevant products
from the knowledge base using keyword matching.

Currently keyword-only; vector similarity is disabled.
Future: Add pgvector cosine similarity search when embedding is needed.
"""
from typing import Any


def search_products_keyword(
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
) -> list[tuple[dict[str, Any], float]]:
    query_lower = query.lower()
    keywords = [kw for kw in query_lower.replace(",", " ").replace(".", " ").split() if len(kw) >= 2]

    def score_product(product: dict[str, Any]) -> float:
        name = (product.get("name") or "").lower()
        category = (product.get("category") or "").lower()
        desc = (product.get("description") or "").lower()
        specs = (product.get("technical_specs") or "").lower()
        certs = (product.get("certifications") or "").lower()

        score = 0.0
        for kw in keywords:
            if kw in name:
                score += 0.6
            if kw in category:
                score += 0.15
            if kw in desc:
                score += 0.05
            if kw in specs:
                score += 0.1
            if kw in certs:
                score += 0.1
        return min(score, 1.0)

    scored = [(p, score_product(p)) for p in products]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


async def search_products_hybrid(
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
    vector_weight: float = 0.0,
) -> list[tuple[dict[str, Any], float]]:
    return search_products_keyword(query, products, top_k)
