import re
import json
import logging
from typing import Any
import httpx

from app.core.config import settings, is_llm_available

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM = """You are an AI assistant for an international trade company. Extract structured information from customer inquiry messages.

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
For missing info, note what the customer didn't specify (quantity, budget, timeline, payment terms, etc)."""

QUOTE_SYSTEM = """You are a professional sales assistant for an international trade company. Generate a formal quotation email in English based on the provided inquiry and matched products.

Return ONLY valid JSON:
{
  "subject": "email subject line",
  "emailBody": "full email body with greeting, product details, pricing, payment terms, shipping terms, and closing",
  "totalAmountLow": number (low end estimate in USD),
  "totalAmountHigh": number (high end estimate in USD)
}

Use professional tone. Include: greeting, thank you, product recommendations with specs, estimated total, payment terms (T/T 30/70), shipping terms (FOB), questions to confirm, closing with contact info."""

NO_MATCH_SYSTEM = """You are a professional sales assistant. Write a polite email in English to a customer whose inquiry could not be matched to any products in the catalog. Apologize, suggest they provide more details, and offer to forward their request to product specialists. The email should be professional, warm, and solution-oriented. Return ONLY the email text, with subject line on the first line as "Subject: ..."."""


async def _call_llm(system_prompt: str, user_message: str, json_mode: bool = False) -> str:
    body: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.OPENAI_BASE_URL}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            },
            json=body,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def _parse_json_response(response: str) -> dict[str, Any]:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if m:
            return json.loads(m.group(1))
        return {}


# ═══════════════════════════════════════════════════════════════════
# Real AI analysis
# ═══════════════════════════════════════════════════════════════════

async def _analyze_with_ai(raw_message: str) -> dict[str, Any]:
    response = await _call_llm(ANALYSIS_SYSTEM, raw_message, json_mode=True)
    parsed = _parse_json_response(response)

    return {
        "product_category": parsed.get("productCategory", "other"),
        "quantity": parsed.get("quantity") if isinstance(parsed.get("quantity"), (int, float)) else None,
        "technical_params": parsed.get("technicalParams") if isinstance(parsed.get("technicalParams"), dict) else {},
        "target_price": parsed.get("targetPrice") if isinstance(parsed.get("targetPrice"), (int, float)) else None,
        "required_certifications": parsed.get("requiredCertifications") if isinstance(parsed.get("requiredCertifications"), list) else [],
        "delivery_location": parsed.get("deliveryLocation"),
        "delivery_country": parsed.get("deliveryCountry"),
        "missing_info": parsed.get("missingInfo") if isinstance(parsed.get("missingInfo"), list) else [],
    }


# ═══════════════════════════════════════════════════════════════════
# Mock / rule-based analysis
# ═══════════════════════════════════════════════════════════════════

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "led_lighting": ["led", "light", "lamp", "bulb", "lighting", "luminaire"],
    "electronics": ["electronic", "circuit", "pcb", "chip", "sensor"],
    "machinery": ["machine", "motor", "pump", "valve", "equipment"],
    "textiles": ["fabric", "textile", "garment", "cloth", "t-shirt"],
    "furniture": ["furniture", "chair", "table", "sofa", "desk"],
    "packaging": ["package", "box", "carton", "bag", "wrap"],
    "auto_parts": ["auto", "car", "vehicle", "engine", "brake"],
    "hardware": ["hardware", "tool", "screw", "bolt", "fastener"],
}

KNOWN_CERTS = ["CE", "RoHS", "FCC", "UL", "TUV", "ISO", "REACH", "FDA", "SAA"]


