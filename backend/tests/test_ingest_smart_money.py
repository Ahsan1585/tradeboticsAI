"""Unit tests for the smart-money ingestion job (Phase 2b). All SEC/OpenFIGI
calls are mocked via the services.sec_edgar module boundary."""
from unittest.mock import MagicMock, patch

from jobs.ingest_smart_money import ingest_13f, ingest_form4


def _fund_table_mock(existing_rows):
    """Builds a MagicMock for supabase.table('smart_money_13f') that
    returns existing_rows on select().eq().execute() and records upserts."""
    m = MagicMock()
    m.select.return_value.eq.return_value.execute.return_value.data = existing_rows
    return m


def test_ingest_13f_classifies_new_position():
    tracked_funds = [("Test Fund", "0001111111")]

    def fake_table(name):
        m = MagicMock()
        if name == "market_universe":
            m.select.return_value.execute.return_value.data = [{"ticker": "AAPL"}]
        elif name == "smart_money_13f":
            m.select.return_value.eq.return_value.execute.return_value.data = []  # no prior holding
        return m

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    with patch("jobs.ingest_smart_money.sec_edgar.get_latest_13f_accession",
               return_value={"accession": "0001-A", "filing_date": "2026-05-15", "primary_document": "primary_doc.xml"}), \
         patch("jobs.ingest_smart_money.sec_edgar.get_13f_infotable_document", return_value="53405.xml"), \
         patch("jobs.ingest_smart_money.sec_edgar.get_filing_document", return_value="<xml/>"), \
         patch("jobs.ingest_smart_money.sec_edgar.parse_13f_holdings",
               return_value=[{"cusip": "037833100", "issuer_name": "APPLE INC", "value": 1000, "shares": 100}]), \
         patch("jobs.ingest_smart_money.sec_edgar.resolve_cusips_to_tickers", return_value={"037833100": "AAPL"}):
        result = ingest_13f(mock_client, tracked_funds)

    assert result["written"] == 1
    # smart_money_13f mock is a distinct MagicMock from fake_table's per-name instances,
    # so inspect via the table() call history instead.
    smart_money_calls = [c for c in mock_client.table.call_args_list if c[0][0] == "smart_money_13f"]
    assert len(smart_money_calls) >= 1


def test_ingest_13f_skips_ticker_outside_universe():
    tracked_funds = [("Test Fund", "0001111111")]

    def fake_table(name):
        m = MagicMock()
        if name == "market_universe":
            m.select.return_value.execute.return_value.data = [{"ticker": "MSFT"}]  # AAPL not in universe
        elif name == "smart_money_13f":
            m.select.return_value.eq.return_value.execute.return_value.data = []
        return m

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    with patch("jobs.ingest_smart_money.sec_edgar.get_latest_13f_accession",
               return_value={"accession": "0001-A", "filing_date": "2026-05-15", "primary_document": "primary_doc.xml"}), \
         patch("jobs.ingest_smart_money.sec_edgar.get_13f_infotable_document", return_value="53405.xml"), \
         patch("jobs.ingest_smart_money.sec_edgar.get_filing_document", return_value="<xml/>"), \
         patch("jobs.ingest_smart_money.sec_edgar.parse_13f_holdings",
               return_value=[{"cusip": "037833100", "issuer_name": "APPLE INC", "value": 1000, "shares": 100}]), \
         patch("jobs.ingest_smart_money.sec_edgar.resolve_cusips_to_tickers", return_value={"037833100": "AAPL"}):
        result = ingest_13f(mock_client, tracked_funds)

    assert result["written"] == 0


def test_ingest_13f_isolates_per_fund_failure():
    tracked_funds = [("Bad Fund", "0009999999"), ("Good Fund", "0001111111")]

    def fake_table(name):
        m = MagicMock()
        if name == "market_universe":
            m.select.return_value.execute.return_value.data = [{"ticker": "AAPL"}]
        elif name == "smart_money_13f":
            m.select.return_value.eq.return_value.execute.return_value.data = []
        return m

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    def fake_get_latest(cik):
        if cik == "0009999999":
            raise ConnectionError("SEC EDGAR timeout")
        return {"accession": "0001-A", "filing_date": "2026-05-15", "primary_document": "primary_doc.xml"}

    with patch("jobs.ingest_smart_money.sec_edgar.get_latest_13f_accession", side_effect=fake_get_latest), \
         patch("jobs.ingest_smart_money.sec_edgar.get_13f_infotable_document", return_value="53405.xml"), \
         patch("jobs.ingest_smart_money.sec_edgar.get_filing_document", return_value="<xml/>"), \
         patch("jobs.ingest_smart_money.sec_edgar.parse_13f_holdings",
               return_value=[{"cusip": "037833100", "issuer_name": "APPLE INC", "value": 1000, "shares": 100}]), \
         patch("jobs.ingest_smart_money.sec_edgar.resolve_cusips_to_tickers", return_value={"037833100": "AAPL"}):
        result = ingest_13f(mock_client, tracked_funds)

    assert result["funds_processed"] == 2
    assert result["written"] == 1  # only Good Fund's holding wrote successfully


