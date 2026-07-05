# backend/jobs/eod_ingest.py
"""Nightly EOD ingest: fetches yesterday's OHLCV bars for the whole
universe into price_history, then rescoring each ticker into
market_universe using the same calculate_quant_metrics used by /analyze.
Run via GitHub Actions (.github/workflows/eod.yml):
    cd backend && python -m jobs.eod_ingest
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment."""
import os
import sys
from datetime import date, timedelta, datetime, timezone

import yfinance as yf
from supabase import create_client

from services.market_data import fetch_ohlcv_batch, upsert_price_history, load_price_history_df
from services.metrics import calculate_quant_metrics, sanitize_nans
from jobs.backfill_price_history import SECTOR_ETFS


def run(supabase_client, tickers: list[str], batch_size: int = 100) -> dict:
    end = date.today()
    start = end - timedelta(days=7)  # small nightly window; price_history dedupes on (ticker, d)
    rows_written = 0
    scored = 0

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"[eod_ingest] fetching batch {i}-{i + len(batch)} of {len(tickers)}", file=sys.stderr)
        bars = fetch_ohlcv_batch(batch, start, end)
        for ticker, df in bars.items():
            rows_written += upsert_price_history(supabase_client, ticker, df)

        for ticker in batch:
            if _score_ticker(supabase_client, ticker):
                scored += 1

    return {"tickers_processed": len(tickers), "rows_written": rows_written, "scored": scored}


def _score_ticker(supabase_client, ticker: str) -> bool:
    hist = load_price_history_df(supabase_client, ticker, lookback_days=130)
    if hist.empty or len(hist) < 20:
        return False

    current_price = round(float(hist["Close"].iloc[-1]), 2)
    prev_price = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else current_price

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
    except Exception as e:
        print(f"[eod_ingest] info fetch failed for {ticker}: {e}", file=sys.stderr)
        info = {}
        stock = yf.Ticker(ticker)

    try:
        (total_score, tech_score, fund_score, _, _, _, _, _, _, _, sector, pe, _) = calculate_quant_metrics(
            hist, info, stock, current_price, prev_price, ticker
        )
    except Exception as e:
        print(f"[eod_ingest] scoring failed for {ticker}: {e}", file=sys.stderr)
        return False

    daily_change = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0.0

    supabase_client.table("market_universe").upsert(sanitize_nans({
        "ticker": ticker,
        "price": current_price,
        "daily_change": round(daily_change, 2),
        "tech_score": int(tech_score),
        "fund_score": int(fund_score),
        "sector": sector,
        "pe": round(pe, 2) if pe else 0,
        "last_scanned": datetime.now(timezone.utc).isoformat(),
    })).execute()
    return True


def _load_universe_tickers(supabase_client) -> list[str]:
    response = supabase_client.table("market_universe").select("ticker").execute()
    return sorted({row["ticker"] for row in response.data} | set(SECTOR_ETFS))


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)
    all_tickers = _load_universe_tickers(client)
    print(f"[eod_ingest] processing {len(all_tickers)} tickers", file=sys.stderr)
    summary = run(client, all_tickers)
    print(f"[eod_ingest] done: {summary}", file=sys.stderr)
