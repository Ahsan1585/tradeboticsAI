"""Nightly compute job (Phase 2a): reads price_history, computes honest
indicators and deterministic per-horizon signals for every ticker, and
writes the results to daily_metrics. Run via GitHub Actions after
eod_ingest:
    cd backend && python -m jobs.compute_daily_metrics
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment."""
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd
from supabase import create_client

from services.market_data import load_price_history_df, has_earnings_within_5d
from services.metrics import sanitize_nans, safe_float
from services import indicators, signals

MIN_HISTORY_DAYS = 60

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Financial Services": "XLF",
    "Financial": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}
DEFAULT_SECTOR_ETF = "SPY"


def _load_regime(supabase_client) -> tuple[str, pd.Series]:
    spy_hist = load_price_history_df(supabase_client, "SPY", lookback_days=250)
    spy_close = spy_hist["Close"]
    if len(spy_close) < 200:
        return "risk_off", spy_close  # not enough history to trust the gate -> fail safe

    sma200 = indicators.sma(spy_close, 200)
    sma20 = indicators.sma(spy_close, 20)
    regime = indicators.market_regime(
        close=float(spy_close.iloc[-1]),
        sma200=float(sma200.iloc[-1]),
        sma20_slope=indicators.slope(sma20, lookback=5),
    )
    return regime, spy_close


def _lens_scores(hist: pd.DataFrame, spy_close: pd.Series, sector_close: pd.Series, fundamentals_score: float) -> dict:
    close = hist["Close"]
    sma20 = indicators.sma(close, 20)
    sma50 = indicators.sma(close, 50)
    sma200 = indicators.sma(close, 200)
    rsi14 = indicators.rsi(close, 14)
    macd_line, macd_signal, macd_hist = indicators.macd(close)
    atr14 = indicators.atr(hist["High"], hist["Low"], close, 14)
    bbw = indicators.bb_width(close, 20)

    price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    open_price = float(hist["Open"].iloc[-1])
    atr_val = float(atr14.iloc[-1]) if pd.notna(atr14.iloc[-1]) else 0.0
    sma20_val = float(sma20.iloc[-1]) if pd.notna(sma20.iloc[-1]) else price

    ext = indicators.extension(price, sma20_val, atr_val)
    gap = indicators.gap_percent(open_price, prev_close)
    rel_spy = indicators.relative_strength(close, spy_close, lookback=20) if len(spy_close) > 20 else 0.0
    rel_sector = indicators.relative_strength(close, sector_close, lookback=20) if len(sector_close) > 20 else 0.0

    trend_score = 50.0
    trend_score += 15 if pd.notna(sma20.iloc[-1]) and price > sma20.iloc[-1] else -15
    trend_score += 15 if pd.notna(sma50.iloc[-1]) and price > sma50.iloc[-1] else -15
    trend_score += 20 if pd.notna(sma200.iloc[-1]) and price > sma200.iloc[-1] else -10
    trend_score = max(0.0, min(100.0, trend_score))

    momentum_score = float(rsi14.iloc[-1]) if pd.notna(rsi14.iloc[-1]) else 50.0
    hist_slope = indicators.slope(macd_hist, lookback=3)
    if pd.notna(hist_slope):
        momentum_score += 10 if hist_slope > 0 else -10
    momentum_score = max(0.0, min(100.0, momentum_score))

    rel_avg = (rel_spy + rel_sector) / 2
    rel_strength_score = max(0.0, min(100.0, 50 + rel_avg * 500))

    avg_volume = float(hist["Volume"].rolling(20).mean().iloc[-1])
    volume = float(hist["Volume"].iloc[-1])
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    volume_score = max(0.0, min(100.0, 50 + (volume_ratio - 1) * 100))

    return {
        "price": price, "sma20": sma20_val,
        "sma50": float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None,
        "sma200": float(sma200.iloc[-1]) if pd.notna(sma200.iloc[-1]) else None,
        "rsi14": float(rsi14.iloc[-1]) if pd.notna(rsi14.iloc[-1]) else None,
        "macd_line": float(macd_line.iloc[-1]), "macd_signal": float(macd_signal.iloc[-1]),
        "macd_hist": float(macd_hist.iloc[-1]), "atr14": atr_val,
        "bb_width": float(bbw.iloc[-1]) if pd.notna(bbw.iloc[-1]) else None,
        "extension": ext, "gap_pct": gap,
        "rel_strength_spy": rel_spy, "rel_strength_sector": rel_sector,
        "trend_score": trend_score, "momentum_score": momentum_score,
        "rel_strength_score": rel_strength_score, "volume_score": volume_score,
        "fundamentals_score": fundamentals_score,
    }


