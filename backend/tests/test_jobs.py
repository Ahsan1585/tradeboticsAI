import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from jobs.backfill_price_history import run as run_backfill


def test_backfill_batches_tickers_and_writes_rows():
    tickers = [f"T{i}" for i in range(150)]  # forces 2 batches of 100 + 50
    fake_df = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [100]},
        index=pd.to_datetime(["2026-01-02"]),
    )

    with patch("jobs.backfill_price_history.fetch_ohlcv_batch") as mock_fetch:
        mock_fetch.return_value = {t: fake_df for t in tickers[:100]}  # first batch full data

        mock_client = MagicMock()
        result = run_backfill(mock_client, tickers, batch_size=100)

    assert mock_fetch.call_count == 2  # one call per batch of <=100
    first_call_tickers = mock_fetch.call_args_list[0][0][0]
    assert len(first_call_tickers) == 100
    second_call_tickers = mock_fetch.call_args_list[1][0][0]
    assert len(second_call_tickers) == 50
    assert result["tickers_processed"] == 150


import numpy as np


def _fake_hist_df():
    idx = pd.date_range("2025-11-01", periods=40, freq="B")
    close = np.linspace(100, 110, len(idx))
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": [1_000_000] * len(idx)},
        index=idx,
    )


def test_eod_ingest_writes_bars_and_scores_universe():
    from jobs.eod_ingest import run as run_eod_ingest

    tickers = ["AAPL"]
    fake_df = pd.DataFrame(
        {"Open": [110.0], "High": [111.0], "Low": [109.0], "Close": [110.0], "Volume": [500000]},
        index=pd.to_datetime(["2026-07-03"]),
    )

    with patch("jobs.eod_ingest.fetch_ohlcv_batch") as mock_fetch, \
         patch("jobs.eod_ingest.load_price_history_df") as mock_load, \
         patch("jobs.eod_ingest.yf.Ticker") as mock_ticker_cls:
        mock_fetch.return_value = {"AAPL": fake_df}
        mock_load.return_value = _fake_hist_df()
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"sector": "Technology", "trailingPE": 20.0}
        mock_ticker_instance.options = []
        mock_ticker_cls.return_value = mock_ticker_instance

        mock_client = MagicMock()
        result = run_eod_ingest(mock_client, tickers, batch_size=100)

    assert result["tickers_processed"] == 1
    assert result["scored"] == 1
    mock_client.table.assert_any_call("market_universe")
    upsert_calls = mock_client.table.return_value.upsert.call_args_list
    universe_upsert = next(c for c in upsert_calls if "tech_score" in c[0][0])
    assert universe_upsert[0][0]["ticker"] == "AAPL"


def test_eod_ingest_isolates_scoring_failure_per_ticker():
    """One ticker's load_price_history_df blowing up must not abort the
    whole batch: the failing ticker should just not be scored, while its
    sibling in the same batch still gets scored normally."""
    from jobs.eod_ingest import run as run_eod_ingest

    tickers = ["BADTICK", "AAPL"]
    fake_bar_df = pd.DataFrame(
        {"Open": [110.0], "High": [111.0], "Low": [109.0], "Close": [110.0], "Volume": [500000]},
        index=pd.to_datetime(["2026-07-03"]),
    )

    def fake_load(client, ticker, lookback_days=130):
        if ticker == "BADTICK":
            raise ConnectionError("supabase read failed")
        return _fake_hist_df()

    with patch("jobs.eod_ingest.fetch_ohlcv_batch") as mock_fetch, \
         patch("jobs.eod_ingest.load_price_history_df", side_effect=fake_load), \
         patch("jobs.eod_ingest.yf.Ticker") as mock_ticker_cls:
        mock_fetch.return_value = {"BADTICK": fake_bar_df, "AAPL": fake_bar_df}
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"sector": "Technology", "trailingPE": 20.0}
        mock_ticker_instance.options = []
        mock_ticker_cls.return_value = mock_ticker_instance

        mock_client = MagicMock()
        result = run_eod_ingest(mock_client, tickers, batch_size=100)

    assert result["tickers_processed"] == 2
    assert result["scored"] == 1  # only AAPL, BADTICK's load failure must not count and must not raise
    upsert_calls = mock_client.table.return_value.upsert.call_args_list
    universe_upserts = [c for c in upsert_calls if isinstance(c[0][0], dict) and "tech_score" in c[0][0]]
    assert len(universe_upserts) == 1
    assert universe_upserts[0][0][0]["ticker"] == "AAPL"


