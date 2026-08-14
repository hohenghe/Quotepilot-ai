"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Sparkles, Send, Search, Mail, Heart, User, Package, Check, Copy, Star, Store } from "lucide-react"
import { analyzeAndMatch, login, register, sendInquiryToSeller, getBuyerInquiries, getSavedProducts, saveProduct, unsaveProduct } from "@/lib/api-client"
import { saveAuth, isAuthenticated, getUser, logout } from "@/lib/auth"
import AuthForm from "@/components/AuthForm"
import DashboardShell from "@/components/DashboardShell"
import EmptyState from "@/components/EmptyState"
import PageLoader from "@/components/PageLoader"
import StatusBadge from "@/components/StatusBadge"
import ReviewModal from "@/components/ReviewModal"
import SellerModal from "@/components/SellerModal"
import { TableSkeleton } from "@/components/LoadingSkeleton"
import { useToast } from "@/components/Toast"
import type { AuthFormData } from "@/components/AuthForm"
import type { FullAnalysisResult, BuyerInquiryItem, SavedProductItem } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"

export default function BuyerPage() {
  const { t } = useT()
  const toast = useToast()
  const [authMode, setAuthMode] = useState<"login" | "register">("login")
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [sentInquiries, setSentInquiries] = useState<Set<number>>(new Set())
  const [sendingId, setSendingId] = useState<number | null>(null)

  const [active, setActive] = useState("discover")
  const [rawMessage, setRawMessage] = useState("")
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<FullAnalysisResult | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const [buyerInquiries, setBuyerInquiries] = useState<BuyerInquiryItem[]>([])
  const [inquiriesLoading, setInquiriesLoading] = useState(false)
  const [inquiriesError, setInquiriesError] = useState(false)
  const [inquiriesPage, setInquiriesPage] = useState(1)
  const [inquiriesHasNext, setInquiriesHasNext] = useState(false)
  const [inquiriesLoadingMore, setInquiriesLoadingMore] = useState(false)

  const [savedProducts, setSavedProducts] = useState<SavedProductItem[]>([])
  const [savedLoading, setSavedLoading] = useState(false)
  const [savedError, setSavedError] = useState(false)

  const [reviewTarget, setReviewTarget] = useState<{ id: number; name: string } | null>(null)
  const [sellerTarget, setSellerTarget] = useState<{ id: number; name: string } | null>(null)

  const [authReady, setAuthReady] = useState(false)
  useEffect(() => { setAuthReady(true) }, [])

  const user = authReady ? getUser() : null
  const loggedIn = authReady && isAuthenticated()

  const nav = [
    { key: "discover", label: t.nav.discover, icon: Search },
    { key: "inquiries", label: t.nav.myInquiries, icon: Mail },
    { key: "saved", label: t.nav.saved, icon: Heart },
    { key: "profile", label: t.nav.profile, icon: User },
  ]

  const handleAuth = async (data: AuthFormData) => {
    setAuthLoading(true)
    setAuthError(null)
    try {
      const res = authMode === "register"
        ? await register(data.email, data.password, data.name, data.country, data.phone, "buyer")
        : await login(data.email, data.password, "buyer")
      saveAuth(res.token, {
        user_id: res.user_id, email: res.email, role: res.role, name: res.name,
        store_name: res.store_name, country: res.country || data.country, phone: res.phone || data.phone, uid: res.uid,
      })
    } catch (e: any) {
      setAuthError(e.message || "Authentication failed")
    } finally {
      setAuthLoading(false)
    }
  }

  const handleAnalyze = async () => {
    if (!rawMessage.trim()) return
    setAnalyzing(true)
    setResult(null)
    setAnalysisError(null)
    try {
      const res = await analyzeAndMatch(rawMessage, user?.email || undefined)
      setResult(res)
    } catch (e: any) {
      setAnalysisError(e.message || t.common.somethingWentWrong)
      toast.push("error", e.message || t.common.somethingWentWrong)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleSendInquiry = async (productId: number) => {
    setSendingId(productId)
    try {
      await sendInquiryToSeller(rawMessage, productId, user?.email || undefined)
      setSentInquiries(prev => new Set(prev).add(productId))
      toast.push("success", t.buyer.inquirySent)
    } catch (e: any) {
      toast.push("error", e.message || t.common.somethingWentWrong)
    } finally {
      setSendingId(null)
    }
  }

  const handleLogout = () => {
    logout()
    setRawMessage("")
    setResult(null)
  }

  const loadBuyerInquiries = useCallback(async () => {
    setInquiriesLoading(true)
    setInquiriesError(false)
    try {
      const data = await getBuyerInquiries(1, 20)
      setBuyerInquiries(data.items)
      setInquiriesPage(data.page)
      setInquiriesHasNext(data.has_next)
    } catch {
      setInquiriesError(true)
    } finally {
      setInquiriesLoading(false)
    }
  }, [])

  const loadMoreBuyerInquiries = async () => {
    setInquiriesLoadingMore(true)
    try {
      const data = await getBuyerInquiries(inquiriesPage + 1, 20)
      setBuyerInquiries(prev => [...prev, ...data.items])
      setInquiriesPage(data.page)
      setInquiriesHasNext(data.has_next)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setInquiriesLoadingMore(false)
    }
  }

  useEffect(() => {
    if (active === "inquiries") {
      loadBuyerInquiries()
    }
  }, [active, loadBuyerInquiries])

  const savedIds = new Set(savedProducts.map(s => s.product_id))

  const loadSavedProducts = useCallback(async () => {
    setSavedLoading(true)
    setSavedError(false)
    try {
      const items = await getSavedProducts()
      setSavedProducts(items)
    } catch {
      setSavedError(true)
    } finally {
      setSavedLoading(false)
    }
  }, [])

  const handleToggleSave = async (productId: number) => {
    if (savedIds.has(productId)) {
      try {
        await unsaveProduct(productId)
        setSavedProducts(prev => prev.filter(s => s.product_id !== productId))
        toast.push("success", t.buyer.unsave)
      } catch {
        toast.push("error", t.common.somethingWentWrong)
      }
    } else {
      try {
        await saveProduct(productId)
        await loadSavedProducts()
        toast.push("success", t.buyer.save)
      } catch {
        toast.push("error", t.common.somethingWentWrong)
      }
    }
  }

  useEffect(() => {
    if (user && user.role !== "admin") {
      loadSavedProducts()
    }
  }, [user?.user_id, user?.role, loadSavedProducts])

  if (!authReady) {
    return <PageLoader />
  }

  if (!loggedIn || !user) {
    return (
      <AuthForm
        mode={authMode}
        role="buyer"
        onSubmit={handleAuth}
        onToggleMode={() => { setAuthMode(authMode === "login" ? "register" : "login"); setAuthError(null) }}
        loading={authLoading}
        error={authError}
        title={t.buyer.portalTitle}
      />
    )
  }

  if (user.role !== "buyer" && user.role !== "admin") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 w-full max-w-sm text-center">
          <h1 className="text-base font-semibold text-slate-900">{t.common.accountMismatch}</h1>
          <button className="btn-primary w-full mt-6" onClick={handleLogout}>
            {t.common.signOut}
          </button>
        </div>
      </div>
    )
  }

  return (
    <DashboardShell
      nav={nav}
      active={active}
      onNavigate={setActive}
      userEmail={user.email}
      onSignOut={handleLogout}
    >
      {active === "discover" ? (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.buyer.title}</h1>
            <p className="mt-1 text-sm text-slate-500">{t.buyer.subtitle}</p>
          </header>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <div className="card p-6">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-brand-600" />
                  <span className="text-xs font-medium text-brand-700">{t.buyer.aiPowered}</span>
                </div>
                <h2 className="mt-2 text-lg font-semibold text-slate-900">{t.buyer.workspaceTitle}</h2>
                <textarea
                  ref={textareaRef}
                  className="input mt-3 min-h-[150px] resize-y"
                  placeholder={t.buyer.placeholder}
                  value={rawMessage}
                  onChange={e => setRawMessage(e.target.value)}
                />
                <button
                  className="btn-primary w-full mt-4 py-2.5"
                  onClick={handleAnalyze}
                  disabled={analyzing || !rawMessage.trim()}
                >
                  {analyzing ? (
                    <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> {t.buyer.analyzing}</>
                  ) : (
                    <><Sparkles className="w-4 h-4" /> {t.buyer.findProducts}</>
                  )}
                </button>
                {analysisError && (
                  <p className="mt-3 text-sm text-red-600">{analysisError}</p>
                )}
              </div>
            </div>

            <div className="lg:col-span-1">
              <div className="card p-6">
                <h3 className="text-sm font-semibold text-slate-900">{t.buyer.tipsTitle}</h3>
                <ul className="mt-3 space-y-2.5">
                  {t.buyer.tips.map((tip, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                      <Check className="w-4 h-4 text-brand-500 flex-shrink-0 mt-0.5" />
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {result && result.matchedProducts.length > 0 && (
            <div className="mt-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-900">
                  {t.buyer.results(result.matchedProducts.length)}
                </h2>
                {result.aiUsed && <span className="badge badge-neutral">{t.buyer.aiBadge}</span>}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {result.matchedProducts.map(mp => {
                  const sent = sentInquiries.has(mp.product_id)
                  const pct = Math.round(mp.match_score * 100)
                  return (
                    <div key={mp.product_id} className="card p-5 flex flex-col">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="font-medium text-slate-900 truncate">{mp.product_name}</h3>
                          {mp.sku && <p className="mt-0.5 text-xs text-slate-400">SKU: {mp.sku}</p>}
                          {mp.seller_name && (
                            <button
                              onClick={() => setSellerTarget({ id: mp.seller_id!, name: mp.seller_name! })}
                              className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline"
                            >
                              <Store className="w-3.5 h-3.5" />
                              {t.buyer.supplier}: {mp.seller_name}
                            </button>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className="badge badge-success">{t.buyer.matchLabel(pct)}</span>
                          {user.role !== "admin" && (
                            <button
                              onClick={() => handleToggleSave(mp.product_id)}
                              className={`p-1.5 rounded-lg transition-colors ${
                                savedIds.has(mp.product_id)
                                  ? "text-brand-600 bg-brand-50"
                                  : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                              }`}
                              aria-label={savedIds.has(mp.product_id) ? t.buyer.unsave : t.buyer.save}
                            >
                              <Heart className={`w-4 h-4 ${savedIds.has(mp.product_id) ? "fill-current" : ""}`} />
                            </button>
                          )}
                        </div>
                      </div>
                      <p className="mt-2 text-xs text-slate-500 line-clamp-2">{mp.match_reason}</p>
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-500">
                        {mp.moq != null && <span>{t.buyer.moqLabel}: {mp.moq}</span>}
                        {mp.lead_time_days != null && <span>{t.buyer.leadTime}: {mp.lead_time_days}d</span>}
                        {mp.certifications && <span>{t.buyer.certs}: {mp.certifications}</span>}
                        <span className="inline-flex items-center gap-1">
                          <Heart className="w-3.5 h-3.5" />
                          {mp.favorite_count ?? 0}
                        </span>
                      </div>
                      {mp.pricing && <p className="mt-2 text-xs text-slate-400 truncate">{mp.pricing}</p>}
                      <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                        <button
                          onClick={() => handleSendInquiry(mp.product_id)}
                          disabled={sent || sendingId === mp.product_id}
                          className="btn-primary w-full"
                        >
                          <Send className="w-4 h-4" />
                          {sent ? t.buyer.inquirySent : t.buyer.requestQuote}
                        </button>
                        <button
                          className="btn-secondary w-full"
                          disabled={!mp.seller_id}
                          onClick={() => setReviewTarget({ id: mp.seller_id!, name: mp.seller_name || t.buyer.seller })}
                        >
                          <Star className="w-4 h-4" />
                          {t.review.title}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {result && result.matchedProducts.length === 0 && (
            <div className="mt-8">
              <EmptyState
                icon={<Package className="w-5 h-5" />}
                title={t.buyer.noMatchTitle}
                description={t.buyer.noMatchHint}
                action={
                  <button className="btn-secondary" onClick={() => textareaRef.current?.focus()}>
                    {t.buyer.editRequest}
                  </button>
                }
              />
            </div>
          )}
        </>
      ) : active === "inquiries" ? (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.nav.myInquiries}</h1>
          </header>

          {inquiriesLoading ? (
            <TableSkeleton rows={4} cols={3} />
          ) : inquiriesError ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadBuyerInquiries}>{t.common.tryAgain}</button>}
            />
          ) : buyerInquiries.length === 0 ? (
            <EmptyState icon={<Mail className="w-5 h-5" />} title={t.buyer.noInquiries} />
          ) : (
            <div className="space-y-4">
              {buyerInquiries.map(inq => (
                <div key={inq.id} className="card p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-medium text-slate-900 truncate">{inq.product_name || "—"}</h3>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {t.buyer.supplier}: {inq.seller_name || inq.seller_email || "—"}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {inq.created_at ? new Date(inq.created_at).toLocaleDateString() : ""}
                      </p>
                    </div>
                    <StatusBadge
                      status={inq.status}
                      label={inq.status === "replied" ? t.buyer.replied : t.buyer.pending}
                    />
                  </div>

                  <div className="mt-3 bg-slate-50 rounded-lg p-3">
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-1">{t.buyer.request}</p>
                    <p className="whitespace-pre-wrap text-sm text-slate-700">{inq.raw_message}</p>
                  </div>

                  {inq.reply_body && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-slate-700">{t.buyer.reply}</span>
                        <button
                          className="btn-secondary btn-sm"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(inq.reply_body || "")
                              toast.push("success", t.common.copied)
                            } catch {
                              toast.push("error", t.common.somethingWentWrong)
                            }
                          }}
                        >
                          <Copy className="w-3.5 h-3.5" /> {t.common.copy}
                        </button>
                      </div>
                      <p className="whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 border border-slate-200 p-3 rounded-lg max-h-60 overflow-y-auto">
                        {inq.reply_body}
                      </p>
                    </div>
                  )}
                </div>
              ))}
              {inquiriesHasNext && (
                <div className="pt-2 text-center">
                  <button className="btn-secondary" onClick={loadMoreBuyerInquiries} disabled={inquiriesLoadingMore}>
                    {inquiriesLoadingMore ? t.common.loading : t.common.loadMore}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      ) : active === "saved" ? (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.buyer.savedTitle}</h1>
          </header>

          {user.role === "admin" ? (
            <EmptyState icon={<Heart className="w-5 h-5" />} title={t.common.adminNoTrading} />
          ) : savedLoading ? (
            <TableSkeleton rows={4} cols={3} />
          ) : savedError ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadSavedProducts}>{t.common.tryAgain}</button>}
            />
          ) : savedProducts.length === 0 ? (
            <EmptyState icon={<Heart className="w-5 h-5" />} title={t.buyer.savedEmpty} description={t.buyer.savedDesc} />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {savedProducts.map(sp => (
                <div key={sp.product_id} className="card p-5 flex flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-medium text-slate-900 truncate">{sp.name}</h3>
                      {sp.sku && <p className="mt-0.5 text-xs text-slate-400">SKU: {sp.sku}</p>}
                    </div>
                    <span className="badge badge-neutral flex-shrink-0">{sp.category?.replace(/_/g, " ")}</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-500">
                    {sp.moq != null && <span>{t.buyer.moqLabel}: {sp.moq}</span>}
                    {sp.lead_time_days != null && <span>{t.buyer.leadTime}: {sp.lead_time_days}d</span>}
                    {sp.certifications && <span>{t.buyer.certs}: {sp.certifications}</span>}
                  </div>
                  {sp.pricing && <p className="mt-2 text-xs text-slate-400 truncate">{sp.pricing}</p>}
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <button className="btn-secondary w-full" onClick={() => handleToggleSave(sp.product_id)}>
                      <Heart className="w-4 h-4" />
                      {t.buyer.unsave}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <EmptyState
          title={nav.find(n => n.key === active)?.label || ""}
          description={t.common.comingSoon}
        />
      )}

      <ReviewModal
        sellerId={reviewTarget?.id ?? 0}
        sellerName={reviewTarget?.name ?? ""}
        open={reviewTarget !== null}
        canWrite={user.role !== "admin"}
        onClose={() => setReviewTarget(null)}
      />

      <SellerModal
        sellerId={sellerTarget?.id ?? 0}
        sellerName={sellerTarget?.name ?? ""}
        open={sellerTarget !== null}
        onReview={() => {
          setReviewTarget({ id: sellerTarget!.id, name: sellerTarget!.name })
          setSellerTarget(null)
        }}
        onClose={() => setSellerTarget(null)}
      />
    </DashboardShell>
  )
}
