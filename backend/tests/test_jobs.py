import pandas as pd
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