async def _analyze_mock(raw_message: str) -> dict[str, Any]:
    text = raw_message.lower()

    quantity = None
    for pat in [
        r"(\d+)\s*(?:units?|pcs?|pieces?|sets?)",
        r"(?:qty|quantity)[:\s]*(\d+)",
        r"need\s+(\d+)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            quantity = int(m.group(1))
            break

    detected_category = "other"
    max_matches = 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in kws if kw in text)
        if matches > max_matches:
            max_matches = matches
            detected_category = cat

    technical_params: dict[str, str] = {}
    voltage_match = re.search(r"(\d+[-~]\d+|[23]\d{2})\s*v", text)
    if voltage_match:
        technical_params["voltage"] = voltage_match.group(1).upper() + "V"

    plug_match = re.search(r"(EU|US|UK|AU)\s*(?:plug|standard)", text, re.IGNORECASE)
    if plug_match:
        technical_params["plugType"] = plug_match.group(1).upper()

    watt_match = re.search(r"(\d+)\s*(?:watt|w)(?!/)", text)
    if watt_match:
        technical_params["wattage"] = watt_match.group(1) + "W"

    size_match = re.search(r"(\d+x\d+(?:x\d+)?)\s*(?:cm|mm)", text)
    if size_match:
        technical_params["dimensions"] = size_match.group(1) + ("mm" if "mm" in text else "cm")

    temp_match = re.search(r"(\d+)\s*k", text)
    if temp_match:
        technical_params["colorTemperature"] = temp_match.group(1) + "K"

    certifications = [c for c in KNOWN_CERTS if re.search(rf"\b{c}\b", text, re.IGNORECASE)]

    delivery_country = None
    delivery_location = None
    country_match = re.search(
        r"(?:delivery|ship(?:ping)?|dest(?:ination)?)\s*(?:to)?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
        raw_message,
        re.IGNORECASE,
    )
    if country_match:
        delivery_location = country_match.group(1).strip()
        delivery_country = delivery_location

    city_match = re.search(
        r"(?:to|in|at)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z][a-z]+)",
        raw_message,
    )
    if city_match:
        delivery_location = f"{city_match.group(1)}, {city_match.group(2)}"
        delivery_country = city_match.group(2).strip()

    target_price = None
    price_match = re.search(r"(?:price|budget|target)\s*(?:[$€]|USD|EUR|around)?\s*\$?(\d+[.,]?\d*)", text)
    if price_match:
        try:
            target_price = float(price_match.group(1).replace(",", "."))
        except ValueError:
            pass

    missing_info = []
    if not quantity:
        missing_info.append("Order quantity not specified")
    if not technical_params:
        missing_info.append("Technical specifications not fully provided")
    if not delivery_location:
        missing_info.append("Delivery address/destination not specified")
    if not price_match:
        missing_info.append("Budget/target price not mentioned")
    if not re.search(r"(?:deadline|timeline|delivery\s*date|need\s*by)", text, re.IGNORECASE):
        missing_info.append("Expected delivery timeline not provided")
    if not re.search(r"(?:payment|terms|TT|L/C|term)", text, re.IGNORECASE):
        missing_info.append("Payment terms not specified")
    if not missing_info:
        missing_info.append("Inquiry is well-detailed")

    return {
        "product_category": detected_category,
        "quantity": quantity,
        "technical_params": technical_params,
        "target_price": target_price,
        "required_certifications": certifications,
        "delivery_location": delivery_location,
        "delivery_country": delivery_country,
        "missing_info": missing_info,
    }


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

async def analyze_inquiry(raw_message: str) -> dict[str, Any]:
    if is_llm_available():
        try:
            logger.info("Calling LLM: %s model=%s", settings.OPENAI_BASE_URL, settings.LLM_MODEL)
            return await _analyze_with_ai(raw_message)
        except Exception as e:
            logger.warning("AI analyze failed, falling back to mock: %s", e)
    else:
        logger.info("LLM not configured, using mock analysis")
    return await _analyze_mock(raw_message)


async def generate_quote_email(
    inquiry_text: str,
    customer_name: str | None,
    matched_products: list[dict[str, Any]],
    additional_notes: str | None = None,
) -> dict[str, Any]:
    if is_llm_available():
        try:
            return await _generate_quote_with_ai(
                inquiry_text, customer_name, matched_products, additional_notes
            )
        except Exception as e:
            logger.warning("AI quote failed, falling back to mock: %s", e)
  
    return await _generate_quote_mock(
        inquiry_text, customer_name, matched_products, additional_notes
    )


async def generate_no_match_response(inquiry_text: str) -> str:
    if is_llm_available():
        try:
            return await _generate_no_match_with_ai(inquiry_text)
        except Exception as e:
            logger.warning("AI no-match failed, falling back to mock: %s", e)
    return _generate_no_match_mock()


# ═══════════════════════════════════════════════════════════════════
# Real AI — quote generation
# ═══════════════════════════════════════════════════════════════════

async def _generate_quote_with_ai(
    inquiry_text: str,
    customer_name: str | None,
    products: list[dict[str, Any]],
    additional_notes: str | None = None,
) -> dict[str, Any]:
    product_lines = []
    for i, p in enumerate(products[:5], 1):
        name = p.get("product_name") or p.get("name", f"Product {i}")
        sku = p.get("sku", "N/A")
        moq = p.get("moq", "-")
        pricing = p.get("pricing", None)
        lead = p.get("lead_time_days", "-")
        price_info = pricing if pricing else "Inquire"
        product_lines.append(
            f"{i}. {name} (SKU: {sku}) - MOQ: {moq} - Pricing: {price_info} - Lead Time: {lead} days"
        )

    user_msg = (
        f"Customer Inquiry:\n{inquiry_text}\n\n"
        f"Customer Name: {customer_name or 'Valued Customer'}\n\n"
        f"Recommended Products:\n" + "\n".join(product_lines)
    )
    if additional_notes:
        user_msg += f"\n\nAdditional Notes: {additional_notes}"

    response = await _call_llm(QUOTE_SYSTEM, user_msg, json_mode=True)
    parsed = _parse_json_response(response)

    return {
        "subject": parsed.get("subject", "Quotation - QuotePilot"),
        "email_body": parsed.get("emailBody", response),
        "matched_products": products,
        "total_amount_low": parsed.get("totalAmountLow", 0),
        "total_amount_high": parsed.get("totalAmountHigh", 0),
        "currency": "USD",
        "notes": additional_notes,
    }


