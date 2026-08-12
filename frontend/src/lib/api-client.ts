import type {
  Inquiry,
  InquiryAnalysis,
  MatchedProduct,
  Quote,
  DashboardStats,
} from "@/types"

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
}

export function isApiAvailable(): boolean {
  return getApiBaseUrl().length > 0
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text.slice(0, 200)}`)
  }

  return res.json()
}

// ── Type adapters: snake_case (backend) ↔ camelCase (frontend) ────

interface ApiInquiry {
  id: number
  customer_name: string | null
  customer_email: string | null
  customer_company: string | null
  raw_message: string
  analyses: ApiInquiryAnalysis[]
  created_at: string | null
}

interface ApiInquiryAnalysis {
  id: number
  inquiry_id: number
  product_category: string | null
  quantity: number | null
  technical_params: Record<string, string>
  target_price: number | null
  required_certifications: string[]
  delivery_location: string | null
  delivery_country: string | null
  missing_info: string[]
  created_at: string | null
}

interface ApiMatchedProduct {
  product_id: number
  product_name: string
  sku: string | null
  match_score: number
  match_reason: string
  moq: number | null
  unit_price: number | null
  price_range_low: number | null
  price_range_high: number | null
  pricing: string | null
  lead_time_days: number | null
  certifications: string | null
  technical_specs: string | null
}

interface ApiInquiryAnalysisResult {
  inquiry: ApiInquiry
  analysis: ApiInquiryAnalysis
  matched_products: ApiMatchedProduct[]
}

interface ApiQuote {
  id: number
  inquiry_id: number | null
  subject: string | null
  email_body: string
  matched_products: ApiMatchedProduct[]
  total_amount_low: number | null
  total_amount_high: number | null
  currency: string
  notes: string | null
  created_at: string | null
}

interface ApiDashboardStats {
  total_products: number
  today_inquiries: number
  total_inquiries: number
  total_quotes: number
  categories: Record<string, number>
}

function adaptInquiry(raw: ApiInquiry): Inquiry {
  return {
    id: raw.id,
    customer_name: raw.customer_name,
    customer_email: raw.customer_email,
    customer_company: raw.customer_company,
    raw_message: raw.raw_message,
    created_at: raw.created_at,
    analyses: (raw.analyses || []).map(adaptAnalysis),
  }
}

function adaptAnalysis(raw: ApiInquiryAnalysis): InquiryAnalysis {
  return {
    id: raw.id,
    inquiry_id: raw.inquiry_id,
    product_category: raw.product_category,
    quantity: raw.quantity,
    technical_params: raw.technical_params || {},
    target_price: raw.target_price,
    required_certifications: raw.required_certifications || [],
    delivery_location: raw.delivery_location,
    delivery_country: raw.delivery_country,
    missing_info: raw.missing_info || [],
    created_at: raw.created_at,
  }
}

function adaptMatchedProduct(raw: ApiMatchedProduct): MatchedProduct {
  return {
    product_id: raw.product_id,
    product_name: raw.product_name,
    sku: raw.sku,
    match_score: raw.match_score,
    match_reason: raw.match_reason,
    moq: raw.moq,
    unit_price: raw.unit_price,
    price_range_low: raw.price_range_low,
    price_range_high: raw.price_range_high,
    pricing: raw.pricing,
    lead_time_days: raw.lead_time_days,
    certifications: raw.certifications,
    technical_specs: raw.technical_specs,
  }
}

function adaptQuote(raw: ApiQuote): Quote {
  return {
    id: raw.id,
    inquiry_id: raw.inquiry_id,
    subject: raw.subject,
    email_body: raw.email_body,
    matched_products: (raw.matched_products || []).map(adaptMatchedProduct),
    total_amount_low: raw.total_amount_low,
    total_amount_high: raw.total_amount_high,
    currency: raw.currency || "USD",
    notes: raw.notes,
    created_at: raw.created_at,
  }
}

// ── Public API ─────────────────────────────────────────────────────

export interface FullAnalysisResult {
  inquiry: Inquiry
  analysis: InquiryAnalysis
  matchedProducts: MatchedProduct[]
}

export async function analyzeAndMatch(
  rawMessage: string,
  customerName?: string,
): Promise<FullAnalysisResult> {
  const data = await request<ApiInquiryAnalysisResult>("/api/inquiries/analyze", {
    method: "POST",
    body: JSON.stringify({
      raw_message: rawMessage,
      customer_name: customerName || null,
      customer_email: null,
      customer_company: null,
    }),
  })

  return {
    inquiry: adaptInquiry(data.inquiry),
    analysis: adaptAnalysis(data.analysis),
    matchedProducts: data.matched_products.map(adaptMatchedProduct),
  }
}

export async function generateQuote(
  inquiryId: number,
  selectedProductIds: number[] = [],
  additionalNotes?: string,
): Promise<Quote> {
  const data = await request<ApiQuote>("/api/quotes/generate", {
    method: "POST",
    body: JSON.stringify({
      inquiry_id: inquiryId,
      selected_product_ids: selectedProductIds,
      additional_notes: additionalNotes || null,
    }),
  })

  return adaptQuote(data)
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return await request<ApiDashboardStats>("/api/dashboard")
}

export async function listInquiries(): Promise<Inquiry[]> {
  const data = await request<{ total: number; items: ApiInquiry[] }>("/api/inquiries")
  return data.items.map(adaptInquiry)
}

export async function getQuoteById(id: number): Promise<Quote> {
  const data = await request<ApiQuote>(`/api/quotes/${id}`)
  return adaptQuote(data)
}
