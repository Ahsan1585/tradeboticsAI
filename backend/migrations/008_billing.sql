-- backend/migrations/008_billing.sql
-- Phase 4: Stripe monetization. Run once in the Supabase SQL editor.
--
-- Model (approved 2026-07-05): new signups get a 7-day full-access trial
-- plus a one-time token grant (see services/billing.py). After the trial,
-- Beginner/Pro deterministic features stay free forever; Pro subscription
-- unlocks permanent full platform access but never unlimited AI -- every
-- AI/LLM-narrated feature always costs tokens regardless of plan.

alter table public.profiles
  add column if not exists plan text not null default 'free',
  add column if not exists stripe_customer_id text,
  add column if not exists trial_ends_at timestamptz;

-- Idempotency ledger for Stripe webhook events: a webhook can be retried
-- by Stripe, and must never double-credit tokens or double-activate a plan.
create table if not exists public.stripe_events (
  event_id    text primary key,
  event_type  text not null,
  processed_at timestamptz not null default now()
);

alter table public.stripe_events enable row level security;
-- No public policies: only the backend's service-role key touches this table.

-- Atomic token credit (the inverse of debit_tokens in 001_debit_tokens.sql),
-- used when a token-pack Stripe Checkout session completes.
create or replace function public.credit_tokens(p_user_id uuid, p_amount int)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  new_balance int;
begin
  update profiles
     set ai_token_balance = ai_token_balance + p_amount
   where id = p_user_id
  returning ai_token_balance into new_balance;

  return new_balance;
end;
$$;

revoke execute on function public.credit_tokens(uuid, int) from anon, authenticated;
grant execute on function public.credit_tokens(uuid, int) to service_role;
