"""Rank suppliers by catalog relevance; customization requires confirmation."""


def select_supplier_matches(matches: list[dict], seller_names: dict, limit: int = 5) -> list[dict]:
    selected = []
    seen = set()
    for match in sorted(matches, key=lambda item: item.get("match_score", 0), reverse=True):
        seller_id = match.get("seller_id")
        if not seller_id or seller_id not in seller_names or seller_id in seen:
            continue
        if match.get("match_score", 0) <= 0:
            continue
        seen.add(seller_id)
        selected.append(match)
        if len(selected) >= limit:
            break
    return selected
