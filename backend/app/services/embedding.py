"""
Embedding service — generates vector embeddings for products.

MVP: returns random vectors of configured dimension.
Future: Replace with OpenAI text-embedding-3-small or other embedding APIs.

Extension point:
    async def get_openai_embedding(text: str) -> list[float]:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=text)
        return resp.data[0].embedding
"""
import random
import hashlib
from app.core.config import settings


def _deterministic_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


async def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for given text.

    MVP: Produces deterministic pseudo-random vectors based on text hash
    to simulate consistent retrieval (same text produces same vector).
    """
    seed = _deterministic_seed(text)
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(settings.EMBEDDING_DIM)]


async def embed_product(product_id: int, product_text: str) -> list[float]:
    """
    Generate embedding for a product from its combined text fields.
    """
    return await generate_embedding(product_text)


def build_product_text(name: str, category: str, description: str, specs: str, certifications: str) -> str:
    """Combine product fields into a single text for embedding."""
    parts = [name, category]
    if description:
        parts.append(description)
    if specs:
        parts.append(specs)
    if certifications:
        parts.append(certifications)
    return " | ".join(parts)
