"""Unit tests for honest technical indicators (Phase 2a).

Each indicator is checked against hand-computed known values. Inputs mirror the
OHLCV DataFrame shape produced by services.market_data.load_price_history_df:
columns Open/High/Low/Close/Volume, ascending DatetimeIndex.
"""
import numpy as np
import pandas as pd
import pytest

from services import indicators


def _series(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype="float64")


# --- SMA ---------------------------------------------------------------------

def test_sma_last_value_matches_hand_calc():
    close = _series([1, 2, 3, 4, 5])
    result = indicators.sma(close, window=3)
    # last 3 = (3+4+5)/3 = 4.0
    assert result.iloc[-1] == pytest.approx(4.0)


def test_sma_is_nan_before_window_filled():
    close = _series([1, 2, 3, 4, 5])
    result = indicators.sma(close, window=3)
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)


# --- RSI (Wilder) ------------------------------------------------------------

def test_rsi_all_gains_approaches_100():
    close = _series(list(range(1, 30)))  # strictly increasing -> no losses
    result = indicators.rsi(close, period=14)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_wilder_matches_reference_vector():
    # Classic Wilder worked example (Kaufman / StockCharts reference series).
    prices = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00,
    ]
    close = _series(prices)
    result = indicators.rsi(close, period=14)
    # Published expected value at the 15th price (~70.46) and 16th (~66.25).
    assert result.iloc[14] == pytest.approx(70.46, abs=0.1)
    assert result.iloc[15] == pytest.approx(66.25, abs=0.1)


# --- MACD --------------------------------------------------------------------

def test_macd_constant_series_is_zero():
    close = _series([50.0] * 60)
    macd_line, signal_line, hist = indicators.macd(close)
    assert macd_line.iloc[-1] == pytest.approx(0.0, abs=1e-9)
    assert signal_line.iloc[-1] == pytest.approx(0.0, abs=1e-9)
    assert hist.iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_macd_uptrend_line_is_positive():
    close = _series([float(x) for x in range(1, 61)])  # steady uptrend
    macd_line, signal_line, hist = indicators.macd(close)
    # Fast EMA sits above slow EMA in an uptrend -> positive MACD line.
    assert macd_line.iloc[-1] > 0


def test_macd_matches_recursive_ema_definition():
    # Verify against the conventional adjust=False recursive-EMA definition.
    close = _series([float(x) for x in [10, 11, 9, 12, 13, 15, 14, 16, 18, 20,
                                        22, 21, 23, 25, 24, 26, 28, 30, 29, 31,
                                        33, 35, 34, 36, 38, 40, 39, 41]])
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    expected_line = ema_fast - ema_slow
    expected_signal = expected_line.ewm(span=9, adjust=False).mean()
    macd_line, signal_line, hist = indicators.macd(close)
    assert macd_line.iloc[-1] == pytest.approx(expected_line.iloc[-1])
    assert signal_line.iloc[-1] == pytest.approx(expected_signal.iloc[-1])
    assert hist.iloc[-1] == pytest.approx((expected_line - expected_signal).iloc[-1])


# --- slope helper ------------------------------------------------------------

def test_slope_positive_for_rising_series():
    s = _series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert indicators.slope(s, lookback=4) > 0


def test_slope_negative_for_falling_series():
    s = _series([5.0, 4.0, 3.0, 2.0, 1.0])
    assert indicators.slope(s, lookback=4) < 0


def test_slope_zero_for_flat_series():
    s = _series([3.0, 3.0, 3.0, 3.0])
    assert indicators.slope(s, lookback=3) == pytest.approx(0.0)


# --- ATR -----------------------------------------------------------------

def _ohlc_df(highs, lows, closes):
    idx = pd.date_range("2024-01-01", periods=len(highs), freq="D")
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes}, index=idx)


def test_atr_hand_calc_simple_case():
    # 3 bars, period=2. True ranges:
    # bar0: no prev close -> TR = H-L = 10-8 = 2
    # bar1: prev close=9 -> TR = max(11-9, |11-9|, |9-9|) = max(2,2,0)=2
    # bar2: prev close=10 -> TR = max(12-10, |12-10|, |10-10|) = max(2,2,0)=2
    df = _ohlc_df(highs=[10, 11, 12], lows=[8, 9, 10], closes=[9, 10, 11])
    result = indicators.atr(df["High"], df["Low"], df["Close"], period=2)
    # Wilder ATR seeded as simple mean of first `period` TRs (bars 0,1) = (2+2)/2=2
    assert result.iloc[1] == pytest.approx(2.0)
    # bar2: (prev_atr*(period-1) + tr)/period = (2*1 + 2)/2 = 2.0
    assert result.iloc[2] == pytest.approx(2.0)


