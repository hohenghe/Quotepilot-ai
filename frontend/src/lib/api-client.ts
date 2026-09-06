import type {
  Inquiry,
  InquiryAnalysis,
  MatchedProduct,
  Product,
  Quote,
  DashboardStats,
} from "@/types"
import { getToken, logout } from "./auth"

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

  let res: Response
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, {
      ...options,
      headers,
    })
  } catch {
    throw new Error(`Network error: could not reach ${getApiBaseUrl()}. Please check your connection.`)
  }

  if (!res.ok) {
    if (res.status === 401) {
      logout()
    }
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
  seller_id: number | null
  seller_name: string | null
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
  favorite_count: number
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
    seller_id: raw.seller_id ?? null,
    seller_name: raw.seller_name ?? null,
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
    favorite_count: raw.favorite_count ?? 0,
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
  store_name: string | null
  avatar_url: string | null
  business_license_url: string | null
  country: string | null
  phone: string | null
  uid: string | null
}

export async function login(identifier: string, password: string, role?: string): Promise<AuthResponse> {
  return await request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ identifier, password, role: role || null }),
  })
}

export async function register(email: string, password: string, name: string, country: string, phone: string, role: "buyer" | "seller" = "buyer"): Promise<{ ok: boolean; message: string }> {
  const data = await request<{ success: boolean; message: string }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name, country, phone, role }),
  })
  return { ok: !!data.success, message: data.message || "" }
}

export async function updateProfile(data: { name?: string; store_name?: string; avatar_url?: string; business_license_url?: string; phone?: string; country?: string }): Promise<AuthResponse> {
  return await request<AuthResponse>("/api/auth/me", {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

// ── Email verification & password reset ─────────────────────────

export interface AuthResult {
  success: boolean
  message: string
  status: number
}

function extractDetail(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e)
  const match = msg.match(/"detail"\s*:\s*"((?:[^"\\]|\\.)*)"/)
  return match ? match[1] : msg
}

async function postAuth(path: string, body: unknown): Promise<AuthResult> {
  try {
    const data = await request<{ success: boolean; message: string }>(path, {
      method: "POST",
      body: JSON.stringify(body),
    })
    return { success: data.success !== false, message: data.message || "", status: 200 }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    const statusMatch = msg.match(/^API error (\d+):/)
    return {
      success: false,
      message: extractDetail(e),
      status: statusMatch ? Number(statusMatch[1]) : 0,
    }
  }
}

export async function verifyEmail(token: string): Promise<AuthResult> {
  return await postAuth("/api/auth/verify-email", { token })
}

export async function resendVerification(email: string): Promise<AuthResult> {
  return await postAuth("/api/auth/resend-verification", { email })
}

export async function forgotPassword(email: string): Promise<AuthResult> {
  return await postAuth("/api/auth/forgot-password", { email })
}

export async function resetPassword(token: string, newPassword: string): Promise<AuthResult> {
  return await postAuth("/api/auth/reset-password", { token, new_password: newPassword })
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

export async function adminResetAll(): Promise<void> {
  await request("/api/admin/reset", { method: "DELETE" })
}

export async function adminClearSavedProducts(): Promise<number> {
  const data = await request<{ success: boolean; deleted_count: number }>("/api/admin/saved-products", { method: "DELETE" })
  return data.deleted_count
}

export async function adminSendTestVerificationEmail(email: string): Promise<{ message: string }> {
  return await request("/api/admin/tests/verification-email", {
    method: "POST",
    body: JSON.stringify({ email }),
  })
}

export async function adminTestLlm(prompt: string): Promise<{ ai_used: boolean; analysis: Record<string, unknown> }> {
  return await request("/api/admin/tests/llm", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  })
}

export async function adminCreateTestProduct(): Promise<{ product_id: number; name: string; sku: string }> {
  return await request("/api/admin/tests/products", { method: "POST" })
}

