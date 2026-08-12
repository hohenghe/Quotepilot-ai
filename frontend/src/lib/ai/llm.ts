/**
 * LLM service — inquiry analysis and quote email generation.
 * Uses real AI when NEXT_PUBLIC_LLM_API_KEY is set, falls back to mock rules.
 */

import type { MatchedProduct } from "@/types"
import { isLLMAvailable, chatCompletion } from "./api-config"

export interface ExtractedInfo {
  productCategory: string
  quantity: number | null
  technicalParams: Record<string, string>
  targetPrice: number | null
  requiredCertifications: string[]
  deliveryLocation: string | null
  deliveryCountry: string | null
  missingInfo: string[]
}

// ═══════════════════════════════════════════════════════════════════
// Real AI — calls OpenAI-compatible API
// ═══════════════════════════════════════════════════════════════════

const ANALYSIS_SYSTEM = `You are an AI assistant for an international trade company. Extract structured information from customer inquiry messages.

Return ONLY valid JSON in this exact format:
{
  "productCategory": "one of: led_lighting, electronics, machinery, textiles, furniture, packaging, auto_parts, hardware, other",
  "quantity": number or null,
  "technicalParams": { "key": "value" } like voltage, plugType, wattage, dimensions, colorTemperature, material,
  "targetPrice": number or null (in USD),
  "requiredCertifications": ["CE", "RoHS", etc.],
  "deliveryLocation": "City, Country" or null,
  "deliveryCountry": "Country" or null,
  "missingInfo": ["info not provided by customer"]
}

Extract any technical params mentioned (voltage, power, size, material, color temp, etc).
For certifications, look for standards like CE, RoHS, FCC, UL, TUV, ISO, REACH, FDA.
For missing info, note what the customer didn't specify (quantity, budget, timeline, payment terms, etc).`

async function analyzeWithAI(rawMessage: string): Promise<ExtractedInfo> {
  if (!isLLMAvailable()) throw new Error("LLM not available")

  const response = await chatCompletion(ANALYSIS_SYSTEM, rawMessage, true)

  let parsed: any
  try {
    parsed = JSON.parse(response)
  } catch {
    // Try to extract JSON from markdown code blocks
    const match = response.match(/```(?:json)?\s*([\s\S]*?)\s*```/)
    parsed = match ? JSON.parse(match[1]) : {}
  }

  return {
    productCategory: parsed.productCategory || "other",
    quantity: typeof parsed.quantity === "number" ? parsed.quantity : null,
    technicalParams: parsed.technicalParams || {},
    targetPrice: typeof parsed.targetPrice === "number" ? parsed.targetPrice : null,
    requiredCertifications: Array.isArray(parsed.requiredCertifications) ? parsed.requiredCertifications : [],
    deliveryLocation: parsed.deliveryLocation || null,
    deliveryCountry: parsed.deliveryCountry || null,
    missingInfo: Array.isArray(parsed.missingInfo) ? parsed.missingInfo : [],
  }
}

const QUOTE_SYSTEM = `You are a professional sales assistant for an international trade company. Generate a formal quotation email in English based on the provided inquiry and matched products.

Return ONLY valid JSON:
{
  "subject": "email subject line",
  "emailBody": "full email body with greeting, product details, pricing, payment terms, shipping terms, and closing",
  "totalAmountLow": number (low end estimate in USD),
  "totalAmountHigh": number (high end estimate in USD)
}

Use professional tone. Include: greeting, thank you, product recommendations with specs, estimated total, payment terms (T/T 30/70), shipping terms (FOB), questions to confirm, closing with contact info.`

