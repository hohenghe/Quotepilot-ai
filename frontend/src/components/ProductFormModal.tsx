"use client"

import { useState, useEffect } from "react"
import { X, ImagePlus, Trash2, Loader2 } from "lucide-react"
import { createProduct, updateProduct, uploadImage } from "@/lib/api-client"
import type { ProductPayload } from "@/lib/api-client"
import { useToast } from "@/components/Toast"
import { useT } from "@/i18n/I18nProvider"
import type { Product } from "@/types"

const CATEGORIES = [
  "led_lighting", "electronics", "machinery", "textiles",
  "furniture", "packaging", "auto_parts", "hardware", "other",
]

interface Props {
  open: boolean
  initial: Product | null
  onClose: () => void
  onSaved: () => void
}

const MAX_IMAGES = 10

export default function ProductFormModal({ open, initial, onClose, onSaved }: Props) {
  const { t } = useT()
  const toast = useToast()

  const [name, setName] = useState("")
  const [sku, setSku] = useState("")
  const [category, setCategory] = useState("other")
  const [description, setDescription] = useState("")
  const [technicalSpecs, setTechnicalSpecs] = useState("")
  const [certifications, setCertifications] = useState("")
  const [moq, setMoq] = useState("")
  const [unitPrice, setUnitPrice] = useState("")
  const [priceLow, setPriceLow] = useState("")
  const [priceHigh, setPriceHigh] = useState("")
  const [pricing, setPricing] = useState("")
  const [leadTime, setLeadTime] = useState("")
  const [images, setImages] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (initial) {
      setName(initial.name || "")
      setSku(initial.sku || "")
      setCategory(initial.category || "other")
      setDescription(initial.description || "")
      setTechnicalSpecs(initial.technical_specs || "")
      setCertifications(initial.certifications || "")
      setMoq(initial.moq != null ? String(initial.moq) : "")
      setUnitPrice(initial.unit_price != null ? String(initial.unit_price) : "")
      setPriceLow(initial.price_range_low != null ? String(initial.price_range_low) : "")
      setPriceHigh(initial.price_range_high != null ? String(initial.price_range_high) : "")
      setPricing(initial.pricing || "")
      setLeadTime(initial.lead_time_days != null ? String(initial.lead_time_days) : "")
      setImages(initial.images || [])
    } else {
      setName(""); setSku(""); setCategory("other"); setDescription("")
      setTechnicalSpecs(""); setCertifications(""); setMoq(""); setUnitPrice("")
      setPriceLow(""); setPriceHigh(""); setPricing(""); setLeadTime(""); setImages([])
    }
  }, [open, initial])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null

  const num = (v: string) => (v.trim() === "" ? null : Number(v))

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (images.length >= MAX_IMAGES) {
      toast.push("error", t.seller.maxImages)
      e.target.value = ""
      return
    }
    setUploading(true)
    try {
      const res = await uploadImage(file, "product")
      setImages(prev => [...prev, res.url])
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const removeImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    if (!name.trim()) return
    setSaving(true)
    const payload: ProductPayload = {
      name: name.trim(),
      sku: sku.trim() || null,
      category,
      description: description.trim() || null,
      technical_specs: technicalSpecs.trim() || null,
      certifications: certifications.trim() || null,
      moq: num(moq),
      unit_price: num(unitPrice),
      price_range_low: num(priceLow),
      price_range_high: num(priceHigh),
      pricing: pricing.trim() || null,
      lead_time_days: num(leadTime),
      images,
    }
    try {
      if (initial) {
        await updateProduct(initial.id, payload)
      } else {
        await createProduct(payload)
      }
      toast.push("success", t.seller.productSaved)
      onSaved()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div className="relative bg-white w-full sm:max-w-2xl sm:rounded-xl border border-slate-200 shadow-lg max-h-[92vh] flex flex-col rounded-t-2xl">
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-slate-200 flex-shrink-0">
          <h2 className="text-lg font-semibold text-slate-900">
            {initial ? t.seller.editProduct : t.seller.addProduct}
          </h2>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg" aria-label={t.common.cancel}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          <div>
            <label className="label">{t.seller.productName} *</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">{t.products.sku}</label>
              <input className="input" value={sku} onChange={e => setSku(e.target.value)} />
            </div>
            <div>
              <label className="label">{t.seller.productCategory}</label>
              <select className="input" value={category} onChange={e => setCategory(e.target.value)}>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="label">{t.seller.productDesc}</label>
            <textarea className="input min-h-[70px] resize-y" value={description} onChange={e => setDescription(e.target.value)} />
          </div>

          <div>
            <label className="label">{t.seller.productSpecs}</label>
            <textarea className="input min-h-[60px] resize-y" value={technicalSpecs} onChange={e => setTechnicalSpecs(e.target.value)} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">{t.seller.productCerts}</label>
              <input className="input" value={certifications} onChange={e => setCertifications(e.target.value)} />
            </div>
            <div>
              <label className="label">{t.seller.productPricing}</label>
              <input className="input" value={pricing} onChange={e => setPricing(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div>
              <label className="label">{t.products.moq}</label>
              <input className="input" type="number" value={moq} onChange={e => setMoq(e.target.value)} />
            </div>
            <div>
              <label className="label">{t.products.unitPrice}</label>
              <input className="input" type="number" value={unitPrice} onChange={e => setUnitPrice(e.target.value)} />
            </div>
            <div>
              <label className="label">{t.products.leadTime}</label>
              <input className="input" type="number" value={leadTime} onChange={e => setLeadTime(e.target.value)} />
            </div>
            <div>
              <label className="label">{t.seller.priceLow}</label>
              <input className="input" type="number" value={priceLow} onChange={e => setPriceLow(e.target.value)} />
            </div>
            <div>
              <label className="label">{t.seller.priceHigh}</label>
              <input className="input" type="number" value={priceHigh} onChange={e => setPriceHigh(e.target.value)} />
            </div>
          </div>

          <div>
            <label className="label">{t.seller.productImages} ({images.length}/{MAX_IMAGES})</label>
            <div className="flex flex-wrap gap-2">
              {images.map((img, i) => (
                <div key={i} className="relative w-16 h-16">
                  <img src={img} alt="" className="w-16 h-16 object-cover rounded-lg border border-slate-200" />
                  <button
                    onClick={() => removeImage(i)}
                    className="absolute -top-1.5 -right-1.5 bg-white border border-slate-200 rounded-full p-0.5 text-slate-500 hover:text-red-600"
                    aria-label={t.common.delete}
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {images.length < MAX_IMAGES && (
                <label className="w-16 h-16 border-2 border-dashed border-slate-300 rounded-lg flex items-center justify-center text-slate-400 cursor-pointer hover:border-brand-400 hover:text-brand-500">
                  {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ImagePlus className="w-5 h-5" />}
                  <input type="file" accept="image/*" className="hidden" onChange={handleImageUpload} disabled={uploading} />
                </label>
              )}
            </div>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-slate-200 flex gap-3 flex-shrink-0">
          <button className="btn-secondary flex-1" onClick={onClose}>{t.common.cancel}</button>
          <button className="btn-primary flex-1" onClick={handleSubmit} disabled={saving || !name.trim()}>
            {saving ? t.common.loading : t.seller.save}
          </button>
        </div>
      </div>
    </div>
  )
}
