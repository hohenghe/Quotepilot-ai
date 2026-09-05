"use client"

import { useState } from "react"
import Link from "next/link"
import { KeyRound } from "lucide-react"
import { forgotPassword } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import BrandLogo from "@/components/BrandLogo"

export default function ForgotPasswordPage() {
  const { t } = useT()
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    if (!email.trim()) return
    setLoading(true)
    setError(null)
    const res = await forgotPassword(email.trim())
    setLoading(false)
    if (res.success) {
      setSent(true)
    } else {
      setError(res.status === 429 ? t.auth.waitCooldown : t.common.somethingWentWrong)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-10 relative">
      <div className="absolute top-4 right-4 z-50">
        <LanguageSwitcher />
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 w-full max-w-md mx-4">
        <div className="text-center mb-6">
          <BrandLogo className="w-40 mx-auto mb-5" />
          <div className="mx-auto w-12 h-12 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center mb-4">
            <KeyRound className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">{t.auth.forgotPasswordTitle}</h1>
          <p className="text-sm text-slate-500 mt-1">{t.auth.forgotPasswordSubtitle}</p>
        </div>

        {sent ? (
          <>
            <p className="text-sm text-slate-600 text-center">{t.auth.resetEmailSent}</p>
            <Link href="/buyer" className="btn-primary w-full justify-center mt-6">
              {t.auth.goToLogin}
            </Link>
          </>
        ) : (
          <>
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 mb-4">
                {error}
              </div>
            )}
            <div className="mb-4">
              <label className="label">{t.auth.email}</label>
              <input
                className="input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
              />
            </div>
            <button
              className="btn-primary w-full justify-center py-3 text-base"
              onClick={handleSubmit}
              disabled={loading || !email.trim()}
            >
              {loading ? t.common.loading : t.auth.sendResetLink}
            </button>
            <Link
              href="/buyer"
              className="block text-center text-sm text-slate-500 hover:text-slate-700 mt-4"
            >
              {t.auth.goToLogin}
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
