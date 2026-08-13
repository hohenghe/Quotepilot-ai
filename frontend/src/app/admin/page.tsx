"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { LayoutDashboard, Users, Package, Mail, FileText, Inbox } from "lucide-react"
import { isAuthenticated, isAdmin, getUser, logout } from "@/lib/auth"
import { adminGetDashboard, adminListSellers, adminListProducts, adminListInquiries } from "@/lib/api-client"
import DashboardShell from "@/components/DashboardShell"
import StatCard from "@/components/StatCard"
import EmptyState from "@/components/EmptyState"
import PageLoader from "@/components/PageLoader"
import { TableSkeleton, Skeleton } from "@/components/LoadingSkeleton"
import { useT } from "@/i18n/I18nProvider"
import type { Product, Inquiry } from "@/types"

interface SellerInfo {
  id: number
  email: string
  name: string | null
  product_count: number
  created_at: string | null
}

interface Stats {
  total_products: number
  total_inquiries: number
  total_quotes: number
  total_sellers: number
  categories: Record<string, number>
}

type Tab = "overview" | "sellers" | "products" | "inquiries"

export default function AdminPage() {
  const { t } = useT()
  const router = useRouter()

  const [authReady, setAuthReady] = useState(false)
  useEffect(() => {
    if (!isAuthenticated() || !isAdmin()) {
      router.push("/admin/login")
      return
    }
    setAuthReady(true)
  }, [router])

  const user = authReady ? getUser() : null

  const [tab, setTab] = useState<Tab>("overview")
  const [stats, setStats] = useState<Stats | null>(null)
  const [sellers, setSellers] = useState<SellerInfo[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [inquiries, setInquiries] = useState<Inquiry[]>([])
  const [loading, setLoading] = useState(true)

  const nav = [
    { key: "overview", label: t.nav.overview, icon: LayoutDashboard },
    { key: "sellers", label: t.nav.sellers, icon: Users },
    { key: "products", label: t.nav.products, icon: Package },
    { key: "inquiries", label: t.nav.inquiries, icon: Mail },
  ]

  const loadAll = useCallback(() => {
    setLoading(true)
    Promise.all([
      adminGetDashboard().then(setStats).catch(() => setStats(null)),
      adminListSellers().then(setSellers).catch(() => setSellers([])),
      adminListProducts().then(d => setProducts(d.items)).catch(() => setProducts([])),
      adminListInquiries().then(d => setInquiries(d.items)).catch(() => setInquiries([])),
    ]).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (isAdmin()) loadAll()
  }, [loadAll])

  const handleLogout = () => {
    logout()
    router.push("/admin/login")
  }

  const maxCategory = Math.max(1, ...Object.values(stats?.categories || {}).map(Number))

  if (!authReady) {
    return <PageLoader />
  }

  return (
    <DashboardShell
      nav={nav}
      active={tab}
      onNavigate={(k) => setTab(k as Tab)}
      userEmail={user?.email}
      onSignOut={handleLogout}
    >
      {tab === "overview" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.title}</h1>
            <p className="mt-1 text-sm text-slate-500">{t.admin.portalTitle}</p>
          </header>

          {loading ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="card p-5">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-8 w-16 mt-4" />
                </div>
              ))}
            </div>
          ) : stats === null ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadAll}>{t.common.tryAgain}</button>}
            />
          ) : (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label={t.admin.kpiProducts} value={stats.total_products} icon={Package} />
                <StatCard label={t.admin.kpiSellers} value={stats.total_sellers} icon={Users} />
                <StatCard label={t.admin.kpiInquiries} value={stats.total_inquiries} icon={Inbox} />
                <StatCard label={t.admin.kpiQuotes} value={stats.total_quotes} icon={FileText} />
              </div>

              {Object.keys(stats.categories || {}).length > 0 && (
                <div className="card p-6 mt-6">
                  <h2 className="text-base font-semibold text-slate-900 mb-5">{t.admin.byCategory}</h2>
                  <div className="space-y-4 max-w-xl">
                    {Object.entries(stats.categories).map(([cat, count]) => (
                      <div key={cat}>
                        <div className="flex items-center justify-between gap-2 text-sm mb-1.5">
                          <span className="capitalize text-slate-700 truncate min-w-0">{cat.replace(/_/g, " ")}</span>
                          <span className="text-slate-500 font-medium flex-shrink-0">{count}</span>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-brand-500 rounded-full transition-all duration-300"
                            style={{ width: `${Math.max(4, (Number(count) / maxCategory) * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === "sellers" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.sellers}</h1>
          </header>
          {loading ? (
            <TableSkeleton rows={5} cols={4} />
          ) : sellers.length === 0 ? (
            <EmptyState icon={<Users className="w-5 h-5" />} title={t.admin.emptySellers} />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th">{t.admin.tableSeller}</th>
                      <th className="th">{t.admin.tableEmail}</th>
                      <th className="th">{t.admin.tableProducts}</th>
                      <th className="th">{t.admin.tableJoined}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sellers.map(s => (
                      <tr key={s.id} className="hover:bg-slate-50/70">
                        <td className="td font-medium text-slate-900">{s.name || s.email}</td>
                        <td className="td text-slate-500">{s.email}</td>
                        <td className="td text-slate-500">{s.product_count}</td>
                        <td className="td text-slate-500">
                          {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "products" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.products}</h1>
          </header>
          {loading ? (
            <TableSkeleton rows={6} cols={4} />
          ) : products.length === 0 ? (
            <EmptyState icon={<Package className="w-5 h-5" />} title={t.admin.emptyProducts} />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th">{t.admin.tableProduct}</th>
                      <th className="th">{t.admin.tableSku}</th>
                      <th className="th">{t.admin.tableSeller}</th>
                      <th className="th">{t.admin.tableCategory}</th>
                      <th className="th">{t.admin.tableMoq}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map(p => (
                      <tr key={p.id} className="hover:bg-slate-50/70">
                        <td className="td font-medium text-slate-900 max-w-[320px]">
                          <div className="truncate">{p.name}</div>
                        </td>
                        <td className="td text-slate-500">{p.sku || "—"}</td>
                        <td className="td text-slate-500 max-w-[180px]">
                          <div className="truncate">{p.seller_name || p.seller_email || "—"}</div>
                        </td>
                        <td className="td">
                          <span className="badge badge-neutral">{p.category?.replace(/_/g, " ")}</span>
                        </td>
                        <td className="td text-slate-500">{p.moq ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "inquiries" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.inquiries}</h1>
          </header>
          {loading ? (
            <TableSkeleton rows={6} cols={4} />
          ) : inquiries.length === 0 ? (
            <EmptyState icon={<Mail className="w-5 h-5" />} title={t.admin.emptyInquiries} />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th">{t.admin.tableId}</th>
                      <th className="th">{t.admin.tableBuyer}</th>
                      <th className="th">{t.admin.tableMessage}</th>
                      <th className="th">{t.admin.tableDate}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inquiries.map(i => (
                      <tr key={i.id} className="hover:bg-slate-50/70">
                        <td className="td text-slate-500">#{i.id}</td>
                        <td className="td text-slate-500">{i.customer_email || "—"}</td>
                        <td className="td max-w-[420px]">
                          <div className="truncate text-slate-700">{i.raw_message}</div>
                        </td>
                        <td className="td text-slate-500">
                          {i.created_at ? new Date(i.created_at).toLocaleDateString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </DashboardShell>
  )
}
