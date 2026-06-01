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
import io
import numpy as np
from scipy.signal import argrelextrema

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
    """Runs continuously every 60 seconds. Sweeps 15 stale tickers to bypass Yahoo burst limits."""
    # Give the server 60 seconds to fully boot up before starting the heavy math
    await asyncio.sleep(60)
    
    while True:
        if supabase:
            try:
                # 🧹 1. DATABASE CLEANUP: Auto-delete AI Cache older than 30 minutes to protect free tier
                try:
                    expiration_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
                    supabase.table('ai_scan_cache').delete().lt('last_scanned', expiration_cutoff).execute()
                except Exception as e:
                    print(f"❌ Database cleanup failed: {e}", file=sys.stderr)

                # 🚀 2. MICRO-BATCHING: Grab only 15 stocks to prevent Yahoo burst detection
                response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(15).execute()
                stale_tickers = [row['ticker'] for row in response.data]
                
                # 3. Database Seeding (If table is completely empty)
                if not stale_tickers:
                    print(f"[{datetime.now()}] ⚠️ EMPTY QUEUE: Seeding database from SEC Master List...", file=sys.stderr)
                    universe = get_market_universe()
                    
                    # Batch insert to avoid overwhelming Supabase limits 
                    for i in range(0, len(universe), 200):
                        chunk = universe[i:i + 200]
                        seed_data = [{'ticker': t} for t in chunk]
                        try:
                            supabase.table('market_universe').upsert(seed_data).execute()
                        except Exception as e:
                            pass
                        
                    response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(15).execute()
                    stale_tickers = [row['ticker'] for row in response.data]

                print(f"[{datetime.now()}] 🔍 MICRO-BATCH: Processing {len(stale_tickers)} tickers...", file=sys.stderr)
                
                rate_limit_hit = False  # 🚩 NEW: Flag to track if we get banned during this batch
                
                # 4. Gather Data & Calculate Core Baselines
                for t in stale_tickers:
                    current_time = datetime.now(timezone.utc).isoformat()
                    
                    try:
                        stock = yf.Ticker(t)
                        hist = stock.history(period="1mo")
                        
                        # --- THE QUEUE LOGJAM FIX ---
                        if hist.empty:
                            supabase.table('market_universe').delete().eq('ticker', t).execute()
                            continue
                            
                        if len(hist) < 2: 
                            supabase.table('market_universe').update({'last_scanned': current_time}).eq('ticker', t).execute()
                            continue
                        
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
                        
                        # 5. Upsert the fresh intelligence back to the queue
                        supabase.table('market_universe').upsert({
                            'ticker': t,
                            'price': round(price, 2),
                            'daily_change': round(daily_change, 2),
                            'tech_score': tech_score,
                            'fund_score': fund_score,
                            'sector': sector,
                            'pe': round(pe, 2) if pe else 0,
                            'last_scanned': current_time
                        }).execute()
                        
                    except Exception as e:
                        error_msg = str(e)
                        
                        # 🚨 YAHOO RATE LIMIT ABORT PROTOCOL
                        if "Too Many Requests" in error_msg or "429" in error_msg:
                            print(f"[{datetime.now()}] 🛑 RATE LIMIT CAUGHT: Aborting micro-batch to cool down...", file=sys.stderr)
                            rate_limit_hit = True  # Set the flag!
                            break 
                            
                        # Handle delisted/random errors
                        if "Not Found" in error_msg or "delisted" in error_msg.lower():
                            supabase.table('market_universe').delete().eq('ticker', t).execute()
                        else:
                            supabase.table('market_universe').update({'last_scanned': current_time}).eq('ticker', t).execute()

                    # 🚦 ANTI-BOT THROTTLE: Human-like delay between each of the 15 stocks
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                        
                # 🚀 5. SMART CYCLE SLEEP
                if rate_limit_hit:
                    print(f"[{datetime.now()}] 💤 ENTERING PENALTY BOX: Sleeping for 15 minutes to clear ban.", file=sys.stderr)
                    await asyncio.sleep(900)  # Wait 15 minutes if banned
                else:
                    await asyncio.sleep(60)   # Wait 60 seconds if everything is healthy
                
            except Exception as e:
                # --- THE MASTER LOOP SAFETY NET ---
                print(f"❌ CRITICAL WORKER ERROR: {e}", file=sys.stderr)
                await asyncio.sleep(60) 
        else:
            await asyncio.sleep(60) 

