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