def compute_ticker_metrics(
    ticker: str, hist: pd.DataFrame, spy_close: pd.Series, sector_close: pd.Series,
    fundamentals_score: float, earnings_within_5d: bool, regime: str,
) -> dict | None:
    """Pure computation: raw indicators + per-horizon signals for one
    ticker. Returns None when there isn't enough history to trust the
    longer-window indicators (SMA50/rel-strength)."""
    if len(hist) < MIN_HISTORY_DAYS:
        return None

    lenses = _lens_scores(hist, spy_close, sector_close, fundamentals_score)

    horizons = {
        horizon: signals.build_signal(
            ticker=ticker, horizon=horizon,
            trend=lenses["trend_score"], momentum=lenses["momentum_score"],
            rel_strength=lenses["rel_strength_score"], volume=lenses["volume_score"],
            fundamentals=lenses["fundamentals_score"],
            regime=regime, extension=lenses["extension"], gap_pct=lenses["gap_pct"],
            earnings_within_5d=earnings_within_5d, price=lenses["price"], atr=lenses["atr14"],
        )
        for horizon in signals.HORIZON_LOOKBACKS
    }

    return {
        "ticker": ticker,
        "d": date.today().isoformat(),
        "price": round(lenses["price"], 2),
        "sma20": round(lenses["sma20"], 2) if lenses["sma20"] is not None else None,
        "sma50": round(lenses["sma50"], 2) if lenses["sma50"] is not None else None,
        "sma200": round(lenses["sma200"], 2) if lenses["sma200"] is not None else None,
        "rsi14": round(lenses["rsi14"], 2) if lenses["rsi14"] is not None else None,
        "macd_line": round(lenses["macd_line"], 4),
        "macd_signal": round(lenses["macd_signal"], 4),
        "macd_hist": round(lenses["macd_hist"], 4),
        "atr14": round(lenses["atr14"], 4),
        "bb_width": round(lenses["bb_width"], 4) if lenses["bb_width"] is not None else None,
        "extension": round(lenses["extension"], 3),
        "gap_pct": round(lenses["gap_pct"], 3),
        "rel_strength_spy": round(lenses["rel_strength_spy"], 4),
        "rel_strength_sector": round(lenses["rel_strength_sector"], 4),
        "trend_score": round(lenses["trend_score"], 2),
        "momentum_score": round(lenses["momentum_score"], 2),
        "rel_strength_score": round(lenses["rel_strength_score"], 2),
        "volume_score": round(lenses["volume_score"], 2),
        "fundamentals_score": round(lenses["fundamentals_score"], 2),
        "regime": regime,
        "earnings_within_5d": earnings_within_5d,
        "signals": sanitize_nans(horizons),
        "engine_version": "v1",
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def run(supabase_client, tickers: list[str]) -> dict:
    regime, spy_close = _load_regime(supabase_client)
    sector_close_cache: dict[str, pd.Series] = {}
    written = 0

    for ticker in tickers:
        try:
            hist = load_price_history_df(supabase_client, ticker, lookback_days=250)
            if hist.empty:
                continue

            universe_row = (
                supabase_client.table("market_universe").select("sector,pe,margins,rev_growth")
                .eq("ticker", ticker).limit(1).execute()
            )
            info = universe_row.data[0] if universe_row.data else {}
            sector = info.get("sector") or DEFAULT_SECTOR_ETF
            etf = SECTOR_ETF_MAP.get(sector, DEFAULT_SECTOR_ETF)
            if etf not in sector_close_cache:
                sector_close_cache[etf] = load_price_history_df(supabase_client, etf, lookback_days=250)["Close"]

            fscore = indicators.fundamentals_score(
                pe=safe_float(info.get("pe", 0)),
                margins=safe_float(info.get("margins", 0)),
                rev_growth=safe_float(info.get("rev_growth", 0)),
            )
            earnings_soon = has_earnings_within_5d(ticker)

            row = compute_ticker_metrics(ticker, hist, spy_close, sector_close_cache[etf], fscore, earnings_soon, regime)
            if row is None:
                continue

            supabase_client.table("daily_metrics").upsert(row, on_conflict="ticker,d").execute()
            written += 1
        except Exception as e:
            print(f"[compute_daily_metrics] failed for {ticker}: {e}", file=sys.stderr)

    return {"tickers_processed": len(tickers), "written": written, "regime": regime}


def _load_universe_tickers(supabase_client) -> list[str]:
    response = supabase_client.table("market_universe").select("ticker").execute()
    return sorted({row["ticker"] for row in response.data})


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)
    all_tickers = _load_universe_tickers(client)
    print(f"[compute_daily_metrics] processing {len(all_tickers)} tickers", file=sys.stderr)
    summary = run(client, all_tickers)
    print(f"[compute_daily_metrics] done: {summary}", file=sys.stderr)
