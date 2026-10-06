"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter } from "next/navigation"
import { LayoutDashboard, Users, Package, Mail, FileText, Inbox, Search, Trash2, ChevronLeft, ChevronRight, Star, Flag, FlaskConical, Send, Bot, Plus, Activity, RefreshCw } from "lucide-react"
import { isAuthenticated, isAdmin, getUser, logout } from "@/lib/auth"
import { adminGetDashboard, adminListProducts, adminListInquiries, deleteProducts, adminResetAll, adminClearSavedProducts, adminListUsers, adminDeleteUsers, adminDeleteInquiries, adminListReviews, deleteReview, adminSendTestVerificationEmail, adminVerifyTestEmailCode, adminTestLlm, adminGetLlmStatus, adminGetEmbeddingStatus, adminTestEmbedding, adminGetRecognitionStatus, adminTestRecognition, adminCreateTestProduct, adminDeleteTestProduct } from "@/lib/api-client"
import DashboardShell from "@/components/DashboardShell"
import StatCard from "@/components/StatCard"
import EmptyState from "@/components/EmptyState"
import PageLoader from "@/components/PageLoader"
import ConfirmDialog from "@/components/ConfirmDialog"
import { TableSkeleton, Skeleton } from "@/components/LoadingSkeleton"
import { useToast } from "@/components/Toast"
import { useT } from "@/i18n/I18nProvider"
import type { Product, Inquiry } from "@/types"
import type { AdminUserItem, ReviewItem, AdminEmbeddingStatus, AdminEmbeddingTestResult, RecognizedFields } from "@/lib/api-client"
import { adminCreateAccount } from "@/lib/api-client"

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
  const [createOpen, setCreateOpen] = useState(false)
  const [creatingAccount, setCreatingAccount] = useState(false)
  const [createError, setCreateError] = useState("")
  const [newAccount, setNewAccount] = useState({ email: "", password: "", name: "", role: "seller" as "buyer" | "seller" | "admin", distribution: "" })
  const createAccount = async (event: React.FormEvent) => {
    event.preventDefault()
    if (creatingAccount) return
    setCreateError("")
    if (newAccount.role === "seller" && !newAccount.distribution) { setCreateError("请选择是否支持铺货"); return }
    setCreatingAccount(true)
    try {
      await adminCreateAccount({ email: newAccount.email.trim(), password: newAccount.password, name: newAccount.name.trim(), role: newAccount.role, supports_distribution: newAccount.role === "seller" ? newAccount.distribution === "yes" : undefined })
      setNewAccount({ email: "", password: "", name: "", role: "seller", distribution: "" })
      setCreateOpen(false)
      toast.push("success", "账号已创建，可从指定端直接登录")
      await loadAccounts()
    } catch (error) { setCreateError(error instanceof Error ? error.message : "创建失败") }
    finally { setCreatingAccount(false) }
  }
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
  const [testEmailCode, setTestEmailCode] = useState("")
  const [verifyingTestEmail, setVerifyingTestEmail] = useState(false)
  const [testEmailVerified, setTestEmailVerified] = useState(false)
  const [testPrompt, setTestPrompt] = useState("Please analyze a request for 500 LED desk lamps, 12W, CE certified, delivered to Germany.")
  const [testingLlm, setTestingLlm] = useState(false)
  const [llmResult, setLlmResult] = useState<Record<string, unknown> | null>(null)
  const [llmError, setLlmError] = useState("")
  const [llmStatus, setLlmStatus] = useState<{ llm_available: boolean; model: string } | null>(null)
  const [embeddingStatus, setEmbeddingStatus] = useState<AdminEmbeddingStatus | null>(null)
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false)
  const [diagnosticsError, setDiagnosticsError] = useState(false)
  const [embeddingTextA, setEmbeddingTextA] = useState("LED desk lamp, 12W, CE certified")
  const [embeddingTextB, setEmbeddingTextB] = useState("12 watt LED table light with CE certification")
  const [testingEmbedding, setTestingEmbedding] = useState(false)
  const [embeddingResult, setEmbeddingResult] = useState<AdminEmbeddingTestResult | null>(null)
  const [embeddingError, setEmbeddingError] = useState("")
  const [recognitionStatus, setRecognitionStatus] = useState<{ configured: boolean; ocr_model: string; vision_model: string } | null>(null)
  const [recognitionFile, setRecognitionFile] = useState<File | null>(null)
  const [testingRecognition, setTestingRecognition] = useState(false)
  const [recognitionResult, setRecognitionResult] = useState<RecognizedFields | null>(null)
  const [recognitionError, setRecognitionError] = useState("")
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

  const loadDiagnostics = useCallback(async () => {
    setDiagnosticsLoading(true)
    const [llm, embedding, recognition] = await Promise.allSettled([
      adminGetLlmStatus(), adminGetEmbeddingStatus(), adminGetRecognitionStatus(),
    ])
    setLlmStatus(llm.status === "fulfilled" ? llm.value : null)
    setEmbeddingStatus(embedding.status === "fulfilled" ? embedding.value : null)
    setRecognitionStatus(recognition.status === "fulfilled" ? recognition.value : null)
    setDiagnosticsError(llm.status === "rejected" || embedding.status === "rejected" || recognition.status === "rejected")
    setDiagnosticsLoading(false)
  }, [])

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

  useEffect(() => {
    if (authReady && tab === "testing") loadDiagnostics()
  }, [authReady, tab, loadDiagnostics])

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

  const selectableAccounts = accounts.filter(a => a.role !== "admin")
  const allAccountsSelected = selectableAccounts.length > 0 && selectableAccounts.every(a => selectedAccountIds.has(a.id))
  const toggleSelectAllAccounts = () => {
    setSelectedAccountIds(allAccountsSelected ? new Set() : new Set(selectableAccounts.map(a => a.id)))
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

  const errorMessage = (error: unknown) => {
    if (!(error instanceof Error)) return "操作失败"
    const message = error.message.replace(/^API error \d+:\s*/, "")
    try {
      const body: unknown = JSON.parse(message)
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
        return body.detail
      }
    } catch { /* Non-JSON errors already contain a readable message. */ }
    return message
  }

  const handleTestEmail = async () => {
    setSendingTestEmail(true)
    setTestEmailResult(null)
    try {
      const recipient = testEmail.trim()
      await adminSendTestVerificationEmail(recipient)
      setTestEmailCode("")
      setTestEmailVerified(false)
      setTestEmailResult("验证码已发送，请在 5 分钟内回输，完成邮件功能测试。")
      toast.push("success", "测试验证码已发送")
    } catch (error) {
      setTestEmailResult(errorMessage(error))
      toast.push("error", "测试验证码发送失败")
    } finally {
      setSendingTestEmail(false)
    }
  }

  const handleVerifyTestEmail = async () => {
    if (!/^\d{6}$/.test(testEmailCode) || !testEmail.trim()) return
    setVerifyingTestEmail(true)
    setTestEmailResult(null)
    try {
      await adminVerifyTestEmailCode(testEmail.trim(), testEmailCode)
      setTestEmailVerified(true)
      setTestEmailResult("测试通过：邮件送达且回输验证码正确。")
      toast.push("success", "邮件验证码测试通过")
    } catch {
      setTestEmailResult("验证码不正确或已过期，请重试；过期后可重新发送。")
      toast.push("error", "验证码无效或已过期")
    } finally {
      setVerifyingTestEmail(false)
    }
  }

  const handleTestLlm = async () => {
    setTestingLlm(true)
    setLlmResult(null)
    setLlmError("")
    try {
      const result = await adminTestLlm(testPrompt)
      setLlmResult({ ai_used: result.ai_used, ...result.analysis })
      toast.push("success", "大模型调用完成")
    } catch (error) {
      setLlmError(errorMessage(error))
      toast.push("error", errorMessage(error))
    } finally {
      setTestingLlm(false)
    }
  }

  const handleTestEmbedding = async () => {
    setTestingEmbedding(true)
    setEmbeddingResult(null)
    setEmbeddingError("")
    try {
      const result = await adminTestEmbedding(embeddingTextA.trim(), embeddingTextB.trim())
      setEmbeddingResult(result)
      toast.push("success", "向量模型调用完成")
    } catch (error) {
      setEmbeddingError(errorMessage(error))
      toast.push("error", "向量模型测试失败")
    } finally {
      setTestingEmbedding(false)
    }
  }

  const handleTestRecognition = async () => {
    if (!recognitionFile) return
    setTestingRecognition(true)
    setRecognitionResult(null)
    setRecognitionError("")
    try {
      setRecognitionResult(await adminTestRecognition(recognitionFile))
      toast.push("success", "图片识别调用完成")
    } catch (error) {
      setRecognitionError(errorMessage(error))
      toast.push("error", "图片识别测试失败")
    } finally {
      setTestingRecognition(false)
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
            <button className="btn-primary mt-3" onClick={() => { setCreateOpen(!createOpen); setCreateError("") }}><Plus className="w-4 h-4" />新增账号</button>
          </header>

          {createOpen && <form className="card p-5 mb-5" onSubmit={createAccount}>
            <h2 className="font-semibold mb-2">新增专属账号</h2>
            <p className="text-sm text-slate-500 mb-4">管理员创建的账号无需验证邮件即可登录，仅允许指定端。卖家端包含网页与小程序，请妥善交付密码。</p>
            <fieldset disabled={creatingAccount} className="grid md:grid-cols-2 gap-4">
              <label className="label">登录账号<input className="input mt-1" type="text" required minLength={1} maxLength={300} autoComplete="off" placeholder="邮箱或微信审核账号" value={newAccount.email} onChange={e => setNewAccount({ ...newAccount, email: e.target.value })} /></label>
              <label className="label">名称 / 公司名称<input className="input mt-1" required maxLength={200} value={newAccount.name} onChange={e => setNewAccount({ ...newAccount, name: e.target.value })} /></label>
              <label className="label">初始密码<input className="input mt-1" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={newAccount.password} onChange={e => setNewAccount({ ...newAccount, password: e.target.value })} /></label>
              <label className="label">仅允许登录<select className="input mt-1" value={newAccount.role} onChange={e => setNewAccount({ ...newAccount, role: e.target.value as typeof newAccount.role })}><option value="seller">卖家端（网页 / 小程序）</option><option value="buyer">买家端</option><option value="admin">管理端</option></select></label>
              {newAccount.role === "seller" && <label className="label">是否支持铺货（必选）<select required className="input mt-1" value={newAccount.distribution} onChange={e => setNewAccount({ ...newAccount, distribution: e.target.value })}><option value="">请选择</option><option value="yes">是</option><option value="no">否</option></select></label>}
              {newAccount.role === "admin" && <p className="text-sm text-amber-700">管理端账号拥有管理权限，请仅分配给可信任的工作人员。</p>}
            </fieldset>
            {createError && <p role="alert" className="text-sm text-red-600 mt-3">{createError}</p>}
            <div className="flex gap-2 mt-4"><button className="btn-primary" disabled={creatingAccount}>{creatingAccount ? "创建中…" : "创建账号"}</button><button type="button" className="btn-secondary" disabled={creatingAccount} onClick={() => { setCreateOpen(false); setNewAccount({ ...newAccount, password: "" }) }}>取消</button></div>
          </form>}

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
                            disabled={a.role === "admin"}
                            onChange={() => toggleSelectAccount(a.id)}
                            aria-label={a.email}
                          />
                        </td>
                        <td className="td font-medium text-slate-900">{a.name || a.email}</td>
                        <td className="td text-slate-500">{a.email}</td>
                        <td className="td">
                          <span className="badge badge-neutral capitalize">{a.role}</span>
                          {a.restricted_port && <span className="block text-xs text-slate-500 mt-1">仅限此端</span>}
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
            <p className="mt-1 text-sm text-slate-500">仅管理员可用。模型测试会调用已配置的服务并产生用量；结果不包含密钥或原始向量。</p>
          </header>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <section className="card p-6 xl:col-span-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-slate-900">
                  <Activity className="w-5 h-5 text-brand-600" />
                  <h2 className="font-semibold">模型配置与商品向量状态</h2>
                </div>
                <button className="btn-secondary btn-sm" onClick={loadDiagnostics} disabled={diagnosticsLoading}>
                  <RefreshCw className="w-4 h-4" />
                  {diagnosticsLoading ? "刷新中…" : "刷新状态"}
                </button>
              </div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="font-medium text-slate-700">询盘大模型</p>
                  <p className="mt-1 text-slate-600">{llmStatus ? `${llmStatus.model} · ${llmStatus.llm_available ? "已配置" : "未配置"}` : "状态不可用"}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="font-medium text-slate-700">向量模型</p>
                  <p className="mt-1 text-slate-600">{embeddingStatus ? `${embeddingStatus.model} · ${embeddingStatus.configured ? "已配置" : "未配置"}` : "状态不可用"}</p>
                  {embeddingStatus && <p className="mt-2 text-xs text-slate-500">活跃商品 {embeddingStatus.stats.total} · 已完成 {embeddingStatus.stats.completed} · 待处理 {embeddingStatus.stats.pending} · 处理中 {embeddingStatus.stats.processing} · 失败 {embeddingStatus.stats.failed}</p>}
                </div>
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="font-medium text-slate-700">图片识别</p>
                  <p className="mt-1 text-slate-600">{recognitionStatus ? `${recognitionStatus.configured ? "已配置" : "未配置"} · OCR ${recognitionStatus.ocr_model || "未设置"} · 视觉 ${recognitionStatus.vision_model || "未设置"}` : "状态不可用"}</p>
                </div>
              </div>
              {diagnosticsError && <p className="mt-3 text-sm text-amber-700">部分状态读取失败，请刷新或检查后端连接。</p>}
              <p className="mt-3 text-xs text-slate-500">“已配置”只表示密钥和地址存在；请运行下方调用测试确认服务可用。</p>
            </section>

            <section className="card p-6">
              <div className="flex items-center gap-2 text-slate-900">
                <Mail className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold">验证邮件投递</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">向指定地址发送六位验证码，再回输验证，检查 Brevo 投递与验证码校验。测试不会改变账户状态。</p>
              <input
                className="input mt-4"
                type="email"
                value={testEmail}
                onChange={e => {
                  setTestEmail(e.target.value)
                  setTestEmailCode("")
                  setTestEmailVerified(false)
                  setTestEmailResult(null)
                }}
                disabled={sendingTestEmail || verifyingTestEmail}
                placeholder="test@example.com"
              />
              <button className="btn-primary mt-3 w-full" onClick={handleTestEmail} disabled={sendingTestEmail || !testEmail.trim()}>
                <Send className="w-4 h-4" />
                {sendingTestEmail ? "发送中…" : "发送测试验证码"}
              </button>
              {!!testEmail.trim() && !testEmailVerified && (
                <div className="mt-4 border-t border-slate-200 pt-4">
                  <label className="label">回输发往 {testEmail.trim()} 的六位验证码</label>
                  <input
                    className="input mt-2 text-center tracking-widest"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={testEmailCode}
                    onChange={e => setTestEmailCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="六位数字验证码"
                  />
                  <button className="btn-primary mt-3 w-full" onClick={handleVerifyTestEmail}
                    disabled={verifyingTestEmail || sendingTestEmail || testEmailCode.length !== 6}>
                    {verifyingTestEmail ? "验证中…" : "验证测试码"}
                  </button>
                </div>
              )}
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
                onChange={e => { setTestPrompt(e.target.value); setLlmResult(null); setLlmError("") }}
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
              {llmError && <p className="mt-3 text-sm text-red-700 break-words">{llmError}</p>}
            </section>

            <section className="card p-6 xl:col-span-2">
              <div className="flex items-center gap-2 text-slate-900">
                <Activity className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold">向量模型实时测试</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">用两段文本调用当前向量模型，检查维度、耗时和余弦相似度。每次点击都会发起真实调用，不使用查询缓存，也不写入商品。</p>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="text-sm font-medium text-slate-700">文本 A
                  <textarea className="input mt-1 min-h-24 resize-y" value={embeddingTextA} maxLength={500}
                    onChange={e => { setEmbeddingTextA(e.target.value); setEmbeddingResult(null); setEmbeddingError("") }} />
                </label>
                <label className="text-sm font-medium text-slate-700">文本 B
                  <textarea className="input mt-1 min-h-24 resize-y" value={embeddingTextB} maxLength={500}
                    onChange={e => { setEmbeddingTextB(e.target.value); setEmbeddingResult(null); setEmbeddingError("") }} />
                </label>
              </div>
              <button className="btn-primary mt-3" onClick={handleTestEmbedding}
                disabled={testingEmbedding || !embeddingTextA.trim() || !embeddingTextB.trim()}>
                <Activity className="w-4 h-4" />
                {testingEmbedding ? "调用中…" : "调用向量模型"}
              </button>
              {embeddingResult && (
                <div className="mt-4 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-900">
                  <p className="font-medium">调用成功 · {embeddingResult.model}</p>
                  <p className="mt-1">维度 {embeddingResult.dimension} · 耗时 {embeddingResult.latency_ms} ms · 余弦相似度 {embeddingResult.similarity.toFixed(4)}</p>
                  <p className="mt-2 text-xs text-emerald-800">相似度仅供诊断，不代表商品匹配质量或数据库检索已通过。</p>
                </div>
              )}
              {embeddingError && <p className="mt-3 text-sm text-red-700 break-words">{embeddingError}</p>}
            </section>

            <section className="card p-6">
              <div className="flex items-center gap-2 text-slate-900">
                <Search className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold">OCR＋视觉识别测试</h2>
              </div>
              <p className="mt-2 text-sm text-slate-500">上传商品图片，复用卖家端的图片校验与两阶段识别。只返回建议字段，不保存商品。</p>
              <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="admin-recognition-file">测试图片</label>
              <input id="admin-recognition-file" type="file" accept="image/jpeg,image/png,image/webp" className="mt-2 block w-full text-sm text-slate-600"
                disabled={testingRecognition}
                onChange={e => { setRecognitionFile(e.target.files?.[0] || null); setRecognitionResult(null); setRecognitionError("") }} />
              <p className="mt-2 text-xs text-slate-500">支持 JPG、PNG、WebP，最大 5 MB。</p>
              <button className="btn-primary mt-3 w-full" onClick={handleTestRecognition}
                disabled={testingRecognition || !recognitionFile}>
                <Search className="w-4 h-4" />
                {testingRecognition ? "识别中…" : "测试图片识别"}
              </button>
              {recognitionResult && <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-100 whitespace-pre-wrap break-words">{JSON.stringify(recognitionResult, null, 2)}</pre>}
              {recognitionError && <p className="mt-3 text-sm text-red-700 break-words">{recognitionError}</p>}
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
