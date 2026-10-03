"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { MailCheck, Loader2 } from "lucide-react"
import { verifyEmail, verifyLegacyEmailLink, resendVerification } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import BrandLogo from "@/components/BrandLogo"

export default function VerifyEmailPage() {
  const { t } = useT()
  const [status, setStatus] = useState<"form" | "loading" | "success">("form")
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [resending, setResending] = useState(false)
  const [resendMessage, setResendMessage] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setEmail(params.get("email") || "")
    const oldToken = params.get("token")
    if (oldToken) {
      setStatus("loading")
      verifyLegacyEmailLink(oldToken).then(result => {
        setStatus(result.success ? "success" : "form")
        if (!result.success) setError(t.auth.verifyInvalid)
      })
    }
  }, [])

  const handleVerify = async () => {
    if (!email.trim() || !/^\d{6}$/.test(code)) {
      setError(t.auth.verifyInvalid)
      return
    }
    setStatus("loading")
    setError(null)
    const result = await verifyEmail(email.trim(), code)
    setStatus(result.success ? "success" : "form")
    if (!result.success) setError(result.status === 429 ? t.auth.waitCooldown : t.auth.verifyInvalid)
  }

  const handleResend = async () => {
    if (!email.trim()) return
    setResending(true)
    setResendMessage(null)
    const result = await resendVerification(email.trim())
    setResending(false)
    setResendMessage(result.success ? t.auth.resendSent : (result.status === 429 ? t.auth.waitCooldown : t.auth.verifyInvalid))
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-10 relative">
      <div className="absolute top-4 right-4 z-50"><LanguageSwitcher /></div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 w-full max-w-md mx-4 text-center">
        <BrandLogo className="w-40 mx-auto mb-6" />
        {status === "loading" && <>
          <Loader2 className="mx-auto w-10 h-10 text-brand-600 animate-spin" />
          <h1 className="text-xl font-bold text-slate-900 mt-4">{t.auth.verifying}</h1>
        </>}
        {status === "success" && <>
          <div className="mx-auto w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
            <MailCheck className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">{t.auth.verifySuccess}</h1>
          <Link href="/buyer" className="btn-primary w-full justify-center mt-6">{t.auth.goToLogin}</Link>
          <Link href="/seller/login" className="block text-center text-sm text-brand-600 hover:text-brand-700 mt-4">{t.auth.iAmSeller}</Link>
        </>}
        {status === "form" && <>
          <h1 className="text-xl font-bold text-slate-900">{t.auth.verifyPrompt}</h1>
          {error && <p className="text-sm text-red-600 mt-4">{error}</p>}
          <div className="mt-6 text-left">
            <label className="label">{t.auth.email}</label>
            <input className="input-field" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" />
            <label className="label block mt-4">{t.auth.verificationCode}</label>
            <input className="input-field text-center tracking-widest" inputMode="numeric" autoComplete="one-time-code"
              maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))} />
            <button className="btn-primary w-full justify-center mt-5" onClick={handleVerify} disabled={!email.trim() || code.length !== 6}>
              {t.auth.verifyCode}
            </button>
            {resendMessage && <p className="text-sm text-slate-600 mt-4">{resendMessage}</p>}
            <button className="w-full text-center text-sm text-brand-600 hover:text-brand-700 mt-4"
              onClick={handleResend} disabled={resending || !email.trim()}>
              {resending ? t.common.loading : t.auth.resendVerification}
            </button>
          </div>
          <Link href="/buyer" className="block text-center text-sm text-brand-600 hover:text-brand-700 mt-6">{t.auth.goToLogin}</Link>
          <Link href="/seller/login" className="block text-center text-sm text-brand-600 hover:text-brand-700 mt-4">{t.auth.iAmSeller}</Link>
        </>}
      </div>
    </div>
  )
}
