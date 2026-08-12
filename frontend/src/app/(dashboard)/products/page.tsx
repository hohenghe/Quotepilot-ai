"use client"

import { useState, useMemo, useEffect } from "react"
import { Upload, Search, Trash2, ChevronRight, Package } from "lucide-react"
import type { Product } from "@/types"
import {
  getAllProducts,
  uploadFile,
  deleteProduct,
  deleteAllProducts,
  refreshProducts,
} from "@/lib/store"
import PageHeader from "@/components/PageHeader"
import EmptyState from "@/components/EmptyState"
import { useT } from "@/i18n/I18nProvider"

export default function ProductsPage() {
  const { t } = useT()
  const [products, setProducts] = useState<Product[]>(() => getAllProducts())
  const [search, setSearch] = useState("")
  const [uploading, setUploading] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [uploadMsg, setUploadMsg] = useState<{ type: "success"; text: string } | { type: "error"; text: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  useEffect(() => {
    refreshProducts().then(setProducts)
  }, [])

  const filtered = useMemo(() => {
    if (!search.trim()) return products
    const q = search.toLowerCase()
    return products.filter(
      p => p.name.toLowerCase().includes(q) || (p.sku || "").toLowerCase().includes(q)
    )
  }, [products, search])

  const refresh = async () => setProducts(await refreshProducts())

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    try {
      const newProducts = await uploadFile(file)
      setProducts(newProducts)
      setUploadMsg({ type: "success", text: t.products.parsedSuccess(file.name, newProducts.length) })
    } catch (err: any) {
      setUploadMsg({ type: "error", text: err.message || t.common.parseFailed })
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const handleDelete = (id: number) => {
    deleteProduct(id)
    refresh()
  }

  const handleDeleteAll = async () => {
    setDeleting(true)
    await deleteAllProducts()
    setProducts([])
    setDeleting(false)
    setShowDeleteConfirm(false)
  }

  return (
    <div>
      <PageHeader
        title={t.products.title}
        description={t.products.countInCatalog(products.length)}
        action={
          <div className="flex items-center gap-2">
            {products.length > 0 && (
              <button
                className="btn-secondary !bg-red-50 !text-red-600 !border-red-200 hover:!bg-red-100"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 className="w-4 h-4" />
                {t.products.deleteAll}
              </button>
            )}
            <label className="btn-primary cursor-pointer">
              <Upload className="w-4 h-4" />
              {uploading ? t.products.parsing : t.products.uploadFile}
              <input
                type="file"
                className="hidden"
                accept=".pdf,.xlsx,.xls,.docx,.doc,.csv"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>
        }
      />

      {uploadMsg && (
        <div
          className={`mb-4 p-3 rounded-lg text-sm ${
            uploadMsg.type === "success"
              ? "bg-green-50 text-green-700 border border-green-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          {uploadMsg.text}
        </div>
      )}

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          placeholder={t.products.searchPlaceholder}
          className="input-field pl-10"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {products.length === 0 ? (
        <EmptyState
          icon={<Package className="w-6 h-6 text-gray-400" />}
          title={t.products.emptyTitle}
          description={t.products.emptyDescription}
          action={
            <label className="btn-primary cursor-pointer">
              <Upload className="w-4 h-4" />
              {t.products.uploadFirstFile}
              <input
                type="file"
                className="hidden"
                accept=".pdf,.xlsx,.xls,.docx,.doc,.csv"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          }
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((product) => (
            <div
              key={product.id}
              className="card p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() =>
                setSelectedProduct(
                  selectedProduct?.id === product.id ? null : product
                )
              }
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">
                      {product.name}
                    </h3>
                    <span className="badge badge-blue capitalize">
                      {product.category.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 line-clamp-2 mb-2">
                    {product.description || t.common.noDescription}
                  </p>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    {product.sku && <span>{t.products.sku}: {product.sku}</span>}
                    {product.moq && <span>{t.products.moq}: {product.moq}</span>}
                    {product.unit_price && (
                      <span>{t.products.unitPrice}: ${product.unit_price}</span>
                    )}
                    {product.lead_time_days && (
                      <span>{t.products.leadTime}: {product.lead_time_days}{t.common.days}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(product.id)
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title={t.common.delete}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <ChevronRight
                    className={`w-4 h-4 text-gray-400 transition-transform ${
                      selectedProduct?.id === product.id ? "rotate-90" : ""
                    }`}
                  />
                </div>
              </div>

              {selectedProduct?.id === product.id && (
                <div className="mt-3 pt-3 border-t border-gray-100 space-y-2 text-sm">
                  {product.technical_specs && (
                    <div>
                      <span className="font-medium text-gray-700">{t.products.technicalSpecs}:</span>
                      <p className="text-gray-600 mt-0.5">{product.technical_specs}</p>
                    </div>
                  )}
                  {product.pricing && (
                    <div>
                      <span className="font-medium text-gray-700">{t.products.pricing}:</span>
                      <p className="text-gray-600 mt-0.5 whitespace-pre-wrap">{product.pricing}</p>
                    </div>
                  )}
                  {product.certifications && (
                    <div>
                      <span className="font-medium text-gray-700">{t.products.certifications}:</span>
                      <div className="flex gap-1 mt-0.5">
                        {product.certifications.split(",").map((c) => (
                          <span key={c.trim()} className="badge badge-green">
                            {c.trim()}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {filtered.length === 0 && search && (
            <p className="text-center text-sm text-gray-400 py-8">
              {t.products.noMatch(search)}
            </p>
          )}
        </div>
      )}

      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <p className="text-gray-900 font-semibold mb-2">{t.products.deleteAllTitle}</p>
            <p className="text-sm text-gray-600 mb-5">{t.products.deleteAllDesc(products.length)}</p>
            <div className="flex justify-end gap-2">
              <button
                className="btn-secondary text-sm"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
              >
                {t.common.cancel}
              </button>
              <button
                className="btn-primary !bg-red-600 hover:!bg-red-700 text-sm"
                onClick={handleDeleteAll}
                disabled={deleting}
              >
                {deleting ? t.products.deleting : t.products.deleteAllConfirm}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
