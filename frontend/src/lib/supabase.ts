import { createClient, type SupabaseClient } from "@supabase/supabase-js"

let _client: SupabaseClient | null = null

function getClient(): SupabaseClient {
  if (_client) return _client
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || ""
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""
  _client = createClient(url, key)
  return _client as SupabaseClient
}

export function isSupabaseMode(): boolean {
  if (typeof window === "undefined") return false
  return (
    (process.env.NEXT_PUBLIC_SUPABASE_URL || "").length > 0 &&
    (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "").length > 0
  )
}

export function supabase() {
  return getClient()
}
