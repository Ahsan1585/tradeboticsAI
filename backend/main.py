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
import cloudscraper

load_dotenv()

# ==========================================
# --- THE BROWSER SPOOFER (CLOUDFLARE BYPASS) ---
# ==========================================
def get_yf_session():
    """Uses Cloudscraper with randomized headers to bypass Render IP bans."""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # Randomize the User-Agent to slip past WAF fingerprinting
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    ]
    scraper.headers.update({
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    return scraper

# ==========================================
# --- KEEP ALIVE CONFIGURATION ---
# ==========================================
# ⚠️ REPLACE WITH YOUR ACTUAL LIVE RENDER APP URL
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
# --- THE STEALTH DATA WORKER ---
# ==========================================
async def staleness_worker_loop():
    """Runs continuously every 3 minutes. Sweeps 15 stale tickers using Cloudscraper."""
    await asyncio.sleep(60)
    
    while True:
        if supabase:
            try:
                # 🧹 1. DATABASE CLEANUP
                try:
                    expiration_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
                    supabase.table('ai_scan_cache').delete().lt('last_scanned', expiration_cutoff).execute()
                except Exception:
                    pass

                # 🚀 2. MICRO-BATCHING
                response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(15).execute()
                stale_tickers = [row['ticker'] for row in response.data]
                
                # 3. Database Seeding 
                if not stale_tickers:
                    print(f"[{datetime.now()}] ⚠️ EMPTY QUEUE: Seeding database from Wikipedia S&P 500...", file=sys.stderr)
                    universe = get_market_universe()
                    for i in range(0, len(universe), 200):
                        chunk = universe[i:i + 200]
                        seed_data = [{'ticker': t} for t in chunk]
                        try:
                            supabase.table('market_universe').upsert(seed_data).execute()
                        except Exception:
                            pass
                        
                    response = supabase.table('market_universe').select('ticker').order('last_scanned', desc=False, nullsfirst=True).limit(15).execute()
                    stale_tickers = [row['ticker'] for row in response.data]

                print(f"[{datetime.now()}] 🔍 STEALTH BATCH: Processing {len(stale_tickers)} tickers...", file=sys.stderr)
                rate_limit_hit = False
                
                # 🛡️ Create one heavily disguised master session
                master_session = get_yf_session()
                
                # # 4. Gather Data
                for t in stale_tickers:
                    current_time = datetime.now(timezone.utc).isoformat()
                    
                    try:
                        stock = yf.Ticker(t, session=master_session)
                        
                        # 1. UPGRADED MEMORY: Fetch 3 months of data to calculate multi-horizon metrics
                        hist = stock.history(period="3mo")
                        
                        if hist.empty:
                            supabase.table('market_universe').delete().eq('ticker', t).execute()
                            continue
                            
                        if len(hist) < 40: # We need at least 40 trading days to construct the 1-month trend proxy
                            supabase.table('market_universe').update({'last_scanned': current_time}).eq('ticker', t).execute()
                            continue
                        
                        price = float(hist['Close'].iloc[-1])
                        prev_price = float(hist['Close'].iloc[-2])
                        daily_change = ((price - prev_price) / prev_price) * 100

                        # 2. Fetch Fundamentals (Added Revenue Growth to eliminate Bank/Value Bias)
                        pe, margins, rev_growth, sector = 0, 0, 0, "S&P 500"
                        try:
                            info = stock.info
                            pe = info.get("trailingPE", 0)
                            margins = info.get("profitMargins", 0)
                            rev_growth = info.get("revenueGrowth", 0) 
                            sector = info.get("sector", "Macro Profile")
                        except Exception:
                            # If info endpoint is throttled, safely proceed with baseline data
                            pass

                        # =======================================================
                        # --- MULTI-FACTOR QUANT ENGINE 2.0 (DUAL-HORIZON) ---
                        # =======================================================
                        
                        # --- 1. TECHNICAL ENGINE (1-Week Velocity & 1-Month Trend) ---
                        tech_base = 50
                        
                        sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                        sma_40 = hist['Close'].rolling(window=40).mean().iloc[-1] # 1-Month Trend Proxy
                        std_dev = hist['Close'].rolling(window=20).std().iloc[-1]
                        upper_band = sma_20 + (2 * std_dev)
                        lower_band = sma_20 - (2 * std_dev)

                        # Trend Alignment (1-Month Horizon Support)
                        if price > sma_20: tech_base += 10
                        else: tech_base -= 10
                        
                        if sma_20 > sma_40: tech_base += 10 # Strong medium-term structural layout
                        else: tech_base -= 5

                        # Mean Reversion & Extreme Volatility (1-Week Swing Target)
                        if price > upper_band: tech_base -= 15 # Overextended this week, high pullback risk
                        elif price < lower_band: tech_base += 15 # Drastically oversold, primed for a technical bounce

                        # MACD Momentum Proxy
                        if price > prev_price: tech_base += 5
                        else: tech_base -= 5

                        # RSI Execution Momentum
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

                        if real_rsi >= 70: tech_base -= 15 # Overbought ceiling reached
                        elif real_rsi <= 30: tech_base += 15 # Deep exhaustion floor reached
                        elif 50 < real_rsi < 65: tech_base += 5 # Healthy accumulation track

                        # Institutional Volume Profile
                        try:
                            volume = int(hist['Volume'].iloc[-1])
                            avg_volume = int(hist['Volume'].rolling(20).mean().iloc[-1])
                            if volume > (avg_volume * 1.2): tech_base += 10 # Heavy institutional conviction
                            else: tech_base -= 5
                        except Exception:
                            pass
                            
                        # Volume Weighted Average Price (VWAP Proxy)
                        try:
                            typical_price = (hist['High'] + hist['Low'] + hist['Close']) / 3
                            vwap_proxy = round((typical_price * hist['Volume']).sum() / hist['Volume'].sum(), 2)
                            if price > vwap_proxy: tech_base += 10
                            else: tech_base -= 10
                        except Exception:
                            pass

                        tech_score = max(10, min(95, tech_base))
                        
                        # --- 2. FUNDAMENTAL ENGINE (Balanced for Growth, Software & Value) ---
                        fund_base = 50
                        
                        # Valuation Metric (Maintains Value/Bank balance)
                        if pe and 0 < pe < 25: fund_base += 10
                        elif pe and 25 <= pe <= 45: fund_base += 5 # Reasonable multiple for tech scaling
                        elif pe and pe > 50: fund_base -= 15
                        
                        # Operational Efficiency (Maintains high-performing structures)
                        if margins and margins > 0.20: fund_base += 10
                        elif margins and margins > 0.10: fund_base += 5
                        elif margins and margins < 0: fund_base -= 20
                        
                        # Explosive Growth Factor (The Equalizer: Elevates Tech & Penalizes Stagnant Assets)
                        if rev_growth and rev_growth > 0.15: fund_base += 15 # Top-tier institutional growth
                        elif rev_growth and rev_growth > 0.05: fund_base += 5
                        elif rev_growth and rev_growth < 0: fund_base -= 15 # Decelerating revenue metrics penalized

                        fund_score = max(10, min(95, fund_base))
                        
                        # Save successful data to Supabase
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
                        if "Too Many Requests" in error_msg or "429" in error_msg or "Rate limited" in error_msg:
                            print(f"[{datetime.now()}] 🛑 RATE LIMIT CAUGHT: Aborting micro-batch to cool down...", file=sys.stderr)
                            rate_limit_hit = True 
                            break 
                            
                        if "Not Found" in error_msg or "delisted" in error_msg.lower():
                            supabase.table('market_universe').delete().eq('ticker', t).execute()
                        else:
                            supabase.table('market_universe').update({'last_scanned': current_time}).eq('ticker', t).execute()

                    # 🚦 ANTI-BOT THROTTLE (Maintained for safety)
                    await asyncio.sleep(random.uniform(1.0, 2.5))
                        
                # 🚀 5. SMART CYCLE SLEEP
                if rate_limit_hit:
                    print(f"[{datetime.now()}] 💤 ENTERING PENALTY BOX: Sleeping for 15 minutes to clear ban.", file=sys.stderr)
                    await asyncio.sleep(900)
                else:
                    print(f"[{datetime.now()}] ✅ Stealth Batch complete. Sleeping for 3 minutes.", file=sys.stderr)
                    await asyncio.sleep(180) 
                
            except Exception as e:
                print(f"❌ CRITICAL WORKER ERROR: {e}", file=sys.stderr)
                await asyncio.sleep(60) 
        else:
            await asyncio.sleep(60)

@asynccontextmanager
async def lifecycle(app: FastAPI):
    # Running both the worker loop and the internal keep-alive loop
    asyncio.create_task(keep_alive_loop())
    asyncio.create_task(staleness_worker_loop())
    yield

app = FastAPI(lifespan=lifecycle)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
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
    except Exception:
        supabase = None
else:
    supabase = None

# --- AI CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

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
            if time_diff < 1800:
                return record['cached_response']
    except Exception:
        pass
    return None

def update_ai_cache(cache_key: str, payload: dict):
    if not supabase: return
    try:
        supabase.table('ai_scan_cache').upsert({
            'cache_key': cache_key,
            'last_scanned': datetime.now(timezone.utc).isoformat(),
            'cached_response': payload
        }).execute()
    except Exception:
        pass

# ==========================================
# --- MATH ENGINE ---
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
    """Fetches the elite S&P 500, Nasdaq 100, and Dow Jones universes from Wikipedia."""
    print(f"[{datetime.now()}] 📡 Fetching Elite S&P 500, Nasdaq 100, & Dow...", file=sys.stderr)
    try:
        # 1. Get S&P 500
        sp_url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        sp_html = requests.get(sp_url, headers={'User-Agent': 'Mozilla/5.0'}).text
        sp_df = pd.read_html(io.StringIO(sp_html))[0]
        sp_tickers = sp_df['Symbol'].tolist()
        
        # 2. Get Nasdaq 100
        ndx_url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        ndx_html = requests.get(ndx_url, headers={'User-Agent': 'Mozilla/5.0'}).text
        ndx_df = pd.read_html(io.StringIO(ndx_html), match='Ticker')[0]
        ndx_tickers = ndx_df['Ticker'].tolist()

        # 3. Get Dow Jones Industrial Average
        dow_url = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
        dow_html = requests.get(dow_url, headers={'User-Agent': 'Mozilla/5.0'}).text
        dow_df = pd.read_html(io.StringIO(dow_html))[1]
        dow_tickers = dow_df['Symbol'].tolist()
        
        # Combine all lists, remove duplicates, and fix dot notation (BRK.B -> BRK-B)
        combined = list(set(sp_tickers + ndx_tickers + dow_tickers))
        clean_tickers = [str(t).replace('.', '-') for t in combined]
        
        print(f"✅ UNIVERSE UPDATED: {len(clean_tickers)} elite symbols loaded.", file=sys.stderr)
        return clean_tickers
    except Exception as e:
        print(f"❌ WIKIPEDIA FETCH ERROR: {e} | Activating Top 100 Emergency Fallback Universe...", file=sys.stderr)
        return [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "TSLA", "V",
            "UNH", "JPM", "XOM", "MA", "WMT", "JNJ", "AVGO", "PG", "ORCL", "COST",
            "HD", "CVX", "MRK", "AMD", "NFLX", "KO", "PEP", "BAC", "ADBE", "MCD",
            "CRM", "ABBV", "TMO", "CSCO", "ACN", "WFC", "QCOM", "LIN", "INTU", "VZ",
            "GE", "AMGN", "TXN", "PM", "DIS", "NEE", "HON", "IBM", "LOW", "CAT",
            "UNP", "SCHW", "INTC", "BKNG", "SPGI", "AMAT", "DE", "ISRG", "AXP", "TJX",
            "MDLZ", "NOW", "SYK", "LRCX", "ADI", "MS", "GS", "PGR", "REGN", "MMC",
            "ETN", "VRTX", "RTX", "LMT", "BSX", "CVS", "PANW", "MU", "CI", "NKE",
            "PLTR", "BX", "HOOD", "COIN", "SMCI", "SBUX", "MELI", "UBER", "MSTR", "PANW",
            "GILD", "ABT", "MDT", "BA", "F", "GM", "CAT", "SO", "DUK", "PYPL"
        ]

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
        
        if not db_universe:
            return {"results": []}

        scored_candidates = []
        for row in db_universe:
            t = row['ticker']
            tech_score = row['tech_score']
            fund_score = row['fund_score']
            sector = row['sector']
            daily_change = row['daily_change']
            db_price = row['price']

            if req.risk_level == "Aggressive":
                total_score = (tech_score * 0.8) + (fund_score * 0.2)
            elif req.risk_level == "Conservative":
                total_score = (tech_score * 0.2) + (fund_score * 0.8)
            else:
                total_score = (tech_score * 0.5) + (fund_score * 0.5)

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

        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        top_50 = scored_candidates[:50]

        final_results = []
        for candidate in top_50:
            try:
                stock = yf.Ticker(candidate['ticker'], session=get_yf_session())
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

    except Exception:
        return {"results": []}

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str): 
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")

    ticker_upper = ticker.upper()
    now = time.time()

    if ticker_upper in market_cache:
        cached_time, cached_data = market_cache[ticker_upper]
        if now - cached_time < MARKET_CACHE_TTL:
            return cached_data

    try:
        stock = yf.Ticker(ticker_upper, session=get_yf_session())
        hist = stock.history(period="3mo", prepost=True)
        if hist.empty: raise HTTPException(status_code=404, detail="Ticker data not found.")

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
            if raw_mcap >= 1e12: formatted_mcap = f"${raw_mcap / 1e12:.2f} Trillion"
            else: formatted_mcap = f"${raw_mcap / 1e9:.2f} Billion"

        # --- ROBUST EARNINGS DATE EXTRACTION ---
        calendar = stock.calendar
        next_earnings = "Unknown"
        
        if calendar is not None:
            try:
                # yfinance format 1: Dictionary
                if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                    dates = calendar['Earnings Date']
                    if isinstance(dates, list) and len(dates) > 0:
                        # Extract the first date from the list and strip any time data
                        next_earnings = str(dates[0]).split(' ')[0]
                    elif dates:
                        next_earnings = str(dates).split(' ')[0]
                
                # yfinance format 2: Pandas DataFrame
                elif hasattr(calendar, 'empty') and not calendar.empty and 'Earnings Date' in calendar:
                    val = calendar['Earnings Date'].iloc[0]
                    if hasattr(val, 'date'):
                        next_earnings = str(val.date())
                    else:
                        next_earnings = str(val).split(' ')[0]
            except Exception:
                # If Yahoo changes their format again, safely fail and pass "Unknown"
                next_earnings = "Unknown"

        # --- MULTI-FACTOR QUANT ENGINE (LIVE) ---
        tech_base = 50
        
        std_dev = hist['Close'].rolling(window=20).std().iloc[-1] if len(hist) >= 20 else current_price * 0.02
        sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1] if len(hist) >= 20 else current_price
        upper_band = round(sma_20 + (2 * std_dev), 2)
        lower_band = round(sma_20 - (2 * std_dev), 2)
        
        if len(hist) >= 20:
            if current_price > sma_20: tech_base += 10
            else: tech_base -= 10
            
            if current_price > upper_band: tech_base -= 10
            elif current_price < lower_band: tech_base += 10

        if current_price > prev_price: tech_base += 10
        else: tech_base -= 10

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
        
        if real_rsi >= 70: tech_base -= 15
        elif real_rsi <= 30: tech_base += 15
        elif real_rsi > 50: tech_base += 5

        try:
            typical_price = (hist['High'] + hist['Low'] + hist['Close']) / 3
            vwap_proxy = round((typical_price * hist['Volume']).sum() / hist['Volume'].sum(), 2)
        except Exception:
            vwap_proxy = current_price
            
        if volume > avg_volume: tech_base += 10
        else: tech_base -= 5
        
        if current_price > vwap_proxy: tech_base += 10
        else: tech_base -= 10

        tech_score = max(10, min(95, tech_base))
        
        fund_base = 50
        if pe and 0 < pe < 25: fund_base += 20
        elif pe and pe > 50: fund_base -= 20
        if margins and margins > 0.15: fund_base += 20
        elif margins and margins < 0: fund_base -= 25
        fund_score = max(10, min(95, fund_base))
        
        total_score = math.ceil((tech_score + fund_score) / 2)
        vol_surge = f"{round((volume / avg_volume) * 100, 1)}%" if avg_volume > 0 else "N/A"

        news_list = []
        try:
            finnhub_key = os.getenv("FINNHUB_API_KEY")
            if finnhub_key:
                end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker_upper}&from={start_date}&to={end_date}&token={finnhub_key}"
                req = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                finnhub_news = req.json()
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
        except Exception:
            pass

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
            fallback_res = supabase.table('market_universe').select('*').eq('ticker', ticker_upper).execute()
            if fallback_res.data:
                db_data = fallback_res.data[0]
                total_score = math.ceil((db_data['tech_score'] + db_data['fund_score']) / 2)
                fallback_response = {
                    "ticker": ticker_upper,
                    "company_name": f"{ticker_upper} (Cached Data)",
                    "price": db_data['price'],
                    "score": total_score,
                    "tech_score": db_data['tech_score'],
                    "fund_score": db_data['fund_score'],
                    "volume": "N/A",
                    "vol_surge": "N/A",
                    "ledger": [
                        {"factor": "Live Market Status", "val": "Delayed", "status": "NEUTRAL", "reasoning": "Live data momentarily offline. Displaying last recorded structural baseline."}
                    ],
                    "news": [],
                    "ai_tactical": "Live execution feeds are temporarily throttling. Technical scores reflect end-of-day baseline structure.",
                    "support_level": 0,
                    "resistance_level": 0,
                    "fundamentals": {
                        "market_cap": "N/A", 
                        "pe_ratio": str(db_data['pe']),
                        "debt_equity": "N/A",
                        "margin": "N/A",
                        "sentiment": "NEUTRAL",
                        "cash_flow": "N/A",
                        "next_earnings": "Unknown" 
                    }
                }
                market_cache[ticker_upper] = (now, fallback_response)
                return fallback_response
            else:
                raise HTTPException(status_code=429, detail="Live market data offline and no cached database metrics available.")
                
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

        # 🛡️ SAFETY FALLBACKS FOR MISSING DATA
        support_raw = req.data_context.get('support_level')
        res_raw = req.data_context.get('resistance_level')
        
        support_str = f"${support_raw}" if support_raw and support_raw > 0 else "Calculating Base..."
        res_str = f"${res_raw}" if res_raw and res_raw > 0 else "Price Discovery Mode"

        prompt = f"Act as an elite quantitative analyst. Provide a definitive briefing on {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n"
        prompt += f"- Current Price: ${req.data_context.get('price', 'N/A')}\n"
        prompt += f"- Quant Score: {req.data_context.get('score', 'N/A')}\n"
        prompt += f"- Major Support (Floor): {support_str}\n"
        prompt += f"- Major Resistance (Ceiling): {res_str}\n\n"
        
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

        # 🛑 ANTI-HALLUCINATION LEASH
        next_earnings = funds.get("next_earnings", "N/A")
        if next_earnings != "N/A" and next_earnings != "Unknown":
            prompt += f"\nEARNINGS RISK:\n- Next Earnings Date: {next_earnings}\n"
            prompt += "If the Next Earnings Date is today or tomorrow, heavily weigh the binary risk of an earnings gap in your tactical verdict.\n"
        else:
            prompt += "\nEARNINGS RISK:\n- Next Earnings Date: UNKNOWN\n"
            prompt += "CRITICAL MANDATE: The earnings date is currently unavailable. You MUST explicitly state that the catalyst timeline is pending. DO NOT invent, estimate, or assume a future date under any circumstances.\n"

        prompt += (
            "\n🚨 CRITICAL FORMATTING MANDATE:\n"
            "OUTPUT STRICTLY IN CLEAN MARKDOWN. DO NOT use HTML tags. You must use markdown headings (###), bold text (**), and bullet points (*) to make the briefing highly scannable and user-friendly.\n\n"
            "Follow this exact structure:\n"
            "### 🎯 TARGET PRICE RANGE: $[low] - $[high]\n"
            "### ⚖️ AI SIGNAL: [BUY/HOLD/TRIM/SELL]\n"
            f"**📊 STRUCTURAL ZONES:** Support: {support_str} | Resistance: {res_str}\n\n"
            "---\n\n"
            "### 1. Macro & Fundamentals\n"
            "* **Valuation:** [1 concise sentence evaluating P/E and Market Cap]\n"
            "* **Efficiency:** [1 concise sentence evaluating Profit Margin]\n"
            "* **Catalyst Risk:** [1 concise sentence on the Earnings Date or News context]\n\n"
            "### 2. Technical Analysis\n"
            "* **Price Action:** [Analyze current price relative to the structural zones]\n"
            "* **Momentum (RSI & MACD):** [Synthesize the RSI and MACD ledger signals]\n"
            "* **Institutional Flow & VWAP:** [Synthesize Volume and VWAP ledger signals]\n"
            "* **Volatility:** [Synthesize Bollinger Bands ledger signal]\n\n"
            "### 3. The Verdict\n"
            "[A final, punchy 2-sentence conclusion summarizing the Quant Score and justifying your AI Signal]"
        )
        
        response = model.generate_content(prompt)

        # Swapped to pure markdown so it renders beautifully in standard text/markdown widgets
        disclaimer_md = (
            "\n\n---\n"
            "*LEGAL DISCLAIMER: The analysis and quantitative targets provided by TradeBotics AI are for "
            "informational and educational purposes only and do not constitute financial, investment, or trading advice. "
            "This output is generated by an artificial intelligence model relying on historical data, mathematical probabilities, "
            "and technical indicators, which cannot guarantee future performance. Trading equities involves significant risk of capital loss. "
            "You are solely responsible for your own trading decisions. Always conduct your own due diligence or consult "
            "with a licensed financial professional before executing any trades.*"
        )

        try:
            ai_text = response.text.strip() + disclaimer_md
        except ValueError:
            ai_text = "### Execution Blocked\n* AI Node rejected synthesis due to strict safety protocols."

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
        cache_key = f"EXIT_STRAT_{req.ticker.upper()}"
        cached_data = check_ai_cache(cache_key)
        
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens
            return cached_data

        if current_tokens < 2:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 2 Tokens required.")

        current_price = float(req.data_context.get('price', 0))
        support_level = float(req.data_context.get('support_level', 0))
        resistance_level = float(req.data_context.get('resistance_level', 0))

        if current_price >= resistance_level:
            implied_volatility_range = current_price - support_level if support_level < current_price else current_price * 0.05
            support_level = current_price * 0.95  
            resistance_level = current_price + implied_volatility_range  
            
        distance_to_support = round(current_price - support_level, 2)
        distance_to_resistance = round(resistance_level - current_price, 2)

        prompt = f"Act as a quantitative risk manager. Define a strict, scaled risk-management exit protocol for {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n"
        prompt += f"- Current Price: ${current_price}\n"
        prompt += f"- Major Support (Floor): ${round(support_level, 2)}\n"
        prompt += f"- Major Resistance (Ceiling): ${round(resistance_level, 2)}\n"
        prompt += f"- Distance to Support: ${distance_to_support}\n"
        prompt += f"- Distance to Resistance: ${distance_to_resistance}\n\n"
        prompt += "MANDATORY: You must base your Strike Zones and Exit Strategy strictly on these mathematical Support and Resistance levels. Take Profit levels MUST be higher than the Current Price.\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER (SIGNALS):\n"
            for item in ledger: 
                prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

        prompt += (
            "\n🚨 CRITICAL MANDATE - SCALED EXIT STRATEGY REQUIRED:\n"
            "DO NOT provide a general summary. OUTPUT STRICTLY IN HTML FORMAT using this exact structure.\n"
            "CRITICAL: Before suggesting an exit, evaluate the 'Thesis Health'.\n"
            "1. If the current price is within 5% of the Hard Stop Loss, explicitly label the thesis as 'Under Stress' and suggest a 'Hold for Support Test' rather than a profit-taking level.\n"
            "2. Do not suggest a Take Profit level if the price is significantly closer to the Stop Loss than the Resistance Ceiling.\n"
            "3. Always explain: 'Current price is testing structural support; wait for a bounce before planning exit strategies' if applicable.\n\n"
            "<h3>Scaled Execution Protocol</h3>\n"
            "<ul>\n"
            f"<li><strong>📏 DISTANCE TO TARGETS:</strong> Support is ${distance_to_support} away. Resistance is ${distance_to_resistance} away.</li>\n"
            "<li><strong>🟢 TAKE PROFIT 1 (Conservative):</strong> $[Price]. (Explain this as a safe place to take partial profits, typically right before or at the main resistance ceiling).</li>\n"
            "<li><strong>🟢 TAKE PROFIT 2 (Aggressive):</strong> $[Price]. (Explain this as the ultimate runner target if the stock breaks through the ceiling, based on current momentum).</li>\n"
            "<li><strong>🔴 HARD STOP LOSS (SL):</strong> $[Price]. (Explain why dropping below the mathematical support floor invalidates the trade).</li>\n"
            "<li><strong>⚖️ THESIS HEALTH:</strong> [Calculate the Risk/Reward Ratio using TP1 and the Stop Loss]. (Label as 'Under Stress', 'Aggressive', 'Balanced', or 'High-Probability').</li>\n"
            "<li><strong>⏱️ TIME HORIZON:</strong> [State the estimated time in days/weeks for this thesis to play out].</li>\n"
            "</ul>"
        )

        response = model.generate_content(prompt)

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
        
        response = model.generate_content(prompt)

        try:
            ai_text = response.text.strip()
        except ValueError:
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
    except Exception: 
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

        try:
            db_response = supabase.table('market_universe').select('*').not_.is_('tech_score', 'null').execute()
            db_universe = db_response.data
        except Exception:
            db_universe = []

        portfolio_summary = []
        if not req.holdings: raise HTTPException(status_code=400, detail="No holdings provided.")

        for h in req.holdings:
            try:
                ticker = str(h.get('ticker', '')).strip().upper()
                shares = float(h.get('shares', 0))
                cost = float(h.get('cost_basis', 0))
                if not ticker: continue
                if ticker == "ETHU": ticker = "ETH-USD"
                
                stock = yf.Ticker(ticker, session=get_yf_session())
                hist = stock.history(period="1d", prepost=True)
                if hist.empty: continue 
                
                price = round(hist['Close'].iloc[-1], 2)

                db_match = next((item for item in db_universe if item["ticker"] == ticker), None)
                score = math.ceil((db_match['tech_score'] + db_match['fund_score']) / 2) if db_match else 75
                sector = db_match['sector'] if db_match else stock.info.get("sector", "Unknown")

                portfolio_summary.append({
                    "ticker": ticker,
                    "shares": shares,
                    "avg_cost": cost,
                    "current_price": price,
                    "score": score, 
                    "sector": sector,
                    "value": round(shares * price, 2)
                })
            except Exception:
                continue 

        if not portfolio_summary: return {"analysis": "No valid data could be retrieved.", "holdings": []}
        
        scored_candidates = []
        if db_universe:
            for row in db_universe:
                t = row['ticker']
                if any(h['ticker'] == t for h in portfolio_summary): continue
                    
                tech_score = row['tech_score']
                fund_score = row['fund_score']
                sector = row['sector']
                
                if req.trade_style == "Day Trade": total_score = (tech_score * 0.8) + (fund_score * 0.2)
                elif req.trade_style in ["Conservative", "Long Term"]: total_score = (tech_score * 0.2) + (fund_score * 0.8)
                else: total_score = (tech_score * 0.5) + (fund_score * 0.5)
                
                scored_candidates.append({
                    "ticker": t,
                    "price": row['price'],
                    "score": math.ceil(total_score),
                    "sort_weight": math.ceil(total_score),
                    "sector": sector
                })
        else:
            screener_universe = ["NVDA", "AMD", "META", "LLY", "JPM", "COST"]
            for t in screener_universe:
                try:
                    if any(h['ticker'] == t for h in portfolio_summary): continue
                    stock = yf.Ticker(t, session=get_yf_session())
                    hist = stock.history(period="1d")
                    if hist.empty: continue
                    scored_candidates.append({
                        "ticker": t,
                        "price": round(hist['Close'].iloc[-1], 2),
                        "score": 50,
                        "sort_weight": 50,
                        "sector": "Fallback Mode"
                    })
                except Exception:
                    continue

        scored_candidates.sort(key=lambda x: x['sort_weight'], reverse=True)
        elite_basket = [c for c in scored_candidates if c['score'] >= 70][:3]

        if not elite_basket or not portfolio_summary:
            return {
                "analysis": "<h3>1. Horizon Alignment</h3><ul><li>Current core positions are sustaining higher quantitative stability than available sector rotation targets.</li></ul><h3>2. Capital Rotation</h3><ul><li>Market-wide screening shows macro-technical distribution. No high-conviction transition setups detected.</li></ul><h3>3. Precision Execution</h3><ul><li><strong>HOLD ALL POSITIONS:</strong> Capital allocation remains optimized for current volatility models. Maintain baseline structures.</li></ul>",
                "holdings": portfolio_summary,
                "remaining_tokens": current_tokens 
            }

        weakest_asset = min(portfolio_summary, key=lambda x: x['score'])
        strongest_target = elite_basket[0]
        score_delta = strongest_target['score'] - weakest_asset['score']
        confidence_pct = min(99, max(50, 50 + (score_delta * 2)))

        prompt = (
            f"You are a Quantitative Execution Engine.\n"
            f"Target Horizon: {req.trade_style}\n\n"
            f"ROTATION DIRECTIVE:\n"
            f"- LIQUIDATE: {weakest_asset['ticker']} (Score: {weakest_asset['score']}, Sector: {weakest_asset['sector']})\n"
            f"- ALLOCATE: {strongest_target['ticker']} (Score: {strongest_target['score']}, Sector: {strongest_target['sector']})\n"
            f"- DELTA: +{score_delta} Points\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "Write the institutional narrative for this exact rotation. OUTPUT STRICTLY IN HTML FORMAT. DO NOT use markdown.\n"
            "Structure exactly like this:\n"
            "<h3>1. Horizon Alignment</h3>\n<ul><li>[1 short sentence analyzing alpha alignment]</li></ul>\n"
            "<h3>2. Capital Rotation</h3>\n<ul><li>[1 short sentence explaining the sector shift and the quantitative improvement]</li></ul>\n"
            f"<h3>3. Precision Execution</h3>\n<ul><li><strong>LIQUIDATE:</strong> {weakest_asset['ticker']} to harvest liquidity.</li>\n"
            f"<li><strong>ALLOCATE:</strong> Reinvest proceeds directly into {strongest_target['ticker']}.</li></ul>\n"
            f"<h3>4. Rotation Confidence</h3>\n<ul><li><strong>Confidence:</strong> [||||||----] {confidence_pct}%</li></ul>"
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
        stock = yf.Ticker(req.ticker, session=get_yf_session())
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
            except Exception:
                pass

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
    except Exception:
        pass

    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")
    
    try:
        ticker = req.ticker.upper()
        
        stock = yf.Ticker(ticker, session=get_yf_session())
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

        profile_res = supabase.table('profiles').select('virtual_cash_balance').eq('id', req.user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_cash = float(profile_res.data[0]['virtual_cash_balance'])

        portfolio_res = supabase.table('portfolio').select('*').eq('user_id', req.user_id).eq('ticker', ticker).execute()
        current_position = portfolio_res.data[0] if portfolio_res.data else None
        current_shares_held = float(current_position['shares']) if current_position else 0.0

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
        raise HTTPException(status_code=500, detail=str(e))