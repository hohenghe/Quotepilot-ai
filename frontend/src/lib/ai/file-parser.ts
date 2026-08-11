/**
 * File parser — simulates extracting products from uploaded files.
 * Swap in: pdf.js / xlsx / mammoth.js for real client-side parsing.
 */

import type { Product } from "@/types"

const MOCK_PRODUCTS: Omit<Product, "id" | "created_at" | "is_active">[] = [
  {
    name: "LED Panel Light 60x60cm",
    sku: "LED-PL6060-EU",
    category: "led_lighting",
    description: "High-quality LED panel light, 40W, 600x600mm, suitable for office and commercial spaces.",
    technical_specs: "Power: 40W, Voltage: 220-240V, Luminous Flux: 4000lm, Color Temperature: 4000K/6500K, CRI>80, Size: 595x595mm",
    certifications: "CE, RoHS, EMC",
    moq: 100,
    unit_price: 12.50,
    price_range_low: 10.00,
    price_range_high: 15.00,
    pricing: null,
    lead_time_days: 25,
    image_url: null,
  },
  {
    name: "LED High Bay Light 150W",
    sku: "LED-HB150-EU",
    category: "led_lighting",
    description: "Industrial grade LED high bay light, 150W, ideal for warehouses and factories. IP65 waterproof.",
    technical_specs: "Power: 150W, Voltage: 85-265V, Luminous Flux: 18000lm, Color Temperature: 5000K, Beam Angle: 90°, IP65",
    certifications: "CE, RoHS, IP65",
    moq: 50,
    unit_price: 45.00,
    price_range_low: 38.00,
    price_range_high: 52.00,
    pricing: null,
    lead_time_days: 30,
    image_url: null,
  },
  {
    name: "LED Strip Light 5050 RGB",
    sku: "LED-ST5050-RGB",
    category: "led_lighting",
    description: "Flexible LED strip light, 5050 SMD RGB, 60LEDs/m, with remote control.",
    technical_specs: "LED Type: 5050 SMD, 60 LEDs/m, Voltage: DC12V, Power: 14.4W/m, RGB, Width: 10mm, Length: 5m/roll",
    certifications: "CE, RoHS",
    moq: 200,
    unit_price: 3.80,
    price_range_low: 3.00,
    price_range_high: 4.50,
    pricing: null,
    lead_time_days: 15,
    image_url: null,
  },
  {
    name: "LED Flood Light 100W",
    sku: "LED-FL100-EU",
    category: "led_lighting",
    description: "Outdoor LED floodlight, 100W, IP66 waterproof, suitable for building facades and parking lots.",
    technical_specs: "Power: 100W, Voltage: 220-240V, Luminous Flux: 10000lm, Color Temperature: 6500K, IP66, Die-cast aluminum",
    certifications: "CE, RoHS, IP66, TUV",
    moq: 50,
    unit_price: 28.00,
    price_range_low: 24.00,
    price_range_high: 32.00,
    pricing: null,
    lead_time_days: 20,
    image_url: null,
  },
  {
    name: "LED Tube Light T8 120cm",
    sku: "LED-T8-120-EU",
    category: "led_lighting",
    description: "T8 LED tube light, 18W, 120cm, direct replacement for fluorescent tubes.",
    technical_specs: "Power: 18W, Voltage: 220-240V, Luminous Flux: 1800lm, Color Temperature: 4000K/6500K, Length: 1200mm",
    certifications: "CE, RoHS, EMC",
    moq: 500,
    unit_price: 2.50,
    price_range_low: 2.00,
    price_range_high: 3.00,
    pricing: null,
    lead_time_days: 15,
    image_url: null,
  },
]

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export interface ParseResult {
  filename: string
  fileType: string
  products: Omit<Product, "id" | "created_at" | "is_active">[]
}

export async function parseFile(file: File): Promise<ParseResult> {
  const ext = file.name.split(".").pop()?.toLowerCase() || ""

  if (ext === "csv") {
    const products = await parseCSV(file)
    return { filename: file.name, fileType: ext, products }
  }

  // Simulate processing time for other formats
  await sleep(1500)

  let products: typeof MOCK_PRODUCTS

  switch (ext) {
    case "pdf":
      products = MOCK_PRODUCTS.slice(0, 3)
      break
    case "xlsx":
    case "xls":
      products = MOCK_PRODUCTS.slice(2, 5)
      break
    case "docx":
    case "doc":
      products = MOCK_PRODUCTS.slice(3)
      break
    default:
      products = shuffle(MOCK_PRODUCTS).slice(0, 3)
  }

  return {
    filename: file.name,
    fileType: ext,
    products,
  }
}

function parseCSVLine(line: string): string[] {
  const result: string[] = []
  let current = ""
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (ch === "," && !inQuotes) {
      result.push(current.trim())
      current = ""
    } else {
      current += ch
    }
  }
  result.push(current.trim())
  return result
}

async function parseCSV(file: File): Promise<Omit<Product, "id" | "created_at" | "is_active">[]> {
  const text = await file.text()
  const lines = text.split(/\r?\n/).filter(line => line.trim())

  if (lines.length < 2) {
    throw new Error("CSV file must have a header row and at least one data row")
  }

  const headers = parseCSVLine(lines[0]).map(h => h.toLowerCase().replace(/[""\s]/g, ""))
  const products: Omit<Product, "id" | "created_at" | "is_active">[] = []

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i])
    if (values.length === 0 || values.every(v => !v)) continue

    const row: Record<string, string> = {}
    headers.forEach((h, idx) => {
      row[h] = values[idx]?.trim() || ""
    })

    const name = row["name"] || row["productname"] || row["product"] || row["product_name"] || ""
    if (!name) continue

    const pricing = row["pricing"] || null

    products.push({
      name,
      sku: row["sku"] || row["productcode"] || row["product_code"] || null,
      category: (row["category"] || row["productcategory"] || row["product_category"] || "other").toLowerCase().replace(/\s+/g, "_"),
      description: row["description"] || null,
      technical_specs: row["technicalspecs"] || row["technical_specs"] || row["specifications"] || row["specs"] || null,
      certifications: row["certifications"] || row["certs"] || null,
      moq: parseNumber(row["moq"] || row["minimumorderquantity"] || row["minimum_order_quantity"] || row["minqty"]),
      unit_price: null,
      price_range_low: null,
      price_range_high: null,
      pricing,
      lead_time_days: parseNumber(row["leadtime"] || row["lead_time"] || row["leadtime_days"] || row["lead_time_days"] || row["deliverydays"]),
      image_url: null,
    })
  }

  if (products.length === 0) {
    throw new Error("No valid product rows found in CSV")
  }

  return products
}

function parseNumber(val: string | undefined): number | null {
  if (!val) return null
  const cleaned = val.replace(/[^0-9.\-]/g, "")
  const num = parseFloat(cleaned)
  return isNaN(num) ? null : num
}
