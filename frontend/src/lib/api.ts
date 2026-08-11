const BASE_URL = typeof window !== "undefined"
  ? (process.env.NEXT_PUBLIC_API_URL || "")
  : ""

const API_MODE = BASE_URL.length > 0

async function request<T>(path: string, options?: RequestInit): Promise<T | null> {
  if (!API_MODE) return null
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return await res.json()
  } catch {
    return null
  }
}

export function isApiMode(): boolean {
  return API_MODE
}

// ── Products ──────────────────────────────────────────────────────────

export async function apiGetAllProducts() {
  const data = await request<{ items: any[] }>("/api/products")
  return data?.items || null
}

export async function apiUploadProducts(file: File) {
  if (!API_MODE) return null
  const form = new FormData()
  form.append("file", file)
  try {
    const res = await fetch(`${BASE_URL}/api/products/upload`, {
      method: "POST",
      body: form,
    })
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
    return await res.json()
  } catch {
    return null
  }
}

export async function apiDeleteProduct(id: number) {
  await request(`/api/products/${id}`, { method: "DELETE" })
}

export async function apiGetProductStats() {
  return request<{ total_products: number; categories: Record<string, number> }>(
    "/api/products/stats/summary"
  )
}

// ── Inquiries ─────────────────────────────────────────────────────────

export async function apiAnalyzeInquiry(rawMessage: string, customerName?: string) {
  return request<any>("/api/inquiries/analyze", {
    method: "POST",
    body: JSON.stringify({
      raw_message: rawMessage,
      customer_name: customerName || null,
      customer_email: null,
      customer_company: null,
    }),
  })
}

export async function apiGetAllInquiries() {
  const data = await request<{ items: any[] }>("/api/inquiries")
  return data?.items || null
}

// ── Quotes ────────────────────────────────────────────────────────────

export async function apiGenerateQuote(
  inquiryId: number,
  selectedProductIds: number[],
  additionalNotes?: string
) {
  return request<any>("/api/quotes/generate", {
    method: "POST",
    body: JSON.stringify({
      inquiry_id: inquiryId,
      selected_product_ids: selectedProductIds,
      additional_notes: additionalNotes || null,
    }),
  })
}

// ── Dashboard ─────────────────────────────────────────────────────────

export async function apiGetDashboardStats() {
  return request<{
    total_products: number
    total_inquiries: number
    total_quotes: number
  }>("/api/dashboard")
}
