"""Public track-record aggregation (Phase 3): turns resolved BUY signals
from the `signals` log table into the honest, published performance
metrics that replace fake testimonials as the marketing asset.

Only resolved BUY trades count -- HOLD/WAIT/AVOID signals and still-open
BUYs don't have a completed outcome to score. A 'win' is a target_hit, or
a time_exit whose return (at the horizon's own max-holding-period) came in
positive; a 'stopped' trade is always a loss.
"""

_RESOLVED_OUTCOMES = {"target_hit", "stopped", "time_exit"}

# Matches jobs.evaluate_signals._resolve_trade_outcome's max_holding_days,
# which is drawn from services.signals.HORIZON_LOOKBACKS (5/20/60) -- these
# happen to line up exactly with the stored ret_Nd fields.
_HORIZON_EXIT_RETURN_FIELD = {"day": "ret_5d", "swing": "ret_20d", "longterm": "ret_60d"}


def _is_win(row: dict) -> bool:
    outcome = row["trade_outcome"]
    if outcome == "target_hit":
        return True
    if outcome == "stopped":
        return False
    field = _HORIZON_EXIT_RETURN_FIELD.get(row["horizon"], "ret_20d")
    ret = row.get(field)
    return bool(ret is not None and ret > 0)


def compute_track_record(signal_rows: list[dict]) -> dict:
    """Aggregates resolved BUY signals into per-(horizon, engine_version)
    hit rate / avg excess return / win-loss ratio, plus a chronological
    swing-BUY equity curve."""
    resolved_buys = [
        r for r in signal_rows
        if r.get("verdict") == "BUY" and r.get("trade_outcome") in _RESOLVED_OUTCOMES
    ]

    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in resolved_buys:
        key = (row["horizon"], row.get("engine_version", "v1"))
        grouped.setdefault(key, []).append(row)

    tracks = []
    for (horizon, engine_version), rows in grouped.items():
        wins = sum(1 for r in rows if _is_win(r))
        total = len(rows)
        losses = total - wins

        excess_field = _HORIZON_EXIT_RETURN_FIELD.get(horizon, "ret_20d")
        excess_returns = [
            (r.get(excess_field) or 0.0) - (r.get(f"spy_{excess_field}") or 0.0)
            for r in rows if r.get(excess_field) is not None
        ]
        avg_excess_return = sum(excess_returns) / len(excess_returns) if excess_returns else 0.0

        tracks.append({
            "horizon": horizon,
            "engine_version": engine_version,
            "total_resolved": total,
            "wins": wins,
            "losses": losses,
            "hit_rate": round(wins / total * 100, 1) if total else 0.0,
            "avg_excess_return_pct": round(avg_excess_return * 100, 2),
            "win_loss_ratio": round(wins / losses, 2) if losses else float(wins),
        })

    swing_rows = sorted(
        (r for r in resolved_buys if r["horizon"] == "swing"),
        key=lambda r: r["d"],
    )
    equity_curve = []
    cumulative = 1.0
    for r in swing_rows:
        cumulative *= 1 + (r.get("ret_20d") or 0.0)
        equity_curve.append({
            "date": r["d"], "ticker": r["ticker"],
            "cumulative_return_multiple": round(cumulative, 4),
        })

    return {"tracks": tracks, "swing_equity_curve": equity_curve}
