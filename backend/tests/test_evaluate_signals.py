"""Unit tests for the signal-evaluation job (Phase 3): forward returns and
trade_outcome resolution. No look-ahead bias -- outcomes are only resolved
by walking forward through price_history rows strictly after the signal date.
"""
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from jobs.evaluate_signals import compute_signal_evaluation, run


def _hist_after(closes, highs=None, lows=None, start="2026-07-06"):
    idx = pd.date_range(start, periods=len(closes), freq="B")
    highs = highs or [c + 1 for c in closes]
    lows = lows or [c - 1 for c in closes]
    return pd.DataFrame({"Open": closes, "High": highs, "Low": lows, "Close": closes}, index=idx)


# --- compute_signal_evaluation: forward returns -------------------------------

def test_forward_returns_computed_when_enough_history():
    hist_after = _hist_after([102.0, 104.0, 106.0])
    spy_after = _hist_after([101.0, 101.5, 102.0])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="HOLD", stop=None, target=None, max_holding_days=20,
    )
    assert result["ret_1d"] == pytest.approx(0.02)
    assert result["spy_ret_1d"] == pytest.approx(0.01)


def test_forward_returns_none_when_not_enough_history_yet():
    hist_after = _hist_after([102.0])  # only 1 day elapsed
    spy_after = _hist_after([101.0])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="HOLD", stop=None, target=None, max_holding_days=20,
    )
    assert result["ret_1d"] is not None
    assert result["ret_5d"] is None  # only 1 trading day of history so far


# --- compute_signal_evaluation: trade_outcome resolution (BUY only) ----------

def test_non_buy_verdict_has_no_trade_outcome():
    hist_after = _hist_after([102.0, 104.0])
    spy_after = _hist_after([101.0, 101.5])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="HOLD", stop=None, target=None, max_holding_days=20,
    )
    assert result["trade_outcome"] is None


def test_buy_resolves_target_hit_on_first_qualifying_day():
    # target=110; day0 high=105 (miss), day1 high=112 (hit)
    hist_after = _hist_after(closes=[103, 108], highs=[105, 112], lows=[99, 104])
    spy_after = _hist_after([101.0, 101.5])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="BUY", stop=90.0, target=110.0, max_holding_days=20,
    )
    assert result["trade_outcome"] == "target_hit"
    assert result["outcome_date"] == "2026-07-07"  # second business day


def test_buy_resolves_stopped_on_first_qualifying_day():
    # stop=90; day0 low=95 (miss), day1 low=85 (hit)
    hist_after = _hist_after(closes=[92, 87], highs=[96, 90], lows=[95, 85])
    spy_after = _hist_after([101.0, 99.5])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="BUY", stop=90.0, target=120.0, max_holding_days=20,
    )
    assert result["trade_outcome"] == "stopped"
    assert result["outcome_date"] == "2026-07-07"


def test_buy_same_day_stop_and_target_conservatively_resolves_stopped():
    # Ambiguous: both stop and target touched same day -- can't know intraday
    # order from daily bars, so the conservative assumption is 'stopped'.
    hist_after = _hist_after(closes=[105], highs=[115], lows=[85])
    spy_after = _hist_after([101.0])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="BUY", stop=90.0, target=110.0, max_holding_days=20,
    )
    assert result["trade_outcome"] == "stopped"


def test_buy_time_exit_when_max_holding_days_elapse_with_no_hit():
    closes = [101] * 20  # never touches stop(80) or target(150)
    hist_after = _hist_after(closes=closes, highs=[c + 1 for c in closes], lows=[c - 1 for c in closes])
    spy_after = _hist_after([101.0] * 20)
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="BUY", stop=80.0, target=150.0, max_holding_days=5,
    )
    assert result["trade_outcome"] == "time_exit"


def test_buy_stays_open_when_not_enough_days_elapsed_yet():
    hist_after = _hist_after(closes=[101, 102], highs=[102, 103], lows=[100, 101])
    spy_after = _hist_after([101.0, 101.2])
    result = compute_signal_evaluation(
        entry_price=100.0, spy_entry_price=100.0, hist_after=hist_after, spy_after=spy_after,
        verdict="BUY", stop=80.0, target=150.0, max_holding_days=20,
    )
    assert result["trade_outcome"] == "open"


def test_buy_already_resolved_outcome_does_not_get_overwritten_to_open():
    """Once a signal resolves (target_hit/stopped/time_exit), later re-runs
    of the job must not flip it back to 'open' just because we happened to
    slice hist_after starting further out; run() should skip already-
    resolved rows entirely (tested at the run() level below)."""
    pass


# --- run() orchestration -------------------------------------------------------

def _fake_hist(closes, start):
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame(
        {"Open": closes, "High": [c + 1 for c in closes], "Low": [c - 1 for c in closes], "Close": closes},
        index=idx,
    )


def test_run_skips_already_resolved_signals():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.gte.return_value.execute.return_value.data = [
        {"id": 1, "ticker": "AAPL", "horizon": "swing", "verdict": "BUY", "d": "2026-06-01",
         "price_at_signal": 100.0, "stop_price": 90.0, "target_price": 120.0, "trade_outcome": "target_hit"},
    ]

    with patch("jobs.evaluate_signals.load_price_history_df") as mock_load:
        result = run(mock_client)

    mock_load.assert_not_called()
    assert result["skipped_resolved"] == 1
    assert result["evaluated"] == 0


def test_run_evaluates_open_signal_and_upserts_update():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.gte.return_value.execute.return_value.data = [
        {"id": 42, "ticker": "AAPL", "horizon": "swing", "verdict": "BUY", "d": "2026-07-01",
         "price_at_signal": 100.0, "stop_price": 90.0, "target_price": 200.0, "trade_outcome": "open"},
    ]

    def fake_load(client, ticker, lookback_days=250):
        if ticker == "SPY":
            return _fake_hist([100, 101, 101.5, 102], start="2026-06-29")
        return _fake_hist([100, 103, 104, 106], start="2026-06-29")

    with patch("jobs.evaluate_signals.load_price_history_df", side_effect=fake_load):
        result = run(mock_client)

    assert result["evaluated"] == 1
    update_call = mock_client.table.return_value.update.call_args
    assert update_call is not None
    updated_fields = update_call[0][0]
    assert updated_fields["ret_1d"] is not None
