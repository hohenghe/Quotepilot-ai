import re
import json
import logging
from typing import Any
import httpx

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LLM] %(message)s")
logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM = """You are an AI assistant for an international trade company.
Translate the customer inquiry into English (if it is not already in English), then extract structured information from it.

Return ONLY valid JSON in this exact format:
{
  "translation": "English translation of the inquiry (empty string if the inquiry is already in English)",
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


async def _call_llm(
    system_prompt: str,
    user_message: str,
    json_mode: bool = False,
    operation: str = "llm",
    max_tokens: int = 2000,
) -> str:
    body: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
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
        _log_usage(data, operation)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def _log_usage(data: dict[str, Any], operation: str) -> None:
    """Log token/cache usage metadata only (never prompt or response content)."""
    usage = data.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens", 0)
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    details = usage.get("completion_tokens_details") or {}
    reasoning = details.get("reasoning_tokens", 0)

    total = hit + miss
    if total == 0 and prompt_tokens:
        # Some providers only expose total prompt tokens without cache breakdown.
        miss = prompt_tokens
        total = prompt_tokens
    hit_rate = (hit / total * 100.0) if total else 0.0

    logger.info(
        "LLM usage model=%s operation=%s prompt_tokens=%s cache_hit=%s cache_miss=%s completion=%s reasoning=%s cache_hit_rate=%.2f%%",
        settings.LLM_MODEL, operation, prompt_tokens, hit, miss, completion, reasoning, hit_rate,
    )


def _parse_json_response(response: str) -> dict[str, Any]:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if m:
            return json.loads(m.group(1))
        return {}


async def _analyze_with_ai(raw_message: str) -> dict[str, Any]:
    response = await _call_llm(ANALYSIS_SYSTEM, raw_message, json_mode=True, operation="inquiry_analysis", max_tokens=1200)
    parsed = _parse_json_response(response)

    return {
        "translation": (parsed.get("translation") or "").strip(),
        "product_category": parsed.get("productCategory", "other"),
        "quantity": parsed.get("quantity") if isinstance(parsed.get("quantity"), (int, float)) else None,
        "technical_params": parsed.get("technicalParams") if isinstance(parsed.get("technicalParams"), dict) else {},
        "target_price": parsed.get("targetPrice") if isinstance(parsed.get("targetPrice"), (int, float)) else None,
        "required_certifications": parsed.get("requiredCertifications") if isinstance(parsed.get("requiredCertifications"), list) else [],
        "delivery_location": parsed.get("deliveryLocation"),
        "delivery_country": parsed.get("deliveryCountry"),
        "missing_info": parsed.get("missingInfo") if isinstance(parsed.get("missingInfo"), list) else [],
    }


async def analyze_inquiry(raw_message: str) -> dict[str, Any]:
    # Translation and structured analysis are produced in a single request so
    # non-English inquiries no longer cost two separate LLM calls.
    logger.warning("Calling LLM: %s model=%s", settings.OPENAI_BASE_URL, settings.LLM_MODEL)
    result = await _analyze_with_ai(raw_message)
    result["ai_used"] = True
    result["translated"] = bool(result.get("translation"))
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

    response = await _call_llm(QUOTE_SYSTEM, user_msg, json_mode=True, operation="quote_generation", max_tokens=2000)
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
