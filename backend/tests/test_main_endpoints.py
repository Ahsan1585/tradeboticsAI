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
from routers import billing as billing_router


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _override_auth():
    main.app.dependency_overrides[main.get_current_user] = lambda: "test-user-id"
    yield
    main.app.dependency_overrides.pop(main.get_current_user, None)


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


def test_run_screener_shows_watchlist_when_risk_off_but_breadth_healthy(client):
    """Regression: risk_off alone already makes BUY unreachable in
    scoring.verdict(), but is_defensive_mode() also requires weak breadth.
    Without a fallback, that gap produced zero results AND no explanation
    -- a blank, unexplained screen -- whenever breadth stayed healthy
    during a risk-off regime."""
    main.SCREENER_CACHE.clear()
    mock_supabase = MagicMock()

    def fake_table(name):
        m = MagicMock()
        if name == "daily_metrics":
            m.select.return_value.execute.return_value.data = [
                _fake_daily_metrics_row(ticker="HEALTHY1", verdict="WAIT", regime="risk_off", price=150.0, sma50=140.0),
                _fake_daily_metrics_row(ticker="HEALTHY2", verdict="WAIT", regime="risk_off", price=150.0, sma50=140.0),
            ]
        elif name == "market_universe":
            m.select.return_value.execute.return_value.data = [
                {"ticker": "HEALTHY1", "sector": "Technology"}, {"ticker": "HEALTHY2", "sector": "Technology"},
            ]
        return m

    mock_supabase.table.side_effect = fake_table

    with patch.object(main, "supabase", mock_supabase):
        resp = client.post("/run-screener", json={"trade_style": "Swing Trade", "risk_level": "Moderate"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["defensive_mode"] is False  # breadth is healthy -- not "full" defensive mode
    assert len(data["results"]) == 2  # but the watchlist still shows, not a blank list
    assert "message" in data and "no new buy" in data["message"].lower()


def test_track_record_aggregates_signals(client):
    main.TRACK_RECORD_CACHE.clear()
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.execute.return_value.data = [
        {"ticker": "AAPL", "horizon": "swing", "verdict": "BUY", "trade_outcome": "target_hit",
         "engine_version": "v1", "d": "2026-06-01", "ret_5d": 0.01, "ret_20d": 0.08, "ret_60d": 0.1,
         "spy_ret_5d": 0.005, "spy_ret_20d": 0.02, "spy_ret_60d": 0.03},
    ]

    with patch.object(main, "supabase", mock_supabase):
        resp = client.get("/track-record")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tracks"]) == 1
    assert data["tracks"][0]["horizon"] == "swing"
    assert data["tracks"][0]["wins"] == 1


def _mock_client_for_translate(daily_metrics_rows, token_balance=10, new_balance=7, cache_hit=None):
    tables = {}

    def fake_table(name):
        if name not in tables:
            m = MagicMock()
            if name == "daily_metrics":
                m.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = daily_metrics_rows
            elif name == "profiles":
                m.select.return_value.eq.return_value.execute.return_value.data = [{"ai_token_balance": token_balance}]
            elif name == "ai_scan_cache":
                m.select.return_value.eq.return_value.execute.return_value.data = [cache_hit] if cache_hit else []
                m.upsert.return_value.execute.return_value = MagicMock()
            tables[name] = m
        return tables[name]

    client = MagicMock()
    client.table.side_effect = fake_table
    client.rpc.return_value.execute.return_value.data = new_balance
    return client


def test_translate_returns_404_when_no_swing_signal(client):
    mock_supabase = _mock_client_for_translate(daily_metrics_rows=[])
    with patch.object(main, "supabase", mock_supabase):
        resp = client.post("/translate", json={"ticker": "NODATA", "data_context": {}})
    assert resp.status_code == 404


def test_translate_narrates_computed_verdict_without_letting_llm_override_it(client):
    row = _fake_daily_metrics_row(ticker="AAPL", verdict="BUY", price=150.0)
    mock_supabase = _mock_client_for_translate(daily_metrics_rows=[row], token_balance=10, new_balance=7)

    captured_prompt = {}

    async def fake_generate_text(prompt, **kwargs):
        captured_prompt["prompt"] = prompt
        captured_prompt["system_extra"] = kwargs.get("system_extra", "")
        return "### AI Signal: BUY\nSome narrative text."

    with patch.object(main, "supabase", mock_supabase), \
         patch("main.llm_available", return_value=True), \
         patch("main.generate_text", side_effect=fake_generate_text):
        resp = client.post("/translate", json={
            "ticker": "AAPL",
            "data_context": {"fundamentals": {"pe_ratio": "20"}, "ledger": []},
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["remaining_tokens"] == 7
    # The prompt must carry the server-computed verdict verbatim, and forbid
    # the LLM from proposing a different one -- this is the anti-hallucination
    # guarantee this endpoint was rewritten to enforce.
    assert "BUY" in captured_prompt["prompt"]
    assert "150" in captured_prompt["prompt"]
    assert "do not" in captured_prompt["prompt"].lower() or "must" in captured_prompt["prompt"].lower()


def test_translate_uses_real_exit_plan_not_invented_price_targets(client):
    row = _fake_daily_metrics_row(ticker="AAPL", verdict="BUY", price=150.0)
    mock_supabase = _mock_client_for_translate(daily_metrics_rows=[row])

    captured_prompt = {}

    async def fake_generate_text(prompt, **kwargs):
        captured_prompt["prompt"] = prompt
        return "narrative"

    with patch.object(main, "supabase", mock_supabase), \
         patch("main.llm_available", return_value=True), \
         patch("main.generate_text", side_effect=fake_generate_text):
        resp = client.post("/translate", json={"ticker": "AAPL", "data_context": {}})

    assert resp.status_code == 200
    # exit_plan from _fake_daily_metrics_row: entry=150.0, stop=145.0, target=160.0
    assert "145" in captured_prompt["prompt"]
    assert "160" in captured_prompt["prompt"]


def test_billing_status_initializes_trial_on_first_call(client):
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"plan": "free", "trial_ends_at": None, "ai_token_balance": 5}
    ]
    mock_supabase.rpc.return_value.execute.return_value.data = 55

    with patch.object(billing_router, "supabase", mock_supabase):
        resp = client.get("/billing/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_status"] == "trial"
    assert data["trial_ends_at"] is not None
    mock_supabase.rpc.assert_any_call("credit_tokens", {"p_user_id": "test-user-id", "p_amount": billing_router.billing.TRIAL_TOKEN_GRANT})


def test_billing_checkout_subscription_returns_url(client):
    with patch.object(billing_router, "stripe") as mock_stripe, \
         patch.object(billing_router, "STRIPE_PRICE_ID_PRO", "price_pro123"):
        mock_stripe.api_key = "sk_test_fake"
        mock_stripe.checkout.Session.create.return_value = MagicMock(url="https://checkout.stripe.com/abc")
        resp = client.post("/billing/checkout", json={"mode": "subscription"})

    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/abc"


def test_billing_checkout_not_configured_returns_500(client):
    with patch.object(billing_router, "stripe") as mock_stripe:
        mock_stripe.api_key = None
        resp = client.post("/billing/checkout", json={"mode": "subscription"})
    assert resp.status_code == 500


def test_stripe_webhook_activates_subscription_and_is_idempotent(client):
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    fake_event = {
        "id": "evt_test1", "type": "checkout.session.completed",
        "data": {"object": {"customer": "cus_1", "client_reference_id": "user-1",
                             "metadata": {"user_id": "user-1", "kind": "subscription"}}},
    }

    with patch.object(billing_router, "supabase", mock_supabase), \
         patch.object(billing_router, "STRIPE_WEBHOOK_SECRET", "whsec_fake"), \
         patch.object(billing_router, "stripe") as mock_stripe:
        mock_stripe.Webhook.construct_event.return_value = fake_event
        resp = client.post("/stripe/webhook", content=b"{}", headers={"stripe-signature": "fake"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    update_calls = mock_supabase.table.return_value.update.call_args_list
    plan_updates = [c for c in update_calls if c[0][0].get("plan") == "pro"]
    assert len(plan_updates) == 1


def test_list_personas_returns_all_four(client):
    resp = client.get("/personas")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["personas"]}
    assert ids == {"buffett", "lynch", "wood", "burry"}


def test_persona_take_unknown_persona_returns_404(client):
    resp = client.post("/persona-take", json={"ticker": "AAPL", "persona_id": "nobody"})
    assert resp.status_code == 404


def test_persona_take_returns_narrated_verdict(client):
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"ai_token_balance": 10}
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"signals": {"swing": {"verdict": "BUY", "confidence": 82.0, "reason": "Trend and momentum align.",
                                "consensus": {"bullish": 4, "bearish": 0, "neutral": 1, "total": 5}}}}
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"ai_token_balance": 10}]
    mock_supabase.rpc.return_value.execute.return_value.data = 9

    with patch.object(main, "supabase", mock_supabase), \
         patch("main.llm_available", return_value=True), \
         patch("main.check_ai_cache", return_value=None), \
         patch("main.generate_text", return_value="Buffett-style narration of the BUY verdict."):
        resp = client.post("/persona-take", json={"ticker": "AAPL", "persona_id": "buffett"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "BUY"
    assert data["persona"] == "Warren Buffett"
    assert "narration" in data["analysis"].lower()
