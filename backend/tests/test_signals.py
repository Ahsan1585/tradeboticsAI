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
