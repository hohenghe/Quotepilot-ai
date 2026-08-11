"""
File parser service — parses PDF, Excel, Word files into structured product data.

Currently uses mock data for MVP.
Extensible: replace with real PyPDF2/openpyxl/python-docx parsing.
"""
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
        "lead_time_days": 15,
    },
]


async def parse_file(filename: str, file_content: bytes) -> list[dict[str, Any]]:
    """
    Parse uploaded file and extract product data.

    MVP: returns mock products from a fixed catalog.
    Future: Use PyPDF2 for PDF, openpyxl for Excel, python-docx for Word.
    """
    # Simulate processing time
    import asyncio
    await asyncio.sleep(1.5)

    # Return a subset of mock products based on file type for variety
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return MOCK_PRODUCTS_FROM_FILE[:3]
    elif ext in ("xlsx", "xls"):
        return MOCK_PRODUCTS_FROM_FILE[2:5]
    elif ext in ("docx", "doc"):
        return MOCK_PRODUCTS_FROM_FILE[3:]
    else:
        return random.sample(MOCK_PRODUCTS_FROM_FILE, min(3, len(MOCK_PRODUCTS_FROM_FILE)))
