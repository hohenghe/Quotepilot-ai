"use client"

import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import {
  LayoutDashboard, Package, Mail, User, Upload, Trash2, Search, FileText,
  Copy, Clock, CheckCircle2, Inbox, Star, Flag, Pencil, ImagePlus, Plus,
} from "lucide-react"
import { isAuthenticated, isSeller, isAdmin, getUser, logout, saveAuth, getToken } from "@/lib/auth"
import { uploadProducts, getSellerReceivedInquiries, generateSellerReply, getSellerProducts, deleteProducts, updateProfile, getMySellerReviews, reportReview, getSellerScore, uploadImage } from "@/lib/api-client"
import { CHINA_PROVINCES, CHINA_REGIONS, parseRegion, regionValue } from "@/lib/china-cities"
import DashboardShell from "@/components/DashboardShell"
import StatCard from "@/components/StatCard"
import EmptyState from "@/components/EmptyState"
import ConfirmDialog from "@/components/ConfirmDialog"
import StatusBadge from "@/components/StatusBadge"
import PageLoader from "@/components/PageLoader"
import ProductFormModal from "@/components/ProductFormModal"
import { TableSkeleton } from "@/components/LoadingSkeleton"
import { useToast } from "@/components/Toast"
import { useT } from "@/i18n/I18nProvider"
import type { SellerInquiryItem, ReviewItem } from "@/lib/api-client"
import type { Product } from "@/types"

type Tab = "overview" | "products" | "inquiries" | "profile" | "reviews"

