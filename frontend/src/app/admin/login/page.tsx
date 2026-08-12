"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login } from "@/lib/api-client"
import { saveAuth } from "@/lib/auth"
import AuthForm from "@/components/AuthForm"
import type { AuthFormData } from "@/components/AuthForm"

export default function AdminLoginPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAuth = async (data: AuthFormData) => {
    setLoading(true)
    setError(null)
    try {
      const res = await login(data.email, data.password)
      saveAuth(res.token, {
        user_id: res.user_id,
        email: res.email,
        role: res.role,
        name: res.name,
        country: res.country,
        phone: res.phone,
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
      onSubmit={handleAuth}
      onToggleMode={() => {}}
      loading={loading}
      error={error}
      title="Admin Panel"
    />
  )
}
