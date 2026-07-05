-- backend/migrations/003_price_history.sql
-- Daily OHLCV bars, one row per ticker per trading day. Populated by
-- backend/jobs/backfill_price_history.py (one-time) and
-- backend/jobs/eod_ingest.py (nightly). Run once in the Supabase SQL editor.

create table if not exists public.price_history (
  ticker      text not null,
  d           date not null,
  open        numeric,
  high        numeric,
  low         numeric,
  close       numeric,
  adj_close   numeric,
  volume      bigint,
  primary key (ticker, d)
);

create index if not exists price_history_d_idx on public.price_history (d);

-- Public read (mirrors market_universe: no sensitive data, needed by the
-- frontend's future track-record page in Phase 3). Writes go through the
-- backend's service-role key only.
alter table public.price_history enable row level security;

drop policy if exists "price_history_public_read" on public.price_history;
create policy "price_history_public_read" on public.price_history
  for select using (true);
