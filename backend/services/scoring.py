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


def consensus(
    trend: float, momentum: float, rel_strength: float, volume: float, fundamentals: float,
    smart_money: float | None = None,
) -> dict:
    """Multi-lens agreement view: how many of the independent lenses agree
    on direction. Powers the plain-language 'X of 5 signals agree'.
    smart_money (Phase 2b) is an optional 6th lens -- omitted entirely when
    not supplied, so Phase 2a callers see no change in shape."""
    lenses = {
        "trend": trend,
        "momentum": momentum,
        "rel_strength": rel_strength,
        "volume": volume,
        "fundamentals": fundamentals,
    }
    if smart_money is not None:
        lenses["smart_money"] = smart_money
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


_SMART_MONEY_MAX_NUDGE = 5.0  # points; keeps the 5-weight composite dominant


def confidence_score(
    trend: float, momentum: float, rel_strength: float, volume: float, fundamentals: float, regime: str,
    smart_money: float | None = None,
) -> float:
    """Composite score with the regime multiplier applied, clamped 0-100.
    Risk-off regimes dampen confidence so BUY becomes structurally harder
    to reach, without special-casing the verdict logic itself.
    smart_money (Phase 2b) is an optional small bounded nudge (+/-5 points
    at the extremes) -- informational, not a rework of the approved
    5-weight composite. Omitted entirely, confidence is unchanged from
    Phase 2a's behavior."""
    score = composite_score(trend, momentum, rel_strength, volume, fundamentals)
    if regime == "risk_off":
        score *= _RISK_OFF_MULTIPLIER
    if smart_money is not None:
        score += (smart_money - 50.0) / 50.0 * _SMART_MONEY_MAX_NUDGE
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


_FUND_SIGNAL_WEIGHT = 8.0


def smart_money_score(fund_signals: list[str], insider_net_buy_usd: float) -> float:
    """0-100 lens from Phase 2b's smart-money layer. fund_signals: the
    change_type ('new'/'increased'/'decreased'/'unchanged'/'exited') of
    each tracked hedge fund currently or previously holding this ticker.
    insider_net_buy_usd: aggregate dollar value of open-market insider
    purchases minus sales in the trailing window. Insider selling is
    weighted less than buying -- executives sell for many reasons unrelated
    to conviction (taxes, diversification), but voluntarily buying on the
    open market is a strong, low-noise signal."""
    score = 50.0
    bullish_funds = sum(1 for s in fund_signals if s in ("new", "increased"))
    bearish_funds = sum(1 for s in fund_signals if s in ("decreased", "exited"))
    score += bullish_funds * _FUND_SIGNAL_WEIGHT
    score -= bearish_funds * _FUND_SIGNAL_WEIGHT

    if insider_net_buy_usd > 0:
        score += 10.0
    elif insider_net_buy_usd < 0:
        score -= 5.0

    return max(0.0, min(100.0, score))


def exit_plan(entry_price: float, atr: float) -> dict:
    """Mandatory ATR-based exit plan shipped with every BUY: a stop below
    entry and a target above it, sized for roughly a 2:1 reward-to-risk
    ratio (target ATR multiple is double the stop's)."""
    return {
        "entry": entry_price,
        "stop": entry_price - _STOP_ATR_MULT * atr,
        "target": entry_price + _TARGET_ATR_MULT * atr,
    }
