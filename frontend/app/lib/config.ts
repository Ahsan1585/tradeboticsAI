import { supabase } from './supabase';

// Single source of truth for the backend URL.
// Set NEXT_PUBLIC_BACKEND_URL in .env.local (and on Vercel).
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'https://tradebotics-api.onrender.com';

/**
 * fetch() wrapper that attaches the Supabase session JWT.
 * All backend endpoints now verify this token and derive the user id from it —
 * user_id query params / body fields are ignored server-side.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { data: { session } } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  }
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
}
