"use client"

import { useState, useEffect, useCallback } from "react"
import { X, Star, Trash2, ImagePlus } from "lucide-react"
import { getProductReviews, createReview, deleteReview, uploadImage } from "@/lib/api-client"
import { getUser } from "@/lib/auth"
import { useToast } from "@/components/Toast"
import { useT } from "@/i18n/I18nProvider"
import type { ProductReviews } from "@/lib/api-client"

interface Props {
  productId: number
  productName: string
  open: boolean
  canWrite: boolean
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

export default function ReviewModal({ productId, productName, open, canWrite, onClose }: Props) {
  const { t } = useT()
  const toast = useToast()
  const [data, setData] = useState<ProductReviews | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  const [rating, setRating] = useState(0)
  const [content, setContent] = useState("")
  const [images, setImages] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const currentUser = getUser()

  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      setData(await getProductReviews(productId))
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [productId])

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

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const res = await uploadImage(file)
      setImages(prev => [...prev, res.url])
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const handleSubmit = async () => {
    if (rating <= 0) return
    setSubmitting(true)
    try {
      await createReview(productId, rating, content, images)
      toast.push("success", t.review.submitted)
      setRating(0)
      setContent("")
      setImages([])
      await load()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (reviewId: number) => {
    try {
      await deleteReview(reviewId)
      toast.push("success", t.review.deleted)
      await load()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div className="relative bg-white rounded-xl border border-slate-200 shadow-lg w-full max-w-lg max-h-[85vh] flex flex-col" role="dialog" aria-modal="true">
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-slate-200 flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-slate-900 truncate">{productName}</h2>
            {data && (
              <div className="flex items-center gap-2 mt-0.5 text-sm text-slate-500">
                {data.rating != null && <><Stars value={data.rating} /><span>{data.rating.toFixed(1)}</span></>}
                <span>·</span>
                <span>{t.review.count(data.review_count)}</span>
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg" aria-label={t.common.cancel}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {loading ? (
            <p className="text-center text-sm text-slate-400 py-8">{t.common.loading}</p>
          ) : error ? (
            <p className="text-center text-sm text-slate-400 py-8">{t.common.somethingWentWrong}</p>
          ) : data && data.items.length === 0 ? (
            <p className="text-center text-sm text-slate-400 py-8">{t.review.noReviews}</p>
          ) : (
            data?.items.map(r => (
              <div key={r.id} className="border-b border-slate-100 pb-4 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium text-slate-700 truncate">{r.user_name || "—"}</span>
                    <Stars value={r.rating} />
                    <span className="text-xs text-slate-500">{r.rating.toFixed(1)}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-slate-400">{r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}</span>
                    {currentUser && currentUser.user_id === r.user_id && (
                      <button
                        onClick={() => handleDelete(r.id)}
                        className="text-slate-400 hover:text-red-600 p-1 rounded"
                        aria-label={t.review.delete}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
                {r.content && <p className="mt-2 text-sm text-slate-700 whitespace-pre-wrap">{r.content}</p>}
                {r.images.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {r.images.map((img, i) => (
                      <img key={i} src={img} alt="" className="w-16 h-16 object-cover rounded-lg border border-slate-200" />
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {canWrite && (
          <div className="px-5 py-4 border-t border-slate-200 space-y-3 flex-shrink-0">
            <p className="text-sm font-medium text-slate-900">{t.review.write}</p>
            <div className="flex items-center gap-3">
              <Stars value={rating} />
              <input
                type="range"
                min={0}
                max={5}
                step={0.1}
                value={rating}
                onChange={e => setRating(Number(e.target.value))}
                className="flex-1 accent-brand-600"
                aria-label={t.review.yourRating}
              />
              <span className="text-sm text-slate-500 w-12 text-right">{rating.toFixed(1)}</span>
            </div>
            <textarea
              className="input min-h-[80px] resize-y"
              placeholder={t.review.comment}
              value={content}
              onChange={e => setContent(e.target.value)}
            />
            <div className="flex items-center gap-3 flex-wrap">
              <label className="btn-secondary btn-sm cursor-pointer">
                <ImagePlus className="w-4 h-4" />
                {t.review.addImage}
                <input type="file" accept="image/*" className="hidden" onChange={handleImageUpload} disabled={uploading} />
              </label>
              {images.map((img, i) => (
                <img key={i} src={img} alt="" className="w-10 h-10 object-cover rounded-lg border border-slate-200" />
              ))}
            </div>
            <button className="btn-primary w-full" onClick={handleSubmit} disabled={submitting || rating <= 0}>
              {submitting ? t.review.submitting : t.review.submit}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
