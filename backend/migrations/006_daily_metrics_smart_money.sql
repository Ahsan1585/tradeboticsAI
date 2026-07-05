-- backend/migrations/006_daily_metrics_smart_money.sql
-- Phase 2b: adds the smart-money lens to daily_metrics. smart_money_score
-- is the 0-100 lens value (services.scoring.smart_money_score);
-- smart_money_signals is a small jsonb summary (which tracked funds hold
-- it and how their position changed, trailing insider buy/sell $) for
-- display/narration -- kept separate from the heavier smart_money_13f /
-- smart_money_insider tables so /analyze can read one row.

alter table public.daily_metrics
  add column if not exists smart_money_score numeric,
  add column if not exists smart_money_signals jsonb;
