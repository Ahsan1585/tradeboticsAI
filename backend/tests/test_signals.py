"""Unit tests for the signal policy layer (Phase 2a): horizon tracks,
mandatory exit plans on BUYs, and defensive-mode framing in risk-off markets.
"""
import pytest

from services import signals


# --- horizon lookback config --------------------------------------------------

def test_horizon_lookbacks_defined_for_all_three_tracks():
    assert set(signals.HORIZON_LOOKBACKS.keys()) == {"day", "swing", "longterm"}
    # Longer horizons should use longer relative-strength lookback windows.
    assert signals.HORIZON_LOOKBACKS["day"] < signals.HORIZON_LOOKBACKS["swing"] < signals.HORIZON_LOOKBACKS["longterm"]


# --- build_signal (assembles the full signal record) -------------------------

def _bullish_inputs(**overrides):
    base = dict(
        ticker="AAPL", horizon="swing",
        trend=90, momentum=90, rel_strength=90, volume=90, fundamentals=90,
        regime="risk_on", extension=0.5, gap_pct=1.0, earnings_within_5d=False,
        price=200.0, atr=4.0,
    )
    base.update(overrides)
    return base


def test_build_signal_buy_includes_exit_plan():
    result = signals.build_signal(**_bullish_inputs())
    assert result["verdict"] == "BUY"
    assert "exit_plan" in result
    assert result["exit_plan"]["stop"] < result["exit_plan"]["entry"] < result["exit_plan"]["target"]


def test_build_signal_non_buy_has_no_exit_plan():
    result = signals.build_signal(**_bullish_inputs(regime="risk_off"))
    assert result["verdict"] != "BUY"
    assert "exit_plan" not in result


def test_build_signal_includes_consensus_and_reason():
    result = signals.build_signal(**_bullish_inputs())
    assert "consensus" in result
    assert "reason" in result
    assert result["ticker"] == "AAPL"
    assert result["horizon"] == "swing"


def test_build_signal_rejects_unknown_horizon():
    with pytest.raises(ValueError):
        signals.build_signal(**_bullish_inputs(horizon="intraday"))


def test_build_signal_smart_money_omitted_has_no_sixth_lens():
    result = signals.build_signal(**_bullish_inputs())
    assert "smart_money" not in result["consensus"]["lenses"]


def test_build_signal_smart_money_adds_sixth_lens_and_nudges_confidence():
    without = signals.build_signal(**_bullish_inputs())
    with_sm = signals.build_signal(**_bullish_inputs(smart_money=100))
    assert "smart_money" in with_sm["consensus"]["lenses"]
    assert with_sm["confidence"] >= without["confidence"]


# --- defensive mode ------------------------------------------------------------

def test_is_defensive_mode_true_when_risk_off_and_weak_breadth():
    assert signals.is_defensive_mode(regime="risk_off", breadth_pct=25.0) is True


def test_is_defensive_mode_false_when_risk_on():
    assert signals.is_defensive_mode(regime="risk_on", breadth_pct=25.0) is False


def test_is_defensive_mode_false_when_breadth_healthy_despite_risk_off():
    assert signals.is_defensive_mode(regime="risk_off", breadth_pct=80.0) is False


def test_defensive_mode_message_mentions_cash_as_position():
    msg = signals.defensive_mode_message()
    assert "cash" in msg.lower()


# --- signal_log_row (Phase 3: track-record logging) --------------------------

def test_signal_log_row_buy_includes_stop_and_target():
    signal = signals.build_signal(**_bullish_inputs())
    row = signals.signal_log_row(signal, price=200.0, d="2026-07-05", inputs_snapshot={"rsi14": 55})
    assert row["ticker"] == "AAPL"
    assert row["horizon"] == "swing"
    assert row["verdict"] == "BUY"
    assert row["price_at_signal"] == 200.0
    assert row["stop_price"] == signal["exit_plan"]["stop"]
    assert row["target_price"] == signal["exit_plan"]["target"]
    assert row["d"] == "2026-07-05"
    assert row["inputs"] == {"rsi14": 55}


def test_signal_log_row_non_buy_has_null_stop_and_target():
    signal = signals.build_signal(**_bullish_inputs(regime="risk_off"))
    row = signals.signal_log_row(signal, price=200.0, d="2026-07-05", inputs_snapshot={})
    assert row["verdict"] != "BUY"
    assert row["stop_price"] is None
    assert row["target_price"] is None
