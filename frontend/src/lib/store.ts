/**
 * Hybrid store — backend API-first with localStorage fallback.
 * When NEXT_PUBLIC_API_BASE_URL is set, AI operations go through backend.
 * When NEXT_PUBLIC_SUPABASE_URL is set, data syncs across devices via Supabase.
 */
import type { Product, Inquiry, InquiryAnalysis, Quote, MatchedProduct } from "@/types"
import { analyzeInquiry, generateQuoteEmail } from "./ai/llm"
import { searchProducts } from "./ai/rag"
import { isLLMAvailable } from "./ai/api-config"
import { supabase as getSupabase, isSupabaseMode } from "./supabase"
import * as apiClient from "./api-client"

const PRODUCTS_KEY = "quotepilot_products"
const INQUIRIES_KEY = "quotepilot_inquiries"
const QUOTES_KEY = "quotepilot_quotes"
const DRAFT_INQUIRY_KEY = "quotepilot_draft_inquiry"

// ── Persistent state ──────────────────────────────────────────────

let nextProductId = 1
let nextInquiryId = 1
let nextAnalysisId = 1
let nextQuoteId = 1

function load<T>(key: string): T[] {
  if (typeof window === "undefined") return []
  const raw = localStorage.getItem(key)
  return raw ? JSON.parse(raw) : []
}

function save(key: string, data: unknown) {
  if (typeof window === "undefined") return
  localStorage.setItem(key, JSON.stringify(data))
}

// ── Supabase helpers ──────────────────────────────────────────────

interface ProductRow {
  id: number
  name: string
  sku: string | null
  category: string
  description: string | null
  technical_specs: string | null
  certifications: string | null
  moq: number | null
  unit_price: number | null
  price_range_low: number | null
  price_range_high: number | null
  pricing: string | null
  lead_time_days: number | null
  image_url: string | null
  is_active: boolean
  created_at: string
}

function rowToProduct(r: ProductRow): Product {
  return {
    id: r.id,
    name: r.name,
    sku: r.sku,
    category: r.category,
    description: r.description,
    technical_specs: r.technical_specs,
    certifications: r.certifications,
    moq: r.moq,
    unit_price: r.unit_price,
    price_range_low: r.price_range_low,
    price_range_high: r.price_range_high,
    pricing: r.pricing,
    lead_time_days: r.lead_time_days,
    image_url: r.image_url,
    is_active: r.is_active,
    created_at: r.created_at,
  }
}

// ── Products ──────────────────────────────────────────────────────

export async function getAllProductsAsync(): Promise<Product[]> {
  if (isSupabaseMode()) {
    const { data } = await       getSupabase()
      .from("products")
      .select("*")
      .eq("is_active", true)
      .order("created_at", { ascending: false })
    if (data) {
      const products = (data as ProductRow[]).map(rowToProduct)
      save(PRODUCTS_KEY, products)
      return products
    }
  }
  return load<Product>(PRODUCTS_KEY)
}

export function getAllProducts(): Product[] {
  const products = load<Product>(PRODUCTS_KEY)
  return products
}

export function addProduct(p: Omit<Product, "id" | "created_at" | "is_active">): Product {
  const products = getAllProducts()
  const product: Product = {
    ...p,
    id: nextProductId++,
    is_active: true,
    created_at: new Date().toISOString(),
  }
  products.push(product)
  save(PRODUCTS_KEY, products)
  if (typeof window !== "undefined") {
    localStorage.setItem("quotepilot_nextProductId", String(nextProductId))
  }
  return product
}

export function addProducts(items: Omit<Product, "id" | "created_at" | "is_active">[]): Product[] {
  const products = getAllProducts()
  const newProducts: Product[] = items.map(p => ({
    ...p,
    id: nextProductId++,
    is_active: true,
    created_at: new Date().toISOString(),
  }))
  products.push(...newProducts)
  save(PRODUCTS_KEY, products)
  if (typeof window !== "undefined") {
    localStorage.setItem("quotepilot_nextProductId", String(nextProductId))
  }
  return newProducts
}

export async function deleteProduct(id: number) {
  if (isSupabaseMode()) {
    await       getSupabase().from("products").update({ is_active: false }).eq("id", id)
  }
  const products = getAllProducts().filter(p => p.id !== id)
  save(PRODUCTS_KEY, products)
}

