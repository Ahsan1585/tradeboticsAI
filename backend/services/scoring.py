"""Deterministic signal-scoring engine (Phase 2a).

Anti-hallucination guarantee: every number and verdict here is produced by
transparent rules. The LLM (llm.py) only narrates a fixed verdict and the
supplied numbers — it never invents a signal.

Weights (approved plan): trend 30 / momentum 20 / rel-strength 20 /
volume 15 / fundamentals 15. Extension and gap act as penalties (they gate
the verdict, not the underlying score); regime acts as a confidence
multiplier; earnings proximity is a hard veto.
"""

_WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.20,
    "rel_strength": 0.20,
    "volume": 0.15,
    "fundamentals": 0.15,
}

_RISK_OFF_MULTIPLIER = 0.6

_BUY_THRESHOLD = 70.0
_AVOID_THRESHOLD = 30.0

_EXTENSION_LIMIT = 2.0
_GAP_LIMIT_PCT = 3.5

_STOP_ATR_MULT = 1.5
_TARGET_ATR_MULT = 3.0


def lens_signal(score: float, bullish_threshold: float = 60.0, bearish_threshold: float = 40.0) -> str:
    """Classifies a single 0-100 lens score as bullish/neutral/bearish."""
    if score >= bullish_threshold:
        return "bullish"
    if score <= bearish_threshold:
        return "bearish"
    return "neutral"


def composite_score(trend: float, momentum: float, rel_strength: float, volume: float, fundamentals: float) -> float:
    """Weighted composite of the five 0-100 lens scores."""
    return (
        trend * _WEIGHTS["trend"]
        + momentum * _WEIGHTS["momentum"]
        + rel_strength * _WEIGHTS["rel_strength"]
        + volume * _WEIGHTS["volume"]
        + fundamentals * _WEIGHTS["fundamentals"]
    )


def consensus(trend: float, momentum: float, rel_strength: float, volume: float, fundamentals: float) -> dict:
    """Multi-lens agreement view: how many of the five independent lenses
    agree on direction. Powers the plain-language 'X of 5 signals agree'."""
    lenses = {
        "trend": trend,
        "momentum": momentum,
        "rel_strength": rel_strength,
        "volume": volume,
        "fundamentals": fundamentals,
    }
    classified = {name: lens_signal(score) for name, score in lenses.items()}
    bullish = sum(1 for v in classified.values() if v == "bullish")
    bearish = sum(1 for v in classified.values() if v == "bearish")
    neutral = len(classified) - bullish - bearish
    return {
        "lenses": classified,
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "total": len(classified),
    }


def confidence_score(
    trend: float, momentum: float, rel_strength: float, volume: float, fundamentals: float, regime: str
) -> float:
    """Composite score with the regime multiplier applied, clamped 0-100.
    Risk-off regimes dampen confidence so BUY becomes structurally harder
    to reach, without special-casing the verdict logic itself."""
    score = composite_score(trend, momentum, rel_strength, volume, fundamentals)
    if regime == "risk_off":
        score *= _RISK_OFF_MULTIPLIER
    return max(0.0, min(100.0, score))


def verdict(confidence: float, extension: float, gap_pct: float, regime: str, earnings_within_5d: bool) -> tuple[str, str]:
    """Deterministic verdict gates, checked in priority order (hardest
    constraint first). Returns (verdict, plain-language reason).

    BUY only reachable when every independent gate aligns: no earnings
    veto, risk-on regime, not overextended, no chase-risk gap, and
    confidence clears the BUY threshold.
    """
    if earnings_within_5d:
        return "WAIT", "Earnings report is within 5 trading days — no actionable signal until after the print."

    if regime == "risk_off":
        return "WAIT", "Market regime is risk-off (SPY below its 200-day average or losing momentum) — no new BUYs."

    if extension > _EXTENSION_LIMIT:
        return "WAIT", f"Price is extended more than {_EXTENSION_LIMIT} ATR above its 20-day average — wait for a pullback."

    if gap_pct > _GAP_LIMIT_PCT:
        return "WAIT", f"Gapped up more than {_GAP_LIMIT_PCT}% — chasing here carries elevated risk."

    if confidence >= _BUY_THRESHOLD:
        return "BUY", "Trend, momentum, and relative strength all align with a supportive market regime."

    if confidence <= _AVOID_THRESHOLD:
        return "AVOID", "Multiple signals point negative — this does not look like a good entry."

    return "HOLD", "Signals are mixed — no strong edge in either direction right now."


def exit_plan(entry_price: float, atr: float) -> dict:
    """Mandatory ATR-based exit plan shipped with every BUY: a stop below
    entry and a target above it, sized for roughly a 2:1 reward-to-risk
    ratio (target ATR multiple is double the stop's)."""
    return {
        "entry": entry_price,
        "stop": entry_price - _STOP_ATR_MULT * atr,
        "target": entry_price + _TARGET_ATR_MULT * atr,
    }
