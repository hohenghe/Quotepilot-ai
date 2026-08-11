/**
 * RAG (Retrieval-Augmented Generation) — local product search.
 * Swap in: pgvector cosine similarity or external vector DB.
 */

import { generateEmbedding } from "./embedding"
import type { Product } from "@/types"

function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0
  let normA = 0
  let normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  if (normA === 0 || normB === 0) return 0
  return dot / (Math.sqrt(normA) * Math.sqrt(normB))
}

function keywordScore(query: string, product: Product): number {
  const ql = query.toLowerCase()
  const keywords = ql.replace(/[,.]/g, " ").split(/\s+/).filter(k => k.length >= 2)
  let score = 0

  const name = (product.name || "").toLowerCase()
  const cat = (product.category || "").toLowerCase()
  const desc = (product.description || "").toLowerCase()
  const specs = (product.technical_specs || "").toLowerCase()

  for (const kw of keywords) {
    if (name.includes(kw)) score += 0.6
    if (cat.includes(kw)) score += 0.15
    if (desc.includes(kw)) score += 0.05
    if (specs.includes(kw)) score += 0.1
  }
  return Math.min(score, 1)
}

export interface SearchResult {
  product: Product
  score: number
}

export function searchProducts(
  query: string,
  products: Product[],
  topK: number = 5,
  vectorWeight: number = 0.1,
): SearchResult[] {
  if (products.length === 0) return []

  const queryVec = generateEmbedding(query)
  const results: SearchResult[] = []

  for (const p of products) {
    const text = [
      p.name, p.category, p.description,
      p.technical_specs, p.certifications,
    ].filter(Boolean).join(" | ")
    const pVec = generateEmbedding(text)
    const vs = (cosineSimilarity(queryVec, pVec) + 1) / 2
    const ks = keywordScore(query, p)
    const combined = vectorWeight * vs + (1 - vectorWeight) * ks
    results.push({ product: p, score: combined })
  }

  results.sort((a, b) => b.score - a.score)
  return results.slice(0, topK)
}
