"use client"

import { useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import { COUNTRIES } from "@/lib/countries"
import { useT } from "@/i18n/I18nProvider"

interface Props {
  mode: "login" | "register"
  onSubmit: (data: AuthFormData) => Promise<void>
  onToggleMode: () => void
  loading: boolean
  error: string | null
  title: string
}

export interface AuthFormData {
  email: string
  password: string
  name: string
  country: string
  phone: string
}

export default function AuthForm({ mode, onSubmit, onToggleMode, loading, error, title }: Props) {
  const { t } = useT()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [name, setName] = useState("")
  const [country, setCountry] = useState("CN")
  const [phone, setPhone] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setLocalError(null)
    if (!email || !password) return
    if (mode === "register" && password !== confirmPassword) {
      setLocalError(t.auth.passwordMismatch)
      return
    }
    if (mode === "register" && password.length < 6) {
      setLocalError("Password must be at least 6 characters")
      return
    }
    await onSubmit({ email, password, name, country, phone })
  }

  const displayError = localError || error

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md mx-4">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-500 mt-1">
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
            <label className="label">{t.auth.companyName}</label>
            <input
              className="input-field"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Your Company Ltd."
            />
          </div>
        )}

        <div className="mb-4">
          <label className="label">{t.auth.email}</label>
          <input
            className="input-field"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
          />
        </div>

        {mode === "register" && (
          <>
            <div className="mb-4">
              <label className="label">{t.auth.country}</label>
              <select
                className="input-field"
                value={country}
                onChange={e => setCountry(e.target.value)}
              >
                {COUNTRIES.map(c => (
                  <option key={c.code} value={c.code}>
                    {t.country[c.key as keyof typeof t.country]}
                  </option>
                ))}
              </select>
            </div>

            <div className="mb-4">
              <label className="label">{t.auth.phone}</label>
              <input
                className="input-field"
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="+86 138xxxx"
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
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              onClick={() => setShowPassword(!showPassword)}
              tabIndex={-1}
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
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        {mode === "login" && <div className="mb-6" />}

        <button
          className="btn-primary w-full justify-center py-3 text-base"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading
            ? (mode === "register" ? t.auth.registering : t.auth.signingIn)
            : (mode === "register" ? t.auth.createAccount : t.auth.signIn)}
        </button>

        <button
          className="w-full text-center text-sm text-brand-600 hover:text-brand-700 mt-4"
          onClick={onToggleMode}
        >
          {mode === "register" ? t.auth.haveAccount : t.auth.noAccount} {mode === "register" ? t.auth.signIn : t.auth.createAccount}
        </button>
      </div>
    </div>
  )
}