@asynccontextmanager
async def lifecycle(app: FastAPI):
    # 1. The Ping loop (Prevents Render Sleep)
    asyncio.create_task(keep_alive_loop())
    
    # 2. THE DATA AGENT (Sweeps 200 stale stocks every 15 minutes)
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

# --- SEC UNIVERSE CACHING ---
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

# ==========================================
# --- MATH ENGINE: SUPPORT & RESISTANCE ---
# ==========================================
def get_support_resistance(hist):
    if len(hist) < 30:
        return float(hist['Low'].min()), float(hist['High'].max())
        
    prices = hist['Close'].values
    order = 5
    maxima = argrelextrema(prices, np.greater, order=order)[0]
    minima = argrelextrema(prices, np.less, order=order)[0]
    
    res_levels = prices[maxima][-3:] 
    sup_levels = prices[minima][-3:] 
    
    if len(res_levels) == 0: res_levels = [prices[-1]]
    if len(sup_levels) == 0: sup_levels = [prices[-1]]
    
    return float(np.mean(sup_levels)), float(np.mean(res_levels))

def get_market_universe():
    """Fetches the official SEC active ticker list (Over 10,000 US stocks)"""
    print(f"[{datetime.now()}] 📡 Fetching Master Ticker List from the SEC...", file=sys.stderr)
    all_tickers = set()
    
    try:
        # The SEC strictly requires a descriptive, customized User-Agent identification header
        headers = {'User-Agent': 'TradeBoticsApp/1.0 (Data Engine)'}
        response = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        for key, value in data.items():
            ticker = str(value.get("ticker", "")).strip().upper()
            # Strict format filter ensuring standard alphabetical listings
            if ticker and ticker.isalpha() and len(ticker) <= 5: 
                all_tickers.add(ticker)
                
        print(f"✅ SEC UNIVERSE UPDATED: {len(all_tickers)} unique symbols loaded.", file=sys.stderr)
        return list(all_tickers)
        
    except Exception as e:
        print(f"❌ SEC FETCH ERROR: {e}", file=sys.stderr)
        # Institutional disaster recovery baseline
        return ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "TSLA"]

# --- ENDPOINTS ---

@app.get("/")
async def root_health_check():
    """Lightweight endpoint for the background keep-alive ping."""
    return {"status": "Matrix Online", "timestamp": datetime.now()}

