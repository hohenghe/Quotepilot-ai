"""ZherMai cross-lingual retrieval benchmark.

Purpose: verify whether the production embedding model `text-embedding-v4`
(1024 dimensions) can map an English buyer query close to a Chinese seller
product — WITHOUT any translation step — using the SAME embedding code path as
production.

It reuses:
  - `build_product_embedding_text`  (canonical product text)
  - `parse_file`                     (same CSV parsing as seller upload)
  - `embedding_api_call_with_retry`  (production embedding API wrapper)

Three test groups over the SAME product catalog:
  A: Chinese query      -> Chinese product
  B: English query      -> Chinese product   (cross-lingual, no translation)
  C: translated Chinese -> Chinese product   (translation-first baseline)

The C queries are already provided in the JSON; this benchmark never calls a
translation model.

Usage (from backend/):
    python scripts/benchmark_retrieval.py
    python scripts/benchmark_retrieval.py --no-cache
    python scripts/benchmark_retrieval.py --top-k 20

Exit codes: 0 = completed, 2 = configuration error, 3 = API/runtime error.
"""
import argparse
import asyncio
import hashlib
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings, is_embedding_available  # noqa: E402
from app.services.embedding import build_product_embedding_text  # noqa: E402
from app.services.file_parser import parse_file  # noqa: E402
from app.core.retry import embedding_api_call_with_retry  # noqa: E402

# Ensure non-ASCII output (Chinese text, checkmarks) renders on Windows GBK consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EXPECTED_MODEL = "text-embedding-v4"
EXPECTED_DIM = 1024

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sample_data")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cache", "embedding_benchmark")

GROUP_LABELS = {
    "A": "A Chinese",
    "B": "B English",
    "C": "C Translated",
}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# --- cache -----------------------------------------------------------------

def _cache_key(text: str, text_type: str | None) -> str:
    raw = f"{settings.EMBEDDING_MODEL}|{settings.EMBEDDING_DIM}|{text_type or 'none'}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, key + ".json")


def _cache_load(text: str, text_type: str | None) -> list[float] | None:
    key = _cache_key(text, text_type)
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if (
            data.get("text") == text
            and data.get("model") == settings.EMBEDDING_MODEL
            and data.get("dim") == settings.EMBEDDING_DIM
            and data.get("text_type") == (text_type or "none")
        ):
            return data.get("vector")
    except Exception:
        return None
    return None


def _cache_save(text: str, text_type: str | None, vector: list[float]) -> None:
    key = _cache_key(text, text_type)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(key), "w", encoding="utf-8") as f:
        json.dump({
            "model": settings.EMBEDDING_MODEL,
            "dim": settings.EMBEDDING_DIM,
            "text_type": text_type or "none",
            "text": text,
            "vector": vector,
        }, f)


async def _embed_many(
    texts: list[str],
    text_type: str | None,
    use_cache: bool,
) -> tuple[list[list[float]], int]:
    """Embed texts in one batch API call, using a local cache per text.
    Returns (vectors in original order, number of API calls made)."""
    if not texts:
        return [], 0

    result: list[list[float] | None] = [None] * len(texts)
    uncached_idx: list[int] = []
    uncached_texts: list[str] = []

    for i, t in enumerate(texts):
        if use_cache:
            vec = _cache_load(t, text_type)
            if vec is not None:
                result[i] = vec
                continue
        uncached_idx.append(i)
        uncached_texts.append(t)

    calls = 0
    if uncached_texts:
        # DashScope text-embedding-v4 caps each request at EMBEDDING_BATCH_SIZE
        # (10) inputs, so chunk the batch the same way the production worker does.
        batch_size = settings.EMBEDDING_BATCH_SIZE
        for start in range(0, len(uncached_texts), batch_size):
            chunk_texts = uncached_texts[start:start + batch_size]
            chunk_idx = uncached_idx[start:start + batch_size]
            vectors = await embedding_api_call_with_retry(chunk_texts, text_type=text_type)
            if len(vectors) != len(chunk_texts):
                raise RuntimeError("Embedding API returned a mismatched number of vectors")
            for pos, vec in zip(chunk_idx, vectors):
                result[pos] = vec
                if use_cache:
                    _cache_save(texts[pos], text_type, vec)
            calls += 1

    return [v for v in result if v is not None], calls  # type: ignore[list-item]


# --- data ------------------------------------------------------------------

async def _load_products() -> list[dict]:
    path = os.path.join(DATA_DIR, "crosslingual_products.csv")
    with open(path, "rb") as f:
        content = f.read()
    return await parse_file("crosslingual_products.csv", content)


