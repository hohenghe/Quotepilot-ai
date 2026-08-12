import hashlib
import logging
import httpx
from app.core.config import settings, is_embedding_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EMBED] %(message)s")
logger = logging.getLogger(__name__)

_product_embeddings: dict[str, list[float]] = {}
_embed_logged = False


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _get_product_key(product_id: int, text: str) -> str:
    return f"{product_id}:{_text_hash(text)}"


def get_cached_embedding(product_id: int, text: str) -> list[float] | None:
    return _product_embeddings.get(_get_product_key(product_id, text))


def set_cached_embedding(product_id: int, text: str, vec: list[float]) -> None:
    _product_embeddings[_get_product_key(product_id, text)] = vec


def invalidate_product_embeddings(product_id: int) -> None:
    prefix = f"{product_id}:"
    keys = [k for k in _product_embeddings if k.startswith(prefix)]
    for k in keys:
        del _product_embeddings[k]


async def _batch_api_embedding(texts: list[str]) -> list[list[float]]:
    key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{url}/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": texts,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Embedding API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return [d.get("embedding", []) for d in data.get("data", [])]


async def compute_embeddings_batch(
    product_texts: list[tuple[int, str]],
) -> int:
    """Pre-compute embeddings for a batch of products. Returns count computed."""
    global _embed_logged
    if not is_embedding_available():
        return 0

    if not _embed_logged:
        logger.warning("EMBEDDING API: %s model=%s", settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL, settings.EMBEDDING_MODEL)
        _embed_logged = True

    uncached = [(pid, text) for pid, text in product_texts if get_cached_embedding(pid, text) is None]
    if not uncached:
        return 0

    batch_size = 100
    computed = 0
    for i in range(0, len(uncached), batch_size):
        batch = uncached[i:i + batch_size]
        texts = [text for _, text in batch]
        try:
            vectors = await _batch_api_embedding(texts)
            for (pid, text), vec in zip(batch, vectors):
                if vec:
                    set_cached_embedding(pid, text, vec)
                    computed += 1
        except Exception as e:
            logger.warning("Batch embedding failed at offset %d: %s", i, e)
            break

    if computed:
        logger.warning("Embedded %d products (total cache: %d)", computed, len(_product_embeddings))
    return computed


async def generate_embedding(text: str) -> list[float]:
    cache_key = text[:500]
    if is_embedding_available():
        try:
            key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
            url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{url}/embeddings",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {key}",
                    },
                    json={"model": settings.EMBEDDING_MODEL, "input": text},
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"Embedding API error {resp.status_code}")
                data = resp.json()
                return data.get("data", [{}])[0].get("embedding", [])
        except Exception as e:
            logger.warning("Embedding API failed, using mock: %s", e)

    import random
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(settings.EMBEDDING_DIM)]
