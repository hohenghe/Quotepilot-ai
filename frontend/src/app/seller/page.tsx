"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Upload, Trash2, Search, LogOut, Package, Mail, FileText, Copy, CheckSquare, Square } from "lucide-react"
import { isAuthenticated, isSeller, getUser, logout } from "@/lib/auth"
import { uploadProducts, getSellerReceivedInquiries, generateSellerReply, getSellerProducts, deleteSellerProduct } from "@/lib/api-client"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import { useT } from "@/i18n/I18nProvider"
import type { SellerInquiryItem } from "@/lib/api-client"
import type { Product } from "@/types"

export default function SellerPage() {
  const { t } = useT()
  const router = useRouter()
  const user = getUser()

  useEffect(() => {
    if (!isAuthenticated() || !isSeller()) {
      router.push("/seller/login")
    }
  }, [router])

  const [tab, setTab] = useState<"products" | "inquiries">("products")
  const [products, setProducts] = useState<Product[]>([])
  const [productsLoading, setProductsLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [deleting, setDeleting] = useState(false)

  const loadProducts = useCallback(async () => {
    setProductsLoading(true)
    try {
      const data = await getSellerProducts()
      setProducts(data.items)
    } catch { } finally {
      setProductsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated() && isSeller()) loadProducts()
  }, [loadProducts])

  // Inquiries state
  const [inquiries, setInquiries] = useState<SellerInquiryItem[]>([])
  const [loadingInquiries, setLoadingInquiries] = useState(false)
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  const loadInquiries = useCallback(async () => {
    setLoadingInquiries(true)
    try {
      const data = await getSellerReceivedInquiries()
      setInquiries(data.items)
    } catch { } finally {
      setLoadingInquiries(false)
    }
  }, [])

  useEffect(() => {
    if (tab === "inquiries") loadInquiries()
  }, [tab, loadInquiries])

  const filtered = useMemo(() => {
    if (!search.trim()) return products
    const q = search.toLowerCase()
    return products.filter(p => p.name.toLowerCase().includes(q) || (p.sku || "").toLowerCase().includes(q))
  }, [products, search])

  const allSelected = filtered.length > 0 && filtered.every(p => selectedIds.has(p.id))

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map(p => p.id)))
    }
  }

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setMsg(null)
    try {
      await uploadProducts(file)
      setMsg({ type: "success", text: `${file.name} uploaded successfully` })
      await loadProducts()
    } catch (err: any) {
      setMsg({ type: "error", text: err.message || "Upload failed" })
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    setDeleting(true)
    const idsToDelete = new Set(selectedIds)
    // Immediately remove from UI
    setProducts(prev => prev.filter(p => !idsToDelete.has(p.id)))
    setSelectedIds(new Set())
    try {
      for (const id of idsToDelete) {
        await deleteSellerProduct(id)
      }
    } catch (err: any) {
      setMsg({ type: "error", text: err.message || "Delete failed" })
      await loadProducts()
    } finally {
      setDeleting(false)
    }
  }

  const handleGenerateReply = async (inquiryId: number) => {
    setGeneratingId(inquiryId)
    try {
      const reply = await generateSellerReply(inquiryId)
      setInquiries(prev => prev.map(i =>
        i.id === inquiryId ? { ...i, status: "replied", reply_body: reply.email_body } : i
      ))
    } catch { } finally {
      setGeneratingId(null)
    }
  }

  const handleLogout = () => {
    logout()
    router.push("/seller/login")
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Package className="w-5 h-5 text-emerald-600" />
            <span className="font-semibold text-gray-900">{t.seller.portalTitle}</span>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <span className="text-sm text-gray-500">{user?.email}</span>
            <button onClick={handleLogout} className="text-gray-400 hover:text-red-500">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
        <nav className="max-w-5xl mx-auto px-4 flex gap-0">
          <button
            onClick={() => setTab("products")}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === "products" ? "border-emerald-500 text-emerald-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.seller.myProducts} ({products.length})
          </button>
          <button
            onClick={() => setTab("inquiries")}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === "inquiries" ? "border-emerald-500 text-emerald-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.seller.receivedInquiries} {inquiries.length > 0 ? `(${inquiries.length})` : ""}
          </button>
        </nav>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {tab === "products" && (
          <>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="text-xl font-bold text-gray-900">{t.seller.myProducts}</h1>
                <p className="text-sm text-gray-500">{t.seller.productsCount(products.length)}</p>
              </div>
              <div className="flex items-center gap-2">
                {selectedIds.size > 0 && (
                  <button
                    className="btn-primary !bg-red-600 hover:!bg-red-700"
                    onClick={handleDeleteSelected}
                    disabled={deleting}
                  >
                    <Trash2 className="w-4 h-4" />
                    {deleting ? t.seller.deleting : `${t.common.delete} (${selectedIds.size})`}
                  </button>
                )}
                <label className="btn-primary cursor-pointer">
                  <Upload className="w-4 h-4" />
                  {uploading ? t.seller.uploading : t.seller.uploadCsv}
                  <input type="file" className="hidden" accept=".csv" onChange={handleUpload} disabled={uploading} />
                </label>
              </div>
            </div>

            {msg && (
              <div className={`mb-4 p-3 rounded-lg text-sm ${msg.type === "success" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                {msg.text}
              </div>
            )}

            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input className="input-field pl-10 bg-white" placeholder={t.seller.search} value={search} onChange={e => setSearch(e.target.value)} />
            </div>

            {filtered.length > 0 && (
              <label className="flex items-center gap-2 mb-3 px-1 cursor-pointer text-sm text-gray-600 hover:text-gray-900">
                <div className="w-5 h-5 flex items-center justify-center">
                  {allSelected ? <CheckSquare className="w-5 h-5 text-emerald-600" /> : <Square className="w-5 h-5" />}
                </div>
                <input type="checkbox" className="hidden" checked={allSelected} onChange={toggleSelectAll} />
                <span>{t.common.selectAll}</span>
              </label>
            )}

            {productsLoading ? (
              <div className="text-center py-12 text-gray-400">{t.common.loading}</div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>{search ? t.products.noMatch(search) : t.seller.noProducts}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filtered.map(p => (
                  <div key={p.id} className="bg-white rounded-xl p-4 shadow-sm border flex items-center gap-3">
                    <button onClick={() => toggleSelect(p.id)} className="flex-shrink-0 text-gray-400 hover:text-emerald-600">
                      {selectedIds.has(p.id) ? <CheckSquare className="w-5 h-5 text-emerald-600" /> : <Square className="w-5 h-5" />}
                    </button>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900 truncate">{p.name}</h3>
                      <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-500">
                        {p.sku && <span>{t.seller.sku}: {p.sku}</span>}
                        {p.moq && <span>{t.buyer.moqLabel}: {p.moq}</span>}
                        <span className="badge badge-blue">{p.category}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "inquiries" && (
          <>
            <div className="mb-6">
              <h1 className="text-xl font-bold text-gray-900">{t.seller.receivedInquiries}</h1>
              <p className="text-sm text-gray-500">{t.seller.inquiriesDesc}</p>
            </div>

            {loadingInquiries ? (
              <div className="text-center py-12 text-gray-400">{t.common.loading}</div>
            ) : inquiries.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Mail className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>{t.seller.noInquiries}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {inquiries.map(inq => (
                  <div key={inq.id} className="bg-white rounded-xl shadow-sm border p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        {inq.buyer_email && <p className="text-sm text-gray-500">{t.seller.from}: {inq.buyer_email}</p>}
                        <p className="text-xs text-gray-400 mt-1">
                          {inq.created_at ? new Date(inq.created_at).toLocaleString() : ""}
                        </p>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        inq.status === "replied" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                      }`}>
                        {(inq.status === "replied" ? t.seller.replied : t.seller.pending)}
                      </span>
                    </div>

                    <div className="bg-gray-50 rounded-lg p-3 mb-3">
                      <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">{inq.raw_message}</pre>
                    </div>

                    {inq.reply_body ? (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-green-700">{t.seller.aiReply}</span>
                          <button
                            className="btn-secondary text-xs"
                            onClick={() => navigator.clipboard.writeText(inq.reply_body || "")}
                          >
                            <Copy className="w-3 h-3" /> {t.seller.copy}
                          </button>
                        </div>
                        <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-green-50 p-3 rounded-lg font-sans max-h-60 overflow-y-auto">
                          {inq.reply_body}
                        </pre>
                      </div>
                    ) : (
                      <button
                        className="btn-primary w-full justify-center"
                        onClick={() => handleGenerateReply(inq.id)}
                        disabled={generatingId === inq.id}
                      >
                        <FileText className="w-4 h-4" />
                        {generatingId === inq.id ? t.seller.generating : t.seller.generateReply}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
