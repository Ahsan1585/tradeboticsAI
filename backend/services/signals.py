"""Signal policy layer (Phase 2a): ties the deterministic scoring engine to
the three labeled horizon tracks and defensive-mode framing.

Three horizon tracks (approved plan), each with its own promise and its own
public track record:
  - day: pre-market setups from last night's EOD data
  - swing: 5-20 day signals, the headline track-record metric
  - longterm: 3-12 month positioning

Every BUY ships a mandatory ATR-based exit plan (services.scoring.exit_plan).
Defensive mode triggers when the market is risk-off AND breadth is weak —
the screener should show watchlist candidates, not BUYs, with explicit
cash-is-a-position messaging.
"""
from services import scoring

HORIZON_LOOKBACKS = {
    "day": 5,
    "swing": 20,
    "longterm": 60,
}

_DEFENSIVE_BREADTH_THRESHOLD = 40.0


def build_signal(
    ticker: str,
    horizon: str,
    trend: float,
    momentum: float,
    rel_strength: float,
    volume: float,
    fundamentals: float,
    regime: str,
    extension: float,
    gap_pct: float,
    earnings_within_5d: bool,
    price: float,
    atr: float,
    smart_money: float | None = None,
) -> dict:
    """Assembles the full signal record for one ticker/horizon: confidence,
    verdict, plain-language reason, consensus view, and (for BUYs only) a
    mandatory ATR-based exit plan. smart_money (Phase 2b) is an optional
    6th consensus lens plus a small bounded confidence nudge -- omitted
    entirely when not supplied."""
    if horizon not in HORIZON_LOOKBACKS:
        raise ValueError(f"Unknown horizon '{horizon}'; expected one of {list(HORIZON_LOOKBACKS)}")

    confidence = scoring.confidence_score(trend, momentum, rel_strength, volume, fundamentals, regime, smart_money)
    signal_verdict, reason = scoring.verdict(confidence, extension, gap_pct, regime, earnings_within_5d)

    result = {
        "ticker": ticker,
        "horizon": horizon,
        "confidence": confidence,
        "verdict": signal_verdict,
        "reason": reason,
        "consensus": scoring.consensus(trend, momentum, rel_strength, volume, fundamentals, smart_money),
    }

    if signal_verdict == "BUY":
        result["exit_plan"] = scoring.exit_plan(price, atr)

    return result


def signal_log_row(
    signal: dict, price: float, d: str, inputs_snapshot: dict,
    engine_version: str = "v1", source: str = "nightly",
) -> dict:
    """Shapes a build_signal() result into a row for the Phase 3 `signals`
    log table (public track record). stop/target are only populated for
    BUY verdicts -- the mandatory exit plan only exists on BUYs."""
    exit_plan = signal.get("exit_plan")
    return {
        "ticker": signal["ticker"],
        "horizon": signal["horizon"],
        "verdict": signal["verdict"],
        "confidence": signal["confidence"],
        "price_at_signal": price,
        "stop_price": exit_plan["stop"] if exit_plan else None,
        "target_price": exit_plan["target"] if exit_plan else None,
        "inputs": inputs_snapshot,
        "engine_version": engine_version,
        "source": source,
        "d": d,
    }


def is_defensive_mode(regime: str, breadth_pct: float) -> bool:
    """True when the market is risk-off AND breadth is weak — the screener
    should suppress new BUYs and show watchlist candidates instead."""
    return regime == "risk_off" and breadth_pct < _DEFENSIVE_BREADTH_THRESHOLD


def defensive_mode_message() -> str:
    """Explicit cash-is-a-position messaging shown in place of BUY signals
    during defensive mode."""
    return (
        "Markets are in a defensive posture right now — cash is a position. "
        "No new BUY signals today; below are watchlist candidates for when the trend turns."
    )
