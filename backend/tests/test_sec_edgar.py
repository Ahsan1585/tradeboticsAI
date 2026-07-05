"""Unit tests for the SEC EDGAR client (Phase 2b smart-money layer).
All network calls are mocked -- these formats were verified against real
SEC EDGAR/OpenFIGI responses during development, not guessed."""
from unittest.mock import MagicMock, patch

from services import sec_edgar


_13F_XML = """<?xml version="1.0"?>
<informationTable xmlns="https://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>ALLY FINL INC</nameOfIssuer>
    <cusip>02005N100</cusip>
    <value>498992850</value>
    <shrsOrPrnAmt><sshPrnamt>12719675</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>ALLY FINL INC</nameOfIssuer>
    <cusip>02005N100</cusip>
    <value>109996016</value>
    <shrsOrPrnAmt><sshPrnamt>2803875</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>3000000</value>
    <shrsOrPrnAmt><sshPrnamt>15000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
  </infoTable>
</informationTable>"""

_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
    <issuer>
        <issuerCik>0001067983</issuerCik>
        <issuerName>BERKSHIRE HATHAWAY INC</issuerName>
        <issuerTradingSymbol>BRK.B</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId><rptOwnerName>BUFFETT WARREN E</rptOwnerName></reportingOwnerId>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <transactionDate><value>2026-05-22</value></transactionDate>
            <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
            <transactionAmounts>
                <transactionShares><value>1000</value></transactionShares>
                <transactionPricePerShare><value>50.25</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
            <transactionDate><value>2026-05-23</value></transactionDate>
            <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
            <transactionAmounts>
                <transactionShares><value>200</value></transactionShares>
                <transactionPricePerShare><value>51.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>"""


def _submissions_json(forms, accessions, dates, primary_docs):
    return {"filings": {"recent": {"form": forms, "accessionNumber": accessions,
                                    "filingDate": dates, "primaryDocument": primary_docs}}}


# --- parse_13f_holdings -------------------------------------------------------

def test_parse_13f_holdings_aggregates_by_cusip():
    holdings = sec_edgar.parse_13f_holdings(_13F_XML)
    ally = next(h for h in holdings if h["cusip"] == "02005N100")
    assert ally["value"] == 498992850 + 109996016
    assert ally["shares"] == 12719675 + 2803875
    assert ally["issuer_name"] == "ALLY FINL INC"


def test_parse_13f_holdings_keeps_separate_cusips():
    holdings = sec_edgar.parse_13f_holdings(_13F_XML)
    cusips = {h["cusip"] for h in holdings}
    assert cusips == {"02005N100", "037833100"}


def test_parse_13f_holdings_empty_xml_returns_empty_list():
    empty = "<?xml version='1.0'?><informationTable xmlns='https://www.sec.gov/edgar/document/thirteenf/informationtable'></informationTable>"
    assert sec_edgar.parse_13f_holdings(empty) == []


# --- parse_form4_transactions -------------------------------------------------

def test_parse_form4_transactions_extracts_ticker_directly():
    result = sec_edgar.parse_form4_transactions(_FORM4_XML)
    assert result["ticker"] == "BRK.B"


def test_parse_form4_transactions_extracts_buys_and_sells():
    result = sec_edgar.parse_form4_transactions(_FORM4_XML)
    codes = [t["code"] for t in result["transactions"]]
    assert codes == ["P", "S"]
    buy = result["transactions"][0]
    assert buy["shares"] == 1000
    assert buy["price"] == 50.25
    assert buy["acquired_disposed"] == "A"


def test_parse_form4_transactions_no_transactions_returns_empty_list():
    xml = """<?xml version="1.0"?><ownershipDocument>
        <issuer><issuerTradingSymbol>XYZ</issuerTradingSymbol></issuer>
    </ownershipDocument>"""
    result = sec_edgar.parse_form4_transactions(xml)
    assert result["ticker"] == "XYZ"
    assert result["transactions"] == []


# --- get_latest_13f_accession --------------------------------------------------

def test_get_latest_13f_accession_finds_most_recent_non_amendment():
    submissions = _submissions_json(
        forms=["13F-HR/A", "13F-HR", "13F-HR", "4"],
        accessions=["0001-A", "0001193125-26-226661", "0001193125-26-054580", "0009-X"],
        dates=["2026-06-01", "2026-05-15", "2026-02-17", "2026-01-01"],
        primary_docs=["primary_doc.xml", "primary_doc.xml", "primary_doc.xml", "ownership.xml"],
    )
    with patch("services.sec_edgar._sec_get") as mock_get:
        mock_get.return_value.json.return_value = submissions
        result = sec_edgar.get_latest_13f_accession("0001067983")

    assert result["accession"] == "0001193125-26-226661"
    assert result["filing_date"] == "2026-05-15"


def test_get_latest_13f_accession_returns_none_when_no_filings():
    submissions = _submissions_json(forms=["4"], accessions=["0009-X"], dates=["2026-01-01"], primary_docs=["ownership.xml"])
    with patch("services.sec_edgar._sec_get") as mock_get:
        mock_get.return_value.json.return_value = submissions
        result = sec_edgar.get_latest_13f_accession("0001067983")

    assert result is None


# --- get_recent_form4_filings -------------------------------------------------

def test_get_recent_form4_filings_filters_by_date_and_form():
    submissions = _submissions_json(
        forms=["4", "10-K", "4", "4"],
        accessions=["0001-A", "0002-B", "0003-C", "0004-D"],
        dates=["2026-05-22", "2026-04-01", "2026-06-01", "2025-01-01"],
        primary_docs=["ownership.xml", "doc.htm", "ownership.xml", "ownership.xml"],
    )
    with patch("services.sec_edgar._sec_get") as mock_get:
        mock_get.return_value.json.return_value = submissions
        result = sec_edgar.get_recent_form4_filings("0001067983", since_date="2026-05-01")

    accessions = {r["accession"] for r in result}
    assert accessions == {"0001-A", "0003-C"}  # only form=4 filed on/after since_date


# --- resolve_cusips_to_tickers (OpenFIGI) --------------------------------------

def test_resolve_cusips_to_tickers_picks_us_exchange():
    fake_response = MagicMock()
    fake_response.json.return_value = [
        {"data": [
            {"ticker": "ALLY", "exchCode": "US"},
            {"ticker": "ALLY", "exchCode": "UA"},
        ]},
    ]
    with patch("services.sec_edgar.requests.post", return_value=fake_response) as mock_post:
        result = sec_edgar.resolve_cusips_to_tickers(["02005N100"])

    assert result == {"02005N100": "ALLY"}
    mock_post.assert_called_once()


def test_resolve_cusips_to_tickers_handles_unresolved_cusip():
    fake_response = MagicMock()
    fake_response.json.return_value = [{"warning": "No identifier found."}]
    with patch("services.sec_edgar.requests.post", return_value=fake_response):
        result = sec_edgar.resolve_cusips_to_tickers(["000000000"])

    assert result == {}


def test_resolve_cusips_to_tickers_fails_open_on_network_error():
    with patch("services.sec_edgar.requests.post", side_effect=ConnectionError("timeout")):
        result = sec_edgar.resolve_cusips_to_tickers(["02005N100"])
    assert result == {}


def test_resolve_cusips_to_tickers_empty_input_skips_network_call():
    with patch("services.sec_edgar.requests.post") as mock_post:
        result = sec_edgar.resolve_cusips_to_tickers([])
    assert result == {}
    mock_post.assert_not_called()


# --- get_13f_infotable_document -----------------------------------------------

def test_get_13f_infotable_document_picks_non_primary_xml():
    index_json = {"directory": {"item": [
        {"name": "0001193125-26-226661-index.html"},
        {"name": "0001193125-26-226661.txt"},
        {"name": "53405.xml"},
        {"name": "primary_doc.xml"},
    ]}}
    with patch("services.sec_edgar._sec_get") as mock_get:
        mock_get.return_value.json.return_value = index_json
        result = sec_edgar.get_13f_infotable_document("0001067983", "0001193125-26-226661")
    assert result == "53405.xml"


def test_get_13f_infotable_document_returns_none_when_only_primary_doc():
    index_json = {"directory": {"item": [{"name": "primary_doc.xml"}, {"name": "filing-index.html"}]}}
    with patch("services.sec_edgar._sec_get") as mock_get:
        mock_get.return_value.json.return_value = index_json
        result = sec_edgar.get_13f_infotable_document("0001067983", "0001193125-26-226661")
    assert result is None


# --- fetch_ticker_cik_map ------------------------------------------------------

def test_fetch_ticker_cik_map_normalizes_ticker_and_pads_cik():
    fake_json = {
        "0": {"cik_str": 1067983, "ticker": "brk-b", "title": "Berkshire Hathaway"},
        "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple"},
    }
    with patch("services.sec_edgar._sec_get") as mock_get:
        mock_get.return_value.json.return_value = fake_json
        result = sec_edgar.fetch_ticker_cik_map()
    assert result["BRK-B"] == "0001067983"
    assert result["AAPL"] == "0000320193"
