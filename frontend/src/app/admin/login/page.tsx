"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login } from "@/lib/api-client"
import { saveAuth } from "@/lib/auth"

export default function AdminLoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!email || !password) return
    setLoading(true)
    setError(null)
    try {
      const res = await login(email, password)
      saveAuth(res.token, { user_id: res.user_id, email: res.email, role: res.role, name: res.name })
      router.push("/admin")
    } catch (e: any) {
      setError("Invalid credentials")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-gray-200 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm mx-4">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-slate-800 rounded-xl mb-3">
            <span className="text-white font-bold text-lg">A</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">Admin Panel</h1>
          <p className="text-sm text-gray-500 mt-1">Sign in to manage the platform</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 mb-4">{error}</div>
        )}

        <div className="mb-4">
          <label className="label">Email</label>
          <input className="input-field" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@quotepilot.ai" />
        </div>

        <div className="mb-6">
          <label className="label">Password</label>
          <input className="input-field" type="password" value={password} onChange={e => setPassword(e.target.value)} />
        </div>

        <button className="btn-primary w-full justify-center py-3" onClick={handleSubmit} disabled={loading}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </div>
    </div>
  )
}
