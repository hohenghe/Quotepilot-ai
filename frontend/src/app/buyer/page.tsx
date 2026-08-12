"use client"

import { useState } from "react"
import { Sparkles, Copy, TrendingUp, LogOut } from "lucide-react"
import { analyzeAndMatch, login, register } from "@/lib/api-client"
import { saveAuth, isAuthenticated, getUser, logout } from "@/lib/auth"
import AuthForm from "@/components/AuthForm"
import type { AuthFormData } from "@/components/AuthForm"
import type { FullAnalysisResult } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"

export default function BuyerPage() {
  const { t } = useT()
  const [authMode, setAuthMode] = useState<"login" | "register">("login")
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const user = getUser()
  const loggedIn = isAuthenticated()

  // Inquiry state
  const [rawMessage, setRawMessage] = useState("")
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<FullAnalysisResult | null>(null)

  const handleAuth = async (data: AuthFormData) => {
    setAuthLoading(true)
    setAuthError(null)
    try {
      const res = authMode === "register"
        ? await register(data.email, data.password, data.name, data.country, data.phone)
        : await login(data.email, data.password)
      saveAuth(res.token, {
        user_id: res.user_id,
        email: res.email,
        role: res.role,
        name: res.name,
        country: res.country || data.country,
        phone: res.phone || data.phone,
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
    try {
      const res = await analyzeAndMatch(rawMessage, user?.email || undefined)
      setResult(res)
    } catch (e: any) {
      console.warn("Analysis failed", e)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleLogout = () => {
    logout()
    setRawMessage("")
    setResult(null)
  }

  if (!loggedIn || !user) {
    return (
      <AuthForm
        mode={authMode}
        onSubmit={handleAuth}
        onToggleMode={() => { setAuthMode(authMode === "login" ? "register" : "login"); setAuthError(null) }}
        loading={authLoading}
        error={authError}
        title="Buyer Portal"
      />
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="max-w-3xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-500" />
            <span className="text-sm text-gray-500">{user.email}</span>
          </div>
          <button onClick={handleLogout} className="text-gray-400 hover:text-red-500 flex items-center gap-1 text-sm">
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
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
                    {mp.lead_time_days && <span>Lead Time: {mp.lead_time_days}d</span>}
                    {mp.certifications && <span>Certs: {mp.certifications}</span>}
                    {mp.pricing && <span className="text-gray-400">{mp.pricing}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
