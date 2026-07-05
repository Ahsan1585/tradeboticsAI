"""Unit tests for the public track-record aggregation (Phase 3)."""
import pytest

from services.track_record import compute_track_record


def _buy_row(horizon="swing", trade_outcome="target_hit", ret_20d=0.05, spy_ret_20d=0.02,
             engine_version="v1", d="2026-06-01", ticker="AAPL"):
    return {
        "ticker": ticker, "horizon": horizon, "verdict": "BUY", "trade_outcome": trade_outcome,
        "engine_version": engine_version, "d": d,
        "ret_5d": 0.01, "ret_20d": ret_20d, "ret_60d": 0.08,
        "spy_ret_5d": 0.005, "spy_ret_20d": spy_ret_20d, "spy_ret_60d": 0.03,
    }


def test_ignores_non_buy_signals():
    rows = [{"ticker": "AAPL", "horizon": "swing", "verdict": "HOLD", "trade_outcome": None, "d": "2026-06-01"}]
    result = compute_track_record(rows)
    assert result["tracks"] == []


def test_ignores_unresolved_open_trades():
    rows = [_buy_row(trade_outcome="open")]
    result = compute_track_record(rows)
    assert result["tracks"] == []


def test_hit_rate_counts_target_hit_as_win_and_stopped_as_loss():
    rows = [
        _buy_row(trade_outcome="target_hit", ticker="AAPL"),
        _buy_row(trade_outcome="target_hit", ticker="MSFT"),
        _buy_row(trade_outcome="stopped", ticker="GOOGL"),
    ]
    result = compute_track_record(rows)
    track = result["tracks"][0]
    assert track["horizon"] == "swing"
    assert track["total_resolved"] == 3
    assert track["wins"] == 2
    assert track["losses"] == 1
    assert track["hit_rate"] == pytest.approx(66.7, abs=0.1)


def test_time_exit_win_determined_by_matching_horizon_return_sign():
    # swing's max-holding-days return field is ret_20d
    winning_time_exit = _buy_row(trade_outcome="time_exit", ret_20d=0.03, ticker="AAPL")
    losing_time_exit = _buy_row(trade_outcome="time_exit", ret_20d=-0.02, ticker="MSFT")
    result = compute_track_record([winning_time_exit, losing_time_exit])
    track = result["tracks"][0]
    assert track["wins"] == 1
    assert track["losses"] == 1


def test_avg_excess_return_vs_spy():
    rows = [
        _buy_row(ret_20d=0.10, spy_ret_20d=0.02, ticker="AAPL"),   # +8% excess
        _buy_row(ret_20d=0.00, spy_ret_20d=0.02, ticker="MSFT"),   # -2% excess
    ]
    result = compute_track_record(rows)
    track = result["tracks"][0]
    assert track["avg_excess_return_pct"] == pytest.approx(3.0, abs=0.01)  # avg(8, -2) = 3


def test_separate_tracks_per_horizon_and_engine_version():
    rows = [
        _buy_row(horizon="swing", engine_version="v1", ticker="AAPL"),
        _buy_row(horizon="longterm", engine_version="v1", ticker="MSFT"),
        _buy_row(horizon="swing", engine_version="v2", ticker="GOOGL"),
    ]
    result = compute_track_record(rows)
    keys = {(t["horizon"], t["engine_version"]) for t in result["tracks"]}
    assert keys == {("swing", "v1"), ("longterm", "v1"), ("swing", "v2")}


def test_swing_equity_curve_compounds_chronologically():
    rows = [
        _buy_row(horizon="swing", ret_20d=0.10, d="2026-06-01", ticker="AAPL"),
        _buy_row(horizon="swing", ret_20d=0.05, d="2026-06-15", ticker="MSFT"),
    ]
    result = compute_track_record(rows)
    curve = result["swing_equity_curve"]
    assert len(curve) == 2
    assert curve[0]["date"] == "2026-06-01"
    assert curve[0]["cumulative_return_multiple"] == pytest.approx(1.10)
    assert curve[1]["cumulative_return_multiple"] == pytest.approx(1.10 * 1.05)


def test_equity_curve_excludes_non_swing_and_non_buy():
    rows = [
        _buy_row(horizon="longterm", ret_20d=0.50, ticker="AAPL"),
        {"ticker": "MSFT", "horizon": "swing", "verdict": "HOLD", "trade_outcome": None, "d": "2026-06-01"},
    ]
    result = compute_track_record(rows)
    assert result["swing_equity_curve"] == []
