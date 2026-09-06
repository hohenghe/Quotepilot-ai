"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { LayoutDashboard, Users, Package, Mail, FileText, Inbox, Search, Trash2, ChevronLeft, ChevronRight, Star, Flag, FlaskConical, Send, Bot, Plus } from "lucide-react"
import { isAuthenticated, isAdmin, getUser, logout } from "@/lib/auth"
import { adminGetDashboard, adminListProducts, adminListInquiries, deleteProducts, adminResetAll, adminClearSavedProducts, adminListUsers, adminDeleteUsers, adminDeleteInquiries, adminListReviews, deleteReview, adminSendTestVerificationEmail, adminTestLlm, adminCreateTestProduct, adminDeleteTestProduct } from "@/lib/api-client"
import DashboardShell from "@/components/DashboardShell"
import StatCard from "@/components/StatCard"
import EmptyState from "@/components/EmptyState"
import PageLoader from "@/components/PageLoader"
import ConfirmDialog from "@/components/ConfirmDialog"
import { TableSkeleton, Skeleton } from "@/components/LoadingSkeleton"
import { useToast } from "@/components/Toast"
import { useT } from "@/i18n/I18nProvider"
import type { Product, Inquiry } from "@/types"
import type { AdminUserItem, ReviewItem } from "@/lib/api-client"

interface Stats {
  total_products: number
  total_inquiries: number
  total_quotes: number
  total_sellers: number
  categories: Record<string, number>
}

type Tab = "overview" | "accounts" | "products" | "inquiries" | "reviews" | "testing"