async function generateQuoteWithAI(
  inquiryText: string,
  customerName: string | null,
  products: Array<{ name: string; sku: string | null; moq: number | null; pricing: string | null; lead_time_days: number | null }>,
): Promise<{ subject: string; emailBody: string; totalAmountLow: number; totalAmountHigh: number }> {
  if (!isLLMAvailable()) throw new Error("LLM not available")

  const productList = products.map((p, i) =>
    `${i + 1}. ${p.name} (SKU: ${p.sku || "N/A"}) - MOQ: ${p.moq || "-"} - Pricing: ${p.pricing || "Inquire"} - Lead Time: ${p.lead_time_days || "-"} days`
  ).join("\n")

  const userMsg = `Customer Inquiry:\n${inquiryText}\n\nCustomer Name: ${customerName || "Valued Customer"}\n\nRecommended Products:\n${productList}`

  const response = await chatCompletion(QUOTE_SYSTEM, userMsg, true)

  let parsed: any
  try {
    parsed = JSON.parse(response)
  } catch {
    const match = response.match(/```(?:json)?\s*([\s\S]*?)\s*```/)
    parsed = match ? JSON.parse(match[1]) : {}
  }

  return {
    subject: parsed.subject || "Quotation - QuotePilot",
    emailBody: parsed.emailBody || response,
    totalAmountLow: parsed.totalAmountLow || 0,
    totalAmountHigh: parsed.totalAmountHigh || 0,
  }
}

const NO_MATCH_SYSTEM = `You are a professional sales assistant. Write a polite email in English to a customer whose inquiry could not be matched to any products in the catalog. Apologize, suggest they provide more details, and offer to forward their request to product specialists. The email should be professional, warm, and solution-oriented. Return ONLY the email text, with subject line on the first line as "Subject: ...".`

async function generateNoMatchWithAI(inquiryText: string): Promise<string> {
  if (!isLLMAvailable()) throw new Error("LLM not available")

  const response = await chatCompletion(
    NO_MATCH_SYSTEM,
    `Customer Inquiry:\n${inquiryText}\n\nPlease write a professional no-match response email.`,
    false,
  )

  return response.trim()
}

// ═══════════════════════════════════════════════════════════════════
// Mock / rule-based fallback
// ═══════════════════════════════════════════════════════════════════

const CATEGORY_KEYWORDS: Record<string, string[]> = {
  led_lighting: ["led", "light", "lamp", "bulb", "lighting", "luminaire"],
  electronics: ["electronic", "circuit", "pcb", "chip", "sensor"],
  machinery: ["machine", "motor", "pump", "valve", "equipment"],
  textiles: ["fabric", "textile", "garment", "cloth", "t-shirt"],
  furniture: ["furniture", "chair", "table", "sofa", "desk"],
  packaging: ["package", "box", "carton", "bag", "wrap"],
  auto_parts: ["auto", "car", "vehicle", "engine", "brake"],
  hardware: ["hardware", "tool", "screw", "bolt", "fastener"],
}

const KNOWN_CERTS = ["CE", "RoHS", "FCC", "UL", "TUV", "ISO", "REACH", "FDA", "SAA"]

export async function analyzeInquiry(rawMessage: string): Promise<ExtractedInfo> {
  if (isLLMAvailable()) {
    try {
      return await analyzeWithAI(rawMessage)
    } catch (e) {
      console.warn("AI analyze failed, using mock", e)
    }
  }
  return analyzeMock(rawMessage)
}

