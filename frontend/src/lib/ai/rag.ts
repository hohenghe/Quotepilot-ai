import type { Product } from "@/types"

export interface SearchResult {
  product: Product
  score: number
}

export async function searchProducts(
  query: string,
  products: Product[],
  topK: number = 5,
  _vectorWeight: number = 0.5,
): Promise<SearchResult[]> {
  const queryLower = query.toLowerCase()
  const keywords = [...new Set(
    queryLower.replace(/[,.\/]/g, " ").split(/\s+/).filter(kw => kw.length >= 2)
  )]

  const scored = products.map(p => {
    const name = (p.name || "").toLowerCase()
    const category = (p.category || "").toLowerCase().replace(/_/g, " ")
    const desc = (p.description || "").toLowerCase()
    const specs = (p.technical_specs || "").toLowerCase()
    const certs = (p.certifications || "").toLowerCase()

    let score = 0
    for (const kw of keywords) {
      if (name.includes(kw)) score += 0.5
      if (category.includes(kw)) score += 0.25
      if (desc.includes(kw)) score += 0.15
      if (specs.includes(kw)) score += 0.1
      if (certs.includes(kw)) score += 0.05
    }
    return { product: p, score: Math.min(score, 1) }
  })

  scored.sort((a, b) => b.score - a.score)
  return scored.slice(0, topK).filter(r => r.score > 0)
}
