"""Unit tests for the deterministic scoring engine (Phase 2a).

Per the approved plan: rules produce every verdict and number; the LLM only
narrates. This module must be fully deterministic and unit-testable without
any network or LLM calls.
"""
import pytest

from services import scoring


# --- lens_signal (bullish/neutral/bearish classification) -------------------

def test_lens_signal_bullish_above_threshold():
    assert scoring.lens_signal(75) == "bullish"


def test_lens_signal_bearish_below_threshold():
    assert scoring.lens_signal(25) == "bearish"


def test_lens_signal_neutral_in_middle():
    assert scoring.lens_signal(50) == "neutral"


# --- composite_score (weighted average per approved weights) ----------------

def test_composite_score_hand_calc():
    # trend 30 / momentum 20 / rel-strength 20 / volume 15 / fundamentals 15
    result = scoring.composite_score(
        trend=100, momentum=100, rel_strength=100, volume=100, fundamentals=100
    )
    assert result == pytest.approx(100.0)


def test_composite_score_all_zero():
    result = scoring.composite_score(
        trend=0, momentum=0, rel_strength=0, volume=0, fundamentals=0
    )
    assert result == pytest.approx(0.0)


def test_composite_score_weights_trend_highest():
    # Only trend maxed out (weight 0.30) should score higher than only
    # fundamentals maxed out (weight 0.15).
    trend_only = scoring.composite_score(trend=100, momentum=0, rel_strength=0, volume=0, fundamentals=0)
    fundamentals_only = scoring.composite_score(trend=0, momentum=0, rel_strength=0, volume=0, fundamentals=100)
    assert trend_only > fundamentals_only
    assert trend_only == pytest.approx(30.0)
    assert fundamentals_only == pytest.approx(15.0)


# --- consensus (multi-lens agreement view) -----------------------------------

def test_consensus_counts_bullish_lenses():
    result = scoring.consensus(trend=80, momentum=70, rel_strength=20, volume=50, fundamentals=60)
    assert result["bullish"] == 3  # trend, momentum, fundamentals (>=60)
    assert result["bearish"] == 1  # rel_strength
    assert result["neutral"] == 1  # volume
    assert result["total"] == 5


def test_consensus_all_bullish():
    result = scoring.consensus(trend=90, momentum=90, rel_strength=90, volume=90, fundamentals=90)
    assert result["bullish"] == 5
    assert result["bearish"] == 0


# --- confidence_score (composite + regime multiplier, clamped 0-100) --------

def test_confidence_score_risk_on_passes_through():
    conf = scoring.confidence_score(
        trend=100, momentum=100, rel_strength=100, volume=100, fundamentals=100, regime="risk_on"
    )
    assert conf == pytest.approx(100.0)


def test_confidence_score_risk_off_is_dampened():
    conf_on = scoring.confidence_score(
        trend=80, momentum=80, rel_strength=80, volume=80, fundamentals=80, regime="risk_on"
    )
    conf_off = scoring.confidence_score(
        trend=80, momentum=80, rel_strength=80, volume=80, fundamentals=80, regime="risk_off"
    )
    assert conf_off < conf_on


def test_confidence_score_clamped_to_100():
    conf = scoring.confidence_score(
        trend=100, momentum=100, rel_strength=100, volume=100, fundamentals=100, regime="risk_on"
    )
    assert conf <= 100.0


# --- verdict (deterministic gates, priority order) --------------------------

def test_verdict_buy_when_all_gates_align():
    verdict, reason = scoring.verdict(
        confidence=85, extension=0.5, gap_pct=1.0, regime="risk_on", earnings_within_5d=False
    )
    assert verdict == "BUY"


def test_verdict_avoid_when_confidence_very_low():
    verdict, reason = scoring.verdict(
        confidence=15, extension=0.5, gap_pct=1.0, regime="risk_on", earnings_within_5d=False
    )
    assert verdict == "AVOID"


def test_verdict_hold_when_confidence_middling():
    verdict, reason = scoring.verdict(
        confidence=50, extension=0.5, gap_pct=1.0, regime="risk_on", earnings_within_5d=False
    )
    assert verdict == "HOLD"


def test_verdict_earnings_veto_beats_high_confidence():
    verdict, reason = scoring.verdict(
        confidence=95, extension=0.0, gap_pct=0.0, regime="risk_on", earnings_within_5d=True
    )
    assert verdict == "WAIT"
    assert "earnings" in reason.lower()


def test_verdict_regime_risk_off_blocks_buy():
    verdict, reason = scoring.verdict(
        confidence=95, extension=0.0, gap_pct=0.0, regime="risk_off", earnings_within_5d=False
    )
    assert verdict == "WAIT"
    assert "regime" in reason.lower()


def test_verdict_extension_blocks_buy():
    verdict, reason = scoring.verdict(
        confidence=95, extension=2.5, gap_pct=0.0, regime="risk_on", earnings_within_5d=False
    )
    assert verdict == "WAIT"
    assert "extend" in reason.lower() or "pullback" in reason.lower()


def test_verdict_gap_blocks_buy():
    verdict, reason = scoring.verdict(
        confidence=95, extension=0.0, gap_pct=4.0, regime="risk_on", earnings_within_5d=False
    )
    assert verdict == "WAIT"
    assert "gap" in reason.lower() or "chase" in reason.lower()


def test_verdict_gate_priority_earnings_over_regime():
    # Both earnings and risk-off apply; earnings veto message should win
    # since it's checked first (nearer-term, harder constraint).
    verdict, reason = scoring.verdict(
        confidence=95, extension=0.0, gap_pct=0.0, regime="risk_off", earnings_within_5d=True
    )
    assert verdict == "WAIT"
    assert "earnings" in reason.lower()


# --- exit_plan (mandatory ATR-based stop/target on every BUY) --------------

def test_exit_plan_hand_calc():
    plan = scoring.exit_plan(entry_price=100.0, atr=4.0)
    assert plan["stop"] == pytest.approx(100.0 - 1.5 * 4.0)
    assert plan["target"] == pytest.approx(100.0 + 3.0 * 4.0)


def test_exit_plan_target_beats_stop_distance():
    # ~2:1 reward-to-risk by construction.
    plan = scoring.exit_plan(entry_price=50.0, atr=2.0)
    risk = plan["entry"] - plan["stop"]
    reward = plan["target"] - plan["entry"]
    assert reward / risk == pytest.approx(2.0)