def test_eod_ingest_isolates_universe_upsert_failure_per_ticker():
    """One ticker's final market_universe upsert failing (e.g. a Supabase
    write error) must not abort the batch, and since the write never
    landed, that ticker must not be counted as scored even though scoring
    itself succeeded."""
    from jobs.eod_ingest import run as run_eod_ingest

    tickers = ["BADWRITE", "AAPL"]
    fake_bar_df = pd.DataFrame(
        {"Open": [110.0], "High": [111.0], "Low": [109.0], "Close": [110.0], "Volume": [500000]},
        index=pd.to_datetime(["2026-07-03"]),
    )

    def fake_upsert(row, *args, **kwargs):
        mock_result = MagicMock()
        if isinstance(row, dict) and row.get("ticker") == "BADWRITE":
            mock_result.execute.side_effect = ConnectionError("supabase write failed")
        return mock_result

    with patch("jobs.eod_ingest.fetch_ohlcv_batch") as mock_fetch, \
         patch("jobs.eod_ingest.load_price_history_df") as mock_load, \
         patch("jobs.eod_ingest.yf.Ticker") as mock_ticker_cls:
        mock_fetch.return_value = {"BADWRITE": fake_bar_df, "AAPL": fake_bar_df}
        mock_load.return_value = _fake_hist_df()
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"sector": "Technology", "trailingPE": 20.0}
        mock_ticker_instance.options = []
        mock_ticker_cls.return_value = mock_ticker_instance

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.side_effect = fake_upsert
        result = run_eod_ingest(mock_client, tickers, batch_size=100)

    assert result["tickers_processed"] == 2
    assert result["scored"] == 1  # BADWRITE's write failed, so it must not count as scored


def test_eod_ingest_isolates_ohlcv_write_failure_per_ticker():
    """One ticker's upsert_price_history call raising must not abort the
    batch: rows_written should only reflect tickers whose write actually
    succeeded, and scoring should still proceed for every ticker."""
    from jobs.eod_ingest import run as run_eod_ingest

    tickers = ["BADWRITE", "AAPL"]
    fake_bar_df = pd.DataFrame(
        {"Open": [110.0], "High": [111.0], "Low": [109.0], "Close": [110.0], "Volume": [500000]},
        index=pd.to_datetime(["2026-07-03"]),
    )

    def fake_upsert_price_history(client, ticker, df):
        if ticker == "BADWRITE":
            raise ConnectionError("supabase write failed")
        return len(df)

    with patch("jobs.eod_ingest.fetch_ohlcv_batch") as mock_fetch, \
         patch("jobs.eod_ingest.upsert_price_history", side_effect=fake_upsert_price_history), \
         patch("jobs.eod_ingest.load_price_history_df") as mock_load, \
         patch("jobs.eod_ingest.yf.Ticker") as mock_ticker_cls:
        mock_fetch.return_value = {"BADWRITE": fake_bar_df, "AAPL": fake_bar_df}
        mock_load.return_value = _fake_hist_df()
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"sector": "Technology", "trailingPE": 20.0}
        mock_ticker_instance.options = []
        mock_ticker_cls.return_value = mock_ticker_instance

        mock_client = MagicMock()
        result = run_eod_ingest(mock_client, tickers, batch_size=100)

    assert result["tickers_processed"] == 2
    assert result["rows_written"] == 1  # only AAPL's row counted; BADWRITE's raise must not propagate
    assert result["scored"] == 2  # scoring is independent of the OHLCV write and must still run for both