def test_atr_reflects_higher_volatility():
    calm = _ohlc_df(highs=[10]*20, lows=[9]*20, closes=[9.5]*20)
    volatile = _ohlc_df(highs=[10, 15]*10, lows=[9, 5]*10, closes=[9.5, 10]*10)
    calm_atr = indicators.atr(calm["High"], calm["Low"], calm["Close"], period=14).iloc[-1]
    volatile_atr = indicators.atr(volatile["High"], volatile["Low"], volatile["Close"], period=14).iloc[-1]
    assert volatile_atr > calm_atr


# --- Bollinger Band width --------------------------------------------------

def test_bb_width_zero_for_constant_series():
    close = _series([50.0] * 25)
    width = indicators.bb_width(close, window=20, num_std=2)
    assert width.iloc[-1] == pytest.approx(0.0)


def test_bb_width_positive_for_volatile_series():
    values = [50, 55, 45, 52, 48, 51, 49, 53, 47, 50,
              54, 46, 51, 49, 52, 48, 50, 53, 47, 51, 49]
    close = _series([float(v) for v in values])
    width = indicators.bb_width(close, window=20, num_std=2)
    assert width.iloc[-1] > 0


# --- Relative strength ------------------------------------------------------

def test_relative_strength_positive_when_outperforming():
    stock = _series([100.0] * 21)
    stock.iloc[-1] = 120.0  # +20% over the period
    benchmark = _series([100.0] * 21)
    benchmark.iloc[-1] = 105.0  # +5% over the period
    rs = indicators.relative_strength(stock, benchmark, lookback=20)
    assert rs == pytest.approx(0.20 - 0.05, abs=1e-6)


def test_relative_strength_negative_when_underperforming():
    stock = _series([100.0] * 21)
    stock.iloc[-1] = 102.0  # +2%
    benchmark = _series([100.0] * 21)
    benchmark.iloc[-1] = 110.0  # +10%
    rs = indicators.relative_strength(stock, benchmark, lookback=20)
    assert rs < 0


# --- Extension check ---------------------------------------------------------

def test_extension_returns_atr_multiples_above_sma():
    # close 10 above sma20, ATR=5 -> extension = 10/5 = 2.0
    ext = indicators.extension(close=110.0, sma20=100.0, atr=5.0)
    assert ext == pytest.approx(2.0)


def test_extension_negative_when_below_sma():
    ext = indicators.extension(close=90.0, sma20=100.0, atr=5.0)
    assert ext == pytest.approx(-2.0)


def test_extension_zero_atr_does_not_raise():
    ext = indicators.extension(close=110.0, sma20=100.0, atr=0.0)
    assert ext == 0.0


# --- Gap check ---------------------------------------------------------------

def test_gap_percent_hand_calc():
    # open 103.5 vs prior close 100 -> +3.5%
    gap = indicators.gap_percent(open_price=103.5, prev_close=100.0)
    assert gap == pytest.approx(3.5)


def test_gap_percent_negative_gap_down():
    gap = indicators.gap_percent(open_price=96.0, prev_close=100.0)
    assert gap == pytest.approx(-4.0)


# --- Market regime gate -------------------------------------------------------

def test_regime_risk_on_when_above_sma_and_rising():
    close = _series([float(100 + i) for i in range(220)])  # steady uptrend
    sma200 = indicators.sma(close, 200)
    sma20 = indicators.sma(close, 20)
    regime = indicators.market_regime(close.iloc[-1], sma200.iloc[-1], indicators.slope(sma20, lookback=5))
    assert regime == "risk_on"


def test_regime_risk_off_when_below_sma200():
    regime = indicators.market_regime(close=90.0, sma200=100.0, sma20_slope=1.0)
    assert regime == "risk_off"


def test_regime_risk_off_when_sma20_falling():
    regime = indicators.market_regime(close=110.0, sma200=100.0, sma20_slope=-0.5)
    assert regime == "risk_off"


# --- Breadth ------------------------------------------------------------------

def test_breadth_percent_hand_calc():
    above = [True, True, False, True, False]  # 3 of 5 above their 50-SMA
    pct = indicators.breadth_pct(above)
    assert pct == pytest.approx(60.0)


def test_breadth_percent_handles_empty():
    assert indicators.breadth_pct([]) == 0.0


# --- Fundamentals score (0-100 lens for the composite) ------------------------

def test_fundamentals_score_healthy_company_scores_high():
    score = indicators.fundamentals_score(pe=20, margins=0.20, rev_growth=0.15)
    assert score > 60


def test_fundamentals_score_unprofitable_company_scores_low():
    score = indicators.fundamentals_score(pe=0, margins=-0.10, rev_growth=-0.05)
    assert score < 40


def test_fundamentals_score_clamped_0_to_100():
    score = indicators.fundamentals_score(pe=200, margins=-0.9, rev_growth=-0.5)
    assert 0.0 <= score <= 100.0
    score_hi = indicators.fundamentals_score(pe=15, margins=0.5, rev_growth=0.5)
    assert 0.0 <= score_hi <= 100.0
