"""Quant scoring math, relocated from main.py. Phase 1 does not change the
formulas here — Phase 2 replaces this module with honest indicators."""
import math
from scipy.signal import argrelextrema
import numpy as np


def safe_float(val, default=0.0):
    """Safely converts potential NaNs, None, or strings into a clean Python float."""
    try:
        if val is None:
            return default
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return default
        return f_val
    except Exception:
        return default


def sanitize_nans(obj):
    """Recursively strips out any remaining NaNs or Infinities before JSON serialization."""
    if isinstance(obj, float) or type(obj).__module__ == 'numpy':
        try:
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return 0.0
            return val
        except Exception:
            return 0.0
    elif isinstance(obj, dict):
        return {k: sanitize_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nans(i) for i in obj]
    return obj


def calculate_quant_metrics(hist, info, stock_obj, current_price, prev_price, ticker="Asset"):
    """
    The 12-Cylinder Engine (Restored Verbose Version).
    Ensures full parity with original logic while returning exactly 13 values.
    """
    tech_base = 50
    fund_base = 50
    alpha_bonus = 0
    extra_ledger = []

    # 🧹 CLEAN DATA
    clean_close = hist['Close'].dropna()
    valid_hist = hist.dropna(subset=['High', 'Low', 'Close', 'Volume'])

    sector = info.get("sector", "Macro Profile")
    pe = safe_float(info.get("trailingPE", 0))
    margins = safe_float(info.get("profitMargins", 0))
    rev_growth = safe_float(info.get("revenueGrowth", 0))
    fcf = safe_float(info.get("freeCashflow", 0))
    short_interest = safe_float(info.get("shortPercentOfFloat", 0))
    insider_hold = safe_float(info.get("heldPercentInsiders", 0))

    # --- DETAILED TECHNICAL ENGINE ---
    # SMA & BB Logic
    if len(clean_close) >= 20:
        sma_20 = safe_float(clean_close.rolling(window=20).mean().iloc[-1])
        std_dev = safe_float(clean_close.rolling(window=20).std().iloc[-1])
        upper_band = round(sma_20 + (2 * std_dev), 2)
        lower_band = round(sma_20 - (2 * std_dev), 2)

        # Verbose Trending logic
        if current_price > sma_20: tech_base += 15
        else: tech_base -= 15

        # Band Deviation Logic
        if current_price > upper_band: tech_base -= 10
        elif current_price < lower_band: tech_base += 10

        # Squeeze Logic
        bb_width = (upper_band - lower_band) / sma_20 if sma_20 > 0 else 1
        if bb_width < 0.05:
            alpha_bonus += 5
            extra_ledger.append({"factor": "Consolidation", "val": "Tight", "status": "BULLISH", "reasoning": "Volatility compression."})
    else:
        sma_20 = current_price
        upper_band, lower_band = round(current_price * 1.05, 2), round(current_price * 0.95, 2)

    # Detailed Momentum (RSI)
    try:
        delta = clean_close.diff()
        gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rs = gain / loss
        real_rsi = round(100 - (100 / (1 + rs.iloc[-1])), 2)
    except: real_rsi = 50.0

    if real_rsi >= 70: tech_base -= 15
    elif real_rsi <= 30: tech_base += 15
    elif 50 < real_rsi < 65: tech_base += 5

    # Detailed Volume/VWAP logic
    volume = safe_float(valid_hist['Volume'].iloc[-1])
    avg_volume = safe_float(valid_hist['Volume'].rolling(20).mean().iloc[-1])
    if avg_volume > 0 and volume > (avg_volume * 1.2): tech_base += 10
    else: tech_base -= 5

    typical_price = (valid_hist['High'] + valid_hist['Low'] + valid_hist['Close']) / 3
    vwap_proxy = round(safe_float((typical_price * valid_hist['Volume']).sum() / valid_hist['Volume'].sum(), current_price), 2)
    if current_price > vwap_proxy: tech_base += 10
    else: tech_base -= 10

    # --- RESTORED FUNDAMENTAL ENGINE ---
    is_tech = "Technology" in sector or "Communication" in sector
    is_financial = "Financial" in sector

    # PE/Margins/Growth Logic (Verbose)
    if pe > 0 and pe < 25: fund_base += 20
    elif pe >= 25 and pe <= 50 and is_tech: fund_base += 10
    elif pe > 50: fund_base -= 20

    if margins > 0.15: fund_base += 20
    elif margins < 0: fund_base -= 25

    if rev_growth > 0.20: fund_base += 10
    elif rev_growth < 0: fund_base -= 15

    if fcf > 0: fund_base += 5
    elif fcf < 0: fund_base -= 5

    # --- RESTORED ALPHA MULTIPLIERS ---
    if short_interest > 0.15:
        alpha_bonus += 5
        extra_ledger.append({"factor": "Short Interest", "val": f"{round(short_interest*100, 1)}%", "status": "VOLATILE", "reasoning": "High squeeze potential."})

    try:
        opt_dates = stock_obj.options
        if opt_dates:
            chain = stock_obj.option_chain(opt_dates[0])
            calls_vol = chain.calls['volume'].sum()
            puts_vol = chain.puts['volume'].sum()
            if calls_vol > 0:
                pcr = puts_vol / calls_vol
                if pcr < 0.6: alpha_bonus += 5
                elif pcr > 1.5: alpha_bonus -= 20
    except: pass

    total_score = max(10, min(99, math.ceil((tech_base + fund_base) / 2) + alpha_bonus))

    # EXACTLY 13 RETURNS
    return (
        total_score, int(tech_base), int(fund_base), extra_ledger, real_rsi,
        volume, avg_volume, vwap_proxy, upper_band, lower_band,
        sector, pe, margins
    )


def get_support_resistance(hist):
    if len(hist) < 30:
        return float(hist['Low'].min()), float(hist['High'].max())

    prices = hist['Close'].values
    order = 5
    maxima = argrelextrema(prices, np.greater, order=order)[0]
    minima = argrelextrema(prices, np.less, order=order)[0]

    res_levels = prices[maxima][-3:] if len(maxima) > 0 else [prices[-1]]
    sup_levels = prices[minima][-3:] if len(minima) > 0 else [prices[-1]]

    return float(np.mean(sup_levels)), float(np.mean(res_levels))
