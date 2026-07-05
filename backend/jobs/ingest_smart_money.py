"""Smart-money ingestion job (Phase 2b): pulls 13F holdings from a curated
list of tracked hedge funds and Form 4 insider transactions for the app's
own ticker universe, writing to smart_money_13f / smart_money_insider.
13F filings are quarterly and Form 4s are ad hoc, so this runs on its own
(weekly) schedule -- separate from the nightly stock/compute jobs.
Run via GitHub Actions:
    cd backend && python -m jobs.ingest_smart_money
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in the environment.
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

from supabase import create_client

from services import sec_edgar

# CIKs verified directly against SEC EDGAR during development (not guessed).
TRACKED_FUNDS = [
    ("Berkshire Hathaway", "0001067983"),
    ("Pershing Square Capital Management", "0001336528"),
    ("Scion Asset Management", "0001649339"),
    ("Third Point", "0001040273"),
    ("Greenlight Capital", "0001079114"),
    ("Tiger Global Management", "0001167483"),
    ("Duquesne Family Office", "0001536411"),
    ("Baupost Group", "0001061768"),
]

FORM4_LOOKBACK_DAYS = 14
_OPEN_MARKET_CODES = {"P", "S"}  # purchase / sale -- the only voluntary, actionable insider signal


def _classify_change(prev_shares: int | None, shares: int) -> str:
    if prev_shares is None:
        return "new"
    if shares == 0:
        return "exited"
    if shares > prev_shares:
        return "increased"
    if shares < prev_shares:
        return "decreased"
    return "unchanged"


def ingest_13f(supabase_client, tracked_funds=TRACKED_FUNDS) -> dict:
    """For each tracked fund, fetches its latest 13F-HR, resolves CUSIPs to
    tickers already in our universe (holdings outside it aren't actionable
    here), classifies each holding's change vs the fund's previous
    snapshot, and upserts. Positions the fund no longer holds are marked
    'exited' rather than deleted, so history isn't lost."""
    universe_resp = supabase_client.table("market_universe").select("ticker").execute()
    known_tickers = {r["ticker"] for r in universe_resp.data}

    written = 0
    for fund_name, cik in tracked_funds:
        try:
            latest = sec_edgar.get_latest_13f_accession(cik)
            if latest is None:
                continue

            info_doc = sec_edgar.get_13f_infotable_document(cik, latest["accession"])
            if info_doc is None:
                continue
            holdings_xml = sec_edgar.get_filing_document(cik, latest["accession"], info_doc)
            holdings = sec_edgar.parse_13f_holdings(holdings_xml)

            cusips = [h["cusip"] for h in holdings]
            cusip_to_ticker = sec_edgar.resolve_cusips_to_tickers(cusips)

            existing_resp = (
                supabase_client.table("smart_money_13f").select("ticker,shares,cusip")
                .eq("fund_cik", cik).execute()
            )
            existing = {r["ticker"]: r for r in existing_resp.data}
            seen_tickers = set()
            now_iso = datetime.now(timezone.utc).isoformat()

            for h in holdings:
                ticker = cusip_to_ticker.get(h["cusip"])
                if not ticker or ticker not in known_tickers:
                    continue
                seen_tickers.add(ticker)
                prev = existing.get(ticker)
                prev_shares = prev["shares"] if prev else None
                change_type = _classify_change(prev_shares, h["shares"])

                supabase_client.table("smart_money_13f").upsert({
                    "fund_cik": cik, "fund_name": fund_name, "ticker": ticker, "cusip": h["cusip"],
                    "shares": h["shares"], "value": h["value"],
                    "prev_shares": prev_shares, "prev_value": prev["value"] if prev and "value" in prev else None,
                    "change_type": change_type, "filing_date": latest["filing_date"],
                    "accession": latest["accession"], "updated_at": now_iso,
                }, on_conflict="fund_cik,ticker").execute()
                written += 1

            for ticker, prev in existing.items():
                if ticker in seen_tickers or prev.get("shares") == 0:
                    continue
                supabase_client.table("smart_money_13f").upsert({
                    "fund_cik": cik, "fund_name": fund_name, "ticker": ticker, "cusip": prev.get("cusip") or "",
                    "shares": 0, "value": 0, "prev_shares": prev["shares"], "prev_value": None,
                    "change_type": "exited", "filing_date": latest["filing_date"],
                    "accession": latest["accession"], "updated_at": now_iso,
                }, on_conflict="fund_cik,ticker").execute()
                written += 1
        except Exception as e:
            print(f"[ingest_smart_money] 13F ingest failed for {fund_name}: {e}", file=sys.stderr)

    return {"funds_processed": len(tracked_funds), "written": written}


def ingest_form4(supabase_client, lookback_days: int = FORM4_LOOKBACK_DAYS) -> dict:
    """For each ticker in our universe, fetches recent Form 4 filings from
    its own issuer CIK (resolved via SEC's free ticker->CIK map) and stores
    open-market insider buy/sell transactions."""
    universe_resp = supabase_client.table("market_universe").select("ticker").execute()
    tickers = [r["ticker"] for r in universe_resp.data]
    ticker_to_cik = sec_edgar.fetch_ticker_cik_map()
    since = (date.today() - timedelta(days=lookback_days)).isoformat()

    written = 0
    for ticker in tickers:
        cik = ticker_to_cik.get(ticker)
        if not cik:
            continue
        try:
            filings = sec_edgar.get_recent_form4_filings(cik, since_date=since)
            for filing in filings:
                xml = sec_edgar.get_filing_document(cik, filing["accession"], filing["primary_document"])
                parsed = sec_edgar.parse_form4_transactions(xml)
                for txn in parsed["transactions"]:
                    if txn["code"] not in _OPEN_MARKET_CODES or txn["shares"] is None:
                        continue
                    supabase_client.table("smart_money_insider").upsert({
                        "ticker": parsed["ticker"] or ticker, "transaction_code": txn["code"],
                        "shares": txn["shares"], "price": txn["price"],
                        "acquired_disposed": txn["acquired_disposed"], "transaction_date": txn["date"],
                        "accession": filing["accession"],
                    }, on_conflict="accession,ticker,transaction_date,transaction_code,shares").execute()
                    written += 1
        except Exception as e:
            print(f"[ingest_smart_money] Form4 ingest failed for {ticker}: {e}", file=sys.stderr)

    return {"tickers_processed": len(tickers), "written": written}


if __name__ == "__main__":
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    thirteenf_summary = ingest_13f(client)
    print(f"[ingest_smart_money] 13F done: {thirteenf_summary}", file=sys.stderr)

    form4_summary = ingest_form4(client)
    print(f"[ingest_smart_money] Form4 done: {form4_summary}", file=sys.stderr)
