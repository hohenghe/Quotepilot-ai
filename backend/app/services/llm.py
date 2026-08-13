import re
import json
import logging
from typing import Any
import httpx

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LLM] %(message)s")
logger = logging.getLogger(__name__)

TRANSLATE_SYSTEM = "You are a professional translator. Translate the following text to English. Return ONLY the English translation, nothing else — no explanations, no notes."

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


def _has_non_ascii(text: str) -> bool:
    return any(ord(c) > 127 for c in text)


async def _translate_to_english(text: str) -> str:
    return await _call_llm(TRANSLATE_SYSTEM, text, json_mode=False)


async def analyze_inquiry(raw_message: str) -> dict[str, Any]:
    message = raw_message
    translated = False

    if _has_non_ascii(message):
        logger.warning("Non-English detected, translating...")
        message = await _translate_to_english(message)
        translated = True
        logger.warning("Translated inquiry: %s", message[:200])

    logger.warning("Calling LLM: %s model=%s", settings.OPENAI_BASE_URL, settings.LLM_MODEL)
    result = await _analyze_with_ai(message)
    result["ai_used"] = True
    result["translated"] = translated
    return result


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


async def generate_quote_email(
    inquiry_text: str,
    customer_name: str | None,
    matched_products: list[dict[str, Any]],
    additional_notes: str | None = None,
) -> dict[str, Any]:
    return await _generate_quote_with_ai(
        inquiry_text, customer_name, matched_products, additional_notes
    )
