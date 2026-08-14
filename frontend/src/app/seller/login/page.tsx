"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login, register } from "@/lib/api-client"
import { saveAuth, logout } from "@/lib/auth"
import AuthForm from "@/components/AuthForm"
import type { AuthFormData } from "@/components/AuthForm"
import { useT } from "@/i18n/I18nProvider"

export default function SellerLoginPage() {
  const { t } = useT()
  const router = useRouter()
  const [mode, setMode] = useState<"login" | "register">("login")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAuth = async (data: AuthFormData) => {
    setLoading(true)
    setError(null)
    try {
      const res = mode === "register"
        ? await register(data.email, data.password, data.name, data.country, data.phone, "seller")
        : await login(data.email, data.password, "seller")
      if (res.role !== "seller" && res.role !== "admin") {
        logout()
        setError(t.common.accountMismatch)
        return
      }
      saveAuth(res.token, {
        user_id: res.user_id, email: res.email, role: res.role, name: res.name,
        store_name: res.store_name, country: res.country || data.country, phone: res.phone || data.phone, uid: res.uid,
      })
      router.push("/seller")
    } catch (e: any) {
      setError(e.message || "Authentication failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthForm
      mode={mode}
      role="seller"
      onSubmit={handleAuth}
      onToggleMode={() => { setMode(mode === "login" ? "register" : "login"); setError(null) }}
      loading={loading}
      error={error}
      title={t.seller.portalTitle}
    />
  )
}
