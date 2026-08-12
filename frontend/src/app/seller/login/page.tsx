"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login, register } from "@/lib/api-client"
import { saveAuth } from "@/lib/auth"
import AuthForm from "@/components/AuthForm"
import type { AuthFormData } from "@/components/AuthForm"

export default function SellerLoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<"login" | "register">("login")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAuth = async (data: AuthFormData) => {
    setLoading(true)
    setError(null)
    try {
      const res = mode === "register"
        ? await register(data.email, data.password, data.name)
        : await login(data.email, data.password)
      saveAuth(res.token, {
        user_id: res.user_id,
        email: res.email,
        role: res.role,
        name: res.name,
        country: res.country || data.country,
        phone: res.phone || data.phone,
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
      onSubmit={handleAuth}
      onToggleMode={() => { setMode(mode === "login" ? "register" : "login"); setError(null) }}
      loading={loading}
      error={error}
      title="Seller Portal"
    />
  )
}
