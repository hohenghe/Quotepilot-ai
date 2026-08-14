import asyncio
import logging
import random
from typing import Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Status codes that should NOT be retried
FATAL_STATUSES = {400, 401, 403, 404}

# Status codes that should be retried
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class FatalEmbeddingError(RuntimeError):
    """Raised for permanent errors that must NOT be retried."""


async def embedding_api_call_with_retry(
    inputs: list[str],
) -> list[list[float]]:
    key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
    max_retries = settings.EMBEDDING_MAX_RETRIES

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=float(settings.EMBEDDING_TIMEOUT)) as client:
                resp = await client.post(
                    f"{url}/embeddings",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {key}",
                    },
                    json={"model": settings.EMBEDDING_MODEL, "input": inputs},
                )

            if resp.status_code == 200:
                data = resp.json()
                embeddings = [d.get("embedding", []) for d in data.get("data", [])]
                if len(embeddings) != len(inputs):
                    raise FatalEmbeddingError(
                        f"Mismatched response: got {len(embeddings)} vectors for {len(inputs)} inputs"
                    )
                return embeddings

            status = resp.status_code
            body = resp.text[:500]

            if status in FATAL_STATUSES:
                # Permanent error — do NOT retry
                raise FatalEmbeddingError(f"Fatal API error {status}: {body}") from None

            if status in RETRYABLE_STATUSES:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                last_error = RuntimeError(f"Retryable API error {status}: {body}")
                logger.warning(
                    "Embedding batch attempt %d/%d failed (HTTP %d), retrying in %.1fs",
                    attempt + 1, max_retries + 1, status, retry_after
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_after)
                continue

            raise FatalEmbeddingError(f"Unexpected API error {status}: {body}") from None

        except FatalEmbeddingError:
            raise

        except httpx.TimeoutException:
            delay = _backoff_delay(attempt)
            last_error = RuntimeError(f"Request timeout after {settings.EMBEDDING_TIMEOUT}s")
            logger.warning(
                "Embedding batch attempt %d/%d timed out, retrying in %.1fs",
                attempt + 1, max_retries + 1, delay
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
            continue

        except httpx.ConnectError as e:
            delay = _backoff_delay(attempt)
            last_error = RuntimeError(f"Connection failed: {e}")
            logger.warning(
                "Embedding batch attempt %d/%d connection error, retrying in %.1fs",
                attempt + 1, max_retries + 1, delay
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
            continue

        except Exception as e:
            delay = _backoff_delay(attempt)
            last_error = e
            logger.warning(
                "Embedding batch attempt %d/%d error: %s, retrying in %.1fs",
                attempt + 1, max_retries + 1, str(e)[:200], delay
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
            continue

    raise RuntimeError(f"All {max_retries + 1} embedding attempts failed") from last_error


def _backoff_delay(attempt: int) -> float:
    base = 1.0 + random.uniform(0, 1)
    exp = min(2.0 ** attempt, 30.0)
    return base * exp


def _parse_retry_after(header: str | None) -> float:
    if not header:
        return 2.0
    try:
        return float(header)
    except ValueError:
        return 2.0
