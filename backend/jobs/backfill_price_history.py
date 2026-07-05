"""One-time 2-year backfill into price_history. Run once via:
    cd backend && python -m jobs.backfill_price_history
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment."""
import os
import sys
from datetime import date, timedelta

from supabase import create_client

from services.market_data import fetch_ohlcv_batch, upsert_price_history

SECTOR_ETFS = ["SPY", "QQQ", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLRE", "XLU", "XLC"]


def run(supabase_client, tickers: list[str], batch_size: int = 100) -> dict:
    end = date.today()
    start = end - timedelta(days=730)
    rows_written = 0

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"[backfill] fetching batch {i}-{i + len(batch)} of {len(tickers)}", file=sys.stderr)
        bars = fetch_ohlcv_batch(batch, start, end)
        for ticker, df in bars.items():
            rows_written += upsert_price_history(supabase_client, ticker, df)

    return {"tickers_processed": len(tickers), "rows_written": rows_written}


def _load_universe_tickers(supabase_client) -> list[str]:
    response = supabase_client.table("market_universe").select("ticker").execute()
    tickers = sorted({row["ticker"] for row in response.data} | set(SECTOR_ETFS))
    return tickers


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)
    all_tickers = _load_universe_tickers(client)
    print(f"[backfill] backfilling {len(all_tickers)} tickers (2 years each)", file=sys.stderr)
    summary = run(client, all_tickers)
    print(f"[backfill] done: {summary}", file=sys.stderr)
