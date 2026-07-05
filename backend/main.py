from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import math
import time
from datetime import datetime, timezone, timedelta
import yfinance as yf
from dotenv import load_dotenv
from supabase import create_client, Client
import sys
import pandas as pd
import asyncio
import random
import httpx
from contextlib import asynccontextmanager
import requests
import io
load_dotenv()

from llm import generate_text, llm_available
from auth import get_current_user
from services.metrics import safe_float, sanitize_nans, calculate_quant_metrics, get_support_resistance

# ==========================================
# --- KEEP ALIVE CONFIGURATION ---
# ==========================================
RENDER_APP_URL = "https://tradebotics-api.onrender.com/market-briefing" 

async def keep_alive_loop():
    """Loops infinitely every 10 minutes to ping the public URL and prevent sleep."""
    await asyncio.sleep(30)
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                print(f"[{datetime.now()}] 🛰️ SENDING KEEP-ALIVE PING TO PUBLIC URL...", file=sys.stderr)
                response = await client.get(RENDER_APP_URL, timeout=10.0)
                print(f"[{datetime.now()}] 💚 KEEP-ALIVE SUCCESS: Status {response.status_code}", file=sys.stderr)
            except Exception as e:
                print(f"[{datetime.now()}] ⚠️ KEEP-ALIVE PING FAILED: {e}", file=sys.stderr)
            
            await asyncio.sleep(600)

# ==========================================
# --- 12-CYLINDER QUANT ENGINE (ONE SOURCE OF TRUTH) ---
# ==========================================
# ==========================================
# --- THE STEALTH DATA WORKER ---
# ==========================================
def fetch_ticker_data_sync(t):
    """Runs in a separate thread so it doesn't freeze the FastAPI server."""
    stock = yf.Ticker(t)
    hist = stock.history(period="1mo")
    try:
        info = stock.info
    except Exception:
        info = {}
    return stock, hist, info

async def staleness_worker_loop():
    """Runs every 60 minutes. Sweeps the oldest 50 tickers, scores them, and upserts to Supabase."""
    await asyncio.sleep(60)
    
    while True:
        if supabase:
            try:
                print(f"[{datetime.now()}] 🤖 WORKER WAKING UP: Initiating Staleness Sweep...", file=sys.stderr)
                
                response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(50).execute()
                stale_tickers = [row['ticker'] for row in response.data]
                
                if not stale_tickers:
                    print(f"[{datetime.now()}] ⚠️ EMPTY QUEUE: Seeding database from Wikipedia...", file=sys.stderr)
                    universe = await asyncio.to_thread(get_market_universe)
                    print(f"[{datetime.now()}] 📦 Scraped {len(universe)} tickers. Breaking into safe batches of 50...", file=sys.stderr)
                    
                    for i in range(0, len(universe), 50):
                        chunk = universe[i:i + 50]
                        seed_data = [{'ticker': t} for t in chunk]
                        try:
                            supabase.table('market_universe').upsert(seed_data).execute()
                            print(f"✅ Batch {i} to {i+len(chunk)} inserted successfully.", file=sys.stderr)
                        except Exception as e:
                            print(f"❌ Failed to insert batch {i}: {e}", file=sys.stderr)
                        
                    response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(50).execute()
                    stale_tickers = [row['ticker'] for row in response.data]

                print(f"[{datetime.now()}] 🔍 WORKER SCANNING: Processing {len(stale_tickers)} tickers...", file=sys.stderr)
                
                for t in stale_tickers:
                    current_time = datetime.now(timezone.utc).isoformat()
                    
                    try:
                        # THREADED FETCH (Prevents API freeze)
                        stock, hist, info = await asyncio.to_thread(fetch_ticker_data_sync, t)
                        
                        clean_close = hist['Close'].dropna()

                        if clean_close.empty or len(clean_close) < 20:
                            supabase.table('market_universe').update({'last_scanned': current_time}).eq('ticker', t).execute()
                            continue
                            
                        price = float(clean_close.iloc[-1])
                        prev_price = float(clean_close.iloc[-2])
                        daily_change = ((price - prev_price) / prev_price) * 100
                        
                        # Unpack exactly 13 values returned by the math engine
                        (total_score, tech_score, fund_score, _, _, _, _, _, _, _, sector, pe, _) = calculate_quant_metrics(hist, info, stock, price, prev_price, t)
                        
                        supabase.table('market_universe').upsert(sanitize_nans({
                            'ticker': t,
                            'price': round(price, 2),
                            'daily_change': round(daily_change, 2),
                            'tech_score': tech_score,
                            'fund_score': fund_score,
                            'sector': sector,
                            'pe': round(pe, 2) if pe else 0,
                            'last_scanned': current_time
                        })).execute()
                        
                        print(f"✅ Successfully updated {t}", file=sys.stderr)
                        
                    except Exception as e:
                        print(f"❌ Error processing {t}: {e}. Advancing queue...", file=sys.stderr)
                        if "Not Found" in str(e) or "delisted" in str(e).lower():
                            supabase.table('market_universe').delete().eq('ticker', t).execute()
                        else:
                            supabase.table('market_universe').update({'last_scanned': current_time}).eq('ticker', t).execute()
                        continue
                        
                print(f"[{datetime.now()}] ✅ WORKER FINISHED: Queue updated. Sleeping for 60 minutes.", file=sys.stderr)
                await asyncio.sleep(3600)
                
            except Exception as e:
                print(f"❌ CRITICAL WORKER ERROR: {e}", file=sys.stderr)
                print("Worker crashed. Reviving in 60 seconds...", file=sys.stderr)
                await asyncio.sleep(60) 
        else:
            await asyncio.sleep(60)

