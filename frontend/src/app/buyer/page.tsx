"use client"

import { useState } from "react"
import { Sparkles, Copy, Mail, FileText, TrendingUp } from "lucide-react"
import { analyzeAndMatch } from "@/lib/api-client"
import type { FullAnalysisResult } from "@/lib/api-client"

export default function BuyerPage() {
  const [rawMessage, setRawMessage] = useState("")
  const [email, setEmail] = useState("")
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<FullAnalysisResult | null>(null)
  const [noMatchResponse, setNoMatchResponse] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = async () => {
    if (!rawMessage.trim()) return
    setAnalyzing(true)
    setError(null)
    setResult(null)
    setNoMatchResponse(null)
    try {
      const res = await analyzeAndMatch(rawMessage, email || undefined)
      setResult(res)

      if (
        res.matchedProducts.length === 0 ||
        res.matchedProducts.every(p => p.match_score < 0.1)
      ) {
        setNoMatchResponse(
          `Subject: Re: Your Product Inquiry\n\nDear Valued Customer,\n\nThank you for your inquiry. After carefully reviewing your requirements, we were unable to find an exact match in our current catalog. Our team has been notified and will reach out within 24 hours with tailored recommendations.\n\nBest regards,\nQuotePilot AI Team`
        )
      }
    } catch (e: any) {
      setError(e.message || "Analysis failed. Please try again.")
    } finally {
      setAnalyzing(false)
    }
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-sm border mb-4">
            <Sparkles className="w-4 h-4 text-indigo-500" />
            <span className="text-sm font-medium text-gray-600">AI-Powered Product Matching</span>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Tell Us What You Need</h1>
          <p className="text-gray-500">Describe your product requirements and we'll find the best matches.</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Your Email (optional)</label>
          <input
            type="email"
            className="input-field mb-4"
            placeholder="you@company.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />

          <label className="block text-sm font-medium text-gray-700 mb-2">What are you looking for?</label>
          <textarea
            className="input-field min-h-[140px] resize-y mb-4"
            placeholder="Example: We need 500 units of LED panel lights, 220V, EU plug, CE certified, delivery to Germany. Budget around $15 per unit."
            value={rawMessage}
            onChange={e => setRawMessage(e.target.value)}
          />

          <button
            className="btn-primary w-full justify-center text-base py-3"
            onClick={handleAnalyze}
            disabled={analyzing || !rawMessage.trim()}
          >
            {analyzing ? (
              <><div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Analyzing...</>
            ) : (
              <><Sparkles className="w-5 h-5" /> Find Matching Products</>
            )}
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 mb-6">
            {error}
          </div>
        )}

        {result && result.matchedProducts.length > 0 && (
          <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <h2 className="text-lg font-semibold">Matching Products ({result.matchedProducts.length})</h2>
              {result.aiUsed && (
                <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">AI</span>
              )}
            </div>
            <div className="space-y-3">
              {result.matchedProducts.map(mp => (
                <div key={mp.product_id} className="p-4 bg-gray-50 rounded-xl">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold text-gray-900">{mp.product_name}</h3>
                      <p className="text-xs text-gray-500">{mp.match_reason}</p>
                    </div>
                    <span className="text-sm font-bold text-green-600">
                      {Math.round(mp.match_score * 100)}%
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-gray-600">
                    {mp.moq && <span>MOQ: {mp.moq}</span>}
                    {mp.lead_time_days && <span>Lead Time: {mp.lead_time_days} days</span>}
                    {mp.certifications && <span>Certs: {mp.certifications}</span>}
                    {mp.pricing && <span className="text-gray-400">{mp.pricing}</span>}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-4 text-center">
              Our team will email you a detailed quotation within 24 hours.
            </p>
          </div>
        )}

        {noMatchResponse && (
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Mail className="w-5 h-5 text-orange-500" />
                <h2 className="text-lg font-semibold">No Match Found</h2>
              </div>
              <button className="btn-secondary text-xs" onClick={() => handleCopy(noMatchResponse)}>
                <Copy className="w-3 h-3" /> Copy
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 p-4 rounded-xl">{noMatchResponse}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
