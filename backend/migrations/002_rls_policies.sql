-- Row Level Security hardening. Run in the Supabase SQL editor.
-- The frontend talks to Supabase with the ANON key, so RLS is the only thing
-- protecting user rows from other users. The backend uses the service role,
-- which bypasses RLS by design.
--
-- Inspect current state first:
--   select tablename, rowsecurity from pg_tables where schemaname = 'public';
--   select * from pg_policies where schemaname = 'public';

-- ── profiles: owner read; balances are NEVER client-writable ─────────────
alter table public.profiles enable row level security;

drop policy if exists "profiles_owner_select" on public.profiles;
create policy "profiles_owner_select" on public.profiles
  for select using (auth.uid() = id);

-- No insert/update/delete policies on purpose: balance changes go through the
-- backend (service role) only. If profile rows are created by a signup trigger,
-- nothing else is needed. If the frontend must update non-financial columns
-- later, add a column-restricted policy then — do not add a blanket update.

-- ── portfolio: owner-only, full control (paper trading writes go via backend,
--    but reads happen client-side) ─────────────────────────────────────────
alter table public.portfolio enable row level security;

drop policy if exists "portfolio_owner_select" on public.portfolio;
create policy "portfolio_owner_select" on public.portfolio
  for select using (auth.uid() = user_id);

-- ── transaction_ledger: owner read-only ──────────────────────────────────
alter table public.transaction_ledger enable row level security;

drop policy if exists "ledger_owner_select" on public.transaction_ledger;
create policy "ledger_owner_select" on public.transaction_ledger
  for select using (auth.uid() = user_id);

-- ── watchlist: owner-only read/write (frontend manages it directly) ──────
alter table public.watchlist enable row level security;

drop policy if exists "watchlist_owner_all" on public.watchlist;
create policy "watchlist_owner_all" on public.watchlist
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ── market_universe: public read, no client writes ───────────────────────
alter table public.market_universe enable row level security;

drop policy if exists "universe_public_read" on public.market_universe;
create policy "universe_public_read" on public.market_universe
  for select using (true);

-- ── ai_scan_cache: backend-only (no client policies at all) ──────────────
alter table public.ai_scan_cache enable row level security;

-- ── Verification queries ──────────────────────────────────────────────────
-- As an authenticated user (SQL editor -> role: authenticated), these must FAIL:
--   update public.profiles set ai_token_balance = 99999;         -- expect 0 rows
--   select * from public.profiles where id <> auth.uid();        -- expect 0 rows
--   select * from public.ai_scan_cache;                          -- expect 0 rows
