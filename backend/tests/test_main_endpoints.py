"""Lightweight wiring tests for /analyze and /run-screener (Phase 2a):
verifies these endpoints read from daily_metrics and never invoke the
deleted fake-metrics engine. Not a full endpoint test suite (that's Phase 4
scope per the roadmap) -- just enough to catch import/KeyError-class bugs
in this rewrite.
"""
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app)


def _fake_hist_df(days=40):
    idx = pd.date_range("2026-05-01", periods=days, freq="B")
    close = [100.0 + i * 0.1 for i in range(days)]
    return pd.DataFrame(
        {"Open": close, "High": [c + 1 for c in close], "Low": [c - 1 for c in close],
         "Close": close, "Volume": [1_000_000] * days},
        index=idx,
    )


def _fake_daily_metrics_row(ticker="AAPL", verdict="BUY", regime="risk_on", price=150.0, sma50=140.0):
    return {
        "ticker": ticker, "d": "2026-07-05", "price": price,
        "sma20": 148.0, "sma50": sma50, "sma200": 130.0,
        "rsi14": 55.0, "macd_line": 1.2, "macd_signal": 1.0, "macd_hist": 0.2,
        "atr14": 3.0, "bb_width": 0.08, "extension": 0.5, "gap_pct": 0.5,
        "rel_strength_spy": 0.03, "rel_strength_sector": 0.02,
        "trend_score": 70.0, "momentum_score": 65.0, "rel_strength_score": 60.0,
        "volume_score": 55.0, "fundamentals_score": 60.0,
        "regime": regime, "earnings_within_5d": False,
        "signals": {
            "day": {"confidence": 60.0, "verdict": verdict, "reason": "test reason", "consensus": {}},
            "swing": {"confidence": 75.0, "verdict": verdict, "reason": "test reason",
                      "consensus": {}, **({"exit_plan": {"entry": price, "stop": price - 5, "target": price + 10}} if verdict == "BUY" else {})},
            "longterm": {"confidence": 55.0, "verdict": verdict, "reason": "test reason", "consensus": {}},
        },
        "engine_version": "v1",
    }


def test_analyze_returns_404_when_no_daily_metrics_row(client):
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    with patch.object(main, "supabase", mock_supabase):
        resp = client.get("/analyze/NODATA")

    assert resp.status_code == 404


def test_analyze_returns_honest_metrics_shape(client):
    main.market_cache.pop("HONEST", None)
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        _fake_daily_metrics_row(ticker="HONEST")
    ]

    with patch.object(main, "supabase", mock_supabase), \
         patch("main.load_price_history_df", return_value=_fake_hist_df()), \
         patch("main.get_live_quote", side_effect=ValueError("no quote")), \
         patch("main.yf.Ticker") as mock_ticker_cls:
        mock_ticker_cls.return_value.info = {}
        mock_ticker_cls.return_value.calendar = None
        resp = client.get("/analyze/HONEST")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "HONEST"
    assert data["verdict"] == "BUY"
    assert "signals" in data and set(data["signals"].keys()) == {"day", "swing", "longterm"}
    assert isinstance(data["ledger"], list) and len(data["ledger"]) > 0
    assert data["tech_score"] >= 0
    assert data["fund_score"] >= 0


def test_run_screener_returns_buy_signals_in_risk_on_regime(client):
    main.SCREENER_CACHE.clear()
    mock_supabase = MagicMock()

    def fake_table(name):
        m = MagicMock()
        if name == "daily_metrics":
            m.select.return_value.execute.return_value.data = [
                _fake_daily_metrics_row(ticker="BUYME", verdict="BUY", regime="risk_on", sma50=140.0),
                _fake_daily_metrics_row(ticker="SKIPME", verdict="HOLD", regime="risk_on", sma50=140.0),
            ]
        elif name == "market_universe":
            m.select.return_value.execute.return_value.data = [
                {"ticker": "BUYME", "sector": "Technology"}, {"ticker": "SKIPME", "sector": "Technology"},
            ]
        return m

    mock_supabase.table.side_effect = fake_table

    with patch.object(main, "supabase", mock_supabase):
        resp = client.post("/run-screener", json={"trade_style": "Swing Trade", "risk_level": "Moderate"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["defensive_mode"] is False
    tickers = [r["ticker"] for r in data["results"]]
    assert "BUYME" in tickers
    assert "SKIPME" not in tickers  # HOLD verdicts are not screener BUYs


def test_run_screener_defensive_mode_when_risk_off_and_weak_breadth(client):
    main.SCREENER_CACHE.clear()
    mock_supabase = MagicMock()

    def fake_table(name):
        m = MagicMock()
        if name == "daily_metrics":
            m.select.return_value.execute.return_value.data = [
                _fake_daily_metrics_row(ticker="WEAK1", verdict="WAIT", regime="risk_off", price=90.0, sma50=140.0),
                _fake_daily_metrics_row(ticker="WEAK2", verdict="WAIT", regime="risk_off", price=90.0, sma50=140.0),
            ]
        elif name == "market_universe":
            m.select.return_value.execute.return_value.data = [
                {"ticker": "WEAK1", "sector": "Technology"}, {"ticker": "WEAK2", "sector": "Technology"},
            ]
        return m

    mock_supabase.table.side_effect = fake_table

    with patch.object(main, "supabase", mock_supabase):
        resp = client.post("/run-screener", json={"trade_style": "Swing Trade", "risk_level": "Moderate"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["defensive_mode"] is True
    assert "cash" in data["message"].lower()