def test_ingest_13f_marks_dropped_position_as_exited():
    tracked_funds = [("Test Fund", "0001111111")]

    tables = {}

    def fake_table(name):
        if name not in tables:
            m = MagicMock()
            if name == "market_universe":
                m.select.return_value.execute.return_value.data = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
            elif name == "smart_money_13f":
                # Fund previously held MSFT, but the new filing has no MSFT holding.
                m.select.return_value.eq.return_value.execute.return_value.data = [
                    {"ticker": "MSFT", "shares": 500, "cusip": "594918104"}
                ]
            tables[name] = m
        return tables[name]

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    with patch("jobs.ingest_smart_money.sec_edgar.get_latest_13f_accession",
               return_value={"accession": "0001-A", "filing_date": "2026-05-15", "primary_document": "primary_doc.xml"}), \
         patch("jobs.ingest_smart_money.sec_edgar.get_13f_infotable_document", return_value="53405.xml"), \
         patch("jobs.ingest_smart_money.sec_edgar.get_filing_document", return_value="<xml/>"), \
         patch("jobs.ingest_smart_money.sec_edgar.parse_13f_holdings",
               return_value=[{"cusip": "037833100", "issuer_name": "APPLE INC", "value": 1000, "shares": 100}]), \
         patch("jobs.ingest_smart_money.sec_edgar.resolve_cusips_to_tickers", return_value={"037833100": "AAPL"}):
        ingest_13f(mock_client, tracked_funds)

    upsert_calls = tables["smart_money_13f"].upsert.call_args_list
    exited_calls = [c for c in upsert_calls if isinstance(c[0][0], dict) and c[0][0].get("change_type") == "exited"]
    assert len(exited_calls) == 1
    assert exited_calls[0][0][0]["ticker"] == "MSFT"


def test_ingest_form4_stores_open_market_transactions():
    def fake_table(name):
        m = MagicMock()
        if name == "market_universe":
            m.select.return_value.execute.return_value.data = [{"ticker": "AAPL"}]
        return m

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    with patch("jobs.ingest_smart_money.sec_edgar.fetch_ticker_cik_map", return_value={"AAPL": "0000320193"}), \
         patch("jobs.ingest_smart_money.sec_edgar.get_recent_form4_filings",
               return_value=[{"accession": "0002-B", "filing_date": "2026-06-01", "primary_document": "ownership.xml"}]), \
         patch("jobs.ingest_smart_money.sec_edgar.get_filing_document", return_value="<xml/>"), \
         patch("jobs.ingest_smart_money.sec_edgar.parse_form4_transactions", return_value={
             "ticker": "AAPL",
             "transactions": [{"code": "P", "shares": 1000, "price": 190.0, "acquired_disposed": "A", "date": "2026-06-01"}],
         }):
        result = ingest_form4(mock_client, lookback_days=14)

    assert result["written"] == 1
    insider_calls = [c for c in mock_client.table.call_args_list if c[0][0] == "smart_money_insider"]
    assert len(insider_calls) >= 1


def test_ingest_form4_ignores_non_open_market_codes():
    def fake_table(name):
        m = MagicMock()
        if name == "market_universe":
            m.select.return_value.execute.return_value.data = [{"ticker": "AAPL"}]
        return m

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    with patch("jobs.ingest_smart_money.sec_edgar.fetch_ticker_cik_map", return_value={"AAPL": "0000320193"}), \
         patch("jobs.ingest_smart_money.sec_edgar.get_recent_form4_filings",
               return_value=[{"accession": "0002-B", "filing_date": "2026-06-01", "primary_document": "ownership.xml"}]), \
         patch("jobs.ingest_smart_money.sec_edgar.get_filing_document", return_value="<xml/>"), \
         patch("jobs.ingest_smart_money.sec_edgar.parse_form4_transactions", return_value={
             "ticker": "AAPL",
             "transactions": [{"code": "G", "shares": 160, "price": 0.0, "acquired_disposed": "D", "date": "2026-05-22"}],
         }):
        result = ingest_form4(mock_client, lookback_days=14)

    assert result["written"] == 0  # gift ('G') is not an open-market buy/sell signal


def test_ingest_form4_skips_ticker_without_known_cik():
    def fake_table(name):
        m = MagicMock()
        if name == "market_universe":
            m.select.return_value.execute.return_value.data = [{"ticker": "UNKNOWNTICK"}]
        return m

    mock_client = MagicMock()
    mock_client.table.side_effect = fake_table

    with patch("jobs.ingest_smart_money.sec_edgar.fetch_ticker_cik_map", return_value={}), \
         patch("jobs.ingest_smart_money.sec_edgar.get_recent_form4_filings") as mock_get_filings:
        result = ingest_form4(mock_client, lookback_days=14)

    assert result["written"] == 0
    mock_get_filings.assert_not_called()
