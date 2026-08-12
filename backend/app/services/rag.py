from typing import Any
from app.services.embedding import generate_embedding
from app.core.config import is_embedding_available


async def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


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
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
    vector_weight: float = 0.0,
) -> list[tuple[dict[str, Any], float]]:
    use_vector = is_embedding_available()
    if use_vector:
        vector_weight = 0.6
    else:
        vector_weight = 0.0

    query_vec = None
    if use_vector:
        try:
            query_vec = await generate_embedding(query)
        except Exception:
            use_vector = False
            vector_weight = 0.0

    results = []
    for p in products:
        vs = 0.5
        if use_vector and query_vec:
            product_text = f"{p.get('name', '')} {p.get('category', '')} {p.get('description', '')} {p.get('technical_specs', '')}"
            product_vec = await generate_embedding(product_text)
            vs = (await cosine_similarity(query_vec, product_vec) + 1) / 2

        ks = _keyword_score(query, p)
        combined = vector_weight * vs + (1 - vector_weight) * ks
        results.append((p, combined))

    results.sort(key=lambda x: x[1], reverse=True)
    return [(p, s) for p, s in results[:top_k] if s > 0]