@asynccontextmanager
async def lifecycle(app: FastAPI):
    asyncio.create_task(keep_alive_loop())
    asyncio.create_task(staleness_worker_loop())
    yield

app = FastAPI(lifespan=lifecycle)

# Explicit origins only. Set FRONTEND_ORIGINS on Render, e.g.:
# FRONTEND_ORIGINS=https://your-app.vercel.app,http://localhost:3000
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CACHE ---
market_cache = {}
MARKET_CACHE_TTL = 60 
SCREENER_CACHE = {}

# --- SUPABASE CONFIGURATION ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") 

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        supabase = None
else:
    supabase = None

# --- AI CONFIGURATION ---
# LLM calls go through llm.py (Anthropic Claude, default claude-haiku-4-5).
# The identity of the requester comes from auth.get_current_user (verified JWT),
# never from client-supplied user_id fields.

# --- REQUEST MODELS ---
class TradeRequest(BaseModel):
    ticker: str
    trade_type: str
    amount: float
    mode: str

class ScreenerRequest(BaseModel):
    trade_style: str
    risk_level: str

class TranslationRequest(BaseModel):
    ticker: str
    data_context: Dict[str, Any]

class SummaryRequest(BaseModel):
    title: str
    ticker: str
    content: str

class SwapRequest(BaseModel):
    ticker: str
    shares: float
    price: float

class PortfolioRequest(BaseModel):
    holdings: List[Dict[str, Any]]
    trade_style: str = "Long Term"

# --- 30-MINUTE AI CACHE ENGINE ---
def check_ai_cache(cache_key: str) -> dict | None:
    if not supabase: return None
    try:
        response = supabase.table('ai_scan_cache').select('*').eq('cache_key', cache_key).execute()
        if response.data:
            record = response.data[0]
            last_scanned = datetime.fromisoformat(record['last_scanned'].replace('Z', '+00:00'))
            time_diff = (datetime.now(timezone.utc) - last_scanned).total_seconds()
            
            if time_diff < 1800:
                print(f"CACHE HIT [{cache_key}]: Serving from memory. Saves AI Tokens.", file=sys.stderr)
                return record['cached_response']
    except Exception as e:
        print(f"[CACHE] lookup failed for {cache_key}: {e}", file=sys.stderr)
    return None

def update_ai_cache(cache_key: str, payload: dict):
    if not supabase: return
    try:
        supabase.table('ai_scan_cache').upsert({
            'cache_key': cache_key,
            'last_scanned': datetime.now(timezone.utc).isoformat(),
            'cached_response': payload
        }).execute()
    except Exception as e:
        print(f"[CACHE] update failed for {cache_key}: {e}", file=sys.stderr)

# ==========================================
# --- AI TOKEN ACCOUNTING (ATOMIC) ---
# ==========================================
def get_token_balance(user_id: str) -> int:
    profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Operative profile not found.")
    return int(profile_res.data[0]['ai_token_balance'])

def debit_tokens(user_id: str, cost: int) -> int:
    """Atomically debits tokens via the debit_tokens Postgres RPC
    (migrations/001_debit_tokens.sql). Returns the new balance, or raises 402."""
    res = supabase.rpc('debit_tokens', {'p_user_id': user_id, 'p_cost': cost}).execute()
    new_balance = res.data if isinstance(res.data, int) else -1
    if new_balance < 0:
        raise HTTPException(status_code=402, detail=f"INSUFFICIENT BANDWIDTH. {cost} Tokens required.")
    return new_balance

def get_market_universe():
    """Fetches unique tickers from S&P 500, Nasdaq-100, and DJIA from Wikipedia."""
    all_tickers = set()
    sources = [
        {"url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "col": "Symbol"},
        {"url": "https://en.wikipedia.org/wiki/Nasdaq-100", "col": "Ticker"},
        {"url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", "col": "Symbol"}
    ]
    headers = {'User-Agent': 'TradeBoticsApp/1.0 (Data Scraper)'}
    
    for source in sources:
        try:
            response = requests.get(source["url"], headers=headers, timeout=15)
            response.raise_for_status()
            tables = pd.read_html(io.StringIO(response.text))
            
            target_df = None
            target_col_name = None
            
            for df in tables:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
                for col in df.columns:
                    if source["col"].lower() in str(col).lower():
                        target_df = df
                        target_col_name = col
                        break
                if target_df is not None: break
            
            if target_df is not None and target_col_name is not None:
                tickers = target_df[target_col_name].tolist()
                for t in tickers:
                    clean_t = str(t).replace('.', '-').strip()
                    if isinstance(clean_t, str) and 1 <= len(clean_t) <= 5 and clean_t.replace('-', '').isalpha():
                        all_tickers.add(clean_t)
        except Exception:
            pass
            
    if len(all_tickers) < 50:
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "TSLA", "AVGO",
            "JPM", "V", "WMT", "UNH", "XOM", "MA", "PG", "JNJ", "HD", "COST", "MRK", "ABBV", 
            "CRM", "AMD", "CVX", "NFLX", "BAC", "KO", "PEP", "TMO", "LIN", "DIS", "ADBE"
        ]
        
    return list(all_tickers)

