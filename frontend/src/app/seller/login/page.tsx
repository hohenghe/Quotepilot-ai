"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { login, register } from "@/lib/api-client"
import { saveAuth } from "@/lib/auth"

export default function SellerLoginPage() {
  const router = useRouter()
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!email || !password) return
    setLoading(true)
    setError(null)
    try {
      const res = isRegister
        ? await register(email, password, name)
        : await login(email, password)
      saveAuth(res.token, {
        user_id: res.user_id,
        email: res.email,
        role: res.role,
        name: res.name,
      })
      router.push("/seller")
    } catch (e: any) {
      setError(e.message || "Authentication failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-full max-w-md mx-4">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Seller Portal</h1>
          <p className="text-sm text-gray-500 mt-1">
            {isRegister ? "Create your seller account" : "Sign in to manage products"}
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}

        {isRegister && (
          <div className="mb-4">
            <label className="label">Company Name</label>
            <input className="input-field" value={name} onChange={e => setName(e.target.value)} placeholder="Your Company" />
          </div>
        )}

        <div className="mb-4">
          <label className="label">Email</label>
          <input className="input-field" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="seller@company.com" />
        </div>

        <div className="mb-6">
          <label className="label">Password</label>
          <input className="input-field" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Min 6 characters" />
        </div>

        <button className="btn-primary w-full justify-center py-3" onClick={handleSubmit} disabled={loading}>
          {loading ? "Please wait..." : isRegister ? "Create Account" : "Sign In"}
        </button>

        <button
          className="w-full text-center text-sm text-emerald-600 hover:text-emerald-700 mt-4"
          onClick={() => { setIsRegister(!isRegister); setError(null) }}
        >
          {isRegister ? "Already have an account? Sign in" : "New seller? Create account"}
        </button>
      </div>
    </div>
  )
}