async def _load_queries() -> list[dict]:
    path = os.path.join(DATA_DIR, "crosslingual_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- metrics ---------------------------------------------------------------

def _group_metrics(entries: list[dict]) -> dict:
    n = len(entries)
    ranks = [e["rank"] for e in entries if e["rank"] is not None]
    sims = [e["sim"] for e in entries]

    def recall(k: int) -> float:
        return sum(1 for r in ranks if r <= k) / n

    return {
        "r1": recall(1),
        "r5": recall(5),
        "r10": recall(10),
        "mrr": sum(1 / r for r in ranks) / n,
        "mean_sim": statistics.mean(sims) if sims else 0.0,
        "median_sim": statistics.median(sims) if sims else 0.0,
        "min_sim": min(sims) if sims else 0.0,
        "max_sim": max(sims) if sims else 0.0,
        "mean_rank": statistics.mean(ranks) if ranks else float("inf"),
        "median_rank": statistics.median(ranks) if ranks else float("inf"),
    }


# --- main ------------------------------------------------------------------

async def main() -> int:
    args = _parse_args()

    products = await _load_products()
    queries = await _load_queries()

    names = [p["name"] for p in products]
    name_to_id = {name: f"P{idx + 1:03d}" for idx, name in enumerate(names)}
    for q in queries:
        if q["expected_product"] not in name_to_id:
            print(f"ERROR: expected_product not found in CSV: {q['expected_product']}")
            return 2

    # --- configuration guard: must be the production target ---
    print("=" * 60)
    print("ZherMai Cross-Lingual Retrieval Benchmark")
    print("=" * 60)

    if settings.EMBEDDING_MODEL != EXPECTED_MODEL or settings.EMBEDDING_DIM != EXPECTED_DIM:
        print("\nERROR: current embedding configuration is NOT the production test target.")
        print(f"  EMBEDDING_MODEL = {settings.EMBEDDING_MODEL!r} (expected {EXPECTED_MODEL!r})")
        print(f"  EMBEDDING_DIM   = {settings.EMBEDDING_DIM} (expected {EXPECTED_DIM})")
        print("\nFix your environment, e.g.:")
        print(f"  EMBEDDING_MODEL={EXPECTED_MODEL}")
        print(f"  EMBEDDING_DIM={EXPECTED_DIM}")
        print("  EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")
        print("  EMBEDDING_API_KEY=<your DashScope key>")
        print("\nAborting: refusing to benchmark with the wrong model/dimension.")
        return 2

    if not is_embedding_available():
        print("\nERROR: DASHSCOPE_API_KEY / EMBEDDING_API_KEY is not configured.")
        print("Set EMBEDDING_API_KEY and EMBEDDING_BASE_URL "
              "(https://dashscope.aliyuncs.com/compatible-mode/v1).")
        return 2

    base_url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
    print(f"\nModel:     {settings.EMBEDDING_MODEL}")
    print(f"Dimension: {settings.EMBEDDING_DIM}")
    print(f"Base URL:  {base_url}")
    print(f"Products:  {len(products)}")
    print(f"Queries:   {len(queries)}")
    print(f"Cache:     {'enabled' if not args.no_cache else 'disabled'}")
    print(f"text_type: {'query/document' if not args.no_text_type else 'off'}")

    use_text_type = not args.no_text_type

    # --- smoke test: verify model returns 1024-dim vectors ---
    print("\n--- smoke test ---")
    smoke_zh = "304不锈钢保温杯"
    smoke_en = "304 stainless steel insulated bottle"
    try:
        if use_text_type:
            doc_vecs = await embedding_api_call_with_retry([smoke_zh], text_type="document")
            q_vecs = await embedding_api_call_with_retry([smoke_en], text_type="query")
            smoke_vecs = [doc_vecs[0], q_vecs[0]]
        else:
            smoke_vecs = await embedding_api_call_with_retry([smoke_zh, smoke_en])
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: smoke test API call failed: {str(exc)[:300]}")
        return 3

    for text, vec in zip([smoke_zh, smoke_en], smoke_vecs):
        if not vec or len(vec) != EXPECTED_DIM:
            print(f"FAIL: smoke test returned dimension {len(vec) if vec else 0}, expected {EXPECTED_DIM}.")
            print("Aborting: do not continue the benchmark.")
            return 3
    print(f"OK: smoke test returned {EXPECTED_DIM}-dim vectors for both Chinese and English text.")

    # --- embed products (document) ---
    texts = [
        build_product_embedding_text(
            p["name"],
            p.get("category") or "other",
            p.get("description") or "",
            p.get("technical_specs") or "",
            p.get("certifications") or "",
        )
        for p in products
    ]
    print(f"\nEmbedding {len(texts)} products ...")
    try:
        product_vecs, p_calls = await _embed_many(
            texts, "document" if use_text_type else None, use_cache=not args.no_cache
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: product embedding failed: {str(exc)[:300]}")
        return 3

    # --- run queries ---
    query_texts = [q["query"] for q in queries]
    try:
        query_vecs, q_calls = await _embed_many(
            query_texts, "query" if use_text_type else None, use_cache=not args.no_cache
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: query embedding failed: {str(exc)[:300]}")
        return 3

    api_calls = 2 + p_calls + q_calls  # 2 smoke-test calls (or 1 when text_type off)
    if not use_text_type:
        api_calls = 1 + p_calls + q_calls

    # --- compute per-query ranking ---
    grouped: dict[str, list[dict]] = {"A": [], "B": [], "C": []}
    for qi, q in enumerate(queries):
        group = q["type"][0]
        expected_id = name_to_id[q["expected_product"]]
        expected_idx = names.index(q["expected_product"])

        qv = query_vecs[qi]
        sims = [_cosine(qv, pv) for pv in product_vecs]
        order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)
        top_ids = [name_to_id[names[i]] for i in order[: args.top_k]]
        top_sims = [round(sims[i], 4) for i in order[: args.top_k]]

        rank = None
        try:
            rank = order.index(expected_idx) + 1
        except ValueError:
            rank = None

        print("\n" + "=" * 50)
        print(f"Query {group}-{qi + 1:02d}")
        print("=" * 50)
        print(f"\nOriginal Query:\n{q['query']}")
        print(f"\nExpected Product:\n{expected_id} ({q['expected_product']})")
        print(f"\nTop {args.top_k}:")
        for pos, (pid, s) in enumerate(zip(top_ids, top_sims), 1):
            mark = "  ✓" if pid == expected_id else ""
            print(f"{pos:>3}. {pid}   similarity={s:.4f}{mark}")

        if rank is None:
            print(f"\n✗ Not in Top {args.top_k}")
        elif rank == 1:
            print("\n✓ Rank 1")
        elif rank <= 5:
            print(f"\n✓ Rank {rank}")
        elif rank <= args.top_k:
            print(f"\n✓ Rank {rank}")
        else:
            print(f"\n✗ Not in Top {args.top_k}")

        grouped[group].append({"rank": rank, "sim": sims[expected_idx]})

    # --- summary metrics ---
    metrics = {g: _group_metrics(grouped[g]) for g in ("A", "B", "C")}

    print("\n" + "=" * 30)
    print("FINAL RESULTS")
    print("=" * 30)
    print(f"\n{'':16}{'R@1':>8}{'R@5':>8}{'R@10':>8}{'MRR':>8}")
    for g, label in GROUP_LABELS.items():
        m = metrics[g]
        print(f"{label:16}{m['r1']:>8.2f}{m['r5']:>8.2f}{m['r10']:>8.2f}{m['mrr']:>8.4f}")

    # --- per-group similarity/rank statistics ---
    print("\n--- similarity & rank statistics (to expected product) ---")
    for g, label in GROUP_LABELS.items():
        m = metrics[g]
        print(f"\n{label}:")
        print(f"  mean sim={m['mean_sim']:.4f}  median sim={m['median_sim']:.4f}  "
              f"min={m['min_sim']:.4f}  max={m['max_sim']:.4f}")
        print(f"  mean rank={m['mean_rank']:.2f}  median rank={m['median_rank']:.2f}")

    # --- English vs Translated Chinese comparison ---
    b = metrics["B"]
    c = metrics["C"]
    print("\n" + "-" * 60)
    print("English vs Translated Chinese")
    print("-" * 60)
    print(f"{'':22}{'English':>12}{'Translated':>12}")
    print(f"{'Recall@1':22}{b['r1']:>12.2f}{c['r1']:>12.2f}")
    print(f"{'Recall@5':22}{b['r5']:>12.2f}{c['r5']:>12.2f}")
    print(f"{'Recall@10':22}{b['r10']:>12.2f}{c['r10']:>12.2f}")
    print(f"{'MRR':22}{b['mrr']:>12.4f}{c['mrr']:>12.4f}")
    print(f"{'Mean expected sim':22}{b['mean_sim']:>12.4f}{c['mean_sim']:>12.4f}")

    print("\nDifferences (English - Translated):")
    print(f"  R@1  difference: {b['r1'] - c['r1']:+.2f}")
    print(f"  R@5  difference: {b['r5'] - c['r5']:+.2f}")
    print(f"  R@10 difference: {b['r10'] - c['r10']:+.2f}")
    print(f"  MRR  difference: {b['mrr'] - c['mrr']:+.4f}")

    print("\n" + "-" * 60)
    print("Conclusion")
    print("-" * 60)
    if b["r1"] >= c["r1"] and b["mrr"] >= c["mrr"] and b["mean_sim"] >= c["mean_sim"]:
        print("Direct cross-lingual retrieval performs at least as well\n"
              "as translation-first retrieval on this benchmark.")
    else:
        print("Translation-first retrieval performed better on this benchmark.\n"
              "Further evaluation with a larger dataset is recommended.")
    print("\nNote: this is a small-scale sanity check (12 queries, 24 products),\n"
          "not a proof of cross-lingual retrieval quality.")

    # --- API usage ---
    print("\n" + "-" * 60)
    print("Embedding API usage (this run)")
    print("-" * 60)
    print(f"  API calls:        {api_calls}")
    print(f"  Total input texts: {2 + len(texts) + len(query_texts)} "
          f"(smoke=2, products={len(texts)}, queries={len(query_texts)})")
    print("  Tokens:           not exposed by the embedding wrapper")
    print("  Estimated cost:   unavailable (token usage not exposed)")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZherMai cross-lingual retrieval benchmark")
    parser.add_argument("--no-cache", action="store_true", help="force re-fetch embeddings (ignore local cache)")
    parser.add_argument("--top-k", type=int, default=10, help="number of top results to print per query (default 10)")
    parser.add_argument("--no-text-type", action="store_true",
                        help="do not pass text_type (query/document) to the embedding API")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
