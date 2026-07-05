"""Honest technical indicators (Phase 2a).

Manual pandas/numpy implementations — no pandas-ta (unmaintained, numpy 2.x
breakage). Each indicator is small, standard, and unit-tested against known
values. Inputs are the OHLCV columns produced by
services.market_data.load_price_history_df (ascending DatetimeIndex).

Rolling transforms return a full pandas Series (NaN until the window fills) so
callers can inspect slope/history; scalar reductions return a float.
"""
import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average. NaN until `window` observations are available."""
    return close.rolling(window=window).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index.

    Seeds the first average gain/loss with a simple mean over `period`, then
    applies Wilder smoothing: avg = (prev*(period-1) + current) / period.
    Returns 100 when there are no losses in the window.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = np.full(len(close), np.nan)
    avg_loss = np.full(len(close), np.nan)

    if len(close) <= period:
        return pd.Series(avg_gain, index=close.index)

    # First average = simple mean of the first `period` deltas (indices 1..period).
    avg_gain[period] = gain.iloc[1:period + 1].mean()
    avg_loss[period] = loss.iloc[1:period + 1].mean()

    g = gain.to_numpy()
    l = loss.to_numpy()
    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + g[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + l[i]) / period

    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.inf), where=avg_loss != 0)
    result = 100.0 - (100.0 / (1.0 + rs))
    return pd.Series(result, index=close.index)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence.

    Uses the conventional recursive EMA (adjust=False). Returns
    (macd_line, signal_line, histogram) where histogram = line - signal.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def slope(series: pd.Series, lookback: int) -> float:
    """Change in a series over the last `lookback` steps (latest - value
    `lookback` bars ago). Positive means rising. Used for SMA-slope regime
    checks and MACD-histogram momentum."""
    s = series.dropna()
    if len(s) <= lookback:
        return float("nan")
    return float(s.iloc[-1] - s.iloc[-1 - lookback])


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing).

    True range = max(high-low, |high-prev_close|, |low-prev_close|).
    First `period` bar has no prior close, so its TR is just high-low. The
    Wilder average is seeded as a simple mean of the first `period` true
    ranges, then smoothed the same way as Wilder's RSI.
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    tr.iloc[0] = (high.iloc[0] - low.iloc[0])

    result = np.full(len(close), np.nan)
    if len(close) < period:
        return pd.Series(result, index=close.index)

    result[period - 1] = tr.iloc[0:period].mean()
    tr_vals = tr.to_numpy()
    for i in range(period, len(close)):
        result[i] = (result[i - 1] * (period - 1) + tr_vals[i]) / period

    return pd.Series(result, index=close.index)


def bb_width(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.Series:
    """Bollinger Band width as a fraction of the middle band:
    (upper - lower) / sma. Zero for a perfectly flat series."""
    mid = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return (upper - lower) / mid


def relative_strength(stock: pd.Series, benchmark: pd.Series, lookback: int) -> float:
    """Difference in trailing `lookback`-bar returns: stock return minus
    benchmark return. Positive means the stock outperformed."""
    stock_ret = stock.iloc[-1] / stock.iloc[-1 - lookback] - 1.0
    bench_ret = benchmark.iloc[-1] / benchmark.iloc[-1 - lookback] - 1.0
    return float(stock_ret - bench_ret)


def extension(close: float, sma20: float, atr: float) -> float:
    """How many ATRs the price sits above (positive) or below (negative)
    its 20-SMA. Used to downgrade overextended BUYs to WAIT-FOR-PULLBACK."""
    if atr == 0:
        return 0.0
    return (close - sma20) / atr


def gap_percent(open_price: float, prev_close: float) -> float:
    """Percent gap between today's open and yesterday's close."""
    if prev_close == 0:
        return 0.0
    return (open_price - prev_close) / prev_close * 100.0


def market_regime(close: float, sma200: float, sma20_slope: float) -> str:
    """Risk-on only when price is above the 200-SMA AND the 20-SMA is
    rising; otherwise risk-off. Caps all signals at HOLD/WAIT when risk-off."""
    if close > sma200 and sma20_slope > 0:
        return "risk_on"
    return "risk_off"


def breadth_pct(above_sma_flags: list[bool]) -> float:
    """Percent of a universe trading above its own 50-SMA. Empty input -> 0."""
    if not above_sma_flags:
        return 0.0
    return sum(above_sma_flags) / len(above_sma_flags) * 100.0


def fundamentals_score(pe: float, margins: float, rev_growth: float) -> float:
    """0-100 fundamentals lens from real reported figures (P/E, profit
    margin, revenue growth) — unlike the deleted technical proxies, these
    are genuine fundamentals data, just simply weighted."""
    score = 50.0

    if pe > 0 and pe < 25:
        score += 20
    elif pe >= 25:
        score -= 10
    elif pe <= 0:
        score -= 10  # unprofitable or negative earnings

    if margins > 0.15:
        score += 20
    elif margins < 0:
        score -= 25

    if rev_growth > 0.20:
        score += 10
    elif rev_growth < 0:
        score -= 15

    return max(0.0, min(100.0, score))
