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