export default function AdminPage() {
  const { t } = useT()
  const router = useRouter()
  const toast = useToast()

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
  const [accounts, setAccounts] = useState<AdminUserItem[]>([])
  const [accountsTotal, setAccountsTotal] = useState(0)
  const [accountsLoading, setAccountsLoading] = useState(false)
  const [selectedAccountIds, setSelectedAccountIds] = useState<Set<number>>(new Set())
  const [confirmAccountsOpen, setConfirmAccountsOpen] = useState(false)
  const [deletingAccounts, setDeletingAccounts] = useState(false)
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [reviewsError, setReviewsError] = useState(false)
  const [showReportedOnly, setShowReportedOnly] = useState(false)
  const [selectedInquiryIds, setSelectedInquiryIds] = useState<Set<number>>(new Set())
  const [confirmInquiriesOpen, setConfirmInquiriesOpen] = useState(false)
  const [deletingInquiries, setDeletingInquiries] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [productsPage, setProductsPage] = useState(1)
  const [productsTotal, setProductsTotal] = useState(0)
  const [productSearch, setProductSearch] = useState("")
  const [productsLoading, setProductsLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmResetOpen, setConfirmResetOpen] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [confirmClearSavedOpen, setConfirmClearSavedOpen] = useState(false)
  const [clearingSaved, setClearingSaved] = useState(false)
  const [inquiries, setInquiries] = useState<Inquiry[]>([])
  const [loading, setLoading] = useState(true)
  const [testEmail, setTestEmail] = useState("")
  const [sendingTestEmail, setSendingTestEmail] = useState(false)
  const [testEmailResult, setTestEmailResult] = useState<string | null>(null)
  const [testPrompt, setTestPrompt] = useState("Please analyze a request for 500 LED desk lamps, 12W, CE certified, delivered to Germany.")
  const [testingLlm, setTestingLlm] = useState(false)
  const [llmResult, setLlmResult] = useState<Record<string, unknown> | null>(null)
  const [testProduct, setTestProduct] = useState<{ product_id: number; name: string; sku: string } | null>(null)
  const [testingProduct, setTestingProduct] = useState(false)

  const nav = [
    { key: "overview", label: t.nav.overview, icon: LayoutDashboard },
    { key: "accounts", label: t.admin.accounts, icon: Users },
    { key: "products", label: t.nav.products, icon: Package },
    { key: "inquiries", label: t.nav.inquiries, icon: Mail },
    { key: "reviews", label: t.admin.reviews, icon: Star },
    { key: "testing", label: "测试工具", icon: FlaskConical },
  ]

  const loadAll = useCallback(() => {
    setLoading(true)
    Promise.all([
      adminGetDashboard().then(setStats).catch(() => setStats(null)),
      adminListInquiries().then(d => setInquiries(d.items)).catch(() => setInquiries([])),
    ]).finally(() => setLoading(false))
  }, [])

  const loadAccounts = useCallback(async () => {
    setAccountsLoading(true)
    try {
      const data = await adminListUsers(1, 200)
      setAccounts(data.items)
      setAccountsTotal(data.total)
    } catch {
      setAccounts([])
    } finally {
      setAccountsLoading(false)
    }
  }, [])

  const loadReviews = useCallback(async () => {
    setReviewsLoading(true)
    setReviewsError(false)
    try {
      const data = await adminListReviews()
      setReviews(data.items)
    } catch {
      setReviewsError(true)
    } finally {
      setReviewsLoading(false)
    }
  }, [])

  const loadProducts = useCallback(async () => {
    setProductsLoading(true)
    try {
      const data = await adminListProducts(productsPage, productSearch || undefined)
      setProducts(data.items)
      setProductsTotal(data.total)
    } catch {
      setProducts([])
      setProductsTotal(0)
    } finally {
      setProductsLoading(false)
    }
  }, [productsPage, productSearch])

  useEffect(() => {
    if (isAdmin()) loadAll()
  }, [loadAll])

  useEffect(() => {
    if (tab === "products") loadProducts()
  }, [tab, loadProducts])

  useEffect(() => {
    if (tab === "accounts") loadAccounts()
  }, [tab, loadAccounts])

  useEffect(() => {
    if (tab === "reviews") loadReviews()
  }, [tab, loadReviews])

  const handleLogout = () => {
    logout()
    router.push("/admin/login")
  }

  const totalPages = Math.max(1, Math.ceil(productsTotal / 20))
  const allPageSelected = products.length > 0 && products.every(p => selectedIds.has(p.id))

  const toggleSelectAll = () => {
    setSelectedIds(allPageSelected ? new Set() : new Set(products.map(p => p.id)))
  }

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleSearchChange = (value: string) => {
    setProductSearch(value)
    setProductsPage(1)
    setSelectedIds(new Set())
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    setDeleting(true)
    const ids = Array.from(selectedIds)
    try {
      const deletedCount = await deleteProducts(ids)
      setSelectedIds(new Set())
      toast.push("success", t.products.deletedCount(deletedCount))
      const remaining = products.length - deletedCount
      if (remaining <= 0 && productsPage > 1) {
        setProductsPage(productsPage - 1)
      } else {
        await loadProducts()
      }
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setDeleting(false)
      setConfirmDeleteOpen(false)
    }
  }

  const handleResetAll = async () => {
    setResetting(true)
    try {
      await adminResetAll()
      toast.push("success", t.admin.resetSuccess)
      await loadAll()
      setProducts([])
      setProductsTotal(0)
      setProductsPage(1)
      setSelectedIds(new Set())
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setResetting(false)
      setConfirmResetOpen(false)
    }
  }

  const handleClearSaved = async () => {
    setClearingSaved(true)
    try {
      await adminClearSavedProducts()
      toast.push("success", t.admin.savedCleared)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setClearingSaved(false)
      setConfirmClearSavedOpen(false)
    }
  }

  const allAccountsSelected = accounts.length > 0 && accounts.every(a => selectedAccountIds.has(a.id))
  const toggleSelectAllAccounts = () => {
    setSelectedAccountIds(allAccountsSelected ? new Set() : new Set(accounts.map(a => a.id)))
  }
  const toggleSelectAccount = (id: number) => {
    setSelectedAccountIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  }
  const handleDeleteAccounts = async () => {
    if (selectedAccountIds.size === 0) return
    setDeletingAccounts(true)
    try {
      const deleted = await adminDeleteUsers(Array.from(selectedAccountIds))
      setSelectedAccountIds(new Set())
      toast.push("success", t.admin.deletedCount(deleted))
      await loadAccounts()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setDeletingAccounts(false)
      setConfirmAccountsOpen(false)
    }
  }

  const allInquiriesSelected = inquiries.length > 0 && inquiries.every(i => selectedInquiryIds.has(i.id))
  const toggleSelectAllInquiries = () => {
    setSelectedInquiryIds(allInquiriesSelected ? new Set() : new Set(inquiries.map(i => i.id)))
  }
  const toggleSelectInquiry = (id: number) => {
    setSelectedInquiryIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n })
  }
  const handleDeleteInquiries = async () => {
    if (selectedInquiryIds.size === 0) return
    setDeletingInquiries(true)
    try {
      const deleted = await adminDeleteInquiries(Array.from(selectedInquiryIds))
      setSelectedInquiryIds(new Set())
      toast.push("success", t.admin.deletedCount(deleted))
      await loadAll()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setDeletingInquiries(false)
      setConfirmInquiriesOpen(false)
    }
  }

  const handleDeleteReview = async (reviewId: number) => {
    try {
      await deleteReview(reviewId)
      toast.push("success", t.review.deleted)
      await loadReviews()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    }
  }

  const errorMessage = (error: unknown) => error instanceof Error ? error.message.replace(/^API error \d+:\s*/, "") : "操作失败"

  const handleTestEmail = async () => {
    setSendingTestEmail(true)
    setTestEmailResult(null)
    try {
      const result = await adminSendTestVerificationEmail(testEmail.trim())
      setTestEmailResult(result.message)
      toast.push("success", "验证邮件测试已发送")
    } catch (error) {
      setTestEmailResult(errorMessage(error))
      toast.push("error", "验证邮件测试失败")
    } finally {
      setSendingTestEmail(false)
    }
  }

  const handleTestLlm = async () => {
    setTestingLlm(true)
    setLlmResult(null)
    try {
      const result = await adminTestLlm(testPrompt)
      setLlmResult({ ai_used: result.ai_used, ...result.analysis })
      toast.push("success", "大模型调用完成")
    } catch (error) {
      toast.push("error", errorMessage(error))
    } finally {
      setTestingLlm(false)
    }
  }

  const handleCreateTestProduct = async () => {
    setTestingProduct(true)
    try {
      const product = await adminCreateTestProduct()
      setTestProduct(product)
      toast.push("success", `已创建测试商品 #${product.product_id}`)
    } catch (error) {
      toast.push("error", errorMessage(error))
    } finally {
      setTestingProduct(false)
    }
  }

  const handleDeleteTestProduct = async () => {
    if (!testProduct) return
    setTestingProduct(true)
    try {
      await adminDeleteTestProduct(testProduct.product_id)
      toast.push("success", `已删除测试商品 #${testProduct.product_id}`)
      setTestProduct(null)
    } catch (error) {
      toast.push("error", errorMessage(error))
    } finally {
      setTestingProduct(false)
    }
  }

  const maxCategory = Math.max(1, ...Object.values(stats?.categories || {}).map(Number))

  const reportedCount = reviews.filter(r => r.reported).length
  const displayedReviews = showReportedOnly ? reviews.filter(r => r.reported) : reviews

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

          <div className="card p-6 mt-6 border-red-200">
            <h2 className="text-base font-semibold text-red-700">{t.admin.dangerZone}</h2>
            <p className="mt-1 text-sm text-slate-500">{t.admin.deleteAllDesc}</p>
            <div className="mt-4 flex items-center gap-3 flex-wrap">
              <button className="btn-danger" onClick={() => setConfirmResetOpen(true)}>
                <Trash2 className="w-4 h-4" />
                {t.admin.deleteAll}
              </button>
              <button className="btn-danger" onClick={() => setConfirmClearSavedOpen(true)}>
                <Trash2 className="w-4 h-4" />
                {t.admin.clearSaved}
              </button>
            </div>
          </div>
        </>
      )}

      {tab === "accounts" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.accounts}</h1>
          </header>

          {selectedAccountIds.size > 0 && (
            <div className="sticky top-14 lg:top-0 z-10 mb-4 flex items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5">
              <span className="text-sm font-medium text-brand-800">{t.products.selected(selectedAccountIds.size)}</span>
              <button className="btn-danger btn-sm" onClick={() => setConfirmAccountsOpen(true)}>
                <Trash2 className="w-3.5 h-3.5" />
                {t.products.deleteSelected}
              </button>
            </div>
          )}

          {accountsLoading ? (
            <TableSkeleton rows={6} cols={5} />
          ) : accounts.length === 0 ? (
            <EmptyState icon={<Users className="w-5 h-5" />} title={t.admin.emptyAccounts} />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th w-10">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                          checked={allAccountsSelected}
                          onChange={toggleSelectAllAccounts}
                          aria-label={t.products.selectAllPage}
                        />
                      </th>
                      <th className="th">{t.admin.tableUser}</th>
                      <th className="th">{t.admin.tableEmail}</th>
                      <th className="th">{t.admin.tableRole}</th>
                      <th className="th">{t.admin.tableScore}</th>
                      <th className="th">{t.admin.tableJoined}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map(a => (
                      <tr key={a.id} className="hover:bg-slate-50/70">
                        <td className="td w-10">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                            checked={selectedAccountIds.has(a.id)}
                            onChange={() => toggleSelectAccount(a.id)}
                            aria-label={a.email}
                          />
                        </td>
                        <td className="td font-medium text-slate-900">{a.name || a.email}</td>
                        <td className="td text-slate-500">{a.email}</td>
                        <td className="td">
                          <span className="badge badge-neutral capitalize">{a.role}</span>
                        </td>
                        <td className="td text-slate-500">
                          {a.role === "seller" ? (a.score != null ? `★ ${a.score.toFixed(1)}` : "—") : "—"}
                        </td>
                        <td className="td text-slate-500">
                          {a.created_at ? new Date(a.created_at).toLocaleDateString() : "—"}
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
          <header className="mb-6 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.products}</h1>
              {productsTotal > 0 && (
                <p className="mt-1 text-sm text-slate-500">
                  {t.products.showing(
                    (productsPage - 1) * 20 + 1,
                    Math.min(productsPage * 20, productsTotal),
                    productsTotal,
                  )}
                </p>
              )}
            </div>
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                className="input pl-10"
                placeholder={t.products.search}
                value={productSearch}
                onChange={e => handleSearchChange(e.target.value)}
                aria-label={t.products.search}
              />
            </div>
          </header>

          {selectedIds.size > 0 && (
            <div className="sticky top-14 lg:top-0 z-10 mb-4 flex items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5">
              <span className="text-sm font-medium text-brand-800">{t.products.selected(selectedIds.size)}</span>
              <button className="btn-danger btn-sm" onClick={() => setConfirmDeleteOpen(true)}>
                <Trash2 className="w-3.5 h-3.5" />
                {t.products.deleteSelected}
              </button>
            </div>
          )}

          {productsLoading ? (
            <TableSkeleton rows={6} cols={5} />
          ) : products.length === 0 ? (
            <EmptyState
              icon={<Package className="w-5 h-5" />}
              title={productSearch ? t.products.noMatch(productSearch) : t.admin.emptyProducts}
            />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th w-10">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                          checked={allPageSelected}
                          onChange={toggleSelectAll}
                          aria-label={t.products.selectAllPage}
                        />
                      </th>
                      <th className="th">{t.admin.tableProduct}</th>
                      <th className="th">{t.admin.tableSku}</th>
                      <th className="th">{t.admin.tableSeller}</th>
                      <th className="th">{t.admin.tableCategory}</th>
                      <th className="th">{t.admin.tableMoq}</th>
                      <th className="th">{t.products.favorites}</th>
                      <th className="th">{t.products.views}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map(p => (
                      <tr key={p.id} className="hover:bg-slate-50/70">
                        <td className="td w-10">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                            checked={selectedIds.has(p.id)}
                            onChange={() => toggleSelect(p.id)}
                            aria-label={p.name}
                          />
                        </td>
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
                        <td className="td text-slate-500">{p.favorite_count ?? 0}</td>
                        <td className="td text-slate-500">{p.view_count ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!productsLoading && products.length > 0 && (
            <div className="mt-4 flex items-center justify-between">
              <button
                className="btn-secondary"
                onClick={() => setProductsPage(p => Math.max(1, p - 1))}
                disabled={productsPage <= 1}
              >
                <ChevronLeft className="w-4 h-4" />
                {t.products.previous}
              </button>
              <span className="text-sm text-slate-500">{productsPage} / {totalPages}</span>
              <button
                className="btn-secondary"
                onClick={() => setProductsPage(p => p + 1)}
                disabled={productsPage >= totalPages}
              >
                {t.products.next}
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}

      {tab === "inquiries" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.inquiries}</h1>
          </header>

          {selectedInquiryIds.size > 0 && (
            <div className="sticky top-14 lg:top-0 z-10 mb-4 flex items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5">
              <span className="text-sm font-medium text-brand-800">{t.products.selected(selectedInquiryIds.size)}</span>
              <button className="btn-danger btn-sm" onClick={() => setConfirmInquiriesOpen(true)}>
                <Trash2 className="w-3.5 h-3.5" />
                {t.products.deleteSelected}
              </button>
            </div>
          )}

          {loading ? (
            <TableSkeleton rows={6} cols={5} />
          ) : inquiries.length === 0 ? (
            <EmptyState icon={<Mail className="w-5 h-5" />} title={t.admin.emptyInquiries} />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th w-10">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                          checked={allInquiriesSelected}
                          onChange={toggleSelectAllInquiries}
                          aria-label={t.products.selectAllPage}
                        />
                      </th>
                      <th className="th">{t.admin.tableId}</th>
                      <th className="th">{t.admin.tableBuyer}</th>
                      <th className="th">{t.admin.tableMessage}</th>
                      <th className="th">{t.admin.tableDate}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inquiries.map(i => (
                      <tr key={i.id} className="hover:bg-slate-50/70">
                        <td className="td w-10">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                            checked={selectedInquiryIds.has(i.id)}
                            onChange={() => toggleSelectInquiry(i.id)}
                            aria-label={`#${i.id}`}
                          />
                        </td>
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

      {tab === "reviews" && (
        <>
          <header className="mb-6 flex items-center justify-between gap-4 flex-wrap">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.admin.reviews}</h1>
            <div className="flex items-center gap-2">
              <button
                className={!showReportedOnly ? "btn-primary btn-sm" : "btn-secondary btn-sm"}
                onClick={() => setShowReportedOnly(false)}
              >
                {t.admin.showAll}
              </button>
              <button
                className={showReportedOnly ? "btn-primary btn-sm" : "btn-secondary btn-sm"}
                onClick={() => setShowReportedOnly(true)}
              >
                <Flag className="w-3.5 h-3.5" />
                {t.review.reported} ({reportedCount})
              </button>
            </div>
          </header>
          {reviewsLoading ? (
            <TableSkeleton rows={5} cols={5} />
          ) : reviewsError ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadReviews}>{t.common.tryAgain}</button>}
            />
          ) : displayedReviews.length === 0 ? (
            <EmptyState icon={<Star className="w-5 h-5" />} title={t.admin.emptyReviews} />
          ) : (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="th">{t.admin.tableSeller}</th>
                      <th className="th">{t.admin.tableUser}</th>
                      <th className="th">{t.admin.tableRating}</th>
                      <th className="th">{t.admin.tableMessage}</th>
                      <th className="th">{t.admin.tableStatus}</th>
                      <th className="th"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedReviews.map(r => (
                      <tr key={r.id} className="hover:bg-slate-50/70">
                        <td className="td font-medium text-slate-900 max-w-[200px]">
                          <div className="truncate">{r.seller_name || r.seller_email || "—"}</div>
                        </td>
                        <td className="td text-slate-500">{r.user_email || "—"}</td>
                        <td className="td text-slate-500">★ {r.rating.toFixed(1)}</td>
                        <td className="td max-w-[320px]">
                          <div className="truncate text-slate-700">{r.content || "—"}</div>
                        </td>
                        <td className="td">
                          {r.reported ? (
                            <span className="badge badge-danger">{t.review.reported}</span>
                          ) : (
                            <span className="badge badge-neutral">{t.review.normal}</span>
                          )}
                        </td>
                        <td className="td text-right">
                          <button className="btn-secondary btn-sm" onClick={() => handleDeleteReview(r.id)}>
                            <Trash2 className="w-3.5 h-3.5" />
                            {t.common.delete}
                          </button>
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

      {tab === "testing" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">测试工具</h1>
            <p className="mt-1 text-sm text-slate-500">仅管理员可用。测试结果不会暴露密钥；测试商品不会出现在买家搜索中。</p>
          </header>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <section className="card p-6">
              <div className="flex items-center gap-2 text-slate-900">
                <Mail className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold">验证邮件投递</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">向指定地址发送验证邮件样式，用于检查 Brevo 配置和邮件送达。邮件中的链接仅用于测试，不能验证账户。</p>
              <input
                className="input mt-4"
                type="email"
                value={testEmail}
                onChange={e => setTestEmail(e.target.value)}
                placeholder="test@example.com"
              />
              <button className="btn-primary mt-3 w-full" onClick={handleTestEmail} disabled={sendingTestEmail || !testEmail.trim()}>
                <Send className="w-4 h-4" />
                {sendingTestEmail ? "发送中…" : "发送测试验证邮件"}
              </button>
              {testEmailResult && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600 break-words">{testEmailResult}</p>}
            </section>

            <section className="card p-6">
              <div className="flex items-center gap-2 text-slate-900">
                <Package className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold">商品增删测试</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">创建一个不可见的管理员测试商品，再单独删除它；不会影响卖家商品或买家搜索结果。</p>
              <button className="btn-primary mt-4 w-full" onClick={handleCreateTestProduct} disabled={testingProduct || !!testProduct}>
                <Plus className="w-4 h-4" />
                {testingProduct && !testProduct ? "创建中…" : "创建测试商品"}
              </button>
              {testProduct && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-medium text-amber-900">#{testProduct.product_id} · {testProduct.sku}</p>
                  <p className="mt-1 text-xs text-amber-800 break-words">{testProduct.name}</p>
                  <button className="btn-danger mt-3 w-full" onClick={handleDeleteTestProduct} disabled={testingProduct}>
                    <Trash2 className="w-4 h-4" />
                    {testingProduct ? "删除中…" : "删除此测试商品"}
                  </button>
                </div>
              )}
            </section>

            <section className="card p-6 xl:col-span-1">
              <div className="flex items-center gap-2 text-slate-900">
                <Bot className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold">大模型询盘分析</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">使用生产环境的询盘分析提示词直接调用已配置的大模型；配置缺失或调用失败会明确显示。</p>
              <textarea
                className="input mt-4 min-h-32 resize-y"
                value={testPrompt}
                maxLength={2000}
                onChange={e => setTestPrompt(e.target.value)}
              />
              <button className="btn-primary mt-3 w-full" onClick={handleTestLlm} disabled={testingLlm || !testPrompt.trim()}>
                <Bot className="w-4 h-4" />
                {testingLlm ? "调用中…" : "调用大模型"}
              </button>
              {llmResult && (
                <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100 whitespace-pre-wrap break-words">
                  {JSON.stringify(llmResult, null, 2)}
                </pre>
              )}
            </section>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmDeleteOpen}
        title={t.products.deleteConfirmTitle}
        description={t.products.deleteConfirmDesc(selectedIds.size)}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        loading={deleting}
        onConfirm={handleDeleteSelected}
        onCancel={() => setConfirmDeleteOpen(false)}
      />

      <ConfirmDialog
        open={confirmResetOpen}
        title={t.admin.deleteAllTitle}
        description={t.admin.deleteAllDesc}
        confirmLabel={t.admin.deleteAll}
        cancelLabel={t.common.cancel}
        loading={resetting}
        onConfirm={handleResetAll}
        onCancel={() => setConfirmResetOpen(false)}
      />

      <ConfirmDialog
        open={confirmClearSavedOpen}
        title={t.admin.clearSavedTitle}
        description={t.admin.clearSavedDesc}
        confirmLabel={t.admin.clearSaved}
        cancelLabel={t.common.cancel}
        loading={clearingSaved}
        onConfirm={handleClearSaved}
        onCancel={() => setConfirmClearSavedOpen(false)}
      />

      <ConfirmDialog
        open={confirmAccountsOpen}
        title={t.common.delete}
        description={t.admin.deleteAccountsConfirm(selectedAccountIds.size)}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        loading={deletingAccounts}
        onConfirm={handleDeleteAccounts}
        onCancel={() => setConfirmAccountsOpen(false)}
      />

      <ConfirmDialog
        open={confirmInquiriesOpen}
        title={t.common.delete}
        description={t.admin.deleteInquiriesConfirm(selectedInquiryIds.size)}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        loading={deletingInquiries}
        onConfirm={handleDeleteInquiries}
        onCancel={() => setConfirmInquiriesOpen(false)}
      />
    </DashboardShell>
  )
}