export async function uploadFile(file: File): Promise<Product[]> {
  // Parse locally, then upload to Supabase
  const { parseFile } = await import("./ai/file-parser")
  const result = await parseFile(file)
  const parsed = result.products

  if (isSupabaseMode()) {
    const { error } = await       getSupabase().from("products").insert(
      parsed.map(p => ({
        name: p.name,
        sku: p.sku,
        category: p.category,
        description: p.description,
        technical_specs: p.technical_specs,
        certifications: p.certifications,
        moq: p.moq,
        unit_price: p.unit_price,
        price_range_low: p.price_range_low,
        price_range_high: p.price_range_high,
        pricing: p.pricing,
        lead_time_days: p.lead_time_days,
      }))
    )
    if (error) throw new Error(error.message)
    return await getAllProductsAsync()
  }

  addProducts(parsed)
  return getAllProducts()
}

export function getProductById(id: number): Product | undefined {
  return getAllProducts().find(p => p.id === id)
}

export async function refreshProducts(): Promise<Product[]> {
  if (isSupabaseMode()) {
    return await getAllProductsAsync()
  }
  return getAllProducts()
}

// ── Inquiries ─────────────────────────────────────────────────────

export async function getAllInquiriesAsync(): Promise<Inquiry[]> {
  if (isSupabaseMode()) {
    const { data: inqData } = await       getSupabase()
      .from("inquiries")
      .select("*, inquiry_analyses(*)")
      .order("created_at", { ascending: false })
    if (inqData) {
      const inquiries: Inquiry[] = inqData.map((i: any) => ({
        id: i.id,
        customer_name: i.customer_name,
        customer_email: i.customer_email,
        customer_company: i.customer_company,
        raw_message: i.raw_message,
        created_at: i.created_at,
        analyses: (i.inquiry_analyses || []).map((a: any) => ({
          id: a.id,
          inquiry_id: a.inquiry_id,
          product_category: a.product_category,
          quantity: a.quantity,
          technical_params: a.technical_params || {},
          target_price: a.target_price,
          required_certifications: a.required_certifications || [],
          delivery_location: a.delivery_location,
          delivery_country: a.delivery_country,
          missing_info: a.missing_info || [],
          created_at: a.created_at,
        })),
      }))
      save(INQUIRIES_KEY, inquiries)
      return inquiries
    }
  }
  return load<Inquiry>(INQUIRIES_KEY)
}

export function getAllInquiries(): Inquiry[] {
  return load<Inquiry>(INQUIRIES_KEY)
}

export interface FullAnalysisResult {
  inquiry: Inquiry
  analysis: InquiryAnalysis
  matchedProducts: MatchedProduct[]
}

async function doLocalAnalyze(rawMessage: string, customerName?: string): Promise<FullAnalysisResult> {
  const analysisData = await analyzeInquiry(rawMessage)

  const inquiry: Inquiry = {
    id: nextInquiryId++,
    customer_name: customerName || null,
    customer_email: null,
    customer_company: null,
    raw_message: rawMessage,
    created_at: new Date().toISOString(),
    analyses: [],
  }

  const analysis: InquiryAnalysis = {
    id: nextAnalysisId++,
    inquiry_id: inquiry.id,
    product_category: analysisData.productCategory,
    quantity: analysisData.quantity,
    technical_params: analysisData.technicalParams,
    target_price: analysisData.targetPrice,
    required_certifications: analysisData.requiredCertifications,
    delivery_location: analysisData.deliveryLocation,
    delivery_country: analysisData.deliveryCountry,
    missing_info: analysisData.missingInfo,
    created_at: new Date().toISOString(),
  }

  inquiry.analyses = [analysis]

  const inquiries = getAllInquiries()
  inquiries.unshift(inquiry)
  save(INQUIRIES_KEY, inquiries)

  const products = getAllProducts().filter(p => p.is_active)
  const searchResults = await searchProducts(rawMessage, products, 5, isLLMAvailable() ? 0.6 : 0.1)

  const matchedProducts: MatchedProduct[] = searchResults.map(({ product, score }) => {
    const reasons: string[] = []
    if (product.category === analysisData.productCategory) {
      reasons.push("Category matches inquiry requirements")
    }
    if (product.certifications && analysisData.requiredCertifications.length > 0) {
      for (const cert of analysisData.requiredCertifications) {
        if (product.certifications.toLowerCase().includes(cert.toLowerCase())) {
          reasons.push(`${cert} certification confirmed`)
          break
        }
      }
    }
    if (reasons.length === 0) reasons.push("Product specifications align with your requirements")

    return {
      product_id: product.id,
      product_name: product.name,
      sku: product.sku,
      match_score: score,
      match_reason: reasons.join("; "),
      moq: product.moq,
      unit_price: product.unit_price,
      price_range_low: product.price_range_low,
      price_range_high: product.price_range_high,
      pricing: product.pricing,
      lead_time_days: product.lead_time_days,
      certifications: product.certifications,
      technical_specs: product.technical_specs,
    }
  })

  return { inquiry, analysis, matchedProducts }
}