def test_eod_ingest_seeds_etf_bars_but_does_not_score_them():
    """Sector ETFs (SPY, QQQ, etc.) must still get their OHLCV bars written
    to price_history (Phase 2's market-regime gate needs that history), but
    they must NOT be scored into market_universe -- otherwise they leak into
    /run-screener as screenable stock candidates, which never happened with
    the old Wikipedia-scrape-based universe."""
    from jobs.eod_ingest import run as run_eod_ingest

    tickers = ["SPY", "AAPL"]
    fake_bar_df = pd.DataFrame(
        {"Open": [110.0], "High": [111.0], "Low": [109.0], "Close": [110.0], "Volume": [500000]},
        index=pd.to_datetime(["2026-07-03"]),
    )

    with patch("jobs.eod_ingest.fetch_ohlcv_batch") as mock_fetch, \
         patch("jobs.eod_ingest.upsert_price_history") as mock_upsert_ph, \
         patch("jobs.eod_ingest.load_price_history_df") as mock_load, \
         patch("jobs.eod_ingest.yf.Ticker") as mock_ticker_cls:
        mock_fetch.return_value = {"SPY": fake_bar_df, "AAPL": fake_bar_df}
        mock_load.return_value = _fake_hist_df()
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = {"sector": "Technology", "trailingPE": 20.0}
        mock_ticker_instance.options = []
        mock_ticker_cls.return_value = mock_ticker_instance

        mock_client = MagicMock()
        result = run_eod_ingest(mock_client, tickers, batch_size=100)

    # OHLCV bars are still fetched/written for the ETF (needed for Phase 2's
    # regime gate/breadth calc) -- fetch_ohlcv_batch's batch includes SPY,
    # and upsert_price_history was called for SPY too.
    fetched_batch = mock_fetch.call_args_list[0][0][0]
    assert "SPY" in fetched_batch
    upsert_ph_tickers = {c[0][1] for c in mock_upsert_ph.call_args_list}
    assert "SPY" in upsert_ph_tickers

    # But SPY must NOT be scored into market_universe.
    upsert_calls = mock_client.table.return_value.upsert.call_args_list
    universe_upserts = [c for c in upsert_calls if isinstance(c[0][0], dict) and "tech_score" in c[0][0]]
    assert {u[0][0]["ticker"] for u in universe_upserts} == {"AAPL"}
    assert result["scored"] == 1


def _fake_long_hist_df(days=260, start_price=100.0, trend=0.3):
    idx = pd.date_range("2025-08-01", periods=days, freq="B")
    close = start_price + np.arange(days) * trend
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": [1_000_000] * days},
        index=idx,
    )


def test_compute_ticker_metrics_returns_none_when_insufficient_history():
    from jobs.compute_daily_metrics import compute_ticker_metrics
    short_hist = _fake_long_hist_df(days=10)
    spy = short_hist["Close"]
    result = compute_ticker_metrics("AAPL", short_hist, spy, spy, fundamentals_score=50.0, earnings_within_5d=False, regime="risk_on")
    assert result is None


def test_compute_ticker_metrics_produces_all_three_horizons():
    from jobs.compute_daily_metrics import compute_ticker_metrics
    hist = _fake_long_hist_df(days=260, trend=0.5)  # steady uptrend -> should score bullish
    spy = _fake_long_hist_df(days=260, trend=0.1)["Close"]  # weaker benchmark -> positive rel strength
    result = compute_ticker_metrics("AAPL", hist, spy, spy, fundamentals_score=70.0, earnings_within_5d=False, regime="risk_on")

    assert result is not None
    assert result["ticker"] == "AAPL"
    assert set(result["signals"].keys()) == {"day", "swing", "longterm"}
    assert result["regime"] == "risk_on"
    assert result["sma20"] is not None
    assert result["rsi14"] is not None
    assert result["trend_score"] is not None
    assert result["momentum_score"] is not None
    assert result["rel_strength_score"] is not None
    assert result["volume_score"] is not None
    assert result["fundamentals_score"] == pytest.approx(70.0)


