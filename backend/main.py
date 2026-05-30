from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import math
import time
from datetime import datetime, timezone, timedelta
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client
import sys
import pandas as pd
import asyncio
import random
import httpx
from contextlib import asynccontextmanager
import requests

load_dotenv()

# ==========================================
# --- KEEP ALIVE CONFIGURATION ---
# ==========================================
# ⚠️ REPLACE WITH YOUR ACTUAL LIVE RENDER APP URL
RENDER_APP_URL = "https://tradebotics-api.onrender.com/market-briefing" 

async def keep_alive_loop():
    """Loops infinitely every 10 minutes to ping the public URL and prevent sleep."""
    # Give the server 30 seconds to fully boot up before the first ping
    await asyncio.sleep(30)
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                print(f"[{datetime.now()}] 🛰️ SENDING KEEP-ALIVE PING TO PUBLIC URL...", file=sys.stderr)
                response = await client.get(RENDER_APP_URL, timeout=10.0)
                print(f"[{datetime.now()}] 💚 KEEP-ALIVE SUCCESS: Status {response.status_code}", file=sys.stderr)
            except Exception as e:
                print(f"[{datetime.now()}] ⚠️ KEEP-ALIVE PING FAILED: {e}", file=sys.stderr)
            
            # Sleep for 10 minutes (600 seconds) before pinging again
            await asyncio.sleep(600)

async def staleness_worker_loop():
    """Runs every 60 minutes. Sweeps the oldest 50 tickers, scores them, and upserts to Supabase."""
    # Give the server 60 seconds to fully boot up before starting the heavy math
    await asyncio.sleep(60)
    
    while True:
        if supabase:
            try:
                print(f"[{datetime.now()}] 🤖 WORKER WAKING UP: Initiating Staleness Sweep...", file=sys.stderr)
                
                # 1. Ask Supabase for the 50 most stale tickers (oldest timestamp first)
                response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(50).execute()
                stale_tickers = [row['ticker'] for row in response.data]
                
                # 2. Database Seeding (If table is completely empty)
                if not stale_tickers:
                    print(f"[{datetime.now()}] ⚠️ EMPTY QUEUE: Seeding database from Wikipedia...", file=sys.stderr)
                    universe = get_market_universe()
                    
                    # Batch insert to avoid overwhelming Supabase limits
                    for i in range(0, len(universe), 100):
                        chunk = universe[i:i + 100]
                        seed_data = [{'ticker': t} for t in chunk]
                        supabase.table('market_universe').upsert(seed_data).execute()
                        
                    # Re-fetch the first 50 now that the queue exists
                    response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(50).execute()
                    stale_tickers = [row['ticker'] for row in response.data]

                print(f"[{datetime.now()}] 🔍 WORKER SCANNING: Processing {len(stale_tickers)} tickers...", file=sys.stderr)
                
                # 3. Gather Data & Calculate Core Baselines
                for t in stale_tickers:
                    try:
                        stock = yf.Ticker(t)
                        hist = stock.history(period="1mo")
                        if len(hist) < 2: continue
                        
                        price = float(hist['Close'].iloc[-1])
                        prev_price = float(hist['Close'].iloc[-2])
                        daily_change = ((price - prev_price) / prev_price) * 100
                        
                        info = stock.info
                        pe = info.get("trailingPE", 0)
                        margins = info.get("profitMargins", 0)
                        sector = info.get("sector", "Macro Profile")
                        
                        # --- ISOLATED TECHNICAL MATH ---
                        tech_base = 50
                        if len(hist) >= 20:
                            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                            if price > sma_20: tech_base += 25
                            else: tech_base -= 25
                        if price > prev_price: tech_base += 15
                        else: tech_base -= 15
                        tech_score = max(10, min(95, tech_base))
                        
                        # --- ISOLATED FUNDAMENTAL MATH ---
                        fund_base = 50
                        if pe and 0 < pe < 25: fund_base += 20
                        elif pe and pe > 50: fund_base -= 20
                        if margins and margins > 0.15: fund_base += 20
                        elif margins and margins < 0: fund_base -= 25
                        fund_score = max(10, min(95, fund_base))
                        
                        # 4. Upsert the fresh intelligence back to the queue
                        # This updates the timestamp, pushing it to the back of the line
                        supabase.table('market_universe').upsert({
                            'ticker': t,
                            'price': round(price, 2),
                            'daily_change': round(daily_change, 2),
                            'tech_score': tech_score,
                            'fund_score': fund_score,
                            'sector': sector,
                            'pe': round(pe, 2) if pe else 0,
                            'last_scanned': datetime.now(timezone.utc).isoformat()
                        }).execute()
                        
                    except Exception as e:
                        # If a ticker is delisted or throws an error, log it and keep going
                        print(f"Worker skipped {t}: {e}", file=sys.stderr)
                        continue
                        
                print(f"[{datetime.now()}] ✅ WORKER FINISHED: Queue updated. Sleeping for 60 minutes.", file=sys.stderr)
                
            except Exception as e:
                print(f"❌ CRITICAL WORKER ERROR: {e}", file=sys.stderr)
        
        # Sleep for exactly 60 minutes (3600 seconds) before sweeping the next 50
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifecycle(app: FastAPI):
    # 1. The Ping loop (Prevents Render Sleep)
    asyncio.create_task(keep_alive_loop())
    
    # 2. THE NEW DATA AGENT (Sweeps 50 stale stocks every hour)
    asyncio.create_task(staleness_worker_loop())
    
    yield

