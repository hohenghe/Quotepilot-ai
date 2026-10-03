import asyncio
import csv
import io
from typing import Any, Iterable

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

# Parsing XLSX/PDF is CPU and memory intensive. Limit concurrent uploads per
# worker so a burst does not consume every default executor thread.
_PARSE_SEMAPHORE = asyncio.Semaphore(2)


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


def _rows_to_products(rows: Iterable[list[str]]) -> list[dict[str, Any]]:
    rows = iter(rows)
    headers = next(rows, None)
    if headers is None:
        raise ValueError("File must have a header row and at least one data row")
    col_map = _resolve_column(headers)

    if "name" not in col_map:
        raise ValueError("File must have a 'name' column")

    products: list[dict[str, Any]] = []
    for row in rows:
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
        raise ValueError("No valid product rows found")

    return products


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    # Decode one record at a time; holding a full Unicode copy while building
    # all Product dictionaries caused high peak memory on large uploads.
    with io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline="") as stream:
        return _rows_to_products(csv.reader(stream))


def _parse_excel(content: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = (
            ["" if cell is None else str(cell).strip() for cell in row]
            for row in ws.iter_rows(values_only=True)
        )
        return _rows_to_products(rows)
    finally:
        wb.close()


def _parse_docx(content: bytes) -> list[dict[str, Any]]:
    from docx import Document

    doc = Document(io.BytesIO(content))
    rows: list[list[str]] = []
    for table in doc.tables:
        for row in table.rows:
            rows.append([cell.text.strip() for cell in row.cells])
    if not rows:
        raise ValueError("No tables found in Word document; expected a product table")
    return _rows_to_products(rows)


def _parse_pdf(content: bytes) -> list[dict[str, Any]]:
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)

    full_text = "\n".join(parts).strip()
    if not full_text:
        raise ValueError("No extractable text found in PDF")

    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    name = lines[0] if lines else "Imported from PDF"

    return [{
        "name": name,
        "sku": None,
        "category": "other",
        "description": full_text,
        "technical_specs": None,
        "certifications": None,
        "moq": None,
        "unit_price": None,
        "price_range_low": None,
        "price_range_high": None,
        "pricing": None,
        "lead_time_days": None,
    }]


async def parse_file(filename: str, file_content: bytes) -> list[dict[str, Any]]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    parsers = {"csv": _parse_csv, "xlsx": _parse_excel,
               "docx": _parse_docx, "pdf": _parse_pdf}
    parser = parsers.get(ext)
    if parser is not None:
        async with _PARSE_SEMAPHORE:
            return await asyncio.to_thread(parser, file_content)
    if ext == "xls":
        raise ValueError("Legacy .xls format is not supported; please upload .xlsx")
    if ext == "doc":
        raise ValueError("Legacy .doc format is not supported; please upload .docx")

    raise ValueError(f"Unsupported file type: {ext}")