def test_compute_ticker_metrics_without_smart_money_has_no_sixth_lens():
    from jobs.compute_daily_metrics import compute_ticker_metrics
    hist = _fake_long_hist_df(days=260, trend=0.5)
    spy = _fake_long_hist_df(days=260, trend=0.1)["Close"]
    result = compute_ticker_metrics("AAPL", hist, spy, spy, fundamentals_score=70.0, earnings_within_5d=False, regime="risk_on")

    assert result["smart_money_score"] is None
    for horizon_signal in result["signals"].values():
        assert "smart_money" not in horizon_signal["consensus"]["lenses"]


def test_compute_ticker_metrics_with_smart_money_adds_score_and_signals():
    from jobs.compute_daily_metrics import compute_ticker_metrics
    hist = _fake_long_hist_df(days=260, trend=0.5)
    spy = _fake_long_hist_df(days=260, trend=0.1)["Close"]
    result = compute_ticker_metrics(
        "AAPL", hist, spy, spy, fundamentals_score=70.0, earnings_within_5d=False, regime="risk_on",
        fund_signals=["new", "increased"], insider_net_buy_usd=250_000.0,
    )

    assert result["smart_money_score"] > 50.0
    assert result["smart_money_signals"] == {"fund_signals": ["new", "increased"], "insider_net_buy_usd": 250_000.0}
    for horizon_signal in result["signals"].values():
        assert "smart_money" in horizon_signal["consensus"]["lenses"]


def test_compute_ticker_metrics_earnings_veto_propagates_to_all_horizons():
    from jobs.compute_daily_metrics import compute_ticker_metrics
    hist = _fake_long_hist_df(days=260, trend=0.5)
    spy = _fake_long_hist_df(days=260, trend=0.1)["Close"]
    result = compute_ticker_metrics("AAPL", hist, spy, spy, fundamentals_score=70.0, earnings_within_5d=True, regime="risk_on")

    for horizon_signal in result["signals"].values():
        assert horizon_signal["verdict"] == "WAIT"
        assert "earnings" in horizon_signal["reason"].lower()


def _mock_client_with_tables(table_data: dict) -> MagicMock:
    """Builds a supabase client mock where table(name) returns a stable
    per-name MagicMock, so chained select/eq/limit calls can be configured
    independently per table (unlike a bare MagicMock, which would collapse
    all table names onto the same auto-generated mock)."""
    tables = {}

    def fake_table(name):
        if name not in tables:
            m = MagicMock()
            if name in table_data:
                m.select.return_value.execute.return_value.data = table_data[name]
                m.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = table_data[name]
                m.select.return_value.eq.return_value.execute.return_value.data = table_data[name]
                m.select.return_value.gte.return_value.execute.return_value.data = table_data[name]
            tables[name] = m
        return tables[name]

    client = MagicMock()
    client.table.side_effect = fake_table
    client._tables = tables  # test-only escape hatch for assertions
    return client


def test_compute_daily_metrics_run_writes_row_per_ticker():
    from jobs.compute_daily_metrics import run
    long_hist = _fake_long_hist_df(days=260)

    def fake_load(client, ticker, lookback_days=250):
        return long_hist

    mock_client = _mock_client_with_tables({
        "market_universe": [{"sector": "Technology", "pe": 20.0}],
        "smart_money_13f": [],
        "smart_money_insider": [],
    })

    with patch("jobs.compute_daily_metrics.load_price_history_df", side_effect=fake_load), \
         patch("jobs.compute_daily_metrics.has_earnings_within_5d", return_value=False):
        result = run(mock_client, ["AAPL"])

    assert result["tickers_processed"] == 1
    assert result["written"] == 1
    upsert_calls = mock_client._tables["daily_metrics"].upsert.call_args_list
    assert len(upsert_calls) == 1
    assert upsert_calls[0][0][0]["ticker"] == "AAPL"
    assert upsert_calls[0][1]["on_conflict"] == "ticker,d"


