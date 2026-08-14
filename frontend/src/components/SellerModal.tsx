"use client"

import { useState, useEffect, useCallback } from "react"
import { X, Store, Star, Package } from "lucide-react"
import { getSellerProductsById } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"
import type { SellerProductsResult } from "@/lib/api-client"

interface Props {
  sellerId: number
  sellerName: string
  open: boolean
  onReview: () => void
  onClose: () => void
}

function Stars({ value }: { value: number }) {
  const filled = Math.round(value)
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${value}`}>
      {[1, 2, 3, 4, 5].map(i => (
        <Star key={i} className={`w-4 h-4 ${i <= filled ? "text-amber-400 fill-current" : "text-slate-300"}`} />
      ))}
    </span>
  )
}

export default function SellerModal({ sellerId, sellerName, open, onReview, onClose }: Props) {
  const { t } = useT()
  const [data, setData] = useState<SellerProductsResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      setData(await getSellerProductsById(sellerId))
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [sellerId])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null

  const products = data?.items ?? []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div className="relative bg-white rounded-xl border border-slate-200 shadow-lg w-full max-w-2xl max-h-[85vh] flex flex-col" role="dialog" aria-modal="true">
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-slate-200 flex-shrink-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Store className="w-4 h-4 text-brand-600 flex-shrink-0" />
              <h2 className="text-lg font-semibold text-slate-900 truncate">{sellerName}</h2>
            </div>
            {data && data.score != null && (
              <div className="flex items-center gap-2 mt-0.5 text-sm text-slate-500">
                <Stars value={data.score} />
                <span>{data.score.toFixed(1)}</span>
                <span>·</span>
                <span>{t.seller.storeScore}</span>
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg" aria-label={t.common.cancel}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-center text-sm text-slate-400 py-8">{t.common.loading}</p>
          ) : error ? (
            <p className="text-center text-sm text-slate-400 py-8">{t.common.somethingWentWrong}</p>
          ) : products.length === 0 ? (
            <div className="text-center py-8">
              <Package className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="mt-2 text-sm text-slate-400">{t.buyer.noSellerProducts}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {products.map(p => (
                <div key={p.id} className="border border-slate-200 rounded-lg p-4">
                  <h3 className="font-medium text-slate-900 truncate">{p.name}</h3>
                  {p.sku && <p className="mt-0.5 text-xs text-slate-400">SKU: {p.sku}</p>}
                  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                    {p.category && <span>{p.category.replace(/_/g, " ")}</span>}
                    {p.moq != null && <span>{t.buyer.moqLabel}: {p.moq}</span>}
                    {p.lead_time_days != null && <span>{t.buyer.leadTime}: {p.lead_time_days}d</span>}
                  </div>
                  {p.pricing && <p className="mt-2 text-xs text-slate-400 truncate">{p.pricing}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t border-slate-200 flex-shrink-0">
          <button className="btn-primary w-full" onClick={onReview}>
            <Star className="w-4 h-4" />
            {t.review.write}
          </button>
        </div>
      </div>
    </div>
  )
}
