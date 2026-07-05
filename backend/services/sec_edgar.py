"""SEC EDGAR client for the smart-money layer (Phase 2b).

Two filing types, two different resolution problems:
  - 13F-HR (quarterly institutional holdings): reports positions by CUSIP,
    not ticker -- resolved via OpenFIGI's free CUSIP-mapping endpoint.
  - Form 4 (insider transactions): the issuer's ticker is given directly
    in the XML (issuerTradingSymbol), no resolution needed.

All formats below were verified against real SEC EDGAR/OpenFIGI responses
during development (see Phase 2b design notes), not guessed from docs.
SEC requires a descriptive User-Agent with contact info on every request.
"""
import os
import sys
import xml.etree.ElementTree as ET

import requests

_SEC_BASE = "https://data.sec.gov"
_SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
_OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
_OPENFIGI_BATCH_SIZE = 100


def _sec_headers() -> dict:
    ua = os.getenv("SEC_EDGAR_USER_AGENT", "TradeBotics contact@tradebotics.app")
    return {"User-Agent": ua}


def _sec_get(url: str) -> requests.Response:
    return requests.get(url, headers=_sec_headers(), timeout=15)


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_13f_holdings(xml_text: str) -> list[dict]:
    """Parses a 13F information-table XML into holdings aggregated by CUSIP
    (a single filing can list the same CUSIP multiple times across
    sub-adviser/other-manager splits)."""
    root = ET.fromstring(xml_text)
    by_cusip: dict[str, dict] = {}

    for info_table in root:
        if _strip_ns(info_table.tag) != "infoTable":
            continue
        fields = {_strip_ns(child.tag): child for child in info_table}

        cusip = fields["cusip"].text.strip()
        issuer_name = fields["nameOfIssuer"].text.strip() if "nameOfIssuer" in fields else ""
        value = int(fields["value"].text.strip())
        shares_el = fields.get("shrsOrPrnAmt")
        shares = 0
        if shares_el is not None:
            for child in shares_el:
                if _strip_ns(child.tag) == "sshPrnamt":
                    shares = int(child.text.strip())

        if cusip not in by_cusip:
            by_cusip[cusip] = {"cusip": cusip, "issuer_name": issuer_name, "value": 0, "shares": 0}
        by_cusip[cusip]["value"] += value
        by_cusip[cusip]["shares"] += shares

    return list(by_cusip.values())


def parse_form4_transactions(xml_text: str) -> dict:
    """Parses a Form 4 ownership XML into {ticker, transactions: [...]}.
    Only non-derivative (open-market) transactions are extracted -- that's
    the actionable "insider bought/sold on the open market" signal."""
    root = ET.fromstring(xml_text)
    ticker = None
    transactions = []

    for issuer in root:
        if _strip_ns(issuer.tag) != "issuer":
            continue
        for child in issuer:
            if _strip_ns(child.tag) == "issuerTradingSymbol":
                ticker = child.text.strip() if child.text else None

    for table in root:
        if _strip_ns(table.tag) != "nonDerivativeTable":
            continue
        for txn in table:
            if _strip_ns(txn.tag) != "nonDerivativeTransaction":
                continue
            txn_fields = {_strip_ns(child.tag): child for child in txn}

            code = None
            coding = txn_fields.get("transactionCoding")
            if coding is not None:
                for child in coding:
                    if _strip_ns(child.tag) == "transactionCode":
                        code = child.text.strip() if child.text else None

            shares = price = None
            acquired_disposed = None
            date = None
            amounts = txn_fields.get("transactionAmounts")
            if amounts is not None:
                for child in amounts:
                    tag = _strip_ns(child.tag)
                    value_el = child.find("value") if child.find("value") is not None else child
                    text = value_el.text if value_el is not None else None
                    if tag == "transactionShares" and text:
                        shares = int(float(text))
                    elif tag == "transactionPricePerShare" and text:
                        price = float(text)
                    elif tag == "transactionAcquiredDisposedCode" and text:
                        acquired_disposed = text.strip()

            date_el = txn_fields.get("transactionDate")
            if date_el is not None:
                value_el = date_el.find("value")
                if value_el is not None and value_el.text:
                    date = value_el.text.strip()

            transactions.append({
                "code": code, "shares": shares, "price": price,
                "acquired_disposed": acquired_disposed, "date": date,
            })

    return {"ticker": ticker, "transactions": transactions}


