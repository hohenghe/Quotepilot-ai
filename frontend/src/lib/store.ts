/**
 * Local store — in-memory state with localStorage persistence.
 * Replaces the backend API layer.
 */
import type { Product, Inquiry, InquiryAnalysis, Quote, MatchedProduct } from "@/types"
import { analyzeInquiry, generateQuoteEmail, type ExtractedInfo } from "./ai/llm"
import { searchProducts } from "./ai/rag"

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

// ── Products ──────────────────────────────────────────────────────

export function getAllProducts(): Product[] {
  return load<Product>(PRODUCTS_KEY)
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

  // Recover max id on next load
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

export function deleteProduct(id: number) {
  const products = getAllProducts().filter(p => p.id !== id)
  save(PRODUCTS_KEY, products)
}

export function getProductById(id: number): Product | undefined {
  return getAllProducts().find(p => p.id === id)
}

// ── Inquiries ─────────────────────────────────────────────────────

export function getAllInquiries(): Inquiry[] {
  return load<Inquiry>(INQUIRIES_KEY)
}

export interface FullAnalysisResult {
  inquiry: Inquiry
  analysis: InquiryAnalysis
  matchedProducts: MatchedProduct[]
}

export function analyzeAndMatch(rawMessage: string, customerName?: string): FullAnalysisResult {
  const analysisData: ExtractedInfo = analyzeInquiry(rawMessage)

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

  // Persist inquiry
  const inquiries = getAllInquiries()
  inquiries.unshift(inquiry)
  save(INQUIRIES_KEY, inquiries)

  // Product matching
  const products = getAllProducts().filter(p => p.is_active)
  const searchResults = searchProducts(rawMessage, products, 5)

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

export function getInquiryById(id: number): Inquiry | undefined {
  return getAllInquiries().find(i => i.id === id)
}

// ── Quotes ────────────────────────────────────────────────────────

export function generateQuote(
  inquiryId: number,
  selectedProductIds: number[] = [],
  additionalNotes?: string,
): Quote {
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
    const searchResults = searchProducts(inquiry.raw_message, products, 5)
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

  const emailData = generateQuoteEmail(
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

export function getQuoteById(id: number): Quote | undefined {
  return load<Quote>(QUOTES_KEY).find(q => q.id === id)
}

// ── Dashboard ─────────────────────────────────────────────────────

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
