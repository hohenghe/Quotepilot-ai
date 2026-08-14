"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { MailCheck, XCircle, Loader2 } from "lucide-react"
import { verifyEmail, resendVerification } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"
import LanguageSwitcher from "@/components/LanguageSwitcher"

export default function VerifyEmailPage() {
  const { t } = useT()
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading")
  const [resendEmail, setResendEmail] = useState("")
  const [resending, setResending] = useState(false)
  const [resendMessage, setResendMessage] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get("token")
    if (!token) {
      setStatus("error")
      return
    }
    verifyEmail(token).then((res) => {
      setStatus(res.success ? "success" : "error")
    })
  }, [])

  const handleResend = async () => {
    if (!resendEmail.trim()) return
    setResending(true)
    setResendMessage(null)
    const res = await resendVerification(resendEmail.trim())
    setResending(false)
    setResendMessage(res.success ? t.auth.resendSent : (res.status === 429 ? t.auth.waitCooldown : t.auth.verifyInvalid))
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-10 relative">
      <div className="absolute top-4 right-4 z-50">
        <LanguageSwitcher />
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 w-full max-w-md mx-4 text-center">
        {status === "loading" && (
          <>
            <Loader2 className="mx-auto w-10 h-10 text-brand-600 animate-spin" />
            <h1 className="text-xl font-bold text-slate-900 mt-4">{t.auth.verifying}</h1>
          </>
        )}

        {status === "success" && (
          <>
            <div className="mx-auto w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
              <MailCheck className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900">{t.auth.verifySuccess}</h1>
            <Link href="/buyer" className="btn-primary w-full justify-center mt-6">
              {t.auth.goToLogin}
            </Link>
          </>
        )}

        {status === "error" && (
          <>
            <div className="mx-auto w-12 h-12 rounded-full bg-red-50 text-red-600 flex items-center justify-center mb-4">
              <XCircle className="w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-slate-900">{t.auth.verifyInvalid}</h1>

            {resendMessage && <p className="text-sm text-slate-600 mt-4">{resendMessage}</p>}

            <div className="mt-6 text-left">
              <label className="label">{t.auth.email}</label>
              <input
                className="input"
                type="email"
                value={resendEmail}
                onChange={e => setResendEmail(e.target.value)}
                placeholder="you@company.com"
              />
              <button
                className="btn-primary w-full justify-center mt-4"
                onClick={handleResend}
                disabled={resending || !resendEmail.trim()}
              >
                {resending ? t.common.loading : t.auth.resendVerification}
              </button>
            </div>

            <Link href="/buyer" className="block text-center text-sm text-brand-600 hover:text-brand-700 mt-6">
              {t.auth.goToLogin}
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
