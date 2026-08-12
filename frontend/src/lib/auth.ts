const TOKEN_KEY = "quotepilot_token"
const USER_KEY = "quotepilot_user"

export interface AuthUser {
  user_id: number
  email: string
  role: string
  name: string | null
  country: string | null
  phone: string | null
}

export function saveAuth(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(TOKEN_KEY)
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated(): boolean {
  return getToken() !== null
}

export function isSeller(): boolean {
  return getUser()?.role === "seller"
}

export function isAdmin(): boolean {
  return getUser()?.role === "admin"
}
