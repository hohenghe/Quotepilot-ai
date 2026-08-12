"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import { useRouter } from "next/navigation"
import { Upload, Trash2, Search, LogOut, Package, Mail, FileText, Copy } from "lucide-react"
import { isAuthenticated, isSeller, getUser, logout } from "@/lib/auth"
import { uploadProducts, getSellerReceivedInquiries, generateSellerReply } from "@/lib/api-client"
import type { SellerInquiryItem } from "@/lib/api-client"
import type { Product } from "@/types"

export default function SellerPage() {
  const router = useRouter()
  const user = getUser()

  useEffect(() => {
    if (!isAuthenticated() || !isSeller()) {
      router.push("/seller/login")
    }
  }, [router])

  const [tab, setTab] = useState<"products" | "inquiries">("products")
  const [products, setProducts] = useState<Product[]>(() => {
    if (typeof window !== "undefined") {
      const raw = localStorage.getItem("quotepilot_products")
      return raw ? JSON.parse(raw) : []
    }
    return []
  })
  const [search, setSearch] = useState("")
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

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

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setMsg(null)
    try {
      await uploadProducts(file)
      setMsg({ type: "success", text: `${file.name} uploaded successfully` })
    } catch (err: any) {
      setMsg({ type: "error", text: err.message || "Upload failed" })
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const handleDelete = (id: number) => {
    setProducts(prev => prev.filter(p => p.id !== id))
    localStorage.setItem("quotepilot_products", JSON.stringify(products.filter(p => p.id !== id)))
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
            <span className="font-semibold text-gray-900">Seller Portal</span>
          </div>
          <div className="flex items-center gap-3">
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
            My Products ({products.length})
          </button>
          <button
            onClick={() => setTab("inquiries")}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === "inquiries" ? "border-emerald-500 text-emerald-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Received Inquiries {inquiries.length > 0 ? `(${inquiries.length})` : ""}
          </button>
        </nav>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {tab === "products" && (
          <>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-xl font-bold text-gray-900">My Products</h1>
                <p className="text-sm text-gray-500">{products.length} products</p>
              </div>
              <label className="btn-primary cursor-pointer">
                <Upload className="w-4 h-4" />
                {uploading ? "Uploading..." : "Upload CSV"}
                <input type="file" className="hidden" accept=".csv" onChange={handleUpload} disabled={uploading} />
              </label>
            </div>

            {msg && (
              <div className={`mb-4 p-3 rounded-lg text-sm ${msg.type === "success" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                {msg.text}
              </div>
            )}

            <div className="relative mb-6">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input className="input-field pl-10 bg-white" placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} />
            </div>

            {filtered.map(p => (
              <div key={p.id} className="bg-white rounded-xl p-4 shadow-sm border mb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{p.name}</h3>
                    <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-500">
                      {p.sku && <span>SKU: {p.sku}</span>}
                      {p.moq && <span>MOQ: {p.moq}</span>}
                      <span className="badge badge-blue">{p.category}</span>
                    </div>
                  </div>
                  <button onClick={() => handleDelete(p.id)} className="text-gray-400 hover:text-red-500 p-1">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </>
        )}

        {tab === "inquiries" && (
          <>
            <div className="mb-6">
              <h1 className="text-xl font-bold text-gray-900">Received Inquiries</h1>
              <p className="text-sm text-gray-500">Buyers who selected your products</p>
            </div>

            {loadingInquiries ? (
              <div className="text-center py-12 text-gray-400">Loading...</div>
            ) : inquiries.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Mail className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No inquiries received yet.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {inquiries.map(inq => (
                  <div key={inq.id} className="bg-white rounded-xl shadow-sm border p-5">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        {inq.buyer_email && <p className="text-sm text-gray-500">From: {inq.buyer_email}</p>}
                        <p className="text-xs text-gray-400 mt-1">
                          {inq.created_at ? new Date(inq.created_at).toLocaleString() : ""}
                        </p>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        inq.status === "replied" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                      }`}>
                        {inq.status}
                      </span>
                    </div>

                    <div className="bg-gray-50 rounded-lg p-3 mb-3">
                      <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">{inq.raw_message}</pre>
                    </div>

                    {inq.reply_body ? (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-green-700">AI Reply</span>
                          <button
                            className="btn-secondary text-xs"
                            onClick={() => navigator.clipboard.writeText(inq.reply_body || "")}
                          >
                            <Copy className="w-3 h-3" /> Copy
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
                        {generatingId === inq.id ? "Generating..." : "Generate AI Reply"}
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