function analyzeMock(rawMessage: string): ExtractedInfo {
  const text = rawMessage.toLowerCase()

  // Quantity
  let quantity: number | null = null
  const qtyMatch = text.match(/(\d+)\s*(?:units?|pcs?|pieces?|sets?)/i)
    || text.match(/(?:qty|quantity)[:\s]*(\d+)/i)
    || text.match(/need\s+(\d+)/i)
  if (qtyMatch) quantity = parseInt(qtyMatch[1])

  // Category
  let productCategory = "other"
  let maxMatches = 0
  for (const [cat, kws] of Object.entries(CATEGORY_KEYWORDS)) {
    const matches = kws.filter(kw => text.includes(kw)).length
    if (matches > maxMatches) {
      maxMatches = matches
      productCategory = cat
    }
  }

  // Technical params
  const technicalParams: Record<string, string> = {}
  const vm = text.match(/(\d+[-~]\d+|[23]\d{2})\s*v/)
  if (vm) technicalParams["voltage"] = vm[1].toUpperCase() + "V"
  const pm = text.match(/(EU|US|UK|AU)\s*(?:plug|standard)/i)
  if (pm) technicalParams["plugType"] = pm[1].toUpperCase()
  const wm = text.match(/(\d+)\s*(?:watt|w)(?!\/)/)
  if (wm) technicalParams["wattage"] = wm[1] + "W"
  const sm = text.match(/(\d+x\d+(?:x\d+)?)\s*(?:cm|mm)/)
  if (sm) technicalParams["dimensions"] = sm[1] + (text.includes("mm") ? "mm" : "cm")
  const tm = text.match(/(\d+)\s*k/)
  if (tm) technicalParams["colorTemperature"] = tm[1] + "K"

  // Certifications
  const certifications = KNOWN_CERTS.filter(c =>
    new RegExp(`\\b${c}\\b`, "i").test(text)
  )

  // Delivery
  let deliveryCountry: string | null = null
  let deliveryLocation: string | null = null
  const dm = rawMessage.match(
    /(?:delivery|ship(?:ping)?|dest(?:ination)?)\s*(?:to)?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)/i
  )
  if (dm) {
    deliveryLocation = dm[1].trim()
    deliveryCountry = deliveryLocation
  }
  const cm = rawMessage.match(/(?:to|in|at)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z][a-z]+)/)
  if (cm) {
    deliveryLocation = `${cm[1]}, ${cm[2]}`
    deliveryCountry = cm[2].trim()
  }

  // Target price
  let targetPrice: number | null = null
  const priceMatch = text.match(/(?:price|budget|target)\s*(?:[$€]|USD|EUR|around)?\s*\$?(\d+[.,]?\d*)/i)
  if (priceMatch) {
    targetPrice = parseFloat(priceMatch[1].replace(",", "."))
    if (isNaN(targetPrice)) targetPrice = null
  }

  // Missing info
  const missingInfo: string[] = []
  if (!quantity) missingInfo.push("Order quantity not specified")
  if (Object.keys(technicalParams).length === 0) missingInfo.push("Technical specifications not fully provided")
  if (!deliveryLocation) missingInfo.push("Delivery address/destination not specified")
  if (!priceMatch) missingInfo.push("Budget/target price not mentioned")
  if (!/(?:deadline|timeline|delivery\s*date|need\s*by)/i.test(text)) missingInfo.push("Expected delivery timeline not provided")
  if (!/(?:payment|terms|TT|L\/C|term)/i.test(text)) missingInfo.push("Payment terms not specified")
  if (missingInfo.length === 0) missingInfo.push("Inquiry is well-detailed")

  return {
    productCategory,
    quantity,
    technicalParams,
    targetPrice,
    requiredCertifications: certifications,
    deliveryLocation,
    deliveryCountry,
    missingInfo,
  }
}

