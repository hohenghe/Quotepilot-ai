import { createClient, SupabaseClient } from "@supabase/supabase-js"

let _client: SupabaseClient | null = null

export function isSupabaseMode(): boolean {
  if (typeof window === "undefined") return false
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  return typeof url === "string" && url.length > 0 && typeof key === "string" && key.length > 0
}

export function supabase() {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
    _client = createClient(url, key)
  }
  return _client
}
