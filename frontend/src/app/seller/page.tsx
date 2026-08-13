"use client"

import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useRouter } from "next/navigation"
import {
  LayoutDashboard, Package, Mail, User, Upload, Trash2, Search, FileText,
  Copy, Clock, CheckCircle2, Inbox,
} from "lucide-react"
import { isAuthenticated, isSeller, getUser, logout } from "@/lib/auth"
import { uploadProducts, getSellerReceivedInquiries, generateSellerReply, getSellerProducts, deleteProducts } from "@/lib/api-client"
import DashboardShell from "@/components/DashboardShell"
import StatCard from "@/components/StatCard"
import EmptyState from "@/components/EmptyState"
import ConfirmDialog from "@/components/ConfirmDialog"
import StatusBadge from "@/components/StatusBadge"
import PageLoader from "@/components/PageLoader"
import { TableSkeleton } from "@/components/LoadingSkeleton"
import { useToast } from "@/components/Toast"
import { useT } from "@/i18n/I18nProvider"
import type { SellerInquiryItem } from "@/lib/api-client"
import type { Product } from "@/types"

type Tab = "overview" | "products" | "inquiries" | "profile"

export default function SellerPage() {
  const { t } = useT()
  const router = useRouter()
  const toast = useToast()

  const [authReady, setAuthReady] = useState(false)
  useEffect(() => {
    if (!isAuthenticated() || !isSeller()) {
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

  const nav = [
    { key: "overview", label: t.nav.overview, icon: LayoutDashboard },
    { key: "products", label: t.nav.products, icon: Package },
    { key: "inquiries", label: t.nav.inquiries, icon: Mail },
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
    if (isAuthenticated() && isSeller()) loadProducts()
  }, [loadProducts])

  useEffect(() => {
    if (isAuthenticated() && isSeller() && (tab === "inquiries" || tab === "overview")) {
      loadInquiries()
    }
  }, [tab, loadInquiries])

  const filtered = useMemo(() => {
    if (!search.trim()) return products
    const q = search.toLowerCase()
    return products.filter(p => p.name.toLowerCase().includes(q) || (p.sku || "").toLowerCase().includes(q))
  }, [products, search])

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
        </>
      )}

      {tab === "products" && (
        <>
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{t.seller.products}</h1>
              <p className="mt-1 text-sm text-slate-500">{t.seller.productsSubtitle}</p>
            </div>
            <button
              className="btn-primary flex-shrink-0"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <Upload className="w-4 h-4" />
              {uploading ? t.seller.uploading : t.seller.uploadCsv}
            </button>
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

      {tab === "profile" && (
        <EmptyState
          icon={<User className="w-5 h-5" />}
          title={t.nav.profile}
          description={t.common.comingSoon}
        />
      )}

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
    </DashboardShell>
  )
}
