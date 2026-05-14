import { createClient } from '@supabase/supabase-js'

// Clean the URL to ensure no trailing slashes or hidden spaces
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL?.replace(/\/$/, '') || ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

if (!supabaseUrl || !supabaseAnonKey) {
  console.error("UAT Alert: Supabase environment variables are missing or malformed.")
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)