"""Batch OHLCV data access: yfinance primary, Stooq CSV fallback, plus a
bounded-TTL live quote fetch for /analyze. This is the only place in the
codebase that talks to yfinance for historical bars — everything else
reads price_history from the DB."""
import asyncio
import io
import os
import sys
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from cachetools import TTLCache

_OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

_quote_cache: TTLCache = TTLCache(maxsize=512, ttl=60)
_quote_locks: dict[str, asyncio.Lock] = {}


def _stooq_fetch(ticker: str, start: date, end: date) -> pd.DataFrame:
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200 or "Date" not in resp.text:
            return pd.DataFrame(columns=_OHLCV_COLUMNS)
        df = pd.read_csv(io.StringIO(resp.text), parse_dates=["Date"])
        df = df.set_index("Date").sort_index()
        df = df.loc[(df.index.date >= start) & (df.index.date <= end)]
        return df[_OHLCV_COLUMNS] if not df.empty else pd.DataFrame(columns=_OHLCV_COLUMNS)
    except Exception as e:
        print(f"[market_data] Stooq fallback failed for {ticker}: {e}", file=sys.stderr)
        return pd.DataFrame(columns=_OHLCV_COLUMNS)


def fetch_ohlcv_batch(tickers: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    """Fetches daily OHLCV bars for tickers between start and end (inclusive).
    Tries yfinance first (batched, one call for all tickers); any ticker with
    no usable data falls back to Stooq's per-ticker CSV endpoint."""
    result: dict[str, pd.DataFrame] = {}
    try:
        raw = yf.download(
            tickers, start=start, end=end, group_by="ticker", threads=True, auto_adjust=False, progress=False,
        )
    except Exception as e:
        print(f"[market_data] yf.download batch failed: {e}", file=sys.stderr)
        raw = pd.DataFrame()

    single = len(tickers) == 1
    for t in tickers:
        try:
            df = raw[t] if not single and t in raw.columns.get_level_values(0) else raw
            df = df[_OHLCV_COLUMNS].dropna(how="all")
        except Exception:
            df = pd.DataFrame(columns=_OHLCV_COLUMNS)

        if df.empty:
            df = _stooq_fetch(t, start, end)

        if not df.empty:
            result[t] = df

    return result


def upsert_price_history(supabase_client, ticker: str, df: pd.DataFrame) -> int:
    """Upserts one ticker's OHLCV rows into price_history. Returns row count."""
    if df.empty:
        return 0
    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "ticker": ticker,
            "d": ts.strftime("%Y-%m-%d"),
            "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
            "high": float(row["High"]) if pd.notna(row["High"]) else None,
            "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
            "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
            "adj_close": float(row["Close"]) if pd.notna(row["Close"]) else None,
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
        })
    supabase_client.table("price_history").upsert(rows, on_conflict="ticker,d").execute()
    return len(rows)


def load_price_history_df(supabase_client, ticker: str, lookback_days: int = 130) -> pd.DataFrame:
    """Reads the most recent lookback_days rows for ticker back into an
    Open/High/Low/Close/Volume DataFrame, ascending by date."""
    response = (
        supabase_client.table("price_history")
        .select("d,open,high,low,close,volume")
        .eq("ticker", ticker)
        .order("d", desc=True)
        .limit(lookback_days)
        .execute()
    )
    if not response.data:
        return pd.DataFrame(columns=_OHLCV_COLUMNS)

    df = pd.DataFrame(response.data)
    df["d"] = pd.to_datetime(df["d"])
    df = df.set_index("d").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    return df[_OHLCV_COLUMNS]


async def get_live_quote(ticker: str) -> dict:
    """Returns {"price": float, "source": str}. Cached 60s per ticker with
    single-flight de-dupe so concurrent requests for the same ticker don't
    trigger duplicate upstream calls."""
    if ticker in _quote_cache:
        return _quote_cache[ticker]

    lock = _quote_locks.setdefault(ticker, asyncio.Lock())
    async with lock:
        if ticker in _quote_cache:  # re-check: another caller may have filled it while we waited
            return _quote_cache[ticker]

        quote = await asyncio.to_thread(_fetch_live_quote_sync, ticker)
        _quote_cache[ticker] = quote
        return quote


def _fetch_live_quote_sync(ticker: str) -> dict:
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_key:
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": ticker, "token": finnhub_key},
                timeout=10,
            )
            data = resp.json()
            price = data.get("c")
            if price:
                return {"price": float(price), "source": "finnhub"}
        except Exception as e:
            print(f"[market_data] Finnhub quote failed for {ticker}: {e}", file=sys.stderr)

    try:
        fast_info = yf.Ticker(ticker).fast_info
        price = fast_info.get("lastPrice") or fast_info.get("last_price")
        if price:
            return {"price": float(price), "source": "fast_info"}
    except Exception as e:
        print(f"[market_data] fast_info quote failed for {ticker}: {e}", file=sys.stderr)

    raise ValueError(f"No live quote available for {ticker}")


def has_earnings_within_5d(ticker: str, today: date | None = None) -> bool:
    """Checks Finnhub's free earnings calendar for a report in the next 5
    calendar days. Fails open (returns False, i.e. no veto) if the API key
    is missing or the request fails -- a transient API issue must not
    silently block every signal."""
    finnhub_key = os.getenv("FINNHUB_API_KEY")
    if not finnhub_key:
        return False

    today = today or date.today()
    end = today + timedelta(days=5)
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": today.isoformat(), "to": end.isoformat(), "symbol": ticker, "token": finnhub_key},
            timeout=10,
        )
        data = resp.json()
        return bool(data.get("earningsCalendar"))
    except Exception as e:
        print(f"[market_data] earnings calendar fetch failed for {ticker}: {e}", file=sys.stderr)
        return False
