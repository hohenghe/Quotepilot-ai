"use client"

import { useState, useCallback } from "react"
import {
  Sparkles,
  Target,
  Hash,
  Wrench,
  Shield,
  MapPin,
  AlertTriangle,
  TrendingUp,
  DollarSign,
  Copy,
  FileText,
  MailQuestion,
} from "lucide-react"
import { analyzeAndMatch, generateQuote, saveDraftInquiry, getDraftInquiry } from "@/lib/store"
import { generateNoMatchResponse } from "@/lib/ai/llm"
import type { FullAnalysisResult } from "@/lib/store"
import PageHeader from "@/components/PageHeader"
import LoadingSpinner from "@/components/LoadingSpinner"
import { useT } from "@/i18n/I18nProvider"

const DEFAULT_INQUIRY = `We need 500 units of LED lights, 220V, EU plug, CE certificate required, delivery to Germany.

Could you also advise on the best options for office ceiling lighting? Our budget is around $15 per unit.`

type Quote = ReturnType<typeof generateQuote>

export default function InquiryPage() {
  const { t } = useT()
  const [rawMessage, setRawMessage] = useState(() => getDraftInquiry())
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<FullAnalysisResult | null>(null)
  const [quote, setQuote] = useState<Quote | null>(null)
  const [generatingQuote, setGeneratingQuote] = useState(false)
  const [noMatchResponse, setNoMatchResponse] = useState<string | null>(null)
  const [generatingNoMatch, setGeneratingNoMatch] = useState(false)

  const updateDraft = useCallback(
    (text: string) => {
      setRawMessage(text)
      saveDraftInquiry(text)
    },
    []
  )

  const handleAnalyze = async () => {
    if (!rawMessage.trim()) return
    setAnalyzing(true)
    setResult(null)
    setQuote(null)
    setNoMatchResponse(null)
    await new Promise(r => setTimeout(r, 1200))
    const res = analyzeAndMatch(rawMessage)
    setResult(res)
    setAnalyzing(false)

    const allBelowThreshold = res.matchedProducts.length === 0 ||
      res.matchedProducts.every(p => p.match_score < 0.1)
    if (allBelowThreshold) {
      const response = generateNoMatchResponse(rawMessage)
      setNoMatchResponse(response)
    }
  }

  const handleGenerateNoMatch = async () => {
    if (!result) return
    setGeneratingNoMatch(true)
    await new Promise(r => setTimeout(r, 600))
    const response = generateNoMatchResponse(rawMessage)
    setNoMatchResponse(response)
    setGeneratingNoMatch(false)
  }

  const handleGenerateQuote = async () => {
    if (!result) return
    setGeneratingQuote(true)
    await new Promise(r => setTimeout(r, 800))
    const q = generateQuote(
      result.inquiry.id,
      result.matchedProducts.map(p => p.product_id),
      "Please confirm MOQ and lead time."
    )
    setQuote(q)
    setGeneratingQuote(false)
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div>
      <PageHeader
        title={t.inquiry.title}
        description={t.inquiry.subtitle}
      />

      {/* Input */}
      <div className="card p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <label className="label mb-0">{t.inquiry.customerInquiry}</label>
          <button
            onClick={() => updateDraft(DEFAULT_INQUIRY)}
            className="text-xs text-brand-600 hover:text-brand-700 font-medium"
          >
            {t.inquiry.loadExample}
          </button>
        </div>
        <textarea
          className="input-field min-h-[160px] resize-y"
          placeholder={t.inquiry.placeholder}
          value={rawMessage}
          onChange={(e) => updateDraft(e.target.value)}
        />
        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-gray-400">{t.common.characters(rawMessage.length)}</p>
          <button
            className="btn-primary"
            onClick={handleAnalyze}
            disabled={analyzing || !rawMessage.trim()}
          >
            {analyzing ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {t.inquiry.analyzing}
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                {t.inquiry.analyzeInquiry}
              </>
            )}
          </button>
        </div>
      </div>

      {analyzing && <LoadingSpinner text={t.inquiry.aiAnalyzing} />}

      {result && (
        <div className="space-y-6">
          {/* Extracted Info */}
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Target className="w-5 h-5 text-brand-600" />
              <h3 className="text-lg font-semibold text-gray-900">{t.inquiry.extractedInfo}</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {result.analysis.product_category && (
                <InfoCard
                  icon={<Hash className="w-4 h-4" />}
                  label={t.inquiry.productCategory}
                  value={result.analysis.product_category.replace(/_/g, " ")}
                />
              )}
              {result.analysis.quantity && (
                <InfoCard
                  icon={<Hash className="w-4 h-4" />}
                  label={t.inquiry.quantity}
                  value={`${result.analysis.quantity} ${t.common.units}`}
                />
              )}
              {result.analysis.target_price && (
                <InfoCard
                  icon={<DollarSign className="w-4 h-4" />}
                  label={t.inquiry.targetPrice}
                  value={`$${result.analysis.target_price}${t.common.perUnit}`}
                />
              )}
              {result.analysis.delivery_location && (
                <InfoCard
                  icon={<MapPin className="w-4 h-4" />}
                  label={t.inquiry.delivery}
                  value={result.analysis.delivery_location}
                />
              )}
              {Object.keys(result.analysis.technical_params).length > 0 && (
                <InfoCard
                  icon={<Wrench className="w-4 h-4" />}
                  label={t.inquiry.technicalSpecs}
                  value={Object.entries(result.analysis.technical_params)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(", ")}
                />
              )}
              {result.analysis.required_certifications.length > 0 && (
                <InfoCard
                  icon={<Shield className="w-4 h-4" />}
                  label={t.inquiry.certifications}
                  value={result.analysis.required_certifications.join(", ")}
                />
              )}
            </div>

            {result.analysis.missing_info.length > 0 && (
              <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-600" />
                  <span className="text-sm font-medium text-yellow-800">{t.inquiry.missingInfo}</span>
                </div>
                <ul className="space-y-1">
                  {result.analysis.missing_info.map((item, i) => (
                    <li key={i} className="text-sm text-yellow-700 flex items-start gap-2">
                      <span className="mt-0.5">&bull;</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Matched Products */}
          {result.matchedProducts.length > 0 && (
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="w-5 h-5 text-green-600" />
                <h3 className="text-lg font-semibold text-gray-900">{t.inquiry.matchedProducts}</h3>
              </div>
              <div className="space-y-4">
                {result.matchedProducts.map((mp) => (
                  <div
                    key={mp.product_id}
                    className="p-4 bg-gray-50 rounded-lg border border-gray-200"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900">{mp.product_name}</h4>
                        {mp.sku && <p className="text-xs text-gray-500 mt-0.5">{t.products.sku}: {mp.sku}</p>}
                      </div>
                      <span className="badge badge-green text-xs">
                        {t.inquiry.matchPercent((mp.match_score * 100))}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mb-3">{mp.match_reason}</p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                      {mp.moq && (
                        <div>
                          <span className="text-gray-500">{t.inquiry.moq}: </span>
                          <span className="font-medium">{mp.moq}</span>
                        </div>
                      )}
                      {mp.lead_time_days && (
                        <div>
                          <span className="text-gray-500">{t.inquiry.leadTime}: </span>
                          <span className="font-medium">{mp.lead_time_days} {t.common.days}</span>
                        </div>
                      )}
                      {mp.certifications && (
                        <div>
                          <span className="text-gray-500">{t.inquiry.certs}: </span>
                          <span className="font-medium">{mp.certifications}</span>
                        </div>
                      )}
                    </div>
                    {mp.pricing && (
                      <p className="text-xs text-gray-600 mt-2">
                        <span className="font-medium">{t.inquiry.price}:</span> {mp.pricing}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200 flex flex-wrap gap-2">
                <button
                  className="btn-primary"
                  onClick={handleGenerateQuote}
                  disabled={generatingQuote}
                >
                  {generatingQuote ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      {t.inquiry.generating}
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4" />
                      {t.inquiry.generateQuote}
                    </>
                  )}
                </button>
                <button
                  className="btn-secondary"
                  onClick={handleGenerateNoMatch}
                  disabled={generatingNoMatch}
                >
                  {generatingNoMatch ? (
                    <>
                      <div className="w-4 h-4 border-2 border-gray-400/30 border-t-gray-500 rounded-full animate-spin" />
                      {t.inquiry.generatingNoMatch}
                    </>
                  ) : (
                    <>
                      <MailQuestion className="w-4 h-4" />
                      {t.inquiry.generateNoMatchResponse}
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* No-Match Response */}
          {noMatchResponse && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <MailQuestion className="w-5 h-5 text-orange-500" />
                  <h3 className="text-lg font-semibold text-gray-900">{t.inquiry.noMatchResponseTitle}</h3>
                </div>
                <button
                  className="btn-secondary text-xs"
                  onClick={() => handleCopy(noMatchResponse)}
                >
                  <Copy className="w-3.5 h-3.5" />
                  {t.common.copy}
                </button>
              </div>
              {result && (result.matchedProducts.length === 0 ||
                result.matchedProducts.every(p => p.match_score < 0.1)) && (
                <div className="mb-3 p-2 bg-orange-50 border border-orange-200 rounded text-xs text-orange-700">
                  {t.inquiry.noMatchAutoNotice}
                </div>
              )}
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 whitespace-pre-wrap text-sm text-gray-800 leading-relaxed max-h-[500px] overflow-y-auto font-mono text-xs">
                {noMatchResponse}
              </div>
            </div>
          )}

          {/* Quote */}
          {quote && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-purple-600" />
                  <h3 className="text-lg font-semibold text-gray-900">{t.inquiry.generatedQuote}</h3>
                </div>
                <button
                  className="btn-secondary text-xs"
                  onClick={() => handleCopy(quote.email_body)}
                >
                  <Copy className="w-3.5 h-3.5" />
                  {t.common.copy}
                </button>
              </div>

              {quote.subject && (
                <p className="text-sm font-medium text-gray-700 mb-3">
                  {t.inquiry.subject}: {quote.subject}
                </p>
              )}

              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 whitespace-pre-wrap text-sm text-gray-800 leading-relaxed max-h-[500px] overflow-y-auto font-mono text-xs">
                {quote.email_body}
              </div>

              {(quote.total_amount_low || quote.total_amount_high) && (
                <div className="mt-4 flex items-center gap-2 text-sm">
                  <DollarSign className="w-4 h-4 text-gray-500" />
                  <span className="text-gray-600">{t.inquiry.estimatedTotal}: </span>
                  <span className="font-semibold text-gray-900">
                    ${quote.total_amount_low?.toLocaleString()} - $
                    {quote.total_amount_high?.toLocaleString()} {quote.currency}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function InfoCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
      <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center flex-shrink-0 border border-gray-200">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-sm font-medium text-gray-900 capitalize truncate">{value}</p>
      </div>
    </div>
  )
}
