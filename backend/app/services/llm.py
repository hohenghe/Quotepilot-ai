"""
LLM service — analyzes inquiries and generates email replies.

MVP: Uses rule-based extraction + template generation with realistic mock.
Future: Replace with OpenAI GPT-4o, DeepSeek Chat, or any LLM API.

Extension point:
    async def call_llm(system_prompt: str, user_prompt: str) -> str:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        return resp.choices[0].message.content
"""
import re
import random
from typing import Any


async def analyze_inquiry(raw_message: str) -> dict[str, Any]:
    """
    Analyze inquiry text and extract structured information.

    MVP: Regex-based extraction with heuristics.
    Future: Send to LLM for NER + structured extraction.
    """
    text = raw_message.lower()

    # Quantity extraction
    quantity = None
    qty_patterns = [
        r"(\d+)\s*(?:units?|pcs?|pieces?|sets?)",
        r"(?:qty|quantity)[:\s]*(\d+)",
        r"need\s+(\d+)",
    ]
    for pat in qty_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            quantity = int(m.group(1))
            break

    # Product category detection
    category_keywords = {
        "led_lighting": ["led", "light", "lamp", "bulb", "lighting", "luminaire"],
        "electronics": ["electronic", "circuit", "pcb", "chip", "sensor"],
        "machinery": ["machine", "motor", "pump", "valve", "equipment"],
        "textiles": ["fabric", "textile", "garment", "cloth", "t-shirt"],
        "furniture": ["furniture", "chair", "table", "sofa", "desk"],
        "packaging": ["package", "box", "carton", "bag", "wrap"],
        "auto_parts": ["auto", "car", "vehicle", "engine", "brake"],
        "hardware": ["hardware", "tool", "screw", "bolt", "fastener"],
    }
    detected_category = "other"
    max_matches = 0
    for cat, kws in category_keywords.items():
        matches = sum(1 for kw in kws if kw in text)
        if matches > max_matches:
            max_matches = matches
            detected_category = cat

    # Technical params extraction
    technical_params: dict[str, str] = {}
    voltage_match = re.search(r"(\d+[-~]\d+|[23]\d{2})\s*v", text)
    if voltage_match:
        technical_params["voltage"] = voltage_match.group(1).upper() + "V"

    plug_match = re.search(r"(EU|US|UK|AU)\s*(?:plug|standard)", text, re.IGNORECASE)
    if plug_match:
        technical_params["plug_type"] = plug_match.group(1).upper()

    watt_match = re.search(r"(\d+)\s*(?:watt|w)(?!\/)", text)
    if watt_match:
        technical_params["wattage"] = watt_match.group(1) + "W"

    size_match = re.search(r"(\d+x\d+(?:x\d+)?)\s*(?:cm|mm)", text)
    if size_match:
        technical_params["dimensions"] = size_match.group(1) + (
            "mm" if "mm" in text else "cm"
        )

    temp_match = re.search(r"(\d+)\s*k", text)
    if temp_match:
        technical_params["color_temperature"] = temp_match.group(1) + "K"

    # Certifications
    cert_patterns = ["CE", "RoHS", "FCC", "UL", "TUV", "ISO", "REACH", "FDA", "SAA"]
    certifications = [c for c in cert_patterns if re.search(rf"\b{c}\b", text, re.IGNORECASE)]

    # Delivery location
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

    # Target price
    price_match = re.search(r"(?:price|budget|target)[^$€]*(?:[$€]|USD|EUR)?\s*(\d+[.,]?\d*)", text)
    target_price = None
    if price_match:
        try:
            target_price = float(price_match.group(1).replace(",", "."))
        except ValueError:
            pass

    # Missing information
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


async def generate_quote_email(
    inquiry_text: str,
    customer_name: str | None,
    matched_products: list[dict[str, Any]],
    additional_notes: str | None = None,
) -> dict[str, Any]:
    """
    Generate a professional English quotation email.

    MVP: Template-based generation with product data.
    Future: Use LLM to generate personalized, context-aware emails.
    """
    name_part = customer_name or "Sir/Madam"

    # Build product details section
    product_lines = []
    total_low = 0.0
    total_high = 0.0
    qty = 500  # default quantity for estimation

    qty_match = re.search(r"(\d+)\s*(?:units?|pcs?|pieces?)", inquiry_text.lower())
    if qty_match:
        qty = int(qty_match.group(1))

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
    subject = f"Quotation for {matched_products[0].get('product_name', 'Your Request')} - QuotePilot"

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

{f"Additional Notes: {additional_notes}" if additional_notes else ""}

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
