from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import math
import time
from datetime import datetime, timezone
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client  
import sys

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- REQUEST MODELS ---
class TradeRequest(BaseModel):
    user_id: str
    ticker: str
    trade_type: str  
    amount: float    
    mode: str

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

# --- ENDPOINTS ---

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str): 
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
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

        # PULL LIVE NEWS & CALCULATE "HOURS AGO"
        news_list = []
        try:
            finnhub_key = os.getenv("FINNHUB_API_KEY")
            if finnhub_key:
                import urllib.request
                import json
                from datetime import timedelta
                
                # Finnhub requires a date range (last 7 days)
                end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
                
                url = f"https://finnhub.io/api/v1/company-news?symbol={ticker.upper()}&from={start_date}&to={end_date}&token={finnhub_key}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                
                with urllib.request.urlopen(req) as response:
                    finnhub_news = json.loads(response.read().decode())
                    
                    for item in finnhub_news[:5]:
                        # Finnhub returns timestamp in Unix seconds
                        pub_time = item.get("datetime", time.time())
                        hours_ago = int((time.time() - pub_time) / 3600)
                        date_str = "JUST NOW" if hours_ago <= 0 else f"{hours_ago} HR{'S' if hours_ago > 1 else ''} AGO"
                        
                        news_list.append({
                            "title": item.get("headline", "Market Update"),
                            "publisher": item.get("source", "Financial Wire"),
                            "date": date_str,
                            "content": item.get("summary", item.get("url", ""))
                        })
            
            # 🚨 FAILSAFE: If Finnhub key is missing, fallback to yfinance
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
            print(f"News fetch error for {ticker}: {e}", file=sys.stderr)

        ledger = [
            {"factor": "Momentum (RSI)", "val": "62.5" if tech_score > 50 else "38.2", "status": "BULLISH" if tech_score > 50 else "BEARISH", "reasoning": f"{ticker.upper()} is showing upward momentum. Current RSI proxy suggests buying pressure." if tech_score > 50 else f"{ticker.upper()} is losing momentum. RSI proxy suggests selling pressure."},
            {"factor": "Institutional Flow", "val": "High" if volume > avg_volume else "Low", "status": "BULLISH" if volume > avg_volume else "NEUTRAL", "reasoning": f"Current volume of {volume:,} exceeds the historical average of {avg_volume:,}, indicating strong institutional accumulation." if volume > avg_volume else f"Current volume of {volume:,} is below the historical average of {avg_volume:,}, indicating retail-driven consolidation."},
            {"factor": "MACD Divergence", "val": "Positive" if current_price > prev_price else "Negative", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": f"Price action at ${current_price} confirms a positive bullish crossover against the previous close." if current_price > prev_price else f"Price action at ${current_price} indicates a bearish crossover trajectory."},
            {"factor": "VWAP Proximity", "val": f"+{round(((current_price - prev_price)/prev_price)*100, 2)}%" if current_price > prev_price else f"{round(((current_price - prev_price)/prev_price)*100, 2)}%", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": f"The asset is holding firmly above the volume-weighted baseline, supporting the current uptrend." if current_price > prev_price else f"The asset has slipped below the volume-weighted baseline, signaling potential distribution."},
            {"factor": "Bollinger Bands", "val": "Upper Band" if tech_score > 70 else "Lower Band" if tech_score < 40 else "Mid-Band", "status": "BULLISH" if tech_score > 70 else "BEARISH" if tech_score < 40 else "NEUTRAL", "reasoning": f"Price is riding the upper standard deviation channel, suggesting a potential breakout for {ticker.upper()}." if tech_score > 70 else f"Price is testing the lower standard deviation channel, indicating oversold conditions." if tech_score < 40 else f"{ticker.upper()} is consolidating near the mean, awaiting a volatility catalyst."}
        ]

        return {
            "ticker": ticker.upper(),
            "company_name": stock.info.get("shortName", ticker.upper()),
            "price": current_price,
            "score": total_score,
            "tech_score": int(tech_score),
            "fund_score": int(fund_score),
            "volume": f"{volume:,}",
            "vol_surge": vol_surge,
            "ledger": ledger,
            "news": news_list,  # INJECTED LIVE NEWS HEADLINES
            "ai_tactical": f"Market conditions evaluated for {ticker.upper()}. Execution guidance dynamically adjusting to real-time volatility.",
            "fundamentals": {
                "market_cap": formatted_mcap, 
                "pe_ratio": str(round(pe, 2)) if pe else "N/A",
                "debt_equity": str(stock.info.get("debtToEquity", "N/A")),
                "margin": f"{round(margins * 100, 2)}%" if margins else "N/A",
                "sentiment": "BULLISH" if total_score > 65 else "BEARISH" if total_score < 40 else "NEUTRAL",
                "cash_flow": "POSITIVE" if margins and margins > 0 else "NEGATIVE"
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
async def translate_ai(req: TranslationRequest, user_id: str = Query(...)): 
    if not model: return {"analysis": "AI Node Offline."}
    try:
        cache_key = f"TRANSLATE_{req.ticker.upper()}"
        cached_data = check_ai_cache(cache_key)
        
        # Pull user's current token balance to keep UI synced, regardless of cache hit
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens # Inject latest balance without deducting
            return cached_data
            
        if current_tokens < 3:
            raise HTTPException(status_code=402, detail="INSUFFICIENT BANDWIDTH. 3 Tokens required.")

        prompt = f"Act as an elite quantitative analyst. Provide a definitive briefing on {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n- Current Price: ${req.data_context.get('price', 'N/A')}\n- Quant Score: {req.data_context.get('score', 'N/A')}\n\n"
        
        funds = req.data_context.get("fundamentals", {})
        if funds:
            prompt += f"FUNDAMENTAL DNA:\n- P/E Ratio: {funds.get('pe_ratio', 'N/A')}\n- Margin: {funds.get('margin', 'N/A')}\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER:\n"
            for item in ledger: prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

        prompt += (
            "\n🚨 TEMPLATE REQUIREMENT - YOU MUST FOLLOW THIS EXACTLY:\n"
            "Line 1: '🎯 AI STRIKE ZONE: $[low] - $[high]'\n"
            "Line 2: '⚖️ TACTICAL VERDICT: [BUY/HOLD/TRIM/SELL]'\n\n"
            "BRIEFING REQUIREMENTS:\n"
            "1. Macro & Fundamentals: Analyze how current macro conditions and company DNA impact the stock.\n"
            "2. Technical Analysis: Incorporate the provided Technical Ledger. "
            "If BUY, Strike Zone must be in line with current price. "
            "If TRIM/SELL/HOLD, Strike Zone must be based on support/resistance.\n"
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
        # Generate a safe cache key from the article title
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

        # INSIDE @app.post("/summarize")
        
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

        new_token_balance = current_tokens - 1
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        final_response = {
            "summary": [response.text.strip()],
            "remaining_tokens": new_token_balance
        }
        
        update_ai_cache(cache_key, final_response)
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception: 
        return {"summary": ["Summary temporarily unavailable."]}

@app.post("/portfolio-analysis")
async def analyze_portfolio(req: PortfolioRequest, user_id: str = Query(...)): 
    if not model: return {"analysis": "AI Node Offline."}
    try:
        # Cache based on the user's specific portfolio style request
        cache_key = f"PORTFOLIO_{user_id}_{req.trade_style.upper().replace(' ', '_')}"
        cached_data = check_ai_cache(cache_key)
        
        profile_res = supabase.table('profiles').select('ai_token_balance').eq('id', user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_tokens = int(profile_res.data[0]['ai_token_balance'])

        if cached_data:
            cached_data["remaining_tokens"] = current_tokens
            return cached_data
            
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
                hist = stock.history(period="1d")
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
                hist = stock.history(period="1mo")
                if hist.empty: continue
                price = round(hist['Close'].iloc[-1], 2)
                prev_price = round(hist['Close'].iloc[-2], 2)
                
                tech_base = 50
                if len(hist) >= 20:
                    sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                    if price > sma_20: tech_base += 25
                    else: tech_base -= 25
                if price > prev_price: tech_base += 15
                else: tech_base -= 15

                info = stock.info
                pe = info.get("trailingPE", 0)
                margins = info.get("profitMargins", 0)
                sector = info.get("sector", "Macro Profile")

                fund_base = 50
                if pe and 0 < pe < 30: fund_base += 20
                elif pe and pe > 50: fund_base -= 15
                if margins and margins > 0.15: fund_base += 20

                style_bonus = 0
                if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "COIN"]: style_bonus = 20 
                elif req.trade_style == "Swing Trade" and t in ["META", "AVGO", "PLTR"]: style_bonus = 20 
                elif req.trade_style == "Long Term" and t in ["LLY", "COST", "JPM"]: style_bonus = 20 

                total_score = math.ceil(((tech_base + fund_base) / 2) + style_bonus)
                total_score = max(10, min(99, total_score)) 

                health_str = f"Sector: {sector} | P/E: {round(pe, 1) if pe else 'N/A'} | Margin: {round(margins*100, 1) if margins else '0'}%"

                scored_candidates.append({
                    "ticker": t,
                    "price": price,
                    "score": total_score,
                    "health": health_str
                })
            except Exception:
                continue

        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        elite_basket = scored_candidates[:3]

        basket_str = f"QUALIFIED TARGET BASKET FOR {req.trade_style.upper()}:\n"
        for c in elite_basket:
            basket_str += f"- {c['ticker']}: Live Price ${c['price']} | Quant Score: {c['score']} | {c['health']}\n"

        prompt = (
            f"You are a Quantitative Execution Engine. Process this portfolio data:\n{batch_data}\n\n"
            f"Target Strategy Horizon: {req.trade_style}\n\n"
            f"{basket_str}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Be extremely brief. Use bullet points only. No conversational fluff or introductions.\n"
            "2. Under Precision Execution, provide exactly 1 rotation trade. Show the math explicitly: [Shares] * [Live Current Price] = [Total Capital].\n"
            "3. You must select the top target asset solely from the QUALIFIED TARGET BASKET above based on style alignment.\n\n"
            "Structure your output exactly like this:\n"
            f"### 1. Horizon Alignment ({req.trade_style})\n"
            "* [1 short bullet analyzing why current holdings lack optimization for this horizon]\n\n"
            "### 2. Capital Rotation\n"
            "* [1 short bullet explaining the strategic asset class rotation required]\n\n"
            "### 3. Precision Execution\n"
            "- **TRIM [Current Asset Ticker]**: Sell [X] shares * current price $[Live Price] = frees up $[Amount].\n"
            "- **ALLOCATE TO [Target Basket Ticker]**: Buy [X] shares * current price $[Live Price] = deploys $[Amount].\n"
            "- **STRATEGIC LOGIC**: [1 sentence explaining why this asset wins based specifically on its Quant Score, Velocity, or Sector Profile]."
        )

        response = await model.generate_content_async(
            prompt,
            generation_config={"max_output_tokens": 2000, "temperature": 0.1}
        )

        new_token_balance = current_tokens - 5
        supabase.table('profiles').update({'ai_token_balance': new_token_balance}).eq('id', user_id).execute()

        final_response = {
            "analysis": response.text.strip(),
            "holdings": portfolio_summary,
            "remaining_tokens": new_token_balance
        }
        
        update_ai_cache(cache_key, final_response)
        return final_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
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
        target_hist = target_stock.history(period="1d")
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
async def execute_trade(req: TradeRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection offline.")
    try:
        ticker = req.ticker.upper()
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if hist.empty: raise HTTPException(status_code=404, detail="Asset pricing unavailable.")
        live_price = float(hist['Close'].iloc[-1])

        if req.mode == "DOLLARS":
            trade_cost = req.amount
            trade_shares = req.amount / live_price
        else:
            trade_shares = req.amount
            trade_cost = req.amount * live_price

        profile_res = supabase.table('profiles').select('virtual_cash_balance').eq('id', req.user_id).execute()
        if not profile_res.data: raise HTTPException(status_code=404, detail="Operative profile not found.")
        current_cash = float(profile_res.data[0]['virtual_cash_balance'])

        portfolio_res = supabase.table('portfolio').select('*').eq('user_id', req.user_id).eq('ticker', ticker).execute()
        current_position = portfolio_res.data[0] if portfolio_res.data else None
        current_shares_held = float(current_position['shares']) if current_position else 0.0

        if req.trade_type == "BUY":
            if trade_cost > current_cash: raise HTTPException(status_code=400, detail="Insufficient virtual capital.")
            new_cash = current_cash - trade_cost
            
            if current_position:
                old_total_cost = current_shares_held * float(current_position['cost_basis'])
                new_total_shares = current_shares_held + trade_shares
                new_avg_cost = (old_total_cost + trade_cost) / new_total_shares
                
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
            if trade_shares > current_shares_held: raise HTTPException(status_code=400, detail="Insufficient shares in vault.")
            new_cash = current_cash + trade_cost
            new_total_shares = current_shares_held - trade_shares

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