export async function analyzeAndMatch(rawMessage: string, customerName?: string): Promise<FullAnalysisResult> {
  if (apiClient.isApiAvailable()) {
    try {
      const result = await apiClient.analyzeAndMatch(rawMessage, customerName)
      const inquiries = getAllInquiries()
      inquiries.unshift(result.inquiry)
      save(INQUIRIES_KEY, inquiries)
      return result
    } catch (e) {
      console.warn("Backend analyze failed, using local", e)
    }
  }

  if (isSupabaseMode()) {
    const { data: inq } = await       getSupabase()
      .from("inquiries")
      .insert({
        raw_message: rawMessage,
        customer_name: customerName || null,
        customer_email: null,
        customer_company: null,
      })
      .select()
      .single()

    if (inq) {
      const localResult = await doLocalAnalyze(rawMessage, customerName)
      const a = localResult.analysis

      await       getSupabase().from("inquiry_analyses").insert({
        inquiry_id: inq.id,
        product_category: a.product_category,
        quantity: a.quantity,
        technical_params: a.technical_params,
        target_price: a.target_price,
        required_certifications: a.required_certifications,
        delivery_location: a.delivery_location,
        delivery_country: a.delivery_country,
        missing_info: a.missing_info,
      })

      return {
        inquiry: { ...localResult.inquiry, id: inq.id, created_at: inq.created_at },
        analysis: { ...a },
        matchedProducts: localResult.matchedProducts,
      }
    }
  }

  return await doLocalAnalyze(rawMessage, customerName)
}

export function getInquiryById(id: number): Inquiry | undefined {
  return getAllInquiries().find(i => i.id === id)
}

// ── Quotes ────────────────────────────────────────────────────────

async function doLocalGenerateQuote(
  inquiryId: number,
  selectedProductIds: number[] = [],
  additionalNotes?: string,
): Promise<Quote> {
  const inquiry = getInquiryById(inquiryId)
  if (!inquiry) throw new Error("Inquiry not found")

  let matchedProducts: MatchedProduct[] = []

  if (selectedProductIds.length > 0) {
    const allProducts = getAllProducts()
    matchedProducts = allProducts
      .filter(p => selectedProductIds.includes(p.id))
      .map(p => ({
        product_id: p.id,
        product_name: p.name,
        sku: p.sku,
        match_score: 0.92,
        match_reason: "Manually selected",
        moq: p.moq,
        unit_price: p.unit_price,
        price_range_low: p.price_range_low,
        price_range_high: p.price_range_high,
        pricing: p.pricing,
        lead_time_days: p.lead_time_days,
        certifications: p.certifications,
        technical_specs: p.technical_specs,
      }))
  } else {
    const products = getAllProducts().filter(p => p.is_active)
    const searchResults = await searchProducts(inquiry.raw_message, products, 5, isLLMAvailable() ? 0.6 : 0.1)
    matchedProducts = searchResults.map(({ product, score }) => ({
      product_id: product.id,
      product_name: product.name,
      sku: product.sku,
      match_score: score,
      match_reason: "Meets all specified requirements",
      moq: product.moq,
      unit_price: product.unit_price,
      price_range_low: product.price_range_low,
      price_range_high: product.price_range_high,
      pricing: product.pricing,
      lead_time_days: product.lead_time_days,
      certifications: product.certifications,
      technical_specs: product.technical_specs,
    }))
  }

  const emailData = await generateQuoteEmail(
    inquiry.raw_message,
    inquiry.customer_name,
    matchedProducts,
    additionalNotes,
  )

  const quote: Quote = {
    id: nextQuoteId++,
    inquiry_id: inquiryId,
    subject: emailData.subject,
    email_body: emailData.emailBody,
    matched_products: matchedProducts,
    total_amount_low: emailData.totalAmountLow,
    total_amount_high: emailData.totalAmountHigh,
    currency: "USD",
    notes: additionalNotes || null,
    created_at: new Date().toISOString(),
  }

  const quotes = load<Quote>(QUOTES_KEY)
  quotes.unshift(quote)
  save(QUOTES_KEY, quotes)
  return quote
}