export async function adminDeleteTestProduct(productId: number): Promise<{ deleted_product_id: number }> {
  return await request("/api/admin/tests/products", {
    method: "DELETE",
    body: JSON.stringify({ product_id: productId }),
  })
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

export interface BuyerInquiryItem {
  id: number
  product_id: number | null
  product_name: string | null
  seller_id: number | null
  seller_name: string | null
  seller_email: string | null
  raw_message: string
  status: string
  reply_body: string | null
  created_at: string | null
}

export interface PaginatedResult<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  has_next: boolean
}

export async function sendInquiryToSeller(inquiryText: string, productId: number, buyerEmail?: string): Promise<{ ok: boolean; id: number }> {
  return await request("/api/seller-inquiries/send", {
    method: "POST",
    body: JSON.stringify({ inquiry_text: inquiryText, product_id: productId, buyer_email: buyerEmail || null }),
  })
}

export async function getSellerReceivedInquiries(page = 1, pageSize = 50): Promise<PaginatedResult<SellerInquiryItem>> {
  return await request(`/api/seller-inquiries/received?page=${page}&page_size=${pageSize}`)
}

export async function getBuyerInquiries(page = 1, pageSize = 20): Promise<PaginatedResult<BuyerInquiryItem>> {
  return await request(`/api/inquiries/buyer?page=${page}&page_size=${pageSize}`)
}

// ── Saved Products ──────────────────────────────────────────────

export interface SavedProductItem {
  product_id: number
  name: string
  sku: string | null
  category: string
  moq: number | null
  unit_price: number | null
  price_range_low: number | null
  price_range_high: number | null
  pricing: string | null
  lead_time_days: number | null
  certifications: string | null
  technical_specs: string | null
  favorite_count: number
  created_at: string | null
}

export async function getSavedProducts(): Promise<SavedProductItem[]> {
  const data = await request<{ items: SavedProductItem[] }>("/api/saved-products")
  return data.items
}

export async function saveProduct(productId: number): Promise<void> {
  await request("/api/saved-products", {
    method: "POST",
    body: JSON.stringify({ product_id: productId }),
  })
}

export async function unsaveProduct(productId: number): Promise<void> {
  await request(`/api/saved-products/${productId}`, { method: "DELETE" })
}

export async function generateSellerReply(inquiryId: number): Promise<{ subject: string; email_body: string }> {
  return await request("/api/seller-inquiries/generate-reply", {
    method: "POST",
    body: JSON.stringify({ inquiry_id: inquiryId }),
  })
}

export async function getSellerProducts(): Promise<{ total: number; items: Product[] }> {
  const first = await request<{ total: number; items: Product[] }>("/api/products?page=1&page_size=2000")
  return first
}

export interface ProductPayload {
  name: string
  sku?: string | null
  category?: string
  description?: string | null
  technical_specs?: string | null
  certifications?: string | null
  moq?: number | null
  unit_price?: number | null
  price_range_low?: number | null
  price_range_high?: number | null
  pricing?: string | null
  lead_time_days?: number | null
  image_url?: string | null
  images?: string[]
}

