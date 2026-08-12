import type {
  Inquiry,
  InquiryAnalysis,
  MatchedProduct,
  Product,
  Quote,
  DashboardStats,
} from "@/types"
import { getToken } from "./auth"

function getApiBaseUrl(): string {
  let url = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
  if (!url.startsWith("http")) {
    url = "https://" + url
  }
  return url
}

export function isApiAvailable(): boolean {
  return getApiBaseUrl().length > 0
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers,
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
  ai_used: boolean
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
  aiUsed: boolean
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
    aiUsed: data.ai_used ?? false,
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

export async function uploadProducts(file: File): Promise<void> {
  const formData = new FormData()
  formData.append("file", file)
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) headers["Authorization"] = `Bearer ${token}`
  const res = await fetch(`${getApiBaseUrl()}/api/products/upload`, {
    method: "POST",
    body: formData,
    headers,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Upload failed (${res.status}): ${text.slice(0, 200)}`)
  }
}

export async function listInquiries(): Promise<Inquiry[]> {
  const data = await request<{ total: number; items: ApiInquiry[] }>("/api/inquiries")
  return data.items.map(adaptInquiry)
}

export async function getQuoteById(id: number): Promise<Quote> {
  const data = await request<ApiQuote>(`/api/quotes/${id}`)
  return adaptQuote(data)
}

// ── Auth ──────────────────────────────────────────────────────────

interface AuthResponse {
  token: string
  user_id: number
  email: string
  role: string
  name: string | null
  country: string | null
  phone: string | null
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return await request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  })
}

export async function register(email: string, password: string, name: string, country: string, phone?: string): Promise<AuthResponse> {
  return await request<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name, country, phone: phone || null }),
  })
}

// ── Admin ─────────────────────────────────────────────────────────

interface SellerInfo {
  id: number
  email: string
  name: string | null
  product_count: number
  created_at: string | null
}

export async function adminGetDashboard(): Promise<{
  total_products: number
  total_inquiries: number
  total_quotes: number
  total_sellers: number
  categories: Record<string, number>
}> {
  return await request("/api/dashboard/admin")
}

export async function adminListSellers(): Promise<SellerInfo[]> {
  const data = await request<{ sellers: SellerInfo[] }>("/api/dashboard/admin/sellers")
  return data.sellers
}

export async function adminListProducts(
  page = 1, search?: string, sellerId?: number
): Promise<{ total: number; items: Product[] }> {
  let url = `/api/products/admin/all?page=${page}&page_size=20`
  if (search) url += `&search=${encodeURIComponent(search)}`
  if (sellerId) url += `&seller_id=${sellerId}`
  return await request(url)
}

export async function adminListInquiries(
  page = 1
): Promise<{ total: number; items: Inquiry[] }> {
  const data = await request<{ total: number; items: ApiInquiry[] }>(
    `/api/inquiries/admin/all?page=${page}&page_size=20`
  )
  return { total: data.total, items: data.items.map(adaptInquiry) }
}

// ── Seller Inquiries ──────────────────────────────────────────────

export interface SellerInquiryItem {
  id: number
  raw_message: string
  buyer_email: string | null
  product_id: number | null
  status: string
  reply_body: string | null
  created_at: string | null
}

export async function sendInquiryToSeller(inquiryText: string, productId: number, buyerEmail?: string): Promise<{ ok: boolean; id: number }> {
  return await request("/api/seller-inquiries/send", {
    method: "POST",
    body: JSON.stringify({ inquiry_text: inquiryText, product_id: productId, buyer_email: buyerEmail || null }),
  })
}

export async function getSellerReceivedInquiries(page = 1): Promise<{ total: number; items: SellerInquiryItem[] }> {
  return await request(`/api/seller-inquiries/received?page=${page}&page_size=50`)
}

export async function generateSellerReply(inquiryId: number): Promise<{ subject: string; email_body: string }> {
  return await request("/api/seller-inquiries/generate-reply", {
    method: "POST",
    body: JSON.stringify({ inquiry_id: inquiryId }),
  })
}

export async function getSellerProducts(): Promise<{ total: number; items: Product[] }> {
  return await request("/api/products?page=1&page_size=1000")
}