export async function generateQuote(
  inquiryId: number,
  selectedProductIds: number[] = [],
  additionalNotes?: string,
): Promise<Quote> {
  if (apiClient.isApiAvailable()) {
    try {
      const quote = await apiClient.generateQuote(inquiryId, selectedProductIds, additionalNotes)
      const quotes = load<Quote>(QUOTES_KEY)
      quotes.unshift(quote)
      save(QUOTES_KEY, quotes)
      return quote
    } catch (e) {
      console.warn("Backend quote failed, using local", e)
    }
  }

  const localQuote = await doLocalGenerateQuote(inquiryId, selectedProductIds, additionalNotes)

  if (isSupabaseMode()) {
    const { data } = await       getSupabase()
      .from("quotes")
      .insert({
        inquiry_id: inquiryId,
        subject: localQuote.subject,
        email_body: localQuote.email_body,
        matched_products: localQuote.matched_products,
        total_amount_low: localQuote.total_amount_low,
        total_amount_high: localQuote.total_amount_high,
        currency: localQuote.currency,
        notes: localQuote.notes,
      })
      .select()
      .single()
    if (data) {
      return { ...localQuote, id: data.id, created_at: data.created_at }
    }
  }

  return localQuote
}

export function getQuoteById(id: number): Quote | undefined {
  return load<Quote>(QUOTES_KEY).find(q => q.id === id)
}

// ── Dashboard ─────────────────────────────────────────────────────

export async function getDashboardStatsAsync() {
  if (apiClient.isApiAvailable()) {
    try {
      return await apiClient.getDashboardStats()
    } catch (e) {
      console.warn("Backend dashboard failed, using local", e)
    }
  }

  if (isSupabaseMode()) {
    const { data: products } = await       getSupabase()
      .from("products")
      .select("category")
      .eq("is_active", true)

    const categories: Record<string, number> = {}
    if (products) {
      for (const p of products) {
        const cat = (p as any).category || "other"
        categories[cat] = (categories[cat] || 0) + 1
      }
    }

    return {
      total_products: products?.length || 0,
      today_inquiries: 0,
      total_inquiries: 0,
      total_quotes: 0,
      categories,
    }
  }
  return getDashboardStats()
}

export function getDashboardStats() {
  const products = getAllProducts().filter(p => p.is_active)
  const inquiries = getAllInquiries()
  const quotes = load<Quote>(QUOTES_KEY)

  const today = new Date().toISOString().slice(0, 10)
  const todayInquiries = inquiries.filter(i =>
    (i.created_at || "").startsWith(today)
  ).length

  const categories: Record<string, number> = {}
  for (const p of products) {
    categories[p.category] = (categories[p.category] || 0) + 1
  }

  return {
    total_products: products.length,
    today_inquiries: todayInquiries,
    total_inquiries: inquiries.length,
    total_quotes: quotes.length,
    categories,
  }
}

// ── Draft Inquiry ─────────────────────────────────────────────────

export function saveDraftInquiry(text: string) {
  if (typeof window === "undefined") return
  localStorage.setItem(DRAFT_INQUIRY_KEY, text)
}

export function getDraftInquiry(): string {
  if (typeof window === "undefined") return ""
  return localStorage.getItem(DRAFT_INQUIRY_KEY) || ""
}

// ── Init ──────────────────────────────────────────────────────────

export function initStore() {
  if (typeof window === "undefined") return
  const savedPid = localStorage.getItem("quotepilot_nextProductId")
  if (savedPid) nextProductId = parseInt(savedPid) || 1
  const savedIid = localStorage.getItem("quotepilot_nextInquiryId")
  if (savedIid) nextInquiryId = parseInt(savedIid) || 1
  const savedAid = localStorage.getItem("quotepilot_nextAnalysisId")
  if (savedAid) nextAnalysisId = parseInt(savedAid) || 1
  const savedQid = localStorage.getItem("quotepilot_nextQuoteId")
  if (savedQid) nextQuoteId = parseInt(savedQid) || 1
}
