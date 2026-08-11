/**
 * Mock embedding service — generates deterministic vectors for product search.
 * Swap in: OpenAI text-embedding-3-small / DeepSeek embedding API.
 */

const EMBEDDING_DIM = 1536

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

export function generateEmbedding(text: string): number[] {
  const rng = new SeededRNG(hashCode(text))
  return Array.from({ length: EMBEDDING_DIM }, () => rng.next() * 2 - 1)
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