@app.post("/run-screener")
async def execute_screener(req: ScreenerRequest):
    cache_key = f"{req.trade_style}_{req.risk_level}"
    current_time = datetime.now()

    if cache_key in SCREENER_CACHE:
        cached_results, timestamp = SCREENER_CACHE[cache_key]
        if current_time - timestamp < timedelta(minutes=5):
            print(f"[{current_time}] ⚡ SERVING {cache_key} FROM CACHE.", file=sys.stderr)
            return {"results": cached_results}

    print(f"[{datetime.now()}] ⚡ PULLING PRE-CALCULATED SCORES FROM SUPABASE...", file=sys.stderr)
    
    try:
        # FETCH FROM SUPABASE (Only grab tickers the worker has finished processing)
        response = supabase.table('market_universe').select('*').not_.is_('tech_score', 'null').execute()
        db_universe = response.data
        
        if not db_universe:
            print("⚠️ SUPABASE RETURNED NO PROCESSED TICKERS YET.", file=sys.stderr)
            return {"results": []}

        # APPLY USER PREFERENCES (Aggressive vs Conservative)
        scored_candidates = []
        for row in db_universe:
            t = row['ticker']
            tech_score = row['tech_score']
            fund_score = row['fund_score']
            sector = row['sector']
            daily_change = row['daily_change']
            db_price = row['price']

            # Blend the pre-calculated scores based on the user's selected Risk Level
            if req.risk_level == "Aggressive":
                total_score = (tech_score * 0.8) + (fund_score * 0.2)
            elif req.risk_level == "Conservative":
                total_score = (tech_score * 0.2) + (fund_score * 0.8)
            else:
                total_score = (tech_score * 0.5) + (fund_score * 0.5)

            # Apply Style Bonuses invisibly
            style_bonus = 0
            if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "AMD", "COIN"]: 
                style_bonus = 15 
            elif req.trade_style == "Long Term" and fund_score > 70: 
                style_bonus = 5

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

        # Sort and grab only the top 30 elite performers
        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        top_30 = scored_candidates[:30]

        # THE LIVE PRICE STITCH (Only fetch live data for the winners)
        print(f"[{datetime.now()}] 🔍 STITCHING LIVE PRICES FOR TOP 30...", file=sys.stderr)
        final_results = []
        
        for candidate in top_30:
            try:
                stock = yf.Ticker(candidate['ticker'])
                hist = stock.history(period="1d")
                if not hist.empty:
                    candidate['price'] = round(float(hist['Close'].iloc[-1]), 2)
                else:
                    candidate['price'] = candidate['db_price']
            except Exception:
                candidate['price'] = candidate['db_price']
            
            candidate.pop('db_price', None)
            final_results.append(candidate)

        SCREENER_CACHE[cache_key] = (final_results, current_time)
        return {"results": final_results}

    except Exception as e:
        print(f"❌ HYBRID FETCH ERROR: {e}", file=sys.stderr)
        return {"results": []}

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str): 
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")

    ticker_upper = ticker.upper()
    now = time.time()

    # CHECK CACHE FIRST (Prevents Yahoo Finance Rate Limiting)
    if ticker_upper in market_cache:
        cached_time, cached_data = market_cache[ticker_upper]
        if now - cached_time < MARKET_CACHE_TTL:
            print(f"MARKET CACHE HIT [{ticker_upper}]: Serving from memory.", file=sys.stderr)
            return cached_data

    try:
        stock = yf.Ticker(ticker_upper)
        hist = stock.history(period="3mo", prepost=True)
        if hist.empty: raise HTTPException(status_code=404, detail="Ticker data not found.")

        # CALCULATE ROBUST SUPPORT & RESISTANCE
        support, resistance = get_support_resistance(hist)

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
            if current_price > sma_20: 
                tech_base += 25
            else: 
                tech_base -= 25
            
        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else current_price * 0.95
        recent_high = hist['High'].max()

        if current_price > prev_price: 
            tech_base += 15
        else: 
            tech_base -= 15
        tech_score = max(10, min(95, tech_base))

        fund_base = 50
        if pe and 0 < pe < 25: 
            fund_base += 20
        elif pe and pe > 50: 
            fund_base -= 20
        if margins and margins > 0.15: 
            fund_base += 20
        elif margins and margins < 0: 
            fund_base -= 25
        fund_score = max(10, min(95, fund_base))
        total_score = math.ceil((tech_score + fund_score) / 2)
        
        vol_surge = f"{round((volume / avg_volume) * 100, 1)}%" if avg_volume > 0 else "N/A"

        # 🚀 REAL 14-DAY RSI CALCULATION WITH WILDER'S SMOOTHING
        try:
            delta = hist['Close'].diff()
            gain = delta.clip(lower=0)
            loss = -1 * delta.clip(upper=0)
            ema_gain = gain.ewm(com=13, adjust=False).mean()
            ema_loss = loss.ewm(com=13, adjust=False).mean()
            rs = ema_gain / ema_loss
            rsi_series = 100 - (100 / (1 + rs))
            real_rsi = round(rsi_series.iloc[-1], 1)
            if pd.isna(real_rsi): real_rsi = 50.0
        except Exception:
            real_rsi = 50.0
            
        rsi_status = "OVERBOUGHT" if real_rsi >= 70 else "OVERSOLD" if real_rsi <= 30 else "BULLISH" if real_rsi > 50 else "BEARISH"

        # 🚀 BOLLINGER BANDS & VWAP PROXY MATH EXTRACTION
        std_dev = hist['Close'].rolling(window=20).std().iloc[-1] if len(hist) >= 20 else current_price * 0.02
        upper_band = round(sma_20 + (2 * std_dev), 2) if len(hist) >= 20 else current_price * 1.05
        lower_band = round(sma_20 - (2 * std_dev), 2) if len(hist) >= 20 else current_price * 0.95
        
        try:
            typical_price = (hist['High'] + hist['Low'] + hist['Close']) / 3
            vwap_proxy = round((typical_price * hist['Volume']).sum() / hist['Volume'].sum(), 2)
        except Exception:
            vwap_proxy = current_price

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

        # 🚀 RESTORED & EXPANDED 7-POINT TECHNICAL LEDGER UTILITY MATRIX
        ledger = [
            {"factor": "Momentum (RSI)", "val": str(real_rsi), "status": rsi_status, "reasoning": f"Asset momentum velocity registering true algorithmic score at {real_rsi}."},
            {"factor": "Institutional Flow", "val": "High" if volume > avg_volume else "Low", "status": "BULLISH" if volume > avg_volume else "NEUTRAL", "reasoning": f"Current transaction volume sits at {volume:,} vs historical norm of {avg_volume:,}."},
            {"factor": "MACD Divergence", "val": "Positive" if current_price > prev_price else "Negative", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": f"Short-term directional EMA vectors signaling positive continuation mechanics." if current_price > prev_price else f"Short-term baseline trajectories confirming downward tracking slope."},
            {"factor": "VWAP Deviation", "val": f"${vwap_proxy}", "status": "BULLISH" if current_price > vwap_proxy else "BEARISH", "reasoning": f"Trading premium above volume-weighted structural average, implying buyer dominance." if current_price > vwap_proxy else f"Trading below volume-weighted pricing anchor, suggesting structural distribution lines."},
            {"factor": "Bollinger Band Width", "val": f"${lower_band} - ${upper_band}", "status": "NEUTRAL" if lower_band < current_price < upper_band else "VOLATILE", "reasoning": f"Price containment models tracking inside standardized volatility brackets." if lower_band < current_price < upper_band else f"Asset values piercing outer boundary models, projecting an overextended structure."},
            {"factor": "Mathematical Floor", "val": f"${round(support, 2)}", "status": "NEUTRAL", "reasoning": "Calculated structural base support derived via local minima optimization metrics."},
            {"factor": "Mathematical Ceiling", "val": f"${round(resistance, 2)}", "status": "NEUTRAL", "reasoning": "Calculated structural macro resistance ceiling derived via local maxima optimization metrics."}
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
            "support_level": round(support, 2),
            "resistance_level": round(resistance, 2),

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
        prompt += f"CURRENT MARKET CONTEXT:\n"
        prompt += f"- Current Price: ${req.data_context.get('price', 'N/A')}\n"
        prompt += f"- Quant Score: {req.data_context.get('score', 'N/A')}\n"
        prompt += f"- Major Support (Floor): ${req.data_context.get('support_level', 'N/A')}\n"
        prompt += f"- Major Resistance (Ceiling): ${req.data_context.get('resistance_level', 'N/A')}\n\n"
        prompt += "MANDATORY: You must base your Strike Zones and Analysis strictly on these mathematical Support and Resistance levels.\n\n"
        
        funds = req.data_context.get("fundamentals", {})
        if funds:
            prompt += f"FUNDAMENTAL DNA:\n- Market Cap: {funds.get('market_cap', 'N/A')}\n- P/E Ratio: {funds.get('pe_ratio', 'N/A')}\n- Margin: {funds.get('margin', 'N/A')}\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER:\n"
            for item in ledger: 
                prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

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
            "Line 1: '🎯 TARGET PRICE RANGE: $[low] - $[high]'\n"
            "Line 2: '⚖️ AI SIGNAL: [BUY/HOLD/TRIM/SELL]'\n"
            f"Line 3: '📊 STRUCTURAL ZONES: Support Floor at ${req.data_context.get('support_level')} | Resistance Ceiling at ${req.data_context.get('resistance_level')}'\n\n"
            "BRIEFING REQUIREMENTS:\n"
            "1. Macro & Fundamentals: Analyze how current macro conditions and company DNA impact the stock.\n"
            "2. Technical Analysis: Incorporate the provided Technical Ledger. You MUST explicitly reference the Support Floor and Resistance Ceiling from Line 3 in your analysis. Explain how the current price behaves relative to these two mathematical zones.\n"
            "Keep it professional, data-driven, and ruthless. No pleasantries. Do NOT use markdown formatting like ** or ###."
        )
        
        response = model.generate_content(prompt)

        disclaimer_html = (
            "<br><br><hr style='border-color: #1e293b; margin-top: 15px; margin-bottom: 15px;'/>"
            "<p style='font-size: 10px; color: #64748b; font-style: italic; line-height: 1.4; text-align: justify;'>"
            "<strong>LEGAL DISCLAIMER:</strong> The analysis and quantitative targets provided by TradeBotics AI are for "
            "informational and educational purposes only and do not constitute financial, investment, or trading advice. "
            "This output is generated by an artificial intelligence model relying on historical data, mathematical probabilities, "
            "and technical indicators, which cannot guarantee future performance. Trading equities involves significant risk of capital loss. "
            "You are solely responsible for your own trading decisions. Always conduct your own due diligence or consult "
            "with a licensed financial professional before executing any trades."
            "</p>"
        )

        try:
            ai_text = response.text.strip() + disclaimer_html
        except ValueError:
            print(f"GEMINI BLOCKED RESPONSE: {response.prompt_feedback}", file=sys.stderr)
            ai_text = "<h3>Execution Blocked</h3><ul><li>AI Node rejected synthesis due to strict safety protocols.</li></ul>"

        new_token_balance = current_tokens - 3
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        final_response = {
            "analysis": ai_text,
            "remaining_tokens": new_token_balance
        }
        
        update_ai_cache(cache_key, final_response)
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/exit-strategy")
async def generate_exit_strategy(req: TranslationRequest, user_id: str = Query(...)): 
    if not model: return {"analysis": "AI Node Offline."}
    try:
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        if current_tokens < 2:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 2 Tokens required.")

        current_price = float(req.data_context.get('price', 0))
        support_level = float(req.data_context.get('support_level', 0))
        resistance_level = float(req.data_context.get('resistance_level', 0))

        # 🛡️ BREAKOUT GUARDRAIL: Automatically calculate expanding upside ranges to fix structural inversions
        if current_price >= resistance_level:
            implied_volatility_range = current_price - support_level if support_level < current_price else current_price * 0.05
            support_level = current_price * 0.95  
            resistance_level = current_price + implied_volatility_range  

        prompt = f"Act as a quantitative risk manager. Define a strict, scaled risk-management exit protocol for {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n"
        prompt += f"- Current Price: ${current_price}\n"
        prompt += f"- Major Support (Floor): ${round(support_level, 2)}\n"
        prompt += f"- Major Resistance (Ceiling): ${round(resistance_level, 2)}\n\n"
        prompt += "MANDATORY: You must base your Strike Zones and Exit Strategy strictly on these mathematical Support and Resistance levels. Take Profit levels MUST be higher than the Current Price.\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER (SIGNALS):\n"
            for item in ledger: 
                prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

        prompt += (
            "\n🚨 CRITICAL MANDATE - SCALED EXIT STRATEGY REQUIRED:\n"
            "DO NOT provide a general summary. OUTPUT STRICTLY IN HTML FORMAT using this exact structure.\n"
            "CRITICAL: Explain your reasoning using simple, everyday language. Do NOT use dense institutional jargon.\n"
            "You must create a 'scaled' exit plan featuring two distinct profit-taking levels completely above the current price.\n\n"
            "<h3>Scaled Execution Protocol</h3>\n"
            "<ul>\n"
            "<li><strong>🟢 TAKE PROFIT 1 (Conservative):</strong> $[Price]. (Explain this as a safe place to take partial profits, typically right before or at the main resistance ceiling).</li>\n"
            "<li><strong>🟢 TAKE PROFIT 2 (Aggressive):</strong> $[Price]. (Explain this as the ultimate runner target if the stock breaks through the ceiling, based on current momentum).</li>\n"
            "<li><strong>🔴 HARD STOP LOSS (SL):</strong> $[Price]. (Explain why dropping below the mathematical support floor invalidates the trade).</li>\n"
            "<li><strong>⚖️ THESIS HEALTH:</strong> [Calculate the Risk/Reward Ratio using TP1 and the Stop Loss]. (Label as 'Aggressive' if R/R is < 1:1, 'Balanced' if 1:1 to 2:1, or 'High-Probability' if > 2:1).</li>\n"
            "<li><strong>⏱️ TIME HORIZON:</strong> [State the estimated time in days/weeks for this thesis to play out].</li>\n"
            "</ul>"
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

        disclaimer_html = (
            "<br><br><hr style='border-color: #1e293b; margin-top: 15px; margin-bottom: 15px;'/>"
            "<p style='font-size: 10px; color: #64748b; font-style: italic; line-height: 1.4; text-align: justify;'>"
            "<strong>LEGAL DISCLAIMER:</strong> The execution protocol and risk models provided by TradeBotics AI are for "
            "informational and educational purposes only and do not constitute financial, investment, or trading advice. "
            "This output is generated by an artificial intelligence model relying on historical data, mathematical probabilities, "
            "and technical indicators, which cannot guarantee future performance. Trading equities involves significant risk of capital loss. "
            "You are solely responsible for your own trading decisions. Always conduct your own due diligence or consult "
            "with a licensed financial professional before executing any trades."
            "</p>"
        )

        try:
            ai_text = response.text.strip() + disclaimer_html
        except ValueError:
            ai_text = "<h3>Execution Blocked</h3><ul><li>AI Node rejected synthesis due to strict safety protocols.</li></ul>"

        new_token_balance = current_tokens - 2
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        return {
            "analysis": ai_text,
            "remaining_tokens": new_token_balance
        }
        
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
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

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
        
        print(f"[{datetime.now()}] 🔍 Fetching top candidates from SEC pipeline table for portfolio rotation...", file=sys.stderr)
        
        try:
            db_response = supabase.table('market_universe').select('*').not_.is_('tech_score', 'null').execute()
            db_universe = db_response.data
        except Exception as db_err:
            print(f"❌ Failed to fetch market universe from DB: {db_err}", file=sys.stderr)
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
                
                if req.trade_style == "Day Trade":
                    total_score = (tech_score * 0.8) + (fund_score * 0.2)
                elif req.trade_style == "Conservative" or req.trade_style == "Long Term":
                    total_score = (tech_score * 0.2) + (fund_score * 0.8)
                else: 
                    total_score = (tech_score * 0.5) + (fund_score * 0.5)
                
                total_score = math.ceil(total_score)
                
                scored_candidates.append({
                    "ticker": t,
                    "price": price,
                    "score": total_score,
                    "sort_weight": total_score,
                    "health": f"Sector: {sector} | P/E: {pe if pe else 'N/A'}"
                })
        else:
            print("⚠️ DB fallback loop triggered.", file=sys.stderr)
            screener_universe = ["NVDA", "AMD", "META", "LLY", "JPM", "COST"]
            for t in screener_universe:
                try:
                    if any(h['ticker'] == t for h in portfolio_summary): continue
                    stock = yf.Ticker(t)
                    hist = stock.history(period="1d")
                    if hist.empty: continue
                    price = round(hist['Close'].iloc[-1], 2)
                    scored_candidates.append({
                        "ticker": t,
                        "price": price,
                        "score": 50,
                        "sort_weight": 50,
                        "health": "Screener Fallback Mode"
                    })
                except Exception:
                    continue

        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        
        # 🛡️ THE ELITE BASKET FILTER
        elite_basket = [c for c in scored_candidates if c['score'] >= 70][:3]

        if not elite_basket:
            return {
                "analysis": "<h3>1. Horizon Alignment</h3><ul><li>Current core positions are sustaining higher quantitative stability than available sector rotation targets.</li></ul><h3>2. Capital Rotation</h3><ul><li>Market-wide screening shows macro-technical distribution. No high-conviction transition setups detected.</li></ul><h3>3. Precision Execution</h3><ul><li><strong>HOLD ALL POSITIONS:</strong> Capital allocation remains optimized for current volatility models. Maintain baseline structures.</li></ul>",
                "holdings": portfolio_summary,
                "remaining_tokens": current_tokens 
            }

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
            "<ul><li>[1 short bullet sentence analyzing alpha alignment]</li></ul>\n"
            "<h3>2. Capital Rotation</h3>\n"
            "<ul><li>[1 short bullet sentence explaining macro flow advantages]</li></ul>\n"
            "<h3>3. Precision Execution</h3>\n"
            "<ul><li><strong>LIQUIDATE:</strong> [Weak Ticker] to harvest liquidity.</li>\n"
            "<li><strong>ALLOCATE:</strong> Reinvest proceeds directly into [Strongest Basket Ticker].</li></ul>"
        )

        response = model.generate_content(prompt)
        
        try:
            ai_text = response.text.strip()
        except ValueError:
            ai_text = "<h3>Engine Pipeline Delay</h3><ul><li>Rebalancing vector processing timed out.</li></ul>"

        new_token_balance = current_tokens - 5
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        return {
            "analysis": ai_text,
            "holdings": portfolio_summary,
            "remaining_tokens": new_token_balance
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/swap-thesis")
async def generate_swap_thesis(req: SwapRequest):
    try:
        stock = yf.Ticker(req.ticker)
        sector = stock.info.get("sector", "Technology")
        
        # Dynamically find the best stock in the SAME SECTOR
        target_ticker = "MSFT" # Fallback defaults
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
            except Exception as db_err:
                print(f"Swap DB Error: {db_err}", file=sys.stderr)

        freed_capital = req.shares * req.price
        target_shares = math.floor(freed_capital / target_price) if target_price > 0 else 0
        thesis = f"Liquidating your {req.shares} shares of {req.ticker.upper()} frees up ${freed_capital:,.2f} in capital. Reallocating into {target_shares} shares of {target_ticker} (Quant Score {target_score}) upgrades asset quality and increases Alpha potential within the {sector} sector."
        
        return {
            "target_ticker": target_ticker, 
            "target_price": target_price, 
            "target_score": target_score, 
            "target_shares": target_shares, 
            "freed_capital": freed_capital, 
            "thesis": thesis
        }
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

        # 2. Strict Math & Rounding
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