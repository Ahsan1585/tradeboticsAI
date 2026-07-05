import asyncio

import pandas as pd
from datetime import date
from unittest.mock import MagicMock, patch

import services.market_data as market_data
from services.market_data import (
    fetch_ohlcv_batch, upsert_price_history, load_price_history_df, get_live_quote,
    has_earnings_within_5d,
)


def _fake_yf_download_result(tickers):
    """Mimics yf.download(tickers, ...) multi-index column output for 2 tickers."""
    idx = pd.date_range("2026-01-02", periods=3, freq="B")
    cols = pd.MultiIndex.from_product([tickers, ["Open", "High", "Low", "Close", "Volume"]])
    data = {}
    for t in tickers:
        for field, val in [("Open", 10.0), ("High", 11.0), ("Low", 9.0), ("Close", 10.5), ("Volume", 1000)]:
            data[(t, field)] = [val] * len(idx)
    return pd.DataFrame(data, index=idx, columns=cols)


def test_fetch_ohlcv_batch_uses_yfinance_when_available():
    with patch("services.market_data.yf.download") as mock_download:
        mock_download.return_value = _fake_yf_download_result(["AAPL", "MSFT"])
        result = fetch_ohlcv_batch(["AAPL", "MSFT"], date(2026, 1, 1), date(2026, 1, 5))
    assert set(result.keys()) == {"AAPL", "MSFT"}
    assert list(result["AAPL"].columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(result["AAPL"]) == 3


def test_fetch_ohlcv_batch_falls_back_to_stooq_for_missing_ticker():
    stooq_csv = (
        "Date,Open,High,Low,Close,Volume\n"
        "2026-01-02,20.0,21.0,19.0,20.5,5000\n"
        "2026-01-05,20.5,21.5,19.5,21.0,6000\n"
    )
    with patch("services.market_data.yf.download") as mock_download, \
         patch("services.market_data.requests.get") as mock_get:
        # yfinance returns data only for AAPL; ZZZZ comes back empty
        mock_download.return_value = _fake_yf_download_result(["AAPL"])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = stooq_csv
        mock_get.return_value = mock_response

        result = fetch_ohlcv_batch(["AAPL", "ZZZZ"], date(2026, 1, 1), date(2026, 1, 5))

    assert "ZZZZ" in result
    assert list(result["ZZZZ"].columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(result["ZZZZ"]) == 2
    mock_get.assert_called_once()
    assert "zzzz.us" in mock_get.call_args[0][0]


def test_upsert_price_history_writes_expected_rows():
    idx = pd.to_datetime(["2026-01-02", "2026-01-05"])
    df = pd.DataFrame(
        {"Open": [10.0, 10.5], "High": [11.0, 11.5], "Low": [9.0, 9.5], "Close": [10.5, 11.0], "Volume": [1000, 1100]},
        index=idx,
    )
    mock_client = MagicMock()
    mock_table = mock_client.table.return_value
    mock_table.upsert.return_value.execute.return_value = MagicMock()

    count = upsert_price_history(mock_client, "AAPL", df)

    assert count == 2
    mock_client.table.assert_called_with("price_history")
    upserted_rows = mock_table.upsert.call_args[0][0]
    assert upserted_rows[0]["ticker"] == "AAPL"
    assert upserted_rows[0]["d"] == "2026-01-02"
    assert upserted_rows[0]["close"] == 10.5
    assert mock_table.upsert.call_args[1]["on_conflict"] == "ticker,d"


def test_load_price_history_df_reconstructs_ohlcv_shape():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [
        {"d": "2026-01-02", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 1000},
        {"d": "2026-01-05", "open": 10.5, "high": 11.5, "low": 9.5, "close": 11.0, "volume": 1100},
    ]
    (mock_client.table.return_value.select.return_value.eq.return_value
     .order.return_value.limit.return_value.execute.return_value) = mock_response

    df = load_price_history_df(mock_client, "AAPL", lookback_days=130)

    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].iloc[-1] == 11.0
    assert df.index[0] < df.index[1]  # ascending


def _clear_quote_state(ticker: str) -> None:
    """_quote_cache/_quote_locks are module-level singletons that persist
    across test functions within the same session; clear any pre-existing
    entry for our ticker so tests don't contaminate each other."""
    market_data._quote_cache.pop(ticker, None)
    market_data._quote_locks.pop(ticker, None)


def test_get_live_quote_caches_result_and_avoids_second_network_call():
    ticker = "TESTQ1"
    _clear_quote_state(ticker)

    mock_response = MagicMock()
    mock_response.json.return_value = {"c": 123.45}

    with patch.dict("os.environ", {"FINNHUB_API_KEY": "fake-key"}), \
         patch("services.market_data.requests.get") as mock_get:
        mock_get.return_value = mock_response

        first = asyncio.run(get_live_quote(ticker))
        second = asyncio.run(get_live_quote(ticker))

    assert first == {"price": 123.45, "source": "finnhub"}
    assert second == {"price": 123.45, "source": "finnhub"}
    mock_get.assert_called_once()


def test_get_live_quote_falls_back_to_fast_info_when_no_finnhub_key():
    ticker = "TESTQ2"
    _clear_quote_state(ticker)

    mock_ticker = MagicMock()
    mock_ticker.fast_info = {"lastPrice": 67.89}

    with patch("services.market_data.os.getenv", return_value=None), \
         patch("services.market_data.yf.Ticker", return_value=mock_ticker):
        result = asyncio.run(get_live_quote(ticker))

    assert result == {"price": 67.89, "source": "fast_info"}


def test_has_earnings_within_5d_true_when_calendar_has_entries():
    mock_response = MagicMock()
    mock_response.json.return_value = {"earningsCalendar": [{"date": "2026-07-08"}]}
    with patch.dict("os.environ", {"FINNHUB_API_KEY": "fake-key"}), \
         patch("services.market_data.requests.get") as mock_get:
        mock_get.return_value = mock_response
        assert has_earnings_within_5d("AAPL", today=date(2026, 7, 5)) is True


def test_has_earnings_within_5d_false_when_calendar_empty():
    mock_response = MagicMock()
    mock_response.json.return_value = {"earningsCalendar": []}
    with patch.dict("os.environ", {"FINNHUB_API_KEY": "fake-key"}), \
         patch("services.market_data.requests.get") as mock_get:
        mock_get.return_value = mock_response
        assert has_earnings_within_5d("AAPL", today=date(2026, 7, 5)) is False


def test_has_earnings_within_5d_fails_open_without_api_key():
    with patch.dict("os.environ", {}, clear=True):
        assert has_earnings_within_5d("AAPL", today=date(2026, 7, 5)) is False


def test_has_earnings_within_5d_fails_open_on_network_error():
    with patch.dict("os.environ", {"FINNHUB_API_KEY": "fake-key"}), \
         patch("services.market_data.requests.get", side_effect=ConnectionError("timeout")):
        assert has_earnings_within_5d("AAPL", today=date(2026, 7, 5)) is False
