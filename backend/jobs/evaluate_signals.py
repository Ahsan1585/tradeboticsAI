"""Nightly signal-evaluation job (Phase 3): fills forward returns and
resolves trade_outcome for signals logged by compute_daily_metrics.py.
No look-ahead bias -- every computation only reads price_history rows
strictly after the signal's own date. Run via GitHub Actions after
compute_daily_metrics:
    cd backend && python -m jobs.evaluate_signals
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment.
"""
import os
import sys
from datetime import date, timedelta

import pandas as pd
from supabase import create_client

from services.market_data import load_price_history_df
from services.signals import HORIZON_LOOKBACKS

RETURN_WINDOWS = (1, 5, 20, 60)
_LOOKBACK_DAYS_FOR_EVAL = 100  # covers the 60-trading-day window plus weekends/holidays margin
_RESOLVED_OUTCOMES = {"target_hit", "stopped", "time_exit"}


def _forward_return(hist_after: pd.DataFrame, n: int, entry_price: float) -> float | None:
    """Return as of the n-th trading day after the signal (1-indexed).
    None if that many trading days haven't elapsed yet."""
    if len(hist_after) < n or entry_price == 0:
        return None
    return float(hist_after["Close"].iloc[n - 1] / entry_price - 1.0)


def _resolve_trade_outcome(hist_after: pd.DataFrame, stop: float, target: float, max_holding_days: int) -> tuple[str, str | None]:
    """Walks forward day-by-day (chronological order only -- no look-ahead)
    checking each day's High/Low against target/stop; the first day either
    is touched wins. A day where both are touched can't be disambiguated
    from daily OHLC alone, so it conservatively resolves as 'stopped'.
    If max_holding_days elapse with neither hit, resolves 'time_exit'.
    If fewer days have elapsed than max_holding_days, stays 'open'."""
    days_to_check = min(len(hist_after), max_holding_days)
    for i in range(days_to_check):
        row = hist_after.iloc[i]
        hit_target = row["High"] >= target
        hit_stop = row["Low"] <= stop
        if hit_stop:
            return "stopped", hist_after.index[i].date().isoformat()
        if hit_target:
            return "target_hit", hist_after.index[i].date().isoformat()

    if len(hist_after) >= max_holding_days:
        return "time_exit", hist_after.index[max_holding_days - 1].date().isoformat()
    return "open", None


def compute_signal_evaluation(
    entry_price: float, spy_entry_price: float, hist_after: pd.DataFrame, spy_after: pd.DataFrame,
    verdict: str, stop: float | None, target: float | None, max_holding_days: int,
) -> dict:
    """Pure computation: forward returns for both the ticker and SPY, plus
    (BUY only) trade_outcome resolution. No DB or network access -- callers
    supply already-loaded, already-sliced price history."""
    result: dict = {}
    for n in RETURN_WINDOWS:
        result[f"ret_{n}d"] = _forward_return(hist_after, n, entry_price)
        result[f"spy_ret_{n}d"] = _forward_return(spy_after, n, spy_entry_price)

    if verdict == "BUY" and stop is not None and target is not None:
        outcome, outcome_date = _resolve_trade_outcome(hist_after, stop, target, max_holding_days)
        result["trade_outcome"] = outcome
        result["outcome_date"] = outcome_date
    else:
        result["trade_outcome"] = None
        result["outcome_date"] = None

    return result


def run(supabase_client) -> dict:
    since = (date.today() - timedelta(days=_LOOKBACK_DAYS_FOR_EVAL)).isoformat()
    rows = supabase_client.table("signals").select("*").gte("d", since).execute().data or []

    price_cache: dict[str, pd.DataFrame] = {}
    evaluated = 0
    skipped_resolved = 0

    for row in rows:
        if row.get("trade_outcome") in _RESOLVED_OUTCOMES:
            skipped_resolved += 1
            continue

        try:
            ticker = row["ticker"]
            signal_date = date.fromisoformat(row["d"])

            if ticker not in price_cache:
                price_cache[ticker] = load_price_history_df(supabase_client, ticker, lookback_days=250)
            if "SPY" not in price_cache:
                price_cache["SPY"] = load_price_history_df(supabase_client, "SPY", lookback_days=250)

            hist = price_cache[ticker]
            spy_hist = price_cache["SPY"]
            hist_after = hist[hist.index.date > signal_date] if not hist.empty else hist
            spy_after = spy_hist[spy_hist.index.date > signal_date] if not spy_hist.empty else spy_hist

            if hist_after.empty:
                continue  # no new trading days since the signal yet

            max_holding_days = HORIZON_LOOKBACKS.get(row["horizon"], 20)
            evaluation = compute_signal_evaluation(
                entry_price=row["price_at_signal"], spy_entry_price=float(spy_hist.loc[spy_hist.index.date <= signal_date, "Close"].iloc[-1]) if not spy_hist.empty and (spy_hist.index.date <= signal_date).any() else row["price_at_signal"],
                hist_after=hist_after, spy_after=spy_after,
                verdict=row["verdict"], stop=row.get("stop_price"), target=row.get("target_price"),
                max_holding_days=max_holding_days,
            )

            supabase_client.table("signals").update(evaluation).eq("id", row["id"]).execute()
            evaluated += 1
        except Exception as e:
            print(f"[evaluate_signals] failed for signal id={row.get('id')} ticker={row.get('ticker')}: {e}", file=sys.stderr)

    return {"total_open_or_recent": len(rows), "skipped_resolved": skipped_resolved, "evaluated": evaluated}


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)
    summary = run(client)
    print(f"[evaluate_signals] done: {summary}", file=sys.stderr)
