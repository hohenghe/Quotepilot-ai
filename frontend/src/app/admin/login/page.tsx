"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login } from "@/lib/api-client"
import { saveAuth } from "@/lib/auth"
import AuthForm from "@/components/AuthForm"
import type { AuthFormData } from "@/components/AuthForm"
import { useT } from "@/i18n/I18nProvider"

export default function AdminLoginPage() {
  const { t } = useT()
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAuth = async (data: AuthFormData) => {
    setLoading(true)
    setError(null)
    try {
      const res = await login(data.email, data.password, "admin")
      saveAuth(res.token, {
        user_id: res.user_id, email: res.email, role: res.role, name: res.name,
        store_name: res.store_name, country: res.country, phone: res.phone, uid: res.uid,
      })
      router.push("/admin")
    } catch (e: any) {
      setError("Invalid credentials")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthForm
      mode="login"
      role="admin"
      onSubmit={handleAuth}
      onToggleMode={() => {}}
      loading={loading}
      error={error}
      title={t.admin.portalTitle}
    />
  )
}