# ═══════════════════════════════════════════════════════════════════
# Mock quote email
# ═══════════════════════════════════════════════════════════════════

async def _generate_quote_mock(
    inquiry_text: str,
    customer_name: str | None,
    matched_products: list[dict[str, Any]],
    additional_notes: str | None = None,
) -> dict[str, Any]:
    name_part = customer_name or "Sir/Madam"

    qty = 500
    qty_match = re.search(r"(\d+)\s*(?:units?|pcs?|pieces?)", inquiry_text.lower())
    if qty_match:
        qty = int(qty_match.group(1))

    product_lines = []
    total_low = 0.0
    total_high = 0.0

    for i, p in enumerate(matched_products[:5], 1):
        name = p.get("product_name") or p.get("name", f"Product {i}")
        sku = p.get("sku", "N/A")
        moq = p.get("moq", "-")
        unit_price = p.get("unit_price", None)
        low = p.get("price_range_low", None)
        high = p.get("price_range_high", None)
        lead = p.get("lead_time_days", "-")

        price_str = ""
        if unit_price:
            price_str = f"${unit_price:.2f}/unit"
            total_low += unit_price * qty
            total_high += unit_price * qty
        elif low and high:
            price_str = f"${low:.2f} - ${high:.2f}/unit (depending on quantity)"
            total_low += low * qty
            total_high += high * qty
        else:
            price_str = "Please inquire for pricing"

        product_lines.append(
            f"""{i}. **{name}** (SKU: {sku})
   - Match Score: {p.get('match_score', 0) * 100:.0f}%
   - Recommendation: {p.get('match_reason', 'Meets your requirements')}
   - MOQ: {moq} units
   - Unit Price: {price_str}
   - Lead Time: {lead} days
   - Certifications: {p.get('certifications', 'CE, RoHS')}
"""
        )

    products_section = "\n".join(product_lines)
    currency = "USD"
    subject = f"Quotation for {matched_products[0].get('product_name', 'Your Request')} - QuotePilot" if matched_products else "Quotation - QuotePilot"

    email_body = f"""Dear {name_part},

Thank you for your inquiry. We appreciate your interest in our products.

Based on your requirements, we are pleased to recommend the following product(s):

{products_section}

**Estimated Total Amount**: ${total_low:,.2f} - ${total_high:,.2f} {currency}
*(Based on estimated quantity of {qty} units. Final price may vary based on actual order quantity and specifications.)*

**Payment Terms**: T/T, 30% deposit, 70% balance before shipment
**Shipping Terms**: FOB Shenzhen / CIF available upon request

To provide you with the most accurate quotation, we would appreciate if you could confirm the following:

1. Exact order quantity required
2. Preferred delivery date or timeline
3. Shipping method preference (sea freight / air freight)
4. Any specific packaging requirements
5. Billing and shipping address details

{f"Additional Notes: {additional_notes}\n" if additional_notes else ""}
Should you have any questions or require customization, please do not hesitate to contact us. We look forward to building a successful partnership with you.

Best regards,
QuotePilot AI Team
sales@quotepilot.ai
"""

    return {
        "subject": subject,
        "email_body": email_body,
        "matched_products": matched_products,
        "total_amount_low": total_low,
        "total_amount_high": total_high,
        "currency": currency,
        "notes": additional_notes,
    }


# ═══════════════════════════════════════════════════════════════════
# No-match response
# ═══════════════════════════════════════════════════════════════════

async def _generate_no_match_with_ai(inquiry_text: str) -> str:
    response = await _call_llm(
        NO_MATCH_SYSTEM,
        f"Customer Inquiry:\n{inquiry_text}\n\nPlease write a professional no-match response email.",
        json_mode=False,
    )
    return response.strip()


def _generate_no_match_mock() -> str:
    subject = "Re: Your Product Inquiry - QuotePilot"
    body = """Dear Valued Customer,

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
sales@quotepilot.ai"""

    return f"Subject: {subject}\n\n{body}"