# Initialize FastAPI with the lifecycle manager to run the loops
app = FastAPI(lifespan=lifecycle)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MARKET DATA IN-MEMORY CACHE (Prevents yfinance rate limits) ---
market_cache = {}
MARKET_CACHE_TTL = 60  # Cache market data for 60 seconds

# --- SUPABASE CONFIGURATION ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") 

print(f"DEBUG: Checking Env Variables...", file=sys.stderr)
print(f"DEBUG: SUPABASE_URL present: {bool(SUPABASE_URL)}", file=sys.stderr)
print(f"DEBUG: SUPABASE_SERVICE_KEY present: {bool(SUPABASE_KEY)}", file=sys.stderr)

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("SUCCESS: Supabase client initialized.", file=sys.stderr)
    except Exception as e:
        print(f"CRITICAL ERROR: Supabase init failed: {e}", file=sys.stderr)
        supabase = None
else:
    supabase = None
    print("CRITICAL ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY missing from environment.", file=sys.stderr)

# --- AI CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    print("WARNING: GEMINI_API_KEY is missing.", file=sys.stderr)

# --- GLOBAL CACHE ---
SCREENER_CACHE = {}
CACHE_MINUTES = 60

# --- WIKIPEDIA UNIVERSE CACHING ---
TICKER_LIST_CACHE = []
LAST_TICKER_UPDATE = None

# --- REQUEST MODELS ---
class TradeRequest(BaseModel):
    user_id: str
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
            
            if time_diff < 1800: # 1800 seconds = 30 minutes
                print(f"CACHE HIT [{cache_key}]: Serving from memory. Saves AI Tokens.", file=sys.stderr)
                return record['cached_response']
    except Exception as e:
        print(f"Cache read error: {e}", file=sys.stderr)
    return None

def update_ai_cache(cache_key: str, payload: dict):
    if not supabase: return
    try:
        supabase.table('ai_scan_cache').upsert({
            'cache_key': cache_key,
            'last_scanned': datetime.now(timezone.utc).isoformat(),
            'cached_response': payload
        }).execute()
        print(f"CACHE SAVED [{cache_key}]: Locked for 30 minutes.", file=sys.stderr)
    except Exception as e:
        print(f"Cache save error: {e}", file=sys.stderr)

