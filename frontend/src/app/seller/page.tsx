"use client"

import { useState, useEffect, useMemo } from "react"
import { useRouter } from "next/navigation"
import { Upload, Trash2, Search, LogOut, Package, ChevronDown } from "lucide-react"
import { isAuthenticated, isSeller, getUser, logout } from "@/lib/auth"
import { uploadProducts } from "@/lib/api-client"
import type { Product } from "@/types"

export default function SellerPage() {
  const router = useRouter()
  const user = getUser()

  useEffect(() => {
    if (!isAuthenticated() || !isSeller()) {
      router.push("/seller/login")
    }
  }, [router])

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
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900">My Products</h1>
            <p className="text-sm text-gray-500">{products.length} products in your catalog</p>
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
          <input
            className="input-field pl-10 bg-white"
            placeholder="Search your products..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {products.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No products yet. Upload a CSV file to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(p => (
              <div key={p.id} className="bg-white rounded-xl p-4 shadow-sm border">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{p.name}</h3>
                    <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-500">
                      {p.sku && <span>SKU: {p.sku}</span>}
                      {p.moq && <span>MOQ: {p.moq}</span>}
                      {p.lead_time_days && <span>Lead: {p.lead_time_days}d</span>}
                      <span className="badge badge-blue">{p.category}</span>
                    </div>
                  </div>
                  <button onClick={() => handleDelete(p.id)} className="text-gray-400 hover:text-red-500 p-1">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
            {filtered.length === 0 && search && (
              <p className="text-center text-gray-400 py-8">No products match "{search}"</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