# --- ENDPOINTS ---

@app.get("/")
async def root_health_check():
    return {"status": "Matrix Online", "timestamp": datetime.now()}

@app.post("/run-screener")
async def execute_screener(req: ScreenerRequest):
    cache_key = f"{req.trade_style}_{req.risk_level}"
    current_time = datetime.now()

    if cache_key in SCREENER_CACHE:
        cached_results, timestamp = SCREENER_CACHE[cache_key]
        if current_time - timestamp < timedelta(minutes=5):
            return {"results": cached_results}

    try:
        response = supabase.table('market_universe').select('*').not_.is_('tech_score', 'null').execute()
        db_universe = response.data
        if not db_universe: return {"results": []}

        scored_candidates = []
        for row in db_universe:
            t = row['ticker']
            tech_score = row['tech_score']
            fund_score = row['fund_score']
            sector = row['sector']
            daily_change = row['daily_change']
            db_price = row['price']

            if req.risk_level == "Aggressive": total_score = (tech_score * 0.8) + (fund_score * 0.2)
            elif req.risk_level == "Conservative": total_score = (tech_score * 0.2) + (fund_score * 0.8)
            else: total_score = (tech_score * 0.5) + (fund_score * 0.5)

            style_bonus = 0
            if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "AMD", "COIN"]: style_bonus = 15 
            elif req.trade_style == "Long Term" and fund_score > 70: style_bonus = 5

            sort_weight = total_score + style_bonus + (daily_change * 0.01)
            final_display_score = max(10, min(99, math.ceil(total_score + style_bonus)))
            
            scored_candidates.append({
                "ticker": t,
                "score": final_display_score,
                "sort_weight": sort_weight,
                "sector": sector,
                "db_price": db_price, 
                "metrics": f"P/E: {row['pe']} | Sector: {sector}"
            })

        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        top_30 = scored_candidates[:30]

        final_results = []
        for candidate in top_30:
            try:
                stock = yf.Ticker(candidate['ticker'])
                hist = stock.history(period="1d")
                if not hist.empty: candidate['price'] = round(float(hist['Close'].iloc[-1]), 2)
                else: candidate['price'] = candidate['db_price']
            except Exception:
                candidate['price'] = candidate['db_price']
            candidate.pop('db_price', None)
            final_results.append(candidate)

        SCREENER_CACHE[cache_key] = (final_results, current_time)
        return {"results": final_results}
    except Exception:
        return {"results": []}

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str): 
    if not supabase: raise HTTPException(status_code=500, detail="Database connection offline.")

    ticker_upper = ticker.upper()
    now = time.time()

    if ticker_upper in market_cache:
        cached_time, cached_data = market_cache[ticker_upper]
        if now - cached_time < MARKET_CACHE_TTL: return cached_data

    try:
        stock = yf.Ticker(ticker_upper)
        hist = stock.history(period="3mo", prepost=True)
        clean_close = hist['Close'].dropna()
        if clean_close.empty: raise HTTPException(status_code=404, detail="Ticker data not found.")

        support, resistance = get_support_resistance(hist)

        current_price = round(float(clean_close.iloc[-1]), 2)
        prev_price = round(float(clean_close.iloc[-2]), 2) if len(clean_close) > 1 else current_price
        
        try: info = stock.info
        except Exception: info = {}

        # Unpack exactly 13 values returned by the math engine
        (total_score, tech_score, fund_score, extra_ledger, real_rsi, volume, avg_volume, vwap_proxy, upper_band, lower_band, sector, pe, margins) = calculate_quant_metrics(hist, info, stock, current_price, prev_price, ticker_upper)

        raw_mcap = info.get("marketCap")
        formatted_mcap = f"${raw_mcap / 1e12:.2f} Trillion" if raw_mcap and raw_mcap >= 1e12 else f"${raw_mcap / 1e9:.2f} Billion" if raw_mcap else "N/A"

        calendar = stock.calendar
        next_earnings = "Unknown"
        if calendar is not None:
            try:
                if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                    next_earnings = str(calendar['Earnings Date'][0])
                elif 'Earnings Date' in calendar and not calendar.empty:
                    next_earnings = str(calendar['Earnings Date'].iloc[0].date())
            except Exception: pass
        
        vol_surge = f"{round((volume / avg_volume) * 100, 1)}%" if avg_volume > 0 else "N/A"

        news_list = []
        try:
            finnhub_key = os.getenv("FINNHUB_API_KEY")
            if finnhub_key:
                import urllib.request
                import json
                end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker_upper}&from={start_date}&to={end_date}&token={finnhub_key}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    finnhub_news = json.loads(response.read().decode())
                    for item in finnhub_news[:5]:
                        pub_time = item.get("datetime", time.time())
                        hours_ago = int((time.time() - pub_time) / 3600)
                        date_str = "JUST NOW" if hours_ago <= 0 else f"{hours_ago} HR AGO"
                        news_list.append({
                            "title": item.get("headline", "Market Update"),
                            "publisher": item.get("source", "Financial Wire"),
                            "date": date_str,
                            "content": item.get("summary", item.get("url", ""))
                        })
        except Exception: pass

        rsi_status = "OVERBOUGHT" if real_rsi >= 70 else "OVERSOLD" if real_rsi <= 30 else "BULLISH" if tech_score > 50 else "BEARISH"

        ledger = [
            {"factor": "Momentum (RSI)", "val": str(real_rsi), "status": rsi_status, "reasoning": "RSI proxy suggests buying pressure." if tech_score > 50 else "RSI proxy suggests selling pressure."},
            {"factor": "Institutional Flow", "val": "High" if volume > avg_volume else "Low", "status": "BULLISH" if volume > avg_volume else "NEUTRAL", "reasoning": f"Volume of {volume:,} vs average of {avg_volume:,}."},
            {"factor": "MACD Divergence", "val": "Positive" if current_price > prev_price else "Negative", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": "Positive bullish crossover." if current_price > prev_price else "Bearish crossover trajectory."},
            {"factor": "VWAP Deviation", "val": f"${vwap_proxy}", "status": "BULLISH" if current_price > vwap_proxy else "BEARISH", "reasoning": f"Trading {'above' if current_price > vwap_proxy else 'below'} the VWAP."},
            {"factor": "Bollinger Band Width", "val": f"${lower_band} - ${upper_band}", "status": "NEUTRAL" if lower_band <= current_price <= upper_band else "VOLATILE", "reasoning": "Volatility bands range."},
            {"factor": "Mathematical Floor", "val": f"${round(support, 2)}", "status": "NEUTRAL", "reasoning": "Calculated base support level."},
            {"factor": "Mathematical Ceiling", "val": f"${round(resistance, 2)}", "status": "NEUTRAL", "reasoning": "Calculated major resistance."}
        ]
        ledger.extend(extra_ledger)

        # 1. CALCULATE THESE VARIABLES BEFORE FINAL_RESPONSE
        raw_insider = safe_float(info.get("heldPercentInsiders", 0))
        insider_str = f"{round(raw_insider * 100, 2)}%" if raw_insider > 0 else "N/A"
        
        raw_short = safe_float(info.get("shortPercentOfFloat", 0))
        short_str = f"{round(raw_short * 100, 2)}%" if raw_short > 0 else "N/A"
        
        target_price = safe_float(info.get("targetMeanPrice", 0))
        dte = safe_float(info.get("debtToEquity", 0))
        fcf = safe_float(info.get("freeCashflow", 0))

        # 2. DEFINE THE DICTIONARY
        final_response = sanitize_nans({
            "ticker": ticker_upper,
            "company_name": info.get("shortName", ticker_upper),
            "price": current_price,
            "score": total_score,
            "tech_score": int(tech_score),
            "fund_score": int(fund_score),
            "volume": f"{int(volume):,}",
            "vol_surge": vol_surge,
            "ledger": ledger,
            "news": news_list,  
            "ai_tactical": f"Market conditions evaluated for {ticker_upper}.",
            "support_level": round(support, 2),
            "resistance_level": round(resistance, 2),
            "fundamentals": {
                "market_cap": formatted_mcap, 
                "pe_ratio": str(round(pe, 2)) if pe > 0 else "N/A",
                "debt_equity": str(round(dte, 2)) if dte > 0 else "N/A",
                "margin": f"{round(margins * 100, 2)}%" if margins != 0 else "N/A",
                "insider_ownership": insider_str,
                "short_interest": short_str,
                "sentiment": "BULLISH" if target_price > 0 and current_price < target_price else "BEARISH" if target_price > 0 else "NEUTRAL",
                "cash_flow": "POSITIVE" if fcf > 0 else "NEGATIVE",
                "next_earnings": next_earnings
            }
        })
        
        # 🚀 3. SAVE TO CACHE BEFORE RETURNING
        market_cache[ticker_upper] = (now, final_response)
        return final_response
        
    except HTTPException as he: raise he
    except Exception as e:
        if 'Too Many Requests' in str(e) or '429' in str(e): raise HTTPException(status_code=429, detail="MARKET DATA RATE LIMIT EXCEEDED. Stand by.")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
async def translate_ai(req: TranslationRequest, user_id: str = Depends(get_current_user)):
    if not llm_available(): return {"analysis": "AI Node Offline."}
    try:
        cache_key = f"TRANSLATE_{req.ticker.upper()}"
        cached_data = check_ai_cache(cache_key)

        current_tokens = get_token_balance(user_id)

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens
            return cached_data

        if current_tokens < 3:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 3 Tokens required.")

        quant_score = safe_float(req.data_context.get('score', 0))
        
        # 🚨 ENHANCEMENT 5: DYNAMIC PRICE DISCOVERY
        price = safe_float(req.data_context.get('price', 0))
        support_raw = safe_float(req.data_context.get('support_level', 0))
        res_raw = safe_float(req.data_context.get('resistance_level', 0))
        
        support_str = f"${support_raw}" if support_raw > 0 else "Calculating Base..."
        
        if res_raw == 0 or price >= res_raw:
            low_t = round(price * 1.05, 2)
            high_t = round(price * 1.15, 2)
            res_str = f"Price Discovery (${low_t} - ${high_t})"
            price_instruction = f"CRITICAL: {req.ticker} is in PRICE DISCOVERY (above resistance). Project asymmetrical upside targets between ${low_t} and ${high_t} based on momentum, ignoring historical ceilings."
        else:
            res_str = f"${res_raw}"
            price_instruction = "Calculate the target price range realistically using the provided structural zones."

        prompt = f"Act as an elite quantitative analyst. Provide a definitive briefing on {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n- Current Price: ${price}\n- Quant Score: {quant_score}\n- Major Support (Floor): {support_str}\n- Major Resistance (Ceiling): {res_str}\n\n"
        prompt += f"TARGET DIRECTIVE:\n{price_instruction}\n\n"
        
        funds = req.data_context.get("fundamentals", {})
        if funds: prompt += f"FUNDAMENTAL DNA:\n- Market Cap: {funds.get('market_cap', 'N/A')}\n- P/E Ratio: {funds.get('pe_ratio', 'N/A')}\n- Margin: {funds.get('margin', 'N/A')}\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER:\n"
            for item in ledger: prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

        # 🚨 ENHANCEMENT 4: PYTHON OVERRIDE LOGIC (Stops WDC Buy Signal)
        is_overextended = False
        if ledger:
            for item in ledger:
                factor = str(item.get("factor", ""))
                val = str(item.get("val", ""))
                if "MACD Divergence" in factor and "Negative" in val:
                    is_overextended = True
                if "Options Flow" in factor and "Put Heavy" in val:
                    is_overextended = True

        if is_overextended:
            verdict_block = (
                "### 3. The Verdict\n"
                "[You MUST issue a 'WAIT FOR MEAN REVERSION' or 'SELL' signal. Explain that despite strong fundamentals, momentum is breaking down and smart money is hedging (buying puts), making the current price a high-risk bull trap. Anchor your target entry to the Mathematical Floor.]"
            )
            allowed_signals = "[SELL/TRIM/WAIT FOR MEAN REVERSION]"
        elif quant_score >= 90:
            verdict_block = (
                "### ⚡ CONVICTION RATING: STRONG BUY\n"
                "[Forcefully list exactly which premium parameters have aligned to create an asymmetrical upside opportunity.]"
            )
            allowed_signals = "[STRONG BUY/BUY]"
        else:
            verdict_block = "### 3. The Verdict\n[A punchy 2-sentence conclusion justifying your AI Signal]"
            allowed_signals = "[BUY/HOLD/TRIM/SELL]"

        prompt += (
            "\n🚨 CRITICAL FORMATTING MANDATE:\nOUTPUT STRICTLY IN CLEAN MARKDOWN. DO NOT use HTML tags.\n\n"
            "### 🎯 TARGET PRICE RANGE: $[low] - $[high]\n"
            f"### ⚖️ AI SIGNAL: {allowed_signals}\n"
            f"**📊 STRUCTURAL ZONES:** Support Floor at {support_str} | Resistance Ceiling at {res_str}\n\n"
            "---\n\n"
            "### 1. Macro & Fundamentals\n* **Valuation & Efficiency:** [1 sentence evaluating P/E, Margin, and Cash Flow]\n* **Balance Sheet & Sentiment:** [1 sentence on Debt-to-Equity and Sentiment]\n* **Catalyst Risk:** [1 sentence on Earnings Risk]\n\n"
            "### 2. Market Mechanics & Technicals\n* **Price Action & Consolidation:** [Analyze price vs structural zones]\n* **Smart Money & Options Flow:** [Synthesize Institutional Volume and Flow]\n* **Momentum (RSI & MACD):** [Synthesize ledger signals]\n\n"
            f"{verdict_block}"
        )
        raw_text = await generate_text(prompt, max_tokens=1200, purpose="deep_dive")

        disclaimer_html = (
            "<br><br><hr style='border-color: #1e293b; margin-top: 15px; margin-bottom: 15px;'/>"
            "<p style='font-size: 10px; color: #64748b; font-style: italic; line-height: 1.4; text-align: justify;'>"
            "<strong>LEGAL DISCLAIMER:</strong> The analysis and quantitative targets provided by TradeBotics AI are for "
            "informational and educational purposes only and do not constitute financial, investment, or trading advice. "
            "This output is generated by an artificial intelligence model relying on historical data, mathematical probabilities, "
            "and technical indicators, which cannot guarantee future performance. Trading equities involves significant risk of capital loss."
            "</p>"
        )

        if raw_text is None:
            # LLM unavailable/declined: do NOT charge the user.
            return {"analysis": "<h3>Execution Blocked</h3><ul><li>AI Node temporarily unavailable. No tokens were charged.</li></ul>", "remaining_tokens": current_tokens}
        ai_text = raw_text + disclaimer_html

        new_token_balance = debit_tokens(user_id, 3)

        final_response = {"analysis": ai_text, "remaining_tokens": new_token_balance}
        update_ai_cache(cache_key, final_response)
        return final_response

    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/exit-strategy")
async def generate_exit_strategy(req: TranslationRequest, user_id: str = Depends(get_current_user)):
    if not llm_available(): return {"analysis": "AI Node Offline."}
    try:
        current_tokens = get_token_balance(user_id)
        if current_tokens < 2: raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 2 Tokens required.")

        prompt = f"Act as a quantitative risk manager. Define a strict, scaled risk-management exit protocol for {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n- Current Price: ${req.data_context.get('price', 'N/A')}\n- Major Support (Floor): ${req.data_context.get('support_level', 'N/A')}\n- Major Resistance (Ceiling): ${req.data_context.get('resistance_level', 'N/A')}\n\n"
        prompt += "MANDATORY: You must base your Strike Zones and Exit Strategy strictly on these mathematical Support and Resistance levels.\n\n"

        prompt += (
            "\n🚨 CRITICAL MANDATE - SCALED EXIT STRATEGY REQUIRED:\n"
            "DO NOT provide a general summary. OUTPUT STRICTLY IN HTML FORMAT using this exact structure.\n"
            "CRITICAL: Explain your reasoning using simple, everyday language. Do NOT use dense institutional jargon.\n"
            "You must create a 'scaled' exit plan featuring two distinct profit-taking levels.\n\n"
            "<h3>Scaled Execution Protocol</h3>\n<ul>\n"
            "<li><strong>🟢 TAKE PROFIT 1 (Conservative):</strong> $[Price]. (Explain this as a safe place to take partial profits, typically right before or at the main resistance ceiling).</li>\n"
            "<li><strong>🟢 TAKE PROFIT 2 (Aggressive):</strong> $[Price]. (Explain this as the ultimate runner target if the stock breaks through the ceiling, based on current momentum).</li>\n"
            "<li><strong>🔴 HARD STOP LOSS (SL):</strong> $[Price]. (Explain why dropping below the mathematical support floor invalidates the trade).</li>\n"
            "<li><strong>⚖️ THESIS HEALTH:</strong> [Calculate the Risk/Reward Ratio using TP1 and the Stop Loss]. (Label as 'Aggressive' if R/R is < 1:1, 'Balanced' if 1:1 to 2:1, or 'High-Probability' if > 2:1).</li>\n"
            "<li><strong>⏱️ TIME HORIZON:</strong> [State the estimated time in days/weeks for this thesis to play out].</li>\n"
            "</ul>"
        )
        raw_text = await generate_text(prompt, max_tokens=1000, purpose="exit_strategy")

        disclaimer_html = (
            "<br><br><hr style='border-color: #1e293b; margin-top: 15px; margin-bottom: 15px;'/>"
            "<p style='font-size: 10px; color: #64748b; font-style: italic; line-height: 1.4; text-align: justify;'>"
            "<strong>LEGAL DISCLAIMER:</strong> The execution protocol and risk models provided by TradeBotics AI are for "
            "informational and educational purposes only and do not constitute financial, investment, or trading advice."
            "</p>"
        )

        if raw_text is None:
            return {"analysis": "<h3>Execution Blocked</h3><ul><li>AI Node temporarily unavailable. No tokens were charged.</li></ul>", "remaining_tokens": current_tokens}
        ai_text = raw_text + disclaimer_html

        new_token_balance = debit_tokens(user_id, 2)
        return {"analysis": ai_text, "remaining_tokens": new_token_balance}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize")
async def summarize_article(req: SummaryRequest, user_id: str = Depends(get_current_user)):
    if not llm_available(): return {"summary": ["AI Node Offline."]}
    try:
        safe_title = ''.join(e for e in req.title if e.isalnum())[:30]
        cache_key = f"SUMMARY_{req.ticker}_{safe_title}"
        cached_data = check_ai_cache(cache_key)

        current_tokens = get_token_balance(user_id)

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens
            return cached_data

        if current_tokens < 1: raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 1 Token required.")

        prompt = (
            f"Act as an elite quantitative financial analyst. I am providing you with a headline and a brief data snippet. "
            f"Your directive is to SYNTHESIZE and EXPAND upon this intelligence, providing deep institutional market context.\n\n"
            f"HEADLINE: '{req.title}'\nRAW SNIPPET: '{req.content}'\n\n"
            f"STRICT RULES:\n- Output exactly one cohesive paragraph (3 to 4 sentences).\n- You MUST explicitly mention the specific tickers and companies referenced.\n- Do not just repeat the snippet. Add professional market context explaining WHY this event matters to the sector, supply chain, or stock price.\n- Maintain a ruthless, data-driven, and highly informative tone."
        )
        ai_text = await generate_text(prompt, max_tokens=400, purpose="summarize")
        if ai_text is None:
            return {"summary": ["AI Node temporarily unavailable. No tokens were charged."], "remaining_tokens": current_tokens}

        new_token_balance = debit_tokens(user_id, 1)
        final_response = {"summary": [ai_text], "remaining_tokens": new_token_balance}
        update_ai_cache(cache_key, final_response)
        return final_response
    except HTTPException as he: raise he
    except Exception as e:
        print(f"[SUMMARIZE] error: {e}", file=sys.stderr)
        return {"summary": [f"Synthesis Offline. Error logged in terminal."]}

@app.post("/portfolio-analysis")
async def analyze_portfolio(req: PortfolioRequest, user_id: str = Depends(get_current_user)):
    if not llm_available(): return {"analysis": "AI Node Offline."}
    try:
        current_tokens = get_token_balance(user_id)
        if current_tokens < 5: raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 5 Tokens required.")

        portfolio_summary = []
        if not req.holdings: raise HTTPException(status_code=400, detail="No holdings provided.")

        for h in req.holdings:
            try:
                ticker = str(h.get('ticker', '')).strip().upper()
                shares = float(h.get('shares', 0))
                cost = float(h.get('cost_basis', 0))
                if not ticker: continue
                if ticker == "ETHU": ticker = "ETH-USD"
                
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1d", prepost=True)
                if hist.empty: continue 
                
                price = round(hist['Close'].iloc[-1], 2)
                portfolio_summary.append({
                    "ticker": ticker, "shares": shares, "avg_cost": cost, "current_price": price, "score": 75, "value": round(shares * price, 2)
                })
            except Exception: continue 

        if not portfolio_summary: return {"analysis": "No valid data could be retrieved.", "holdings": []}
        batch_data = "\n".join([f"{p['ticker']}: {p['shares']} shares @ live ${p['current_price']} (Total: ${p['value']})" for p in portfolio_summary])
        
        try:
            db_response = supabase.table('market_universe').select('*').not_.is_('tech_score', 'null').execute()
            db_universe = db_response.data
        except Exception as db_err:
            db_universe = []

        scored_candidates = []
        if db_universe:
            for row in db_universe:
                t = row['ticker']
                if any(h['ticker'] == t for h in portfolio_summary): continue
                    
                tech_score = row['tech_score']
                fund_score = row['fund_score']
                sector = row['sector']
                pe = row['pe']
                price = row['price']
                
                if req.trade_style == "Day Trade": total_score = (tech_score * 0.8) + (fund_score * 0.2)
                elif req.trade_style == "Conservative" or req.trade_style == "Long Term": total_score = (tech_score * 0.2) + (fund_score * 0.8)
                else: total_score = (tech_score * 0.5) + (fund_score * 0.5)
                
                total_score = math.ceil(total_score)
                scored_candidates.append({"ticker": t, "price": price, "score": total_score, "sort_weight": total_score, "health": f"Sector: {sector} | P/E: {pe if pe else 'N/A'}"})
        else:
            screener_universe = ["NVDA", "AMD", "META", "LLY", "JPM", "COST"]
            for t in screener_universe:
                try:
                    if any(h['ticker'] == t for h in portfolio_summary): continue
                    stock = yf.Ticker(t)
                    hist = stock.history(period="1d")
                    if hist.empty: continue
                    price = round(hist['Close'].iloc[-1], 2)
                    scored_candidates.append({"ticker": t, "price": price, "score": 50, "sort_weight": 50, "health": "Screener Fallback Mode"})
                except Exception: continue

        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        elite_basket = [c for c in scored_candidates if c['score'] >= 70][:3]

        if not elite_basket:
            return {
                "analysis": "<h3>1. Horizon Alignment</h3><ul><li>Current core positions are sustaining higher quantitative stability than available sector rotation targets.</li></ul><h3>2. Capital Rotation</h3><ul><li>Market-wide screening shows macro-technical distribution. No high-conviction transition setups detected.</li></ul><h3>3. Precision Execution</h3><ul><li><strong>HOLD ALL POSITIONS:</strong> Capital allocation remains optimized for current volatility models. Maintain baseline structures.</li></ul>",
                "holdings": portfolio_summary,
                "remaining_tokens": current_tokens 
            }

        basket_str = f"QUALIFIED TARGET BASKET FOR {req.trade_style.upper()}:\n"
        for c in elite_basket: basket_str += f"- {c['ticker']}: Live Price ${c['price']} | Quant Score: {c['score']} | {c['health']}\n"

        prompt = (
            f"You are a Quantitative Execution Engine operating in a SIMULATED paper-trading environment.\n"
            f"Process this simulated portfolio data:\n{batch_data}\n\n"
            f"Target Strategy Horizon: {req.trade_style}\n\n"
            f"Qualified Target Basket:\n{basket_str}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Be extremely brief. No conversational fluff or introductions.\n"
            "2. Under Precision Execution, identify the weakest holding to liquidate, and the strongest basket asset to acquire.\n"
            "3. DO NOT attempt to calculate precise fractional share math. Use institutional reallocation terms.\n"
            "4. OUTPUT STRICTLY IN HTML FORMAT. DO NOT use markdown like ### or **.\n\n"
            "Structure your HTML output exactly like this:\n"
            "<h3>1. Horizon Alignment</h3>\n<ul><li>[1 short bullet analyzing why current holdings lack optimization for this horizon]</li></ul>\n"
            "<h3>2. Capital Rotation</h3>\n<ul><li>[1 short bullet explaining the strategic asset class rotation required]</li></ul>\n"
            "<h3>3. Precision Execution</h3>\n<ul>\n"
            "<li><strong>LIQUIDATE [Current Asset Ticker]:</strong> Close position at current market price to free up capital.</li>\n"
            "<li><strong>REALLOCATE TO [Target Basket Ticker]:</strong> Deploy freed capital into this high-scoring asset.</li>\n"
            "<li><strong>STRATEGIC LOGIC:</strong> [1 sentence explaining the data-driven reality of the Quant Score. Be brutally honest: do NOT call scores under 70 'strong' or 'high-conviction'. Describe them objectively based on their numerical value].</li>\n"
            "</ul>"
        )
        ai_text = await generate_text(prompt, max_tokens=800, purpose="portfolio")
        if ai_text is None:
            return {"analysis": "<h3>Execution Blocked</h3><ul><li>AI Node temporarily unavailable. No tokens were charged.</li></ul>", "holdings": portfolio_summary, "remaining_tokens": current_tokens}

        new_token_balance = debit_tokens(user_id, 5)
        return {"analysis": ai_text, "holdings": portfolio_summary, "remaining_tokens": new_token_balance}
    except HTTPException as he: raise he
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/swap-thesis")
async def generate_swap_thesis(req: SwapRequest):
    try:
        stock = yf.Ticker(req.ticker)
        sector = stock.info.get("sector", "Technology")
        
        target_ticker = "MSFT" 
        target_score = 90
        target_price = 150.00
        
        if supabase:
            try:
                res = supabase.table('market_universe').select('*').eq('sector', sector).not_.is_('tech_score', 'null').execute()
                if res.data:
                    sorted_sector = sorted(res.data, key=lambda x: (x['tech_score'] + x['fund_score'])/2, reverse=True)
                    for candidate in sorted_sector:
                        if candidate['ticker'] != req.ticker.upper():
                            target_ticker = candidate['ticker']
                            target_score = math.ceil((candidate['tech_score'] + candidate['fund_score'])/2)
                            target_price = candidate['price']
                            break
            except Exception: pass

        freed_capital = req.shares * req.price
        target_shares = math.floor(freed_capital / target_price) if target_price > 0 else 0
        thesis = f"Liquidating your {req.shares} shares of {req.ticker.upper()} frees up ${freed_capital:,.2f} in capital. Reallocating into {target_shares} shares of {target_ticker} (Quant Score {target_score}) upgrades asset quality and increases Alpha potential within the {sector} sector."
        
        return {"target_ticker": target_ticker, "target_price": target_price, "target_score": target_score, "target_shares": target_shares, "freed_capital": freed_capital, "thesis": thesis}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/market-briefing")
async def market_briefing():
    return [
        {"title": "Global markets await next major macro catalyst as volatility indexes contract.", "publisher": "TradeBotics Wire", "date": "1 hr ago"},
        {"title": "Tech sector shows resilience amidst shifting yield curve expectations.", "publisher": "Macro Intelligence", "date": "3 hrs ago"},
        {"title": "Institutional capital flows suggest rotational repositioning ahead of earnings season.", "publisher": "Dark Pool Wire", "date": "5 hrs ago"},
        {"title": "Commodity indices signal potential supply chain constraints in key raw materials.", "publisher": "Global Macro", "date": "6 hrs ago"},
        {"title": "Federal Reserve commentary points toward sustained current monetary policy trajectory.", "publisher": "Central Bank Watch", "date": "8 hrs ago"}
    ]

@app.post("/execute-trade")
async def execute_trade(req: TradeRequest, user_id: str = Depends(get_current_user)):
    if not supabase: raise HTTPException(status_code=500, detail="Database connection offline.")

    try:
        ticker = req.ticker.upper()
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", prepost=True)
        if hist.empty: raise HTTPException(status_code=404, detail="Asset pricing unavailable.")
        live_price = float(hist['Close'].iloc[-1])

        request_amount = float(req.amount)
        if req.mode == "DOLLARS":
            trade_cost = round(request_amount, 2)
            trade_shares = request_amount / live_price
        else:
            trade_shares = request_amount
            trade_cost = round(trade_shares * live_price, 2)

        profile_res = supabase.table('profiles').select('virtual_cash_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_cash = float(profile_res.data[0]['virtual_cash_balance'])

        portfolio_res = supabase.table('portfolio').select('*').eq('user_id', user_id).eq('ticker', ticker).execute()
        current_position = portfolio_res.data[0] if portfolio_res.data else None
        current_shares_held = float(current_position['shares']) if current_position else 0.0

        if req.trade_type == "BUY":
            if trade_cost > current_cash: raise HTTPException(status_code=400, detail="Insufficient virtual capital.")
            new_cash = round(current_cash - trade_cost, 2)
            if current_position:
                old_total_cost = current_shares_held * float(current_position['cost_basis'])
                new_total_shares = current_shares_held + trade_shares
                new_avg_cost = round((old_total_cost + trade_cost) / new_total_shares, 2)
                supabase.table('portfolio').update({'shares': new_total_shares, 'cost_basis': new_avg_cost}).eq('user_id', user_id).eq('ticker', ticker).execute()
            else:
                supabase.table('portfolio').insert({'user_id': user_id, 'ticker': ticker, 'shares': trade_shares, 'cost_basis': live_price}).execute()

        elif req.trade_type == "SELL":
            if trade_shares > (current_shares_held + 0.0001): raise HTTPException(status_code=400, detail="Insufficient shares in vault.")
            new_cash = float(round(current_cash + trade_cost, 2))
            new_total_shares = float(round(current_shares_held - trade_shares, 4))
            if new_total_shares <= 0.0001: supabase.table('portfolio').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            else: supabase.table('portfolio').update({'shares': new_total_shares}).eq('user_id', user_id).eq('ticker', ticker).execute()
        else: raise HTTPException(status_code=400, detail="Invalid trade type.")

        supabase.table('profiles').update({'virtual_cash_balance': new_cash}).eq('id', user_id).execute()
        supabase.table('transaction_ledger').insert({'user_id': user_id, 'transaction_type': req.trade_type, 'ticker': ticker, 'shares': trade_shares, 'price': live_price, 'total_amount': trade_cost}).execute()

        return {"status": "success", "message": f"Order Executed: {req.trade_type} {round(trade_shares, 4)} {ticker}", "execution_price": live_price, "total_cost": trade_cost, "remaining_cash": new_cash}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))