def get_latest_13f_accession(cik: str) -> dict | None:
    """Fetches a filer's submissions and returns its most recent 13F-HR
    (excluding amendments -- 13F-HR/A restates a prior quarter, not new
    information for our purposes). Returns None if no 13F-HR is found."""
    resp = _sec_get(f"{_SEC_BASE}/submissions/CIK{cik}.json")
    recent = resp.json()["filings"]["recent"]

    best = None
    for form, accession, filing_date, primary_doc in zip(
        recent["form"], recent["accessionNumber"], recent["filingDate"], recent["primaryDocument"]
    ):
        if form != "13F-HR":
            continue
        if best is None or filing_date > best["filing_date"]:
            best = {"accession": accession, "filing_date": filing_date, "primary_document": primary_doc}
    return best


def get_recent_form4_filings(cik: str, since_date: str) -> list[dict]:
    """Fetches a filer's submissions and returns Form 4 filings on or after
    since_date (YYYY-MM-DD)."""
    resp = _sec_get(f"{_SEC_BASE}/submissions/CIK{cik}.json")
    recent = resp.json()["filings"]["recent"]

    results = []
    for form, accession, filing_date, primary_doc in zip(
        recent["form"], recent["accessionNumber"], recent["filingDate"], recent["primaryDocument"]
    ):
        if form != "4":
            continue
        if filing_date >= since_date:
            results.append({"accession": accession, "filing_date": filing_date, "primary_document": primary_doc})
    return results


def get_13f_infotable_document(cik: str, accession: str) -> str | None:
    """A 13F-HR filing's primary_document (from submissions JSON) is the
    cover page, not the holdings. The actual information table is a
    separately-named XML file in the same accession folder -- found by
    listing the folder and excluding the known cover-page/index files."""
    accession_no_dashes = accession.replace("-", "")
    cik_no_leading_zeros = str(int(cik))
    url = f"{_SEC_ARCHIVES}/{cik_no_leading_zeros}/{accession_no_dashes}/index.json"
    resp = _sec_get(url)
    items = resp.json()["directory"]["item"]

    for item in items:
        name = item["name"]
        if name == "primary_doc.xml":
            continue
        if name.endswith(".xml"):
            return name
    return None


def fetch_ticker_cik_map() -> dict[str, str]:
    """Downloads SEC's free ticker->CIK reference file and returns a
    {ticker: zero-padded-10-digit-CIK} map. Used to look up Form 4 filings
    per ticker without adding a CIK column to market_universe."""
    resp = _sec_get("https://www.sec.gov/files/company_tickers.json")
    data = resp.json()
    return {
        entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
        for entry in data.values()
    }


def get_filing_document(cik: str, accession: str, document: str) -> str:
    """Downloads one document from a filing's accession folder."""
    accession_no_dashes = accession.replace("-", "")
    cik_no_leading_zeros = str(int(cik))
    url = f"{_SEC_ARCHIVES}/{cik_no_leading_zeros}/{accession_no_dashes}/{document}"
    resp = _sec_get(url)
    return resp.text


def resolve_cusips_to_tickers(cusips: list[str]) -> dict[str, str]:
    """Resolves CUSIPs to US-listed tickers via OpenFIGI's free mapping
    endpoint (no API key required, rate-limited). Fails open (returns {})
    on network errors or unresolved CUSIPs -- a resolution miss should
    just mean that holding is skipped, not that the whole job aborts."""
    if not cusips:
        return {}

    result: dict[str, str] = {}
    try:
        for i in range(0, len(cusips), _OPENFIGI_BATCH_SIZE):
            batch = cusips[i:i + _OPENFIGI_BATCH_SIZE]
            jobs = [{"idType": "ID_CUSIP", "idValue": c} for c in batch]
            resp = requests.post(_OPENFIGI_URL, json=jobs, timeout=15)
            mappings = resp.json()
            for cusip, mapping in zip(batch, mappings):
                data = mapping.get("data") or []
                us_match = next((d for d in data if d.get("exchCode") == "US"), None)
                if us_match and us_match.get("ticker"):
                    result[cusip] = us_match["ticker"]
    except Exception as e:
        print(f"[sec_edgar] OpenFIGI resolution failed: {e}", file=sys.stderr)
        return {}

    return result
