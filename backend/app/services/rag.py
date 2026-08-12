from typing import Any


def search_products_keyword(
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
) -> list[tuple[dict[str, Any], float]]:
    query_lower = query.lower()
    raw_keywords = [kw for kw in query_lower.replace(",", " ").replace(".", " ").replace("/", " ").split() if len(kw) >= 2]
    # Deduplicate while preserving order
    seen = set()
    keywords = []
    for kw in raw_keywords:
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)

    def score_product(product: dict[str, Any]) -> float:
        name = (product.get("name") or "").lower()
        category = (product.get("category") or "").lower().replace("_", " ")
        desc = (product.get("description") or "").lower()
        specs = (product.get("technical_specs") or "").lower()
        certs = (product.get("certifications") or "").lower()

        score = 0.0
        for kw in keywords:
            # Name match is strongest
            if kw in name:
                score += 0.5
            # Category is contextual
            if kw in category:
                score += 0.25
            # Also check if keyword appears as part of a longer word (partial match)
            if kw not in name and kw not in category:
                if kw in desc:
                    score += 0.15
                if kw in specs:
                    score += 0.1
                if kw in certs:
                    score += 0.05

        # Give at least a base score for products in matching category
        if not score and query_lower in name or any(kw in name for kw in keywords):
            score = max(score, 0.1)

        return min(score, 1.0)

    scored = [(p, score_product(p)) for p in products]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(p, s) for p, s in scored[:top_k] if s > 0]


async def search_products_hybrid(
    query: str,
    products: list[dict[str, Any]],
    top_k: int = 5,
    vector_weight: float = 0.0,
) -> list[tuple[dict[str, Any], float]]:
    return search_products_keyword(query, products, top_k)
