/**
 * Embedding service — vector embeddings for product search.
 * Uses real API when NEXT_PUBLIC_LLM_API_KEY is set, falls back to hash-based mock.
 */

import { isLLMAvailable, getEmbedding as apiGetEmbedding } from "./api-config"

const EMBEDDING_DIM = 1536

// ── Mock (hash-based deterministic vectors) ───────────────────────

function hashCode(text: string): number {
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  return Math.abs(hash)
}

class SeededRNG {
  private seed: number
  constructor(seed: number) {
    this.seed = seed
  }
  next(): number {
    this.seed = (this.seed * 1664525 + 1013904223) & 0xFFFFFFFF
    return (this.seed >>> 0) / 0xFFFFFFFF
  }
}

function mockEmbedding(text: string): number[] {
  const rng = new SeededRNG(hashCode(text))
  return Array.from({ length: EMBEDDING_DIM }, () => rng.next() * 2 - 1)
}

// ── Cache ─────────────────────────────────────────────────────────

const cache = new Map<string, number[]>()

// ── Public API ────────────────────────────────────────────────────

export async function generateEmbedding(text: string): Promise<number[]> {
  const key = text.slice(0, 500)
  const cached = cache.get(key)
  if (cached) return cached

  if (isLLMAvailable()) {
    try {
      const vec = await apiGetEmbedding(text)
      if (vec.length > 0) {
        cache.set(key, vec)
        return vec
      }
    } catch {
      // Fall through to mock
    }
  }

  const vec = mockEmbedding(text)
  cache.set(key, vec)
  return vec
}

export function buildProductText(
  name: string,
  category: string,
  description: string | null,
  specs: string | null,
  certifications: string | null,
): string {
  return [name, category, description, specs, certifications]
    .filter(Boolean)
    .join(" | ")
}
