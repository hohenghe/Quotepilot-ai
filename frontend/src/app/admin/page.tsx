"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Package, Mail, FileText, Users, LogOut, BarChart3 } from "lucide-react"
import { isAuthenticated, isAdmin, getUser, logout } from "@/lib/auth"
import { adminGetDashboard, adminListSellers, adminListProducts, adminListInquiries } from "@/lib/api-client"
import type { Product, Inquiry } from "@/types"

interface SellerInfo {
  id: number; email: string; name: string | null; product_count: number; created_at: string | null
}

export default function AdminPage() {
  const router = useRouter()
  const user = getUser()

  useEffect(() => {
    if (!isAuthenticated() || !isAdmin()) {
      router.push("/admin/login")
    }
  }, [router])

  const [tab, setTab] = useState<"overview" | "sellers" | "products" | "inquiries">("overview")
  const [stats, setStats] = useState<any>(null)
  const [sellers, setSellers] = useState<SellerInfo[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [inquiries, setInquiries] = useState<Inquiry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAdmin()) {
      setLoading(true)
      Promise.all([
        adminGetDashboard().then(setStats).catch(() => {}),
        adminListSellers().then(setSellers).catch(() => {}),
        adminListProducts().then(d => setProducts(d.items)).catch(() => {}),
        adminListInquiries().then(d => setInquiries(d.items)).catch(() => {}),
      ]).finally(() => setLoading(false))
    }
  }, [])

  const handleLogout = () => {
    logout()
    router.push("/admin/login")
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-slate-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-slate-800 text-white">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-5 h-5" />
            <span className="font-semibold">Admin Panel</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-300">{user?.email}</span>
            <button onClick={handleLogout} className="text-slate-400 hover:text-white">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
        <nav className="max-w-6xl mx-auto px-4 flex gap-0">
          {(["overview", "sellers", "products", "inquiries"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                tab === t ? "border-white text-white" : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              {t === "overview" ? "Overview" : t}
            </button>
          ))}
        </nav>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {tab === "overview" && stats && (
          <div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <StatCard icon={<Package className="w-5 h-5" />} label="Total Products" value={stats.total_products} color="blue" />
              <StatCard icon={<Mail className="w-5 h-5" />} label="Total Inquiries" value={stats.total_inquiries} color="green" />
              <StatCard icon={<FileText className="w-5 h-5" />} label="Total Quotes" value={stats.total_quotes} color="purple" />
              <StatCard icon={<Users className="w-5 h-5" />} label="Sellers" value={stats.total_sellers} color="orange" />
            </div>
            {Object.keys(stats.categories || {}).length > 0 && (
              <div className="bg-white rounded-xl p-6 shadow-sm border">
                <h2 className="font-semibold mb-4">Product Categories</h2>
                {Object.entries(stats.categories).map(([cat, count]: any) => (
                  <div key={cat} className="flex items-center justify-between py-2 border-b last:border-0">
                    <span className="text-sm capitalize">{cat.replace(/_/g, " ")}</span>
                    <span className="text-sm font-medium">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "sellers" && (
          <div className="bg-white rounded-xl shadow-sm border">
            <div className="p-4 border-b font-semibold">Sellers ({sellers.length})</div>
            {sellers.map(s => (
              <div key={s.id} className="p-4 border-b last:border-0 flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">{s.name || s.email}</p>
                  <p className="text-sm text-gray-500">{s.email}</p>
                </div>
                <span className="text-sm text-gray-600">{s.product_count} products</span>
              </div>
            ))}
          </div>
        )}

        {tab === "products" && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500 mb-4">All products across all sellers</p>
            {products.map(p => (
              <div key={p.id} className="bg-white rounded-xl p-4 shadow-sm border">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{p.name}</h3>
                    <div className="flex gap-2 mt-1 text-xs text-gray-500">
                      {p.sku && <span>SKU: {p.sku}</span>}
                      <span className="badge badge-blue">{p.category}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "inquiries" && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500 mb-4">Recent buyer inquiries</p>
            {inquiries.map(i => (
              <div key={i.id} className="bg-white rounded-xl p-4 shadow-sm border">
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs text-gray-400">#{i.id}</span>
                  <span className="text-xs text-gray-400">
                    {i.created_at ? new Date(i.created_at).toLocaleDateString() : ""}
                  </span>
                </div>
                <p className="text-sm text-gray-700 line-clamp-3">{i.raw_message}</p>
                {i.customer_email && <p className="text-xs text-gray-400 mt-2">From: {i.customer_email}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    purple: "bg-purple-50 text-purple-600",
    orange: "bg-orange-50 text-orange-600",
  }
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${colors[color]}`}>
        {icon}
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}
