import random
import hashlib
import logging
import httpx
from app.core.config import settings, is_embedding_available

logger = logging.getLogger(__name__)


def _deterministic_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def _mock_embedding(text: str) -> list[float]:
    seed = _deterministic_seed(text)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(settings.EMBEDDING_DIM)]


async def _api_embedding(text: str) -> list[float]:
    key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{url}/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": text,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Embedding API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data.get("data", [{}])[0].get("embedding", [])


_cache: dict[str, list[float]] = {}


async def generate_embedding(text: str) -> list[float]:
    cache_key = text[:500]
    if cache_key in _cache:
        return _cache[cache_key]

    if is_embedding_available():
        try:
            vec = await _api_embedding(text)
            _cache[cache_key] = vec
            return vec
        except Exception as e:
            logger.warning("Embedding API failed, using mock: %s", e)

    vec = _mock_embedding(text)
    _cache[cache_key] = vec
    return vec


async def embed_product(product_id: int, product_text: str) -> list[float]:
    return await generate_embedding(product_text)


def build_product_text(name: str, category: str, description: str, specs: str, certifications: str) -> str:
    parts = [name, category]
    if description:
        parts.append(description)
    if specs:
        parts.append(specs)
    if certifications:
        parts.append(certifications)
    return " | ".join(parts)