export async function generateQuoteEmail(
  inquiryText: string,
  customerName: string | null,
  matchedProducts: MatchedProduct[],
  additionalNotes?: string | null,
): Promise<{
  subject: string
  emailBody: string
  totalAmountLow: number
  totalAmountHigh: number
}> {
  if (isLLMAvailable()) {
    try {
      return await generateQuoteWithAI(
        inquiryText,
        customerName,
        matchedProducts.map(p => ({
          name: p.product_name,
          sku: p.sku,
          moq: p.moq,
          pricing: p.pricing,
          lead_time_days: p.lead_time_days,
        })),
      )
    } catch (e) {
      console.warn("AI quote failed, using mock", e)
    }
  }

  const namePart = customerName || "Sir/Madam"

  let qty = 500
  const qm = inquiryText.toLowerCase().match(/(\d+)\s*(?:units?|pcs?|pieces?)/)
  if (qm) qty = parseInt(qm[1])

  const productLines = matchedProducts.slice(0, 5).map((p, i) => {
    let priceStr = ""
    if (p.unit_price) priceStr = `$${p.unit_price.toFixed(2)}/unit`
    else if (p.price_range_low && p.price_range_high) priceStr = `$${p.price_range_low.toFixed(2)} - $${p.price_range_high.toFixed(2)}/unit (depending on quantity)`
    else priceStr = "Please inquire for pricing"

    return `${i + 1}. **${p.product_name || "Product"}** (SKU: ${p.sku || "N/A"})
   - Match Score: ${((p.match_score || 0) * 100).toFixed(0)}%
   - Recommendation: ${p.match_reason || "Meets your requirements"}
   - MOQ: ${p.moq || "-"} units
   - Unit Price: ${priceStr}
   - Lead Time: ${p.lead_time_days || "-"} days
   - Certifications: ${p.certifications || "CE, RoHS"}`
  }).join("\n\n")

  const products = matchedProducts.slice(0, 5)
  let totalLow = 0
  let totalHigh = 0
  for (const p of products) {
    if (p.unit_price) {
      totalLow += p.unit_price * qty
      totalHigh += p.unit_price * qty
    } else {
      totalLow += (p.price_range_low || 0) * qty
      totalHigh += (p.price_range_high || 0) * qty
    }
  }

  const subject = `Quotation for ${products[0]?.product_name || "Your Request"} - QuotePilot`

  const emailBody = `Dear ${namePart},

Thank you for your inquiry. We appreciate your interest in our products.

Based on your requirements, we are pleased to recommend the following product(s):

${productLines}

**Estimated Total Amount**: $${totalLow.toLocaleString()} - $${totalHigh.toLocaleString()} USD
*(Based on estimated quantity of ${qty} units. Final price may vary based on actual order quantity and specifications.)*

**Payment Terms**: T/T, 30% deposit, 70% balance before shipment
**Shipping Terms**: FOB Shenzhen / CIF available upon request

To provide you with the most accurate quotation, we would appreciate if you could confirm the following:

1. Exact order quantity required
2. Preferred delivery date or timeline
3. Shipping method preference (sea freight / air freight)
4. Any specific packaging requirements
5. Billing and shipping address details

${additionalNotes ? `Additional Notes: ${additionalNotes}\n` : ""}
Should you have any questions or require customization, please do not hesitate to contact us. We look forward to building a successful partnership with you.

Best regards,
QuotePilot AI Team
sales@quotepilot.ai`

  return { subject, emailBody, totalAmountLow: totalLow, totalAmountHigh: totalHigh }
}

export async function generateNoMatchResponse(inquiryText: string): Promise<string> {
  if (isLLMAvailable()) {
    try {
      return await generateNoMatchWithAI(inquiryText)
    } catch (e) {
      console.warn("AI no-match failed, using mock", e)
    }
  }

  const subject = "Re: Your Product Inquiry - QuotePilot"

  const body = `Dear Valued Customer,

Thank you for reaching out to us and for your interest in our products. We truly appreciate the opportunity to assist you.

After carefully reviewing your inquiry, we regret to inform you that we were unable to find a perfect match for your specific requirements in our current product catalog. This does not mean we cannot help — our product range is continuously expanding and we also offer custom sourcing and OEM/ODM services.

To better serve you, we would appreciate it if you could provide additional details:

1. Are there any alternative specifications or materials you would consider?
2. What is your target budget range?
3. Do you have samples or reference images you could share?
4. Would you be open to customized solutions?

We will forward your inquiry to our product specialists immediately. They will review your requirements and get back to you within 24 hours with tailored recommendations or alternative solutions.

We are committed to finding the right products for your business and look forward to a successful cooperation.

Best regards,
QuotePilot AI Team
sales@quotepilot.ai`

  return `Subject: ${subject}\n\n${body}`
}
