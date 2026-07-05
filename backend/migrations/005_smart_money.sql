-- backend/migrations/005_smart_money.sql
-- Phase 2b: smart-money tracking. Two independent signals feeding the
-- scoring engine's consensus view:
--   smart_money_13f: latest known holding of each tracked hedge fund in
--     each ticker, with a change classification vs the prior quarter.
--   smart_money_insider: individual open-market insider transactions
--     (Form 4) in a trailing window.
-- Populated by backend/jobs/ingest_smart_money.py (runs less often than
-- the nightly stock job -- 13F filings are quarterly, Form 4s are ad hoc).

create table if not exists public.smart_money_13f (
  fund_cik      text not null,
  fund_name     text not null,
  ticker        text not null,
  cusip         text not null,
  shares        bigint,
  value         numeric,
  prev_shares   bigint,
  prev_value    numeric,
  change_type   text not null,  -- 'new' | 'increased' | 'decreased' | 'unchanged' | 'exited'
  filing_date   date not null,
  accession     text not null,
  updated_at    timestamptz not null default now(),
  primary key (fund_cik, ticker)
);

create index if not exists smart_money_13f_ticker_idx on public.smart_money_13f (ticker);

create table if not exists public.smart_money_insider (
  id                  bigserial primary key,
  ticker              text not null,
  insider_name        text,
  transaction_code    text,     -- 'P' open-market purchase, 'S' sale, etc.
  shares              bigint,
  price               numeric,
  acquired_disposed   text,     -- 'A' acquired, 'D' disposed
  transaction_date    date,
  accession           text not null,
  ingested_at         timestamptz not null default now(),
  unique (accession, ticker, transaction_date, transaction_code, shares)
);

create index if not exists smart_money_insider_ticker_idx on public.smart_money_insider (ticker);
create index if not exists smart_money_insider_date_idx on public.smart_money_insider (transaction_date);

alter table public.smart_money_13f enable row level security;
alter table public.smart_money_insider enable row level security;

drop policy if exists "smart_money_13f_public_read" on public.smart_money_13f;
create policy "smart_money_13f_public_read" on public.smart_money_13f
  for select using (true);

drop policy if exists "smart_money_insider_public_read" on public.smart_money_insider;
create policy "smart_money_insider_public_read" on public.smart_money_insider
  for select using (true);
