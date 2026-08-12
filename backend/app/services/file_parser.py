import csv
import io
import random
from typing import Any


MOCK_PRODUCTS_FROM_FILE = [
    {
        "name": "LED Panel Light 60x60cm",
        "sku": "LED-PL6060-EU",
        "category": "led_lighting",
        "description": "High-quality LED panel light, 40W, 600x600mm, suitable for office and commercial spaces. Energy efficient with long lifespan.",
        "technical_specs": "Power: 40W, Voltage: 220-240V, Luminous Flux: 4000lm, Color Temperature: 4000K/6500K, CRI>80, Size: 595x595mm",
        "certifications": "CE, RoHS, EMC",
        "moq": 100,
        "unit_price": 12.50,
        "price_range_low": 10.00,
        "price_range_high": 15.00,
        "pricing": "Cost: $8.50, Retail: $15.00, Wholesale 100+: $12.00, Wholesale 500+: $10.50",
        "lead_time_days": 25,
    },
    {
        "name": "LED High Bay Light 150W",
        "sku": "LED-HB150-EU",
        "category": "led_lighting",
        "description": "Industrial grade LED high bay light, 150W, ideal for warehouses and factories. IP65 waterproof rating.",
        "technical_specs": "Power: 150W, Voltage: 85-265V, Luminous Flux: 18000lm, Color Temperature: 5000K, Beam Angle: 90°, IP65",
        "certifications": "CE, RoHS, IP65",
        "moq": 50,
        "unit_price": 45.00,
        "price_range_low": 38.00,
        "price_range_high": 52.00,
        "pricing": "Cost: $32.00, Retail: $52.00, Wholesale 50+: $45.00, Wholesale 200+: $38.00",
        "lead_time_days": 30,
    },
    {
        "name": "LED Strip Light 5050 RGB",
        "sku": "LED-ST5050-RGB",
        "category": "led_lighting",
        "description": "Flexible LED strip light, 5050 SMD RGB, 60LEDs/m, with remote control. Perfect for decorative lighting.",
        "technical_specs": "LED Type: 5050 SMD, 60 LEDs/m, Voltage: DC12V, Power: 14.4W/m, RGB color, Width: 10mm, Length: 5m/roll",
        "certifications": "CE, RoHS",
        "moq": 200,
        "unit_price": 3.80,
        "price_range_low": 3.00,
        "price_range_high": 4.50,
        "pricing": "Cost: $2.50, Retail: $4.50, Wholesale 500+: $3.50, Wholesale 1000+: $2.80",
        "lead_time_days": 15,
    },
    {
        "name": "LED Flood Light 100W",
        "sku": "LED-FL100-EU",
        "category": "led_lighting",
        "description": "Outdoor LED floodlight, 100W, IP66 waterproof, suitable for building facades, parking lots, and sports fields.",
        "technical_specs": "Power: 100W, Voltage: 220-240V, Luminous Flux: 10000lm, Color Temperature: 6500K, IP66, Die-cast aluminum housing",
        "certifications": "CE, RoHS, IP66, TUV",
        "moq": 50,
        "unit_price": 28.00,
        "price_range_low": 24.00,
        "price_range_high": 32.00,
        "pricing": "Cost: $19.00, Retail: $32.00, Wholesale 50+: $28.00, Wholesale 100+: $24.00",
        "lead_time_days": 20,
    },
    {
        "name": "LED Tube Light T8 120cm",
        "sku": "LED-T8-120-EU",
        "category": "led_lighting",
        "description": "T8 LED tube light, 18W, 120cm, direct replacement for fluorescent tubes. Flicker-free driver.",
        "technical_specs": "Power: 18W, Voltage: 220-240V, Luminous Flux: 1800lm, Color Temperature: 4000K/6500K, Length: 1200mm, Diameter: 26mm",
        "certifications": "CE, RoHS, EMC",
        "moq": 500,
        "unit_price": 2.50,
        "price_range_low": 2.00,
        "price_range_high": 3.00,
        "pricing": "Cost: $1.20, Retail: $3.00, Wholesale 1000+: $2.20, Wholesale 5000+: $1.80",
        "lead_time_days": 15,
    },
]

COLUMN_ALIASES = {
    "name": ["name", "productname", "product", "product_name"],
    "sku": ["sku", "productcode", "product_code"],
    "category": ["category", "productcategory", "product_category"],
    "description": ["description"],
    "technical_specs": ["technicalspecs", "technical_specs", "specifications", "specs"],
    "certifications": ["certifications", "certs"],
    "moq": ["moq", "minimumorderquantity", "minimum_order_quantity", "minqty"],
    "pricing": ["pricing"],
    "lead_time_days": ["leadtime", "lead_time", "leadtime_days", "lead_time_days", "deliverydays"],
}


def _normalize(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "").replace(" ", "")


def _parse_number(val: str) -> int | None:
    if not val or not val.strip():
        return None
    cleaned = "".join(c for c in val if c.isdigit() or c in ".-")
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _resolve_column(headers: list[str]) -> dict[str, int]:
    header_map: dict[str, str] = {}
    for h in headers:
        header_map[_normalize(h)] = h

    mapping: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            norm = _normalize(alias)
            if norm in header_map:
                mapping[field] = headers.index(header_map[norm])
                break
    return mapping


async def _parse_csv(filename: str, content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if len(rows) < 2:
        raise ValueError("CSV file must have a header row and at least one data row")

    headers = rows[0]
    col_map = _resolve_column(headers)

    if "name" not in col_map:
        raise ValueError("CSV must have a 'name' column")

    products: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row or all(not cell.strip() for cell in row):
            continue

        def get_val(field: str) -> str:
            idx = col_map.get(field)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        name = get_val("name")
        if not name:
            continue

        category = get_val("category") or "other"
        category = category.lower().replace(" ", "_")

        products.append({
            "name": name,
            "sku": get_val("sku") or None,
            "category": category,
            "description": get_val("description") or None,
            "technical_specs": get_val("technical_specs") or None,
            "certifications": get_val("certifications") or None,
            "moq": _parse_number(get_val("moq")),
            "unit_price": None,
            "price_range_low": None,
            "price_range_high": None,
            "pricing": get_val("pricing") or None,
            "lead_time_days": _parse_number(get_val("lead_time_days")),
        })

    if not products:
        raise ValueError("No valid product rows found in CSV")

    return products


async def parse_file(filename: str, file_content: bytes) -> list[dict[str, Any]]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        return await _parse_csv(filename, file_content)

    import asyncio
    await asyncio.sleep(1.5)

    if ext == "pdf":
        return MOCK_PRODUCTS_FROM_FILE[:3]
    elif ext in ("xlsx", "xls"):
        return MOCK_PRODUCTS_FROM_FILE[2:5]
    elif ext in ("docx", "doc"):
        return MOCK_PRODUCTS_FROM_FILE[3:]
    else:
        return random.sample(MOCK_PRODUCTS_FROM_FILE, min(3, len(MOCK_PRODUCTS_FROM_FILE)))
