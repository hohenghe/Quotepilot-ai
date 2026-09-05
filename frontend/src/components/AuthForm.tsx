"use client"

import { useState } from "react"
import { Eye, EyeOff, MailCheck } from "lucide-react"
import Link from "next/link"
import { COUNTRIES } from "@/lib/countries"
import { CHINA_PROVINCES, CHINA_REGIONS, parseRegion, regionValue } from "@/lib/china-cities"
import { resendVerification } from "@/lib/api-client"
import { useT } from "@/i18n/I18nProvider"
import LanguageSwitcher from "@/components/LanguageSwitcher"
import BrandLogo from "@/components/BrandLogo"

export interface AuthFormData {
  email: string
  password: string
  name: string
  country: string
  phone: string
}

export type AuthSubmitResult = void | { type: "registered"; email: string }

interface Props {
  mode: "login" | "register"
  role: "buyer" | "seller" | "admin"
  onSubmit: (data: AuthFormData) => Promise<AuthSubmitResult>
  onToggleMode: () => void
  loading: boolean
  error: string | null
  title: string
}

export default function AuthForm({ mode, role, onSubmit, onToggleMode, loading, error, title }: Props) {
  const { t } = useT()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [name, setName] = useState("")
  const [country, setCountry] = useState<string>(role === "seller" ? regionValue(CHINA_PROVINCES[0], CHINA_REGIONS[CHINA_PROVINCES[0]][0]) : "CN")
  const [phone, setPhone] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null)
  const [resending, setResending] = useState(false)
  const [resendMessage, setResendMessage] = useState<string | null>(null)

  const handleSubmit = async () => {
    setLocalError(null)
    if (mode === "login") {
      if (!email || !password) return
      await onSubmit({ email, password, name, country, phone })
      return
    }
    if (!email || !password) return
    if (password !== confirmPassword) {
      setLocalError(t.auth.passwordMismatch)
      return
    }
    if (password.length < 8) {
      setLocalError(t.auth.passwordTooShort)
      return
    }
    if (!phone.trim()) {
      setLocalError(t.auth.phoneRequired)
      return
    }
    if (role === "seller" && !name.trim()) {
      setLocalError(t.auth.companyRequired)
      return
    }
    const result = await onSubmit({ email, password, name, country, phone })
    if (result && result.type === "registered") {
      setRegisteredEmail(result.email)
    }
  }

  const handleResend = async () => {
    if (!registeredEmail) return
    setResending(true)
    setResendMessage(null)
    try {
      const res = await resendVerification(registeredEmail)
      setResendMessage(res.success ? t.auth.resendSent : res.message)
    } catch {
      setResendMessage(t.common.somethingWentWrong)
    } finally {
      setResending(false)
    }
  }

  const displayError = localError || error
  const [sellerProvince, sellerCity] = parseRegion(country)

  if (registeredEmail) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center py-10 relative">
        <div className="absolute top-4 right-4 z-50">
          <LanguageSwitcher />
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 w-full max-w-md mx-4 text-center">
          <BrandLogo className="w-40 mx-auto mb-5" />
          <div className="mx-auto w-12 h-12 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center mb-4">
            <MailCheck className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">{t.auth.verifyPrompt}</h1>
          <p className="text-sm text-slate-500 mt-2">{registeredEmail}</p>

          {resendMessage && <p className="text-sm text-slate-600 mt-3">{resendMessage}</p>}

          <button
            className="btn-primary w-full justify-center mt-6"
            onClick={handleResend}
            disabled={resending}
          >
            {resending ? t.common.loading : t.auth.resendVerification}
          </button>
          <button
            className="w-full text-center text-sm text-brand-600 hover:text-brand-700 mt-4"
            onClick={() => { setRegisteredEmail(null); setResendMessage(null) }}
          >
            {t.auth.goToLogin}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-10 relative">
      <div className="absolute top-4 right-4 z-50">
        <LanguageSwitcher />
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-8 w-full max-w-md mx-4">
        <div className="text-center mb-6">
          <BrandLogo className="w-44 mx-auto mb-5" />
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="text-sm text-slate-500 mt-1">
            {mode === "register" ? t.auth.createAccount : t.auth.signIn}
          </p>
        </div>

        {displayError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 mb-4">
            {displayError}
          </div>
        )}

        {mode === "register" && (
          <div className="mb-4">
            <label className="label">{role === "seller" ? t.auth.companyNameRequired : t.auth.companyNameOptional}</label>
            <input
              className="input-field"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your Company Ltd."
            />
          </div>
        )}

        <div className="mb-4">
          <label className="label">{mode === "register" ? t.auth.email : t.auth.identifier}</label>
          <input
            className="input-field"
            type={mode === "register" ? "email" : "text"}
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder={mode === "register" ? "you@company.com" : t.auth.identifier}
            required
          />
        </div>

        {mode === "register" && (
          <>
            <div className="mb-4">
              <label className="label">{role === "seller" ? "地区 *" : t.auth.country}</label>
              {role === "seller" ? (
                <div className="grid grid-cols-2 gap-3">
                  <select
                    className="input-field"
                    aria-label="省份"
                    value={sellerProvince}
                    onChange={e => {
                      const province = e.target.value
                      setCountry(regionValue(province, CHINA_REGIONS[province][0]))
                    }}
                  >
                    {CHINA_PROVINCES.map(province => <option key={province} value={province}>{province}</option>)}
                  </select>
                  <select
                    className="input-field"
                    aria-label="城市"
                    value={sellerCity}
                    onChange={e => setCountry(regionValue(sellerProvince, e.target.value))}
                  >
                    {CHINA_REGIONS[sellerProvince].map(city => <option key={city} value={city}>{city}</option>)}
                  </select>
                </div>
              ) : (
                <select className="input-field" value={country} onChange={e => setCountry(e.target.value)}>
                  {COUNTRIES.map(c => (
                    <option key={c.code} value={c.code}>{t.country[c.key as keyof typeof t.country]}</option>
                  ))}
                </select>
              )}
            </div>

            <div className="mb-4">
              <label className="label">{t.auth.phone}</label>
              <input
                className="input-field"
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="+86 138xxxx"
                required
              />
            </div>
          </>
        )}

        <div className="mb-4">
          <label className="label">{t.auth.password}</label>
          <div className="relative">
            <input
              className="input-field pr-12"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="········"
              required
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              onClick={() => setShowPassword(!showPassword)}
              tabIndex={-1}
              aria-label={showPassword ? t.auth.hidePassword : t.auth.showPassword}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {mode === "register" && (
          <div className="mb-6">
            <label className="label">{t.auth.confirmPassword}</label>
            <div className="relative">
              <input
                className="input-field pr-12"
                type={showPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="········"
                required
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                aria-label={showPassword ? t.auth.hidePassword : t.auth.showPassword}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        {mode === "login" && <div className="mb-6" />}

        {role === "buyer" && (
          <Link
            href="/seller"
            className="block text-center text-sm font-medium text-brand-600 hover:text-brand-700 mb-4"
          >
            {t.auth.iAmSeller}
          </Link>
        )}

        <button
          className="btn-primary w-full justify-center py-3 text-base"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading
            ? (mode === "register" ? t.auth.registering : t.auth.signingIn)
            : (mode === "register" ? t.auth.createAccount : t.auth.signIn)}
        </button>

        {mode === "login" && (
          <Link
            href="/forgot-password"
            className="block text-center text-sm text-slate-500 hover:text-slate-700 mt-4"
          >
            {t.auth.forgotPassword}
          </Link>
        )}

        {role !== "admin" && (
          <button
            className="w-full text-center text-sm text-brand-600 hover:text-brand-700 mt-4"
            onClick={onToggleMode}
          >
            {mode === "register" ? t.auth.haveAccount : t.auth.noAccount} {mode === "register" ? t.auth.signIn : t.auth.createAccount}
          </button>
        )}
      </div>
    </div>
  )
}