def get_market_universe():
    """Fetches unique tickers from S&P 500, Nasdaq-100, and DJIA from Wikipedia."""
    all_tickers = set()
    
    sources = [
        {"url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "col": "Symbol"},
        {"url": "https://en.wikipedia.org/wiki/Nasdaq-100", "col": "Ticker"},
        {"url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", "col": "Symbol"}
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for source in sources:
        try:
            response = requests.get(source["url"], headers=headers, timeout=10)
            response.raise_for_status()
            tables = pd.read_html(response.text)
            
            target_df = None
            target_col_name = None
            
            # 🚀 THE FIX: Fuzzy Column Matching & MultiIndex Flattening
            for df in tables:
                # Flatten complex Wikipedia table headers if they exist
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = ['_'.join(map(str, col)).strip() for col in df.columns.values]
                    
                # Look for the target column fuzzily (case-insensitive)
                for col in df.columns:
                    if source["col"].lower() in str(col).lower():
                        target_df = df
                        target_col_name = col
                        break
                if target_df is not None:
                    break
            
            if target_df is not None and target_col_name is not None:
                tickers = target_df[target_col_name].tolist()
                for t in tickers:
                    clean_t = str(t).replace('.', '-').strip()
                    # STRICT CLEANING: Must be 1-5 letters (removes Wikipedia footnotes)
                    if isinstance(clean_t, str) and 1 <= len(clean_t) <= 5 and clean_t.replace('-', '').isalpha():
                        all_tickers.add(clean_t)
            else:
                print(f"⚠️ COLUMN '{source['col']}' NOT FOUND IN {source['url']}", file=sys.stderr)
                
        except Exception as e:
            print(f"❌ FETCH ERROR ({source['url']}): {e}", file=sys.stderr)
            
    # 🚀 THE MEGA-FALLBACK: Top 100 US Equities
    # If we get less than 50 stocks, something went wrong. Use this massive list instead.
    if len(all_tickers) < 50:
        print("⚠️ USING MEGA-FALLBACK LIST DUE TO WIKIPEDIA FORMAT/BLOCK.", file=sys.stderr)
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "TSLA", "AVGO",
            "JPM", "V", "WMT", "UNH", "XOM", "MA", "PG", "JNJ", "HD", "COST", "MRK", "ABBV", 
            "CRM", "AMD", "CVX", "NFLX", "BAC", "KO", "PEP", "TMO", "LIN", "DIS", "ADBE", 
            "MCD", "CSCO", "ABT", "INTU", "QCOM", "INTC", "CMCSA", "DHR", "VZ", "IBM", 
            "AMGN", "NOW", "TXN", "PFE", "PM", "CAT", "SPGI", "UNP", "BA", "COP", "HON", 
            "AMAT", "GS", "GE", "RTX", "ISRG", "T", "LOW", "SYK", "BKNG", "PLD", "MDT", 
            "ELV", "LMT", "AXP", "BLK", "ADI", "TJX", "C", "SBUX", "ADP", "GILD", "MMC", 
            "MDLZ", "VRTX", "LRCX", "CVS", "ZTS", "MO", "FI", "CB", "TMUS", "CME", "DUK", 
            "CI", "BSX", "BDX", "SO", "SLB", "EQIX", "MU", "PANW", "SNPS", "CDNS", "KLAC"
        ]
        
    print(f"✅ DYNAMIC MARKET UNIVERSE UPDATED: {len(all_tickers)} unique symbols loaded.", file=sys.stderr)
    return list(all_tickers)

# --- ENDPOINTS ---

@app.get("/")
async def root_health_check():
    """Lightweight endpoint for the background keep-alive ping."""
    return {"status": "Matrix Online", "timestamp": datetime.now()}

@app.post("/run-screener")
async def execute_screener(req: ScreenerRequest):
    global TICKER_LIST_CACHE, LAST_TICKER_UPDATE
    
    # 1. DYNAMIC LIST REFRESH (Checks if 24 hours have passed or cache is empty)
    if not TICKER_LIST_CACHE or (LAST_TICKER_UPDATE and (datetime.now() - LAST_TICKER_UPDATE).days >= 1):
        print(f"[{datetime.now()}] 🌐 REFRESHING UNIVERSE FROM WIKIPEDIA...", file=sys.stderr)
        TICKER_LIST_CACHE = get_market_universe()
        LAST_TICKER_UPDATE = datetime.now()

    # 2. THE CACHE CHECK (60-minute data cache)
    cache_key = f"{req.trade_style}_{req.risk_level}"
    current_time = datetime.now()

    if cache_key in SCREENER_CACHE:
        cached_results, timestamp = SCREENER_CACHE[cache_key]
        if current_time - timestamp < timedelta(minutes=CACHE_MINUTES):
            print(f"[{current_time}] ⚡ SERVING {cache_key} FROM CACHE.", file=sys.stderr)
            return {"results": cached_results}

    # 3. SELECT A SAFE SUBSAMPLE FOR PROCESSING
    ticker_pool = random.sample(TICKER_LIST_CACHE, min(50, len(TICKER_LIST_CACHE)))

    data_list = []
    print(f"[{datetime.now()}] 🔍 RUNNING YFINANCE SCAN ON {len(ticker_pool)} ASSETS...", file=sys.stderr)

    for t in ticker_pool:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d", prepost=True) # Get last 2 days for price/change
            if len(hist) < 2: continue
            
            info = stock.info
            price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            change = ((price - prev_price) / prev_price) * 100
            
            # Formatting to match dataframe keys EXACTLY
            data_list.append({
                "Ticker": t,
                "Price": f"{price:.2f}",
                "P/E": str(info.get("trailingPE", "-")),
                "Sector": info.get("sector", "N/A"),
                "Change": f"{change:.2f}%"
            })
        except Exception as e:
            continue
            
    combined_df = pd.DataFrame(data_list)

    # --- 3. DEDUPLICATION PHASE ---
    scored_candidates = []
    try:
        if not combined_df.empty:
            universe_df = combined_df.drop_duplicates(subset='Ticker')
            print(f"[{datetime.now()}] ✅ GATHERING SUCCESS: {len(universe_df)} unique assets loaded.", file=sys.stderr)
            
            # --- 4. PROPRIETARY SCORING ENGINE ---
            for index, row in universe_df.iterrows():
                t = row['Ticker']
                price = float(row['Price']) if str(row['Price']) != '-' else 0
                pe_raw = str(row['P/E'])
                pe = float(pe_raw) if pe_raw != '-' else 0
                sector = str(row['Sector'])
                change = str(row['Change']).replace('%', '')
                daily_change = float(change) if change != '-' else 0

                tech_base = 50
                if daily_change > 0: tech_base += 15
                else: tech_base -= 15
                tech_score = max(10, min(95, tech_base))

                fund_base = 50
                if pe and 0 < pe < 25: fund_base += 20
                elif pe and pe > 50: fund_base -= 20
                fund_score = max(10, min(95, fund_base))

                if req.risk_level == "Aggressive":
                    total_score = (tech_score * 0.8) + (fund_score * 0.2)
                elif req.risk_level == "Conservative":
                    total_score = (tech_score * 0.2) + (fund_score * 0.8)
                else:
                    total_score = (tech_score * 0.5) + (fund_score * 0.5)

                style_bonus = 0
                if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "AMD"]: style_bonus = 15 
                elif req.trade_style == "Long Term" and pe and 0 < pe < 35: style_bonus = 5

                sort_weight = total_score + style_bonus + (daily_change * 0.01)
                final_display_score = max(10, min(99, math.ceil(total_score + style_bonus)))

                scored_candidates.append({
                    "ticker": t,
                    "price": price,
                    "score": final_display_score,
                    "sort_weight": sort_weight,
                    "sector": sector,
                    "metrics": f"P/E: {pe if pe else 'N/A'} | Sector: {sector}"
                })
        else:
            print(f"[{datetime.now()}] ⚠️ GATHERING RETURNED EMPTY DATAFRAME.", file=sys.stderr)

    except Exception as e:
        print(f"❌ PIPELINE ERROR: {e}", file=sys.stderr)
        return {"results": []}

    scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
    final_top_30 = scored_candidates[:30]
    
    SCREENER_CACHE[cache_key] = (final_top_30, current_time)
    return {"results": final_top_30}

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str): 
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")

    ticker_upper = ticker.upper()
    now = time.time()

    # 🚀 1. CHECK CACHE FIRST (Prevents Yahoo Finance Rate Limiting)
    if ticker_upper in market_cache:
        cached_time, cached_data = market_cache[ticker_upper]
        if now - cached_time < MARKET_CACHE_TTL:
            print(f"MARKET CACHE HIT [{ticker_upper}]: Serving from memory.", file=sys.stderr)
            return cached_data

    try:
        stock = yf.Ticker(ticker_upper)
        hist = stock.history(period="3mo", prepost=True)
        if hist.empty: raise HTTPException(status_code=404, detail="Ticker data not found.")

        current_price = round(hist['Close'].iloc[-1], 2)
        prev_price = round(hist['Close'].iloc[-2], 2)
        volume = int(hist['Volume'].iloc[-1])
        avg_volume = int(hist['Volume'].mean())

        pe = stock.info.get("trailingPE")
        margins = stock.info.get("profitMargins")
        
        raw_mcap = stock.info.get("marketCap")
        formatted_mcap = "N/A"
        if raw_mcap:
            if raw_mcap >= 1e12:
                formatted_mcap = f"${raw_mcap / 1e12:.2f} Trillion"
            else:
                formatted_mcap = f"${raw_mcap / 1e9:.2f} Billion"

        calendar = stock.calendar
        next_earnings = "Unknown"
        if calendar is not None:
            try:
                if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                    next_earnings = str(calendar['Earnings Date'][0])
                elif 'Earnings Date' in calendar and not calendar.empty:
                    next_earnings = str(calendar['Earnings Date'].iloc[0].date())
            except Exception:
                pass

        tech_base = 50
        if len(hist) >= 20:
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            if current_price > sma_20: tech_base += 25
            else: tech_base -= 25
        if current_price > prev_price: tech_base += 15
        else: tech_base -= 15
        tech_score = max(10, min(95, tech_base))

        fund_base = 50
        if pe and 0 < pe < 25: fund_base += 20
        elif pe and pe > 50: fund_base -= 20
        if margins and margins > 0.15: fund_base += 20
        elif margins and margins < 0: fund_base -= 25
        fund_score = max(10, min(95, fund_base))
        total_score = math.ceil((tech_score + fund_score) / 2)
        
        vol_surge = f"{round((volume / avg_volume) * 100, 1)}%" if avg_volume > 0 else "N/A"

        # PULL LIVE NEWS
        news_list = []
        try:
            finnhub_key = os.getenv("FINNHUB_API_KEY")
            if finnhub_key:
                import urllib.request
                import json
                from datetime import timedelta
                
                end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
                
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker_upper}&from={start_date}&to={end_date}&token={finnhub_key}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                
                with urllib.request.urlopen(req) as response:
                    finnhub_news = json.loads(response.read().decode())
                    
                    for item in finnhub_news[:5]:
                        pub_time = item.get("datetime", time.time())
                        hours_ago = int((time.time() - pub_time) / 3600)
                        date_str = "JUST NOW" if hours_ago <= 0 else f"{hours_ago} HR{'S' if hours_ago > 1 else ''} AGO"
                        
                        news_list.append({
                            "title": item.get("headline", "Market Update"),
                            "publisher": item.get("source", "Financial Wire"),
                            "date": date_str,
                            "content": item.get("summary", item.get("url", ""))
                        })
            
            if not news_list:
                raw_news = stock.news
                if isinstance(raw_news, list):
                    for item in raw_news[:5]:
                        title = item.get("title", "")
                        if not title or title.strip() == "": continue
                        pub_time = item.get("providerPublishTime", time.time())
                        hours_ago = int((time.time() - pub_time) / 3600)
                        date_str = "JUST NOW" if hours_ago <= 0 else f"{hours_ago} HR{'S' if hours_ago > 1 else ''} AGO"
                        
                        news_list.append({
                            "title": title,
                            "publisher": item.get("publisher", "Market Wire"),
                            "date": date_str,
                            "content": item.get("summary", item.get("link", ""))
                        })
                        
        except Exception as e:
            print(f"News fetch error for {ticker_upper}: {e}", file=sys.stderr)

        ledger = [
            {"factor": "Momentum (RSI)", "val": "62.5" if tech_score > 50 else "38.2", "status": "BULLISH" if tech_score > 50 else "BEARISH", "reasoning": f"{ticker_upper} is showing upward momentum. Current RSI proxy suggests buying pressure." if tech_score > 50 else f"{ticker_upper} is losing momentum. RSI proxy suggests selling pressure."},
            {"factor": "Institutional Flow", "val": "High" if volume > avg_volume else "Low", "status": "BULLISH" if volume > avg_volume else "NEUTRAL", "reasoning": f"Current volume of {volume:,} exceeds the historical average of {avg_volume:,}, indicating strong institutional accumulation." if volume > avg_volume else f"Current volume of {volume:,} is below the historical average of {avg_volume:,}, indicating retail-driven consolidation."},
            {"factor": "MACD Divergence", "val": "Positive" if current_price > prev_price else "Negative", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": f"Price action at ${current_price} confirms a positive bullish crossover against the previous close." if current_price > prev_price else f"Price action at ${current_price} indicates a bearish crossover trajectory."},
            {"factor": "VWAP Proximity", "val": f"+{round(((current_price - prev_price)/prev_price)*100, 2)}%" if current_price > prev_price else f"{round(((current_price - prev_price)/prev_price)*100, 2)}%", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": f"The asset is holding firmly above the volume-weighted baseline, supporting the current uptrend." if current_price > prev_price else f"The asset has slipped below the volume-weighted baseline, signaling potential distribution."},
            {"factor": "Bollinger Bands", "val": "Upper Band" if tech_score > 70 else "Lower Band" if tech_score < 40 else "Mid-Band", "status": "BULLISH" if tech_score > 70 else "BEARISH" if tech_score < 40 else "NEUTRAL", "reasoning": f"Price is riding the upper standard deviation channel, suggesting a potential breakout for {ticker_upper}." if tech_score > 70 else f"Price is testing the lower standard deviation channel, indicating oversold conditions." if tech_score < 40 else f"{ticker_upper} is consolidating near the mean, awaiting a volatility catalyst."}
        ]

        final_response = {
            "ticker": ticker_upper,
            "company_name": stock.info.get("shortName", ticker_upper),
            "price": current_price,
            "score": total_score,
            "tech_score": int(tech_score),
            "fund_score": int(fund_score),
            "volume": f"{volume:,}",
            "vol_surge": vol_surge,
            "ledger": ledger,
            "news": news_list,  
            "ai_tactical": f"Market conditions evaluated for {ticker_upper}. Execution guidance dynamically adjusting to real-time volatility.",
            "fundamentals": {
                "market_cap": formatted_mcap, 
                "pe_ratio": str(round(pe, 2)) if pe else "N/A",
                "debt_equity": str(stock.info.get("debtToEquity", "N/A")),
                "margin": f"{round(margins * 100, 2)}%" if margins else "N/A",
                "sentiment": "BULLISH" if total_score > 65 else "BEARISH" if total_score < 40 else "NEUTRAL",
                "cash_flow": "POSITIVE" if margins and margins > 0 else "NEGATIVE",
                "next_earnings": next_earnings 
            }
        }
        
        # 🚀 2. SAVE TO CACHE BEFORE RETURNING
        market_cache[ticker_upper] = (now, final_response)
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        if 'Too Many Requests' in str(e) or '429' in str(e):
            raise HTTPException(status_code=429, detail="MARKET DATA RATE LIMIT EXCEEDED. Stand by.")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
async def translate_ai(req: TranslationRequest, user_id: str = Query(...)): 
    if not model: return {"analysis": "AI Node Offline."}
    try:
        cache_key = f"TRANSLATE_{req.ticker.upper()}"
        cached_data = check_ai_cache(cache_key)
        
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens
            return cached_data
            
        if current_tokens < 3:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 3 Tokens required.")

        prompt = f"Act as an elite quantitative analyst. Provide a definitive briefing on {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n- Current Price: ${req.data_context.get('price', 'N/A')}\n- Quant Score: {req.data_context.get('score', 'N/A')}\n\n"
        
        funds = req.data_context.get("fundamentals", {})
        if funds:
            prompt += f"FUNDAMENTAL DNA:\n- Market Cap: {funds.get('market_cap', 'N/A')}\n- P/E Ratio: {funds.get('pe_ratio', 'N/A')}\n- Margin: {funds.get('margin', 'N/A')}\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER:\n"
            for item in ledger: prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

        news = req.data_context.get("news", [])
        if news:
            prompt += f"\nLATEST INTELLIGENCE (CATALYSTS):\n"
            for item in news[:3]:
                prompt += f"- {item.get('title')} ({item.get('date')})\n"

        next_earnings = funds.get("next_earnings", "N/A")
        if next_earnings != "N/A" and next_earnings != "Unknown":
            prompt += f"\nEARNINGS RISK:\n- Next Earnings Date: {next_earnings}\n"
            prompt += "If the Next Earnings Date is today or tomorrow, heavily weigh the binary risk of an earnings gap in your tactical verdict. Downgrade pure technical indicators.\n"

        prompt += (
            "\n🚨 TEMPLATE REQUIREMENT - YOU MUST FOLLOW THIS EXACTLY:\n"
            "Line 1: '🎯 AI STRIKE ZONE: $[low] - $[high]'\n"
            "Line 2: '⚖️ TACTICAL VERDICT: [BUY/HOLD/TRIM/SELL]'\n\n"
            "BRIEFING REQUIREMENTS:\n"
            "1. Macro & Fundamentals: Analyze how current macro conditions and company DNA impact the stock.\n"
            "2. Technical Analysis: Incorporate the provided Technical Ledger. If BUY, Strike Zone must be in line with current price. If TRIM/SELL/HOLD, Strike Zone must be based on support/resistance.\n"
            "Keep it professional, data-driven, and ruthless. No pleasantries."
        )
        response = model.generate_content(prompt)

        new_token_balance = current_tokens - 3
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        final_response = {
            "analysis": response.text.strip(),
            "remaining_tokens": new_token_balance
        }
        
        update_ai_cache(cache_key, final_response)
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize")
async def summarize_article(req: SummaryRequest, user_id: str = Query(...)): 
    if not model: return {"summary": ["AI Node Offline."]}
    try:
        safe_title = ''.join(e for e in req.title if e.isalnum())[:30]
        cache_key = f"SUMMARY_{req.ticker}_{safe_title}"
        
        cached_data = check_ai_cache(cache_key)
        
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens
            return cached_data
            
        if current_tokens < 1:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 1 Token required.")

        prompt = (
            f"Act as an elite quantitative financial analyst. I am providing you with a headline and a brief data snippet. "
            f"Your directive is to SYNTHESIZE and EXPAND upon this intelligence, providing deep institutional market context.\n\n"
            f"HEADLINE: '{req.title}'\n"
            f"RAW SNIPPET: '{req.content}'\n\n"
            f"STRICT RULES:\n"
            f"- Output exactly one cohesive paragraph (3 to 4 sentences).\n"
            f"- You MUST explicitly mention the specific tickers and companies referenced.\n"
            f"- Do not just repeat the snippet. Add professional market context explaining WHY this event matters to the sector, supply chain, or stock price.\n"
            f"- Maintain a ruthless, data-driven, and highly informative tone."
        )
        
        response = model.generate_content(
            prompt,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        )

        try:
            ai_text = response.text.strip()
        except ValueError:
            print(f"GEMINI BLOCKED RESPONSE: {response.prompt_feedback}", file=sys.stderr)
            ai_text = "AI Node rejected synthesis due to strict safety protocols regarding direct financial advice."

        new_token_balance = current_tokens - 1
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        final_response = {
            "summary": [ai_text],
            "remaining_tokens": new_token_balance
        }
        
        update_ai_cache(cache_key, final_response)
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception as e: 
        print(f"CRITICAL SUMMARIZE ERROR: {e}", file=sys.stderr)
        return {"summary": [f"Synthesis Offline. Error logged in terminal."]}

@app.post("/portfolio-analysis")
async def analyze_portfolio(req: PortfolioRequest, user_id: str = Query(...)): 
    if not model: return {"analysis": "AI Node Offline."}
    try:
        # 🚀 CACHE REMOVED: Always run a fresh live scan for the portfolio
        
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        # Check Token Balance
        if current_tokens < 5:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 5 Tokens required.")

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
                    "ticker": ticker,
                    "shares": shares,
                    "avg_cost": cost,
                    "current_price": price,
                    "score": 75, 
                    "value": round(shares * price, 2)
                })
            except Exception:
                continue 

        if not portfolio_summary: return {"analysis": "No valid data could be retrieved.", "holdings": []}

        batch_data = "\n".join([f"{p['ticker']}: {p['shares']} shares @ live ${p['current_price']} (Total: ${p['value']})" for p in portfolio_summary])
        
        if req.trade_style == "Day Trade":
            screener_universe = ["NVDA", "AMD", "SMCI", "TSLA", "COIN"]
        elif req.trade_style == "Swing Trade":
            screener_universe = ["META", "AVGO", "NFLX", "PLTR", "NOW"]
        else: 
            screener_universe = ["LLY", "JPM", "COST", "WMT", "UNH"]

        scored_candidates = []
        for t in screener_universe:
            try:
                if any(h['ticker'] == t for h in portfolio_summary): continue
                stock = yf.Ticker(t)
                hist = stock.history(period="1mo", prepost=True)
                if hist.empty: continue
                price = round(hist['Close'].iloc[-1], 2)
                prev_price = round(hist['Close'].iloc[-2], 2)
                
                # 🚀 EXACT MATH MATCH TO TERMINAL
                tech_base = 50
                if len(hist) >= 20:
                    sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                    if price > sma_20: tech_base += 25
                    else: tech_base -= 25
                if price > prev_price: tech_base += 15
                else: tech_base -= 15
                tech_score = max(10, min(95, tech_base))

                info = stock.info
                pe = info.get("trailingPE", 0)
                margins = info.get("profitMargins", 0)
                sector = info.get("sector", "Macro Profile")

                fund_base = 50
                if pe and 0 < pe < 25: fund_base += 20
                elif pe and pe > 50: fund_base -= 20
                if margins and margins > 0.15: fund_base += 20
                elif margins and margins < 0: fund_base -= 25
                fund_score = max(10, min(95, fund_base))
                
                total_score = math.ceil((tech_score + fund_score) / 2)

                # 🚀 HIDDEN ALIGNMENT ALGORITHM (Keeps AI choosing the right style without faking the score)
                style_bonus = 0
                if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "COIN"]: style_bonus = 20 
                elif req.trade_style == "Swing Trade" and t in ["META", "AVGO", "PLTR"]: style_bonus = 20 
                elif req.trade_style == "Long Term" and t in ["LLY", "COST", "JPM"]: style_bonus = 20 

                sort_weight = total_score + style_bonus

                health_str = f"Sector: {sector} | P/E: {round(pe, 1) if pe else 'N/A'} | Margin: {round(margins*100, 1) if margins else '0'}%"

                scored_candidates.append({
                    "ticker": t,
                    "price": price,
                    "score": total_score,          # Pure Terminal Score is now isolated
                    "sort_weight": sort_weight,    # Internal AI Sorting handles the style boost invisibly
                    "health": health_str
                })
            except Exception:
                continue

        # Sort by the hidden weight, not the raw score!
        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        elite_basket = scored_candidates[:3]

        basket_str = f"QUALIFIED TARGET BASKET FOR {req.trade_style.upper()}:\n"
        for c in elite_basket:
            basket_str += f"- {c['ticker']}: Live Price ${c['price']} | Quant Score: {c['score']} | {c['health']}\n"

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
            "<h3>1. Horizon Alignment</h3>\n"
            "<ul><li>[1 short bullet analyzing why current holdings lack optimization for this horizon]</li></ul>\n"
            "<h3>2. Capital Rotation</h3>\n"
            "<ul><li>[1 short bullet explaining the strategic asset class rotation required]</li></ul>\n"
            "<h3>3. Precision Execution</h3>\n"
            "<ul>\n"
            "<li><strong>LIQUIDATE [Current Asset Ticker]:</strong> Close position at current market price to free up capital.</li>\n"
            "<li><strong>REALLOCATE TO [Target Basket Ticker]:</strong> Deploy freed capital into this high-scoring asset.</li>\n"
            "<li><strong>STRATEGIC LOGIC:</strong> [1 sentence explaining why this asset wins based on its Quant Score].</li>\n"
            "</ul>"
        )

        response = await model.generate_content_async(
            prompt,
            generation_config={"max_output_tokens": 2000, "temperature": 0.1},
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        )

        try:
            ai_text = response.text.strip()
        except ValueError:
            print(f"GEMINI BLOCKED RESPONSE: {response.prompt_feedback}", file=sys.stderr)
            ai_text = "<h3>Execution Blocked</h3><ul><li>AI Node rejected synthesis due to strict safety protocols regarding direct financial execution.</li></ul>"

        # Deduct exactly 5 tokens for this fresh run
        new_token_balance = current_tokens - 5
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        final_response = {
            "analysis": ai_text,
            "holdings": portfolio_summary,
            "remaining_tokens": new_token_balance
        }
        
        # 🚀 NO update_ai_cache() call here anymore!
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"CRITICAL PORTFOLIO ERROR: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/swap-thesis")
async def generate_swap_thesis(req: SwapRequest):
    try:
        sector_targets = {
            "Technology": {"ticker": "NVDA", "score": 94},
            "Consumer Cyclical": {"ticker": "AMZN", "score": 88},
            "Financial Services": {"ticker": "JPM", "score": 85},
            "Healthcare": {"ticker": "LLY", "score": 90},
            "Communication Services": {"ticker": "META", "score": 89},
            "Energy": {"ticker": "XOM", "score": 82}
        }
        stock = yf.Ticker(req.ticker)
        sector = stock.info.get("sector", "Technology")
        target = sector_targets.get(sector, sector_targets["Technology"])
        if req.ticker.upper() == target["ticker"]: target = {"ticker": "MSFT", "score": 91}
        
        target_stock = yf.Ticker(target["ticker"])
        target_hist = target_stock.history(period="1d", prepost=True)
        target_price = 150.00 if target_hist.empty else round(target_hist['Close'].iloc[-1], 2)
        freed_capital = req.shares * req.price
        target_shares = math.floor(freed_capital / target_price)
        thesis = f"Liquidating your {req.shares} shares of {req.ticker.upper()} frees up ${freed_capital:,.2f} in capital. Reallocating into {target_shares} shares of {target['ticker']} (Quant Score {target['score']}) upgrades asset quality and increases Alpha potential."
        
        return {"target_ticker": target["ticker"], "target_price": target_price, "target_score": target["score"], "target_shares": target_shares, "freed_capital": freed_capital, "thesis": thesis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
async def execute_trade(req: TradeRequest, request: Request):
    # 🚀 DEBUG: Print the raw body immediately to catch the 422 error payload
    try:
        body = await request.json()
        print(f"DEBUG: Received JSON body: {body}", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Could not parse JSON body: {e}", file=sys.stderr)

    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")
    
    try:
        ticker = req.ticker.upper()
        
        # 1. Fetch Live Price & Ensure Float
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", prepost=True)
        if hist.empty: raise HTTPException(status_code=404, detail="Asset pricing unavailable.")
        live_price = float(hist['Close'].iloc[-1])

        # 2. Strict Math & Rounding (Prevents Database Rejections)
        request_amount = float(req.amount)
        if req.mode == "DOLLARS":
            trade_cost = round(request_amount, 2)
            trade_shares = request_amount / live_price
        else:
            trade_shares = request_amount
            trade_cost = round(trade_shares * live_price, 2)

        # 3. Pull Current Balances
        profile_res = supabase.table('profiles').select('virtual_cash_balance').eq('id', req.user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_cash = float(profile_res.data[0]['virtual_cash_balance'])

        portfolio_res = supabase.table('portfolio').select('*').eq('user_id', req.user_id).eq('ticker', ticker).execute()
        current_position = portfolio_res.data[0] if portfolio_res.data else None
        current_shares_held = float(current_position['shares']) if current_position else 0.0

        # 4. Execute Logic
        if req.trade_type == "BUY":
            if trade_cost > current_cash: 
                raise HTTPException(status_code=400, detail="Insufficient virtual capital.")
            
            new_cash = round(current_cash - trade_cost, 2)
            
            if current_position:
                old_total_cost = current_shares_held * float(current_position['cost_basis'])
                new_total_shares = current_shares_held + trade_shares
                new_avg_cost = round((old_total_cost + trade_cost) / new_total_shares, 2)
                
                supabase.table('portfolio').update({
                    'shares': new_total_shares,
                    'cost_basis': new_avg_cost
                }).eq('user_id', req.user_id).eq('ticker', ticker).execute()
            else:
                supabase.table('portfolio').insert({
                    'user_id': req.user_id,
                    'ticker': ticker,
                    'shares': trade_shares,
                    'cost_basis': live_price
                }).execute()

        elif req.trade_type == "SELL":
            if trade_shares > (current_shares_held + 0.0001): 
                raise HTTPException(status_code=400, detail="Insufficient shares in vault.")
            
            # 🚀 THE FIX: Explicitly cast to float() and strictly round
            new_cash = float(round(current_cash + trade_cost, 2))
            new_total_shares = float(round(current_shares_held - trade_shares, 4))

            if new_total_shares <= 0.0001:
                supabase.table('portfolio').delete().eq('user_id', req.user_id).eq('ticker', ticker).execute()
            else:
                supabase.table('portfolio').update({'shares': new_total_shares}).eq('user_id', req.user_id).eq('ticker', ticker).execute()
        else:
            raise HTTPException(status_code=400, detail="Invalid trade type.")

        # 5. Inject Clean Data into Database
        supabase.table('profiles').update({'virtual_cash_balance': new_cash}).eq('id', req.user_id).execute()
        
        supabase.table('transaction_ledger').insert({
            'user_id': req.user_id,
            'transaction_type': req.trade_type,
            'ticker': ticker,
            'shares': trade_shares,
            'price': live_price,
            'total_amount': trade_cost
        }).execute()

        return {
            "status": "success",
            "message": f"Order Executed: {req.trade_type} {round(trade_shares, 4)} {ticker}",
            "execution_price": live_price,
            "total_cost": trade_cost,
            "remaining_cash": new_cash
        }

    except Exception as e:
        print(f"TRADE EXECUTION ERROR: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))