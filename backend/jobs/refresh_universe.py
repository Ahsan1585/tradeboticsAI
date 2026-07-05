# backend/jobs/refresh_universe.py
"""Monthly universe refresh: re-scrapes S&P 500 / Nasdaq-100 / DJIA
membership from Wikipedia and upserts the ticker list into
market_universe (ticker-only; scoring fields are untouched — those are
maintained nightly by jobs/eod_ingest.py). Run via GitHub Actions
(.github/workflows/refresh_universe.yml):
    cd backend && python -m jobs.refresh_universe
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment."""
import io
import os
import sys

import pandas as pd
import requests
from supabase import create_client
# NOTE: get_market_universe below needs `io`, `pandas as pd`, and `requests` —
# all three are already imported above; do not duplicate the imports inside
# the function body when moving it from main.py.


def get_market_universe():
    """Fetches unique tickers from S&P 500, Nasdaq-100, and DJIA from Wikipedia."""
    all_tickers = set()
    sources = [
        {"url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "col": "Symbol"},
        {"url": "https://en.wikipedia.org/wiki/Nasdaq-100", "col": "Ticker"},
        {"url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", "col": "Symbol"}
    ]
    headers = {'User-Agent': 'TradeBoticsApp/1.0 (Data Scraper)'}

    for source in sources:
        try:
            response = requests.get(source["url"], headers=headers, timeout=15)
            response.raise_for_status()
            tables = pd.read_html(io.StringIO(response.text))

            target_df = None
            target_col_name = None

            for df in tables:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
                for col in df.columns:
                    if source["col"].lower() in str(col).lower():
                        target_df = df
                        target_col_name = col
                        break
                if target_df is not None: break

            if target_df is not None and target_col_name is not None:
                tickers = target_df[target_col_name].tolist()
                for t in tickers:
                    clean_t = str(t).replace('.', '-').strip()
                    if isinstance(clean_t, str) and 1 <= len(clean_t) <= 5 and clean_t.replace('-', '').isalpha():
                        all_tickers.add(clean_t)
        except Exception:
            pass

    if len(all_tickers) < 50:
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "TSLA", "AVGO",
            "JPM", "V", "WMT", "UNH", "XOM", "MA", "PG", "JNJ", "HD", "COST", "MRK", "ABBV",
            "CRM", "AMD", "CVX", "NFLX", "BAC", "KO", "PEP", "TMO", "LIN", "DIS", "ADBE"
        ]

    return list(all_tickers)


def run(supabase_client) -> int:
    tickers = get_market_universe()
    seed_data = [{"ticker": t} for t in tickers]
    for i in range(0, len(seed_data), 100):
        supabase_client.table("market_universe").upsert(seed_data[i:i + 100]).execute()
    return len(tickers)


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)
    n = run(client)
    print(f"[refresh_universe] upserted {n} tickers", file=sys.stderr)
