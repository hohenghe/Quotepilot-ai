"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { KeyRound, XCircle } from "lucide-react"
import { resetPassword } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import BrandLogo from "@/components/BrandLogo"

export default function ResetPasswordPage() {
  const { t } = useT()
  const [token, setToken] = useState<string | null>(null)
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setToken(params.get("token"))
  }, [])

  const handleSubmit = async () => {
    if (!token) return
    if (password.length < 8) {
      setError(t.auth.passwordTooShort)
      return
    }
    if (password !== confirm) {
      setError(t.auth.passwordMismatch)
      return
    }
    setLoading(true)
    setError(null)
    const res = await resetPassword(token, password)
    setLoading(false)
    if (res.success) {
      setDone(true)
    } else {
      setError(res.status === 429 ? t.auth.waitCooldown : t.auth.resetInvalid)
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
          <h1 className="text-2xl font-bold text-slate-900">{t.auth.resetPasswordTitle}</h1>
        </div>

        {!token ? (
          <div className="text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-red-50 text-red-600 flex items-center justify-center mb-4">
              <XCircle className="w-6 h-6" />
            </div>
            <p className="text-sm text-slate-600">{t.auth.resetInvalid}</p>
            <Link href="/forgot-password" className="btn-primary w-full justify-center mt-6">
              {t.auth.forgotPasswordTitle}
            </Link>
          </div>
        ) : done ? (
          <div className="text-center">
            <p className="text-sm text-slate-600">{t.auth.resetSuccess}</p>
            <Link href="/buyer" className="btn-primary w-full justify-center mt-6">
              {t.auth.goToLogin}
            </Link>
          </div>
        ) : (
          <>
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 mb-4">
                {error}
              </div>
            )}
            <div className="mb-4">
              <label className="label">{t.auth.newPassword}</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="········"
              />
            </div>
            <div className="mb-6">
              <label className="label">{t.auth.confirmPassword}</label>
              <input
                className="input"
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="········"
              />
            </div>
            <button
              className="btn-primary w-full justify-center py-3 text-base"
              onClick={handleSubmit}
              disabled={loading || !password || !confirm}
            >
              {loading ? t.common.loading : t.auth.resetPassword}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