export default function SellerPage() {
  const { t } = useT()
  const router = useRouter()
  const toast = useToast()

  const [authReady, setAuthReady] = useState(false)
  useEffect(() => {
    if (!isAuthenticated() || (!isSeller() && !isAdmin())) {
      router.push("/seller/login")
      return
    }
    setAuthReady(true)
  }, [router])

  const user = authReady ? getUser() : null

  const [tab, setTab] = useState<Tab>("overview")
  const [products, setProducts] = useState<Product[]>([])
  const [productsLoading, setProductsLoading] = useState(true)
  const [productsError, setProductsError] = useState(false)
  const [search, setSearch] = useState("")
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [deleting, setDeleting] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [inquiries, setInquiries] = useState<SellerInquiryItem[]>([])
  const [inquiriesTotal, setInquiriesTotal] = useState(0)
  const [inquiriesPage, setInquiriesPage] = useState(1)
  const [inquiriesHasNext, setInquiriesHasNext] = useState(false)
  const [loadingInquiries, setLoadingInquiries] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [inquiriesError, setInquiriesError] = useState(false)
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  const [profileName, setProfileName] = useState("")
  const [profileStoreName, setProfileStoreName] = useState("")
  const [profileAvatar, setProfileAvatar] = useState<string | null>(null)
  const [profileLicense, setProfileLicense] = useState<string | null>(null)
  const [profilePhone, setProfilePhone] = useState("")
  const [profileCountry, setProfileCountry] = useState<string>(regionValue(CHINA_PROVINCES[0], CHINA_REGIONS[CHINA_PROVINCES[0]][0]))
  const [savingProfile, setSavingProfile] = useState(false)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)
  const [uploadingLicense, setUploadingLicense] = useState(false)

  const [productModalOpen, setProductModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)

  const [sellerReviews, setSellerReviews] = useState<ReviewItem[]>([])
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [reviewsError, setReviewsError] = useState(false)
  const [storeScore, setStoreScore] = useState<number | null>(null)

  const nav = [
    { key: "overview", label: t.nav.overview, icon: LayoutDashboard },
    { key: "products", label: t.nav.products, icon: Package },
    { key: "inquiries", label: t.nav.inquiries, icon: Mail },
    { key: "reviews", label: t.seller.reviews, icon: Star },
    { key: "profile", label: t.nav.profile, icon: User },
  ]

  const loadProducts = useCallback(async () => {
    setProductsLoading(true)
    setProductsError(false)
    try {
      const data = await getSellerProducts()
      setProducts(data.items)
    } catch {
      setProductsError(true)
    } finally {
      setProductsLoading(false)
    }
  }, [])

  const loadInquiries = useCallback(async () => {
    setLoadingInquiries(true)
    setInquiriesError(false)
    try {
      const data = await getSellerReceivedInquiries(1, 50)
      setInquiries(data.items)
      setInquiriesTotal(data.total)
      setInquiriesPage(data.page)
      setInquiriesHasNext(data.has_next)
    } catch {
      setInquiriesError(true)
    } finally {
      setLoadingInquiries(false)
    }
  }, [])

  const loadMoreInquiries = async () => {
    setLoadingMore(true)
    try {
      const data = await getSellerReceivedInquiries(inquiriesPage + 1, 50)
      setInquiries(prev => [...prev, ...data.items])
      setInquiriesPage(data.page)
      setInquiriesHasNext(data.has_next)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated() && (isSeller() || isAdmin())) loadProducts()
  }, [loadProducts])

  useEffect(() => {
    if (isAuthenticated() && (isSeller() || isAdmin()) && (tab === "inquiries" || tab === "overview")) {
      loadInquiries()
    }
  }, [tab, loadInquiries])

  useEffect(() => {
    if (tab === "profile" && user) {
      setProfileName(user.name || "")
      setProfileStoreName(user.store_name || "")
      setProfileAvatar(user.avatar_url || null)
      setProfileLicense(user.business_license_url || null)
      setProfilePhone(user.phone || "")
      const [province, city] = parseRegion(user.country)
      setProfileCountry(regionValue(province, city))
    }
  }, [tab, user?.user_id])

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingAvatar(true)
    try {
      const res = await uploadImage(file, "avatar")
      setProfileAvatar(res.url)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setUploadingAvatar(false)
      e.target.value = ""
    }
  }

  const handleLicenseUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingLicense(true)
    try {
      const res = await uploadImage(file, "license")
      setProfileLicense(res.url)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setUploadingLicense(false)
      e.target.value = ""
    }
  }

  const handleSaveProfile = async () => {
    setSavingProfile(true)
    try {
      const res = await updateProfile({
        name: profileName,
        store_name: profileStoreName,
        avatar_url: profileAvatar ?? undefined,
        business_license_url: profileLicense ?? undefined,
        phone: profilePhone,
        country: profileCountry,
      })
      const token = getToken()
      if (token) {
        saveAuth(token, {
          user_id: res.user_id, email: res.email, role: res.role, name: res.name,
          store_name: res.store_name, avatar_url: res.avatar_url, business_license_url: res.business_license_url, country: res.country, phone: res.phone, uid: res.uid,
        })
      }
      toast.push("success", t.seller.profileUpdated)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setSavingProfile(false)
    }
  }

  const loadReviews = useCallback(async () => {
    setReviewsLoading(true)
    setReviewsError(false)
    try {
      const data = await getMySellerReviews()
      setSellerReviews(data.items)
    } catch {
      setReviewsError(true)
    } finally {
      setReviewsLoading(false)
    }
  }, [])

  const loadScore = useCallback(async () => {
    try {
      const data = await getSellerScore()
      setStoreScore(data.score)
    } catch { }
  }, [])

  useEffect(() => {
    if (tab === "reviews") loadReviews()
  }, [tab, loadReviews])

  useEffect(() => {
    if (isAuthenticated() && (isSeller() || isAdmin())) loadScore()
  }, [loadScore])

  const handleReportReview = async (reviewId: number) => {
    try {
      await reportReview(reviewId)
      toast.push("success", t.review.reportSuccess)
      await loadReviews()
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return products
    const q = search.toLowerCase()
    return products.filter(p => p.name.toLowerCase().includes(q) || (p.sku || "").toLowerCase().includes(q))
  }, [products, search])

  const [profileProvince, profileCity] = parseRegion(profileCountry)

  const allSelected = filtered.length > 0 && filtered.every(p => selectedIds.has(p.id))

  const toggleSelectAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(filtered.map(p => p.id)))
  }

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleFile = async (file: File) => {
    setUploading(true)
    try {
      await uploadProducts(file)
      toast.push("success", t.seller.uploaded)
      await loadProducts()
    } catch (err: any) {
      toast.push("error", err.message || t.common.somethingWentWrong)
    } finally {
      setUploading(false)
    }
  }

  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) await handleFile(file)
    e.target.value = ""
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return
    setDeleting(true)
    const idsToDelete = Array.from(selectedIds)
    try {
      const deletedCount = await deleteProducts(idsToDelete)
      setSelectedIds(new Set())
      toast.push("success", t.seller.deletedCount(deletedCount))
      await loadProducts()
    } catch (err: any) {
      toast.push("error", err.message || t.common.somethingWentWrong)
    } finally {
      setDeleting(false)
      setConfirmOpen(false)
    }
  }

  const handleGenerateReply = async (inquiryId: number) => {
    setGeneratingId(inquiryId)
    try {
      const reply = await generateSellerReply(inquiryId)
      setInquiries(prev => prev.map(i =>
        i.id === inquiryId ? { ...i, status: "replied", reply_body: reply.email_body } : i
      ))
      toast.push("success", t.seller.aiGenerated)
    } catch {
      toast.push("error", t.common.somethingWentWrong)
    } finally {
      setGeneratingId(null)
    }
  }

  const handleLogout = () => {
    logout()
    router.push("/seller/login")
  }

  const pendingCount = inquiries.filter(i => i.status !== "replied").length
  const repliedCount = inquiries.filter(i => i.status === "replied").length

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
      <div className="pb-[22rem] md:pb-[24rem]">
      {tab === "overview" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.seller.overview}</h1>
            <p className="mt-1 text-sm text-slate-500">{t.seller.portalTitle}</p>
          </header>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label={t.seller.products} value={products.length} icon={Package} />
            <StatCard label={t.seller.inquiries} value={inquiriesTotal} icon={Inbox} />
            <StatCard label={t.seller.pending} value={pendingCount} icon={Clock} />
            <StatCard label={t.seller.replied} value={repliedCount} icon={CheckCircle2} />
          </div>

          {user?.role === "seller" && (
            <div className="card p-5 mt-4 max-w-sm">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center">
                  <Star className="w-4 h-4" />
                </div>
                <p className="text-sm text-slate-500">{t.seller.storeScore}</p>
              </div>
              <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">
                {storeScore != null ? storeScore.toFixed(1) : "—"}
              </p>
            </div>
          )}
        </>
      )}

      {tab === "products" && (
        <>
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.seller.products}</h1>
              <p className="mt-1 text-sm text-slate-500">{t.seller.productsSubtitle}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
              <button
                className="btn-secondary flex-shrink-0"
                onClick={() => { setEditingProduct(null); setProductModalOpen(true) }}
              >
                <Plus className="w-4 h-4" />
                {t.seller.addProduct}
              </button>
              <button
                className="btn-primary flex-shrink-0"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                <Upload className="w-4 h-4" />
                {uploading ? t.seller.uploading : t.seller.uploadCsv}
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.docx,.pdf"
              className="hidden"
              onChange={handleInputChange}
            />
          </div>

          <div
            className={`card p-6 mb-6 border-2 border-dashed transition-colors ${dragOver ? "border-brand-400 bg-brand-50/50" : "border-slate-200"}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="flex flex-col items-center justify-center text-center">
              <Upload className="w-6 h-6 text-slate-400 mb-2" />
              <p className="text-sm text-slate-600">{t.seller.uploadCsv}</p>
              <p className="mt-1 text-xs text-slate-400">{t.products.uploadFile}</p>
            </div>
          </div>

          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              className="input pl-10"
              placeholder={t.seller.search}
              value={search}
              onChange={e => setSearch(e.target.value)}
              aria-label={t.common.search}
            />
          </div>

          {selectedIds.size > 0 && (
            <div className="sticky top-14 lg:top-0 z-10 mb-4 flex items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-2.5">
              <span className="text-sm font-medium text-brand-800">{t.common.selected(selectedIds.size)}</span>
              <button className="btn-danger btn-sm" onClick={() => setConfirmOpen(true)}>
                <Trash2 className="w-3.5 h-3.5" />
                {t.common.delete}
              </button>
            </div>
          )}

          {productsLoading ? (
            <TableSkeleton rows={6} cols={4} />
          ) : productsError ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadProducts}>{t.common.tryAgain}</button>}
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={<Package className="w-5 h-5" />}
              title={search ? t.products.noMatch(search) : t.seller.noProducts}
              action={
                !search && (
                  <button className="btn-primary" onClick={() => fileInputRef.current?.click()}>
                    <Upload className="w-4 h-4" />
                    {t.seller.uploadCsv}
                  </button>
                )
              }
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
                          checked={allSelected}
                          onChange={toggleSelectAll}
                          aria-label={t.common.selectAll}
                        />
                      </th>
                      <th className="th">{t.seller.tableProduct}</th>
                      <th className="th">{t.seller.sku}</th>
                      <th className="th">{t.seller.tableCategory}</th>
                      <th className="th">{t.seller.tableMoq}</th>
                      <th className="th">{t.products.favorites}</th>
                      <th className="th">{t.products.views}</th>
                      <th className="th"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(p => (
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
                        <td className="td font-medium text-slate-900 max-w-[280px]">
                          <div className="truncate">{p.name}</div>
                        </td>
                        <td className="td text-slate-500 max-w-[180px]">
                          <div className="truncate">{p.sku || "—"}</div>
                        </td>
                        <td className="td">
                          <span className="badge badge-neutral">{p.category?.replace(/_/g, " ")}</span>
                        </td>
                        <td className="td text-slate-500">{p.moq ?? "—"}</td>
                        <td className="td text-slate-500">{p.favorite_count ?? 0}</td>
                        <td className="td text-slate-500">{p.view_count ?? 0}</td>
                        <td className="td text-right">
                          <button
                            className="btn-secondary btn-sm"
                            onClick={() => { setEditingProduct(p); setProductModalOpen(true) }}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                            {t.seller.edit}
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

      {tab === "inquiries" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.seller.inquiries}</h1>
            <p className="mt-1 text-sm text-slate-500">{t.seller.inquiriesDesc}</p>
          </header>

          {loadingInquiries ? (
            <TableSkeleton rows={3} cols={3} />
          ) : inquiriesError ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadInquiries}>{t.common.tryAgain}</button>}
            />
          ) : inquiries.length === 0 ? (
            <EmptyState icon={<Mail className="w-5 h-5" />} title={t.seller.noInquiries} />
          ) : (
            <div className="space-y-4">
              {inquiries.map(inq => (
                <div key={inq.id} className="card p-5">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-slate-900">{inq.buyer_email || t.seller.buyer}</span>
                        <StatusBadge
                          status={inq.status}
                          label={inq.status === "replied" ? t.seller.replied : t.seller.pending}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-400">
                        {t.seller.received}: {inq.created_at ? new Date(inq.created_at).toLocaleString() : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="bg-slate-50 rounded-lg p-3 mb-4">
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-1">{t.seller.from}</p>
                    <p className="whitespace-pre-wrap text-sm text-slate-700">{inq.raw_message}</p>
                  </div>

                  {inq.reply_body ? (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-slate-700">{t.seller.aiGenerated}</span>
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
                          <Copy className="w-3.5 h-3.5" /> {t.seller.copy}
                        </button>
                      </div>
                      <p className="whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 border border-slate-200 p-3 rounded-lg max-h-60 overflow-y-auto">
                        {inq.reply_body}
                      </p>
                    </div>
                  ) : (
                    <button
                      className="btn-primary w-full"
                      onClick={() => handleGenerateReply(inq.id)}
                      disabled={generatingId === inq.id}
                    >
                      <FileText className="w-4 h-4" />
                      {generatingId === inq.id ? t.seller.generating : t.seller.generateReply}
                    </button>
                  )}
                </div>
              ))}
              {inquiriesHasNext && (
                <div className="pt-2 text-center">
                  <button className="btn-secondary" onClick={loadMoreInquiries} disabled={loadingMore}>
                    {loadingMore ? t.common.loading : t.common.loadMore}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {tab === "reviews" && (
        <>
          <header className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.seller.reviews}</h1>
          </header>

          {reviewsLoading ? (
            <TableSkeleton rows={4} cols={3} />
          ) : reviewsError ? (
            <EmptyState
              title={t.common.somethingWentWrong}
              action={<button className="btn-secondary" onClick={loadReviews}>{t.common.tryAgain}</button>}
            />
          ) : sellerReviews.length === 0 ? (
            <EmptyState icon={<Star className="w-5 h-5" />} title={t.seller.noReviews} />
          ) : (
            <div className="space-y-4">
              {sellerReviews.map(r => (
                <div key={r.id} className="card p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-900 truncate">{r.user_name || r.user_email || "—"}</span>
                        <span className="text-amber-500 text-sm">★ {r.rating.toFixed(1)}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">{t.seller.from}: {r.user_email || "—"}</p>
                      <p className="mt-0.5 text-xs text-slate-400">{r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}</p>
                    </div>
                    {r.reported ? (
                      <span className="badge badge-warning flex-shrink-0">{t.review.reported}</span>
                    ) : (
                      <button className="btn-secondary btn-sm flex-shrink-0" onClick={() => handleReportReview(r.id)}>
                        <Flag className="w-3.5 h-3.5" /> {t.review.report}
                      </button>
                    )}
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
              ))}
            </div>
          )}
        </>
      )}

      {tab === "profile" && (
        user?.role === "admin" ? (
          <EmptyState icon={<User className="w-5 h-5" />} title={t.common.adminNoTrading} />
        ) : (
          <>
            <header className="mb-6">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.nav.profile}</h1>
            </header>
            <div className="card p-6 max-w-xl">
              <div className="space-y-4">
                <div>
                  <label className="label">{t.auth.companyNameRequired}</label>
                  <input className="input" value={profileName} onChange={e => setProfileName(e.target.value)} />
                </div>
                <div>
                  <label className="label">{t.seller.storeName}</label>
                  <input
                    className="input"
                    value={profileStoreName}
                    onChange={e => setProfileStoreName(e.target.value)}
                    placeholder={profileName || t.seller.storeName}
                  />
                </div>
                <div>
                  <label className="label">{t.seller.avatar}</label>
                  <div className="flex items-center gap-3">
                    {profileAvatar ? (
                      <img src={profileAvatar} alt="" className="w-16 h-16 rounded-full object-cover border border-slate-200" />
                    ) : (
                      <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                        <User className="w-6 h-6" />
                      </div>
                    )}
                    <label className="btn-secondary btn-sm cursor-pointer">
                      <ImagePlus className="w-4 h-4" />
                      {uploadingAvatar ? t.common.loading : t.seller.uploadAvatar}
                      <input type="file" accept="image/*" className="hidden" onChange={handleAvatarUpload} disabled={uploadingAvatar} />
                    </label>
                  </div>
                </div>
                <div>
                  <label className="label">{t.seller.businessLicense}</label>
                  <div className="flex items-center gap-3">
                    {profileLicense ? (
                      <img src={profileLicense} alt="" className="w-16 h-16 object-cover rounded-lg border border-slate-200" />
                    ) : (
                      <div className="w-16 h-16 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400">
                        <FileText className="w-6 h-6" />
                      </div>
                    )}
                    <label className="btn-secondary btn-sm cursor-pointer">
                      <ImagePlus className="w-4 h-4" />
                      {uploadingLicense ? t.common.loading : t.seller.uploadLicense}
                      <input type="file" accept="image/*" className="hidden" onChange={handleLicenseUpload} disabled={uploadingLicense} />
                    </label>
                  </div>
                </div>
                <div>
                  <label className="label">{t.auth.email}</label>
                  <input className="input bg-slate-50" value={user?.email || ""} disabled />
                </div>
                <div>
                  <label className="label">{t.auth.phone}</label>
                  <input className="input" value={profilePhone} onChange={e => setProfilePhone(e.target.value)} />
                </div>
                <div>
                  <label className="label">地区</label>
                  <div className="grid grid-cols-2 gap-3">
                    <select
                      className="input"
                      aria-label="省份"
                      value={profileProvince}
                      onChange={e => {
                        const province = e.target.value
                        setProfileCountry(regionValue(province, CHINA_REGIONS[province][0]))
                      }}
                    >
                      {CHINA_PROVINCES.map(province => <option key={province} value={province}>{province}</option>)}
                    </select>
                    <select
                      className="input"
                      aria-label="城市"
                      value={profileCity}
                      onChange={e => setProfileCountry(regionValue(profileProvince, e.target.value))}
                    >
                      {CHINA_REGIONS[profileProvince].map(city => <option key={city} value={city}>{city}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="label">{t.seller.memberId}</label>
                  <input className="input bg-slate-50" value={user?.uid || "—"} disabled />
                </div>
                <button className="btn-primary" onClick={handleSaveProfile} disabled={savingProfile}>
                  {savingProfile ? t.common.loading : t.seller.saveProfile}
                </button>
              </div>
            </div>
          </>
        )
      )}

      <footer className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-2 shadow-[0_-4px_16px_rgba(15,23,42,0.06)] backdrop-blur lg:left-64">
        <div className="mx-auto flex max-w-[1400px] flex-col items-center justify-center gap-2">
          <Image
            src="/seller-supported-platforms.png"
            alt="常见外贸平台标识示例：Alibaba.com、Amazon Business、DHgate、Made-in-China.com、Global Sources、IndiaMART、Thomasnet、Faire"
            width={1400}
            height={600}
            className="h-auto w-full max-w-2xl object-contain opacity-85"
          />
          <a
            href="https://sell.zhermai.com"
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-brand-600 hover:text-brand-700 hover:underline"
          >
            Market
          </a>
        </div>
      </footer>

      <ProductFormModal
        open={productModalOpen}
        initial={editingProduct}
        onClose={() => setProductModalOpen(false)}
        onSaved={() => { setProductModalOpen(false); loadProducts() }}
      />

      <ConfirmDialog
        open={confirmOpen}
        title={t.seller.confirmDeleteTitle}
        description={t.seller.confirmDeleteDesc(selectedIds.size)}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
        loading={deleting}
        onConfirm={handleDeleteSelected}
        onCancel={() => setConfirmOpen(false)}
      />
      </div>
    </DashboardShell>
  )
}
