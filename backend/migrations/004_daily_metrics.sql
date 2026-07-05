-- backend/migrations/004_daily_metrics.sql
-- Phase 2a: one row per ticker per trading day holding every honest
-- indicator value plus the deterministic signal (verdict/confidence/exit
-- plan) for each of the three horizon tracks. Populated nightly by
-- backend/jobs/compute_daily_metrics.py. /analyze and /run-screener read
-- from this table instead of computing fake metrics live.

create table if not exists public.daily_metrics (
  ticker              text not null,
  d                   date not null,
  price               numeric,
  sma20               numeric,
  sma50               numeric,
  sma200              numeric,
  rsi14               numeric,
  macd_line           numeric,
  macd_signal         numeric,
  macd_hist           numeric,
  atr14               numeric,
  bb_width            numeric,
  extension           numeric,
  gap_pct             numeric,
  rel_strength_spy    numeric,
  rel_strength_sector numeric,
  trend_score         numeric,
  momentum_score      numeric,
  rel_strength_score  numeric,
  volume_score        numeric,
  fundamentals_score  numeric,
  regime              text,
  earnings_within_5d  boolean not null default false,
  signals             jsonb,   -- {"day": {...}, "swing": {...}, "longterm": {...}} from services.signals.build_signal
  engine_version      text not null default 'v1',
  computed_at         timestamptz not null default now(),
  primary key (ticker, d)
);

create index if not exists daily_metrics_d_idx on public.daily_metrics (d);

-- Public read (needed by the future track-record page in Phase 3; no
-- sensitive data). Writes go through the backend's service-role key only.
alter table public.daily_metrics enable row level security;

drop policy if exists "daily_metrics_public_read" on public.daily_metrics;
create policy "daily_metrics_public_read" on public.daily_metrics
  for select using (true);
