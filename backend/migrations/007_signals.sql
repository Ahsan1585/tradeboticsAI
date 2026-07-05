-- backend/migrations/007_signals.sql
-- Phase 3: logs every signal emitted by the nightly compute job, one row
-- per ticker/horizon/day. Forward returns and trade_outcome are filled in
-- later by backend/jobs/evaluate_signals.py as trading days elapse. This
-- is the data backing the public /track-record page.

create table if not exists public.signals (
  id              bigserial primary key,
  ticker          text not null,
  horizon         text not null,   -- 'day' | 'swing' | 'longterm'
  verdict         text not null,   -- BUY | HOLD | WAIT | AVOID
  confidence      numeric,
  price_at_signal numeric not null,
  stop_price      numeric,         -- BUY only (mandatory exit plan)
  target_price    numeric,         -- BUY only
  inputs          jsonb,           -- full indicator/consensus snapshot at signal time
  engine_version  text not null default 'v1',
  source          text not null default 'nightly',
  d               date not null,   -- trading day the signal was emitted (dedupe key)
  created_at      timestamptz not null default now(),
  ret_1d          numeric,
  ret_5d          numeric,
  ret_20d         numeric,
  ret_60d         numeric,
  spy_ret_1d      numeric,
  spy_ret_5d      numeric,
  spy_ret_20d     numeric,
  spy_ret_60d     numeric,
  trade_outcome   text,            -- 'target_hit' | 'stopped' | 'time_exit' | 'open' | null (non-BUY signals)
  outcome_date    date,
  unique (ticker, horizon, d)
);

create index if not exists signals_d_idx on public.signals (d);
create index if not exists signals_horizon_idx on public.signals (horizon);
create index if not exists signals_trade_outcome_idx on public.signals (trade_outcome);

alter table public.signals enable row level security;

drop policy if exists "signals_public_read" on public.signals;
create policy "signals_public_read" on public.signals
  for select using (true);