export async function createProduct(data: ProductPayload): Promise<Product> {
  return await request<Product>("/api/products", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updateProduct(productId: number, data: ProductPayload): Promise<Product> {
  return await request<Product>(`/api/products/${productId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}

export async function deleteSellerProduct(productId: number): Promise<void> {
  await request(`/api/products/${productId}`, { method: "DELETE" })
}

export async function deleteProducts(productIds: number[]): Promise<number> {
  const data = await request<{ success: boolean; deleted_count: number }>("/api/products/batch", {
    method: "DELETE",
    body: JSON.stringify({ product_ids: productIds }),
  })
  return data.deleted_count
}

export async function deleteAllProducts(): Promise<number> {
  const data = await request<{ success: boolean; deleted_count: number }>("/api/products/all", {
    method: "DELETE",
  })
  return data.deleted_count
}

// ── Product photo recognition ──────────────────────────────────

export interface RecognizedFields {
  name: string | null
  sku: string | null
  category: string | null
  description: string | null
  technical_specs: string | null
  certifications: string | null
  moq: number | null
  unit_price: number | null
  price_range_low: number | null
  price_range_high: number | null
  pricing: string | null
  lead_time_days: number | null
}

export async function recognizeProduct(file: File): Promise<RecognizedFields> {
  const formData = new FormData()
  formData.append("file", file)
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) headers["Authorization"] = `Bearer ${token}`
  const res = await fetch(`${getApiBaseUrl()}/api/products/recognize`, {
    method: "POST",
    body: formData,
    headers,
  })
  if (!res.ok) {
    if (res.status === 401) logout()
    const text = await res.text()
    throw new Error(`Recognition failed (${res.status}): ${text.slice(0, 200)}`)
  }
  const data = await res.json()
  return (data.data ?? {}) as RecognizedFields
}

// ── Reviews ─────────────────────────────────────────────────────

export interface ReviewItem {
  id: number
  seller_id: number
  seller_name?: string | null
  seller_email?: string | null
  user_id: number
  user_name?: string
  user_email?: string
  rating: number
  content: string | null
  images: string[]
  reported: boolean
  created_at: string | null
}

export interface SellerReviews {
  items: ReviewItem[]
  score: number | null
  review_count?: number
}

export async function getSellerReviews(sellerId: number): Promise<SellerReviews> {
  return await request(`/api/reviews?seller_id=${sellerId}`)
}

export async function createReview(sellerId: number, rating: number, content: string, images: string[]): Promise<void> {
  await request("/api/reviews", {
    method: "POST",
    body: JSON.stringify({ seller_id: sellerId, rating, content, images }),
  })
}

export async function deleteReview(reviewId: number): Promise<void> {
  await request(`/api/reviews/${reviewId}`, { method: "DELETE" })
}

export async function reportReview(reviewId: number): Promise<void> {
  await request(`/api/reviews/${reviewId}/report`, { method: "POST" })
}

export async function getMySellerReviews(): Promise<SellerReviews> {
  return await request("/api/reviews/seller")
}

export async function adminListReviews(): Promise<{ items: ReviewItem[] }> {
  return await request("/api/reviews/admin/all")
}

export async function getSellerScore(): Promise<{ score: number | null }> {
  return await request("/api/sellers/score")
}

export interface SellerProductsResult {
  seller_id: number
  seller_name: string | null
  seller_email: string | null
  score: number | null
  items: Product[]
}

export async function getSellerProductsById(sellerId: number): Promise<SellerProductsResult> {
  return await request(`/api/sellers/${sellerId}/products`)
}

// ── Files ───────────────────────────────────────────────────────

export async function uploadImage(file: File, kind: "review" | "product" | "avatar" | "license" = "review"): Promise<{ url: string }> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("kind", kind)
  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) headers["Authorization"] = `Bearer ${token}`
  const res = await fetch(`${getApiBaseUrl()}/api/files/upload`, {
    method: "POST",
    body: formData,
    headers,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Upload failed (${res.status}): ${text.slice(0, 200)}`)
  }
  return res.json()
}

// ── Admin batch ─────────────────────────────────────────────────

export interface AdminUserItem {
  id: number
  email: string
  role: string
  name: string | null
  country: string | null
  phone: string | null
  uid: string | null
  score: number | null
  created_at: string | null
}

export async function adminListUsers(page = 1, pageSize = 50): Promise<{ items: AdminUserItem[]; total: number }> {
  return await request(`/api/admin/users?page=${page}&page_size=${pageSize}`)
}

export async function adminDeleteUsers(ids: number[]): Promise<number> {
  const data = await request<{ success: boolean; deleted_count: number }>("/api/admin/users/batch", {
    method: "DELETE",
    body: JSON.stringify({ ids }),
  })
  return data.deleted_count
}

export async function adminDeleteInquiries(ids: number[]): Promise<number> {
  const data = await request<{ success: boolean; deleted_count: number }>("/api/inquiries/batch", {
    method: "DELETE",
    body: JSON.stringify({ ids }),
  })
  return data.deleted_count
}