def test_compute_daily_metrics_run_logs_signals_for_every_horizon():
    from jobs.compute_daily_metrics import run
    long_hist = _fake_long_hist_df(days=260)

    def fake_load(client, ticker, lookback_days=250):
        return long_hist

    mock_client = _mock_client_with_tables({
        "market_universe": [{"sector": "Technology", "pe": 20.0}],
        "smart_money_13f": [],
        "smart_money_insider": [],
    })

    with patch("jobs.compute_daily_metrics.load_price_history_df", side_effect=fake_load), \
         patch("jobs.compute_daily_metrics.has_earnings_within_5d", return_value=False):
        run(mock_client, ["AAPL"])

    signal_upserts = mock_client._tables["signals"].upsert.call_args_list
    assert len(signal_upserts) == 3  # day, swing, longterm
    horizons_logged = {c[0][0]["horizon"] for c in signal_upserts}
    assert horizons_logged == {"day", "swing", "longterm"}
    assert signal_upserts[0][1]["on_conflict"] == "ticker,horizon,d"


def test_compute_daily_metrics_run_feeds_smart_money_into_row():
    from jobs.compute_daily_metrics import run
    long_hist = _fake_long_hist_df(days=260)

    def fake_load(client, ticker, lookback_days=250):
        return long_hist

    mock_client = _mock_client_with_tables({
        "market_universe": [{"sector": "Technology", "pe": 20.0}],
        "smart_money_13f": [{"ticker": "AAPL", "change_type": "increased"}, {"ticker": "AAPL", "change_type": "new"}],
        "smart_money_insider": [
            {"ticker": "AAPL", "transaction_code": "P", "shares": 1000, "price": 100.0},
            {"ticker": "AAPL", "transaction_code": "S", "shares": 200, "price": 100.0},
        ],
    })

    with patch("jobs.compute_daily_metrics.load_price_history_df", side_effect=fake_load), \
         patch("jobs.compute_daily_metrics.has_earnings_within_5d", return_value=False):
        result = run(mock_client, ["AAPL"])

    assert result["written"] == 1
    row = mock_client._tables["daily_metrics"].upsert.call_args_list[0][0][0]
    assert row["smart_money_score"] is not None
    assert row["smart_money_score"] > 50.0  # net buying (1000 bought - 200 sold) + 2 bullish fund signals
    assert row["smart_money_signals"]["fund_signals"] == ["increased", "new"]
    assert row["smart_money_signals"]["insider_net_buy_usd"] == pytest.approx((1000 - 200) * 100.0)


def test_compute_daily_metrics_run_isolates_per_ticker_failure():
    from jobs.compute_daily_metrics import run
    long_hist = _fake_long_hist_df(days=260)

    def fake_load(client, ticker, lookback_days=250):
        if ticker == "BADTICK":
            raise ConnectionError("supabase read failed")
        return long_hist

    mock_client = _mock_client_with_tables({
        "market_universe": [{"sector": "Technology", "pe": 20.0}],
        "smart_money_13f": [],
        "smart_money_insider": [],
    })

    with patch("jobs.compute_daily_metrics.load_price_history_df", side_effect=fake_load), \
         patch("jobs.compute_daily_metrics.has_earnings_within_5d", return_value=False):
        result = run(mock_client, ["BADTICK", "AAPL"])

    assert result["tickers_processed"] == 2
    assert result["written"] == 1  # only AAPL


def test_refresh_universe_upserts_scraped_tickers():
    from jobs.refresh_universe import run as run_refresh

    with patch("jobs.refresh_universe.get_market_universe") as mock_scrape:
        mock_scrape.return_value = ["AAPL", "MSFT", "GOOGL"]
        mock_client = MagicMock()

        count = run_refresh(mock_client)

    assert count == 3
    mock_client.table.assert_called_with("market_universe")
    upserted = mock_client.table.return_value.upsert.call_args[0][0]
    assert {row["ticker"] for row in upserted} == {"AAPL", "MSFT", "GOOGL"}
