"use client"

import { useState } from "react"
import { FileText, Copy, ExternalLink } from "lucide-react"
import { getAllInquiries } from "@/lib/store"
import type { Inquiry } from "@/types"
import PageHeader from "@/components/PageHeader"
import EmptyState from "@/components/EmptyState"
import { useT } from "@/i18n/I18nProvider"

export default function QuotePage() {
  const { t } = useT()
  const [inquiries] = useState<Inquiry[]>(() => getAllInquiries())
  const [selectedInquiry, setSelectedInquiry] = useState<Inquiry | null>(null)

  return (
    <div>
      <PageHeader
        title={t.quote.title}
        description={t.quote.subtitle}
      />

      {inquiries.length === 0 ? (
        <EmptyState
          icon={<FileText className="w-6 h-6 text-gray-400" />}
          title={t.quote.emptyTitle}
          description={t.quote.emptyDescription}
          action={
            <a href="/inquiry" className="btn-primary">
              {t.quote.goToInquiry}
            </a>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-2">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              {t.quote.recentInquiries}
            </h3>
            {inquiries.map((inq) => (
              <button
                key={inq.id}
                onClick={() => setSelectedInquiry(inq)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedInquiry?.id === inq.id
                    ? "border-brand-300 bg-brand-50"
                    : "border-gray-200 bg-white hover:border-gray-300"
                }`}
              >
                <p className="text-xs font-medium text-gray-900 truncate mb-1">
                  {inq.customer_name || t.quote.unknownCustomer}
                </p>
                <p className="text-xs text-gray-500 line-clamp-2">
                  {inq.raw_message.slice(0, 100)}...
                </p>
                {inq.created_at && (
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(inq.created_at).toLocaleDateString()}
                  </p>
                )}
              </button>
            ))}
          </div>

          <div className="lg:col-span-2">
            {selectedInquiry ? (
              <div className="card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {t.quote.inquiryNumber(selectedInquiry.id)}
                  </h3>
                  <button
                    className="btn-secondary text-xs"
                    onClick={() => navigator.clipboard.writeText(selectedInquiry.raw_message)}
                  >
                    <Copy className="w-3.5 h-3.5" />
                    {t.common.copy}
                  </button>
                </div>

                {selectedInquiry.customer_name && (
                  <div className="flex flex-wrap gap-3 mb-4">
                    <span className="text-sm text-gray-600">
                      <span className="font-medium">{t.quote.customer}:</span> {selectedInquiry.customer_name}
                    </span>
                    {selectedInquiry.customer_company && (
                      <span className="text-sm text-gray-600">
                        <span className="font-medium">{t.quote.company}:</span> {selectedInquiry.customer_company}
                      </span>
                    )}
                    {selectedInquiry.customer_email && (
                      <span className="text-sm text-gray-600">
                        <span className="font-medium">{t.quote.email}:</span> {selectedInquiry.customer_email}
                      </span>
                    )}
                  </div>
                )}

                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-700 whitespace-pre-wrap mb-4">
                  {selectedInquiry.raw_message}
                </div>

                <a href="/inquiry" className="btn-primary text-xs inline-flex">
                  <ExternalLink className="w-3.5 h-3.5" />
                  {t.quote.analyzeAndGenerate}
                </a>
              </div>
            ) : (
              <div className="card p-8 flex flex-col items-center justify-center text-center">
                <FileText className="w-10 h-10 text-gray-300 mb-3" />
                <h3 className="text-lg font-semibold text-gray-500 mb-1">{t.quote.selectInquiry}</h3>
                <p className="text-sm text-gray-400">
                  {t.quote.selectInquiryDesc}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
