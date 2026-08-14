export interface Product {
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
  view_count: number
  favorite_count: number
  created_at: string | null
  seller_name: string | null
  seller_email: string | null
}

export interface ProductListResponse {
  total: number
  items: Product[]
}

export interface DocumentResponse {
  id: number
  filename: string
  file_type: string
  status: string
  products_count: number
  error_message: string | null
  created_at: string | null
}

export interface InquiryAnalysis {
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

export interface Inquiry {
  id: number
  customer_name: string | null
  customer_email: string | null
  customer_company: string | null
  raw_message: string
  analyses: InquiryAnalysis[]
  created_at: string | null
}

export interface MatchedProduct {
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

export interface InquiryAnalysisResult {
  inquiry: Inquiry
  analysis: InquiryAnalysis
  matched_products: MatchedProduct[]
}

export interface Quote {
  id: number
  inquiry_id: number | null
  subject: string | null
  email_body: string
  matched_products: MatchedProduct[]
  total_amount_low: number | null
  total_amount_high: number | null
  currency: string
  notes: string | null
  created_at: string | null
}

export interface DashboardStats {
  total_products: number
  today_inquiries: number
  total_inquiries: number
  total_quotes: number
  categories: Record<string, number>
}
