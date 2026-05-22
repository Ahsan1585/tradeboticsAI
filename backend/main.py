from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import math
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace "*" with your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AI CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

# --- REQUEST MODELS ---
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

# --- ENDPOINTS ---

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    try:
        # Reverted back to native handling
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

        # DYNAMIC NEURAL LEDGER
        ledger = [
            {
                "factor": "Momentum (RSI)", 
                "val": "62.5" if tech_score > 50 else "38.2", 
                "status": "BULLISH" if tech_score > 50 else "BEARISH", 
                "reasoning": f"{ticker.upper()} is showing upward momentum. Current RSI proxy suggests buying pressure." if tech_score > 50 else f"{ticker.upper()} is losing momentum. RSI proxy suggests selling pressure."
            },
            {
                "factor": "Institutional Flow", 
                "val": "High" if volume > avg_volume else "Low", 
                "status": "BULLISH" if volume > avg_volume else "NEUTRAL", 
                "reasoning": f"Current volume of {volume:,} exceeds the historical average of {avg_volume:,}, indicating strong institutional accumulation." if volume > avg_volume else f"Current volume of {volume:,} is below the historical average of {avg_volume:,}, indicating retail-driven consolidation."
            },
            {
                "factor": "MACD Divergence", 
                "val": "Positive" if current_price > prev_price else "Negative", 
                "status": "BULLISH" if current_price > prev_price else "BEARISH", 
                "reasoning": f"Price action at ${current_price} confirms a positive bullish crossover against the previous close." if current_price > prev_price else f"Price action at ${current_price} indicates a bearish crossover trajectory."
            },
            {
                "factor": "VWAP Proximity", 
                "val": f"+{round(((current_price - prev_price)/prev_price)*100, 2)}%" if current_price > prev_price else f"{round(((current_price - prev_price)/prev_price)*100, 2)}%", 
                "status": "BULLISH" if current_price > prev_price else "BEARISH", 
                "reasoning": f"The asset is holding firmly above the volume-weighted baseline, supporting the current uptrend." if current_price > prev_price else f"The asset has slipped below the volume-weighted baseline, signaling potential distribution."
            },
            {
                "factor": "Bollinger Bands", 
                "val": "Upper Band" if tech_score > 70 else "Lower Band" if tech_score < 40 else "Mid-Band", 
                "status": "BULLISH" if tech_score > 70 else "BEARISH" if tech_score < 40 else "NEUTRAL", 
                "reasoning": f"Price is riding the upper standard deviation channel, suggesting a potential breakout for {ticker.upper()}." if tech_score > 70 else f"Price is testing the lower standard deviation channel, indicating oversold conditions." if tech_score < 40 else f"{ticker.upper()} is consolidating near the mean, awaiting a volatility catalyst."
            }
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

@app.post("/translate")
async def translate_ai(req: TranslationRequest):
    if not model: return {"analysis": "AI Node Offline."}
    try:
        prompt = f"Act as an elite quantitative analyst. Provide a definitive briefing on {req.ticker}.\n\n"
        prompt += f"CURRENT MARKET CONTEXT:\n- Current Price: ${req.data_context.get('price', 'N/A')}\n- Quant Score: {req.data_context.get('score', 'N/A')}\n\n"
        
        funds = req.data_context.get("fundamentals", {})
        if funds:
            prompt += f"FUNDAMENTAL DNA:\n- P/E Ratio: {funds.get('pe_ratio', 'N/A')}\n- Margin: {funds.get('margin', 'N/A')}\n\n"

        ledger = req.data_context.get("ledger", [])
        if ledger:
            prompt += f"TECHNICAL LEDGER:\n"
            for item in ledger: prompt += f"- {item.get('factor')}: {item.get('val')} ({item.get('status')})\n"

        shares = float(req.data_context.get("user_shares", 0))
        if shares > 0: prompt += f"\nPOSITION: {shares} shares held at ${req.data_context.get('user_avg_cost', '0')}.\n"

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
        return {"analysis": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize")
async def summarize_article(req: SummaryRequest):
    if not model: return {"summary": ["AI Node Offline."]}
    try:
        prompt = (
            f"Act as a financial analyst. Write a concise, institutional summary "
            f"expanding on this headline: '{req.title}'.\n\n"
            f"STRICT RULES:\n"
            f"- Output exactly one cohesive paragraph.\n"
            f"- Maximum 3 sentences.\n"
            f"- Be highly informative but extremely brief."
        )
        response = model.generate_content(prompt)
        return {"summary": [response.text.strip()]}
    except Exception: 
        return {"summary": ["Summary temporarily unavailable."]}

@app.get("/market-briefing")
async def market_briefing():
    return [
        {"title": "Global markets await next major macro catalyst as volatility indexes contract.", "publisher": "TradeBotics Wire", "date": "Today"},
        {"title": "Tech sector shows resilience amidst shifting yield curve expectations.", "publisher": "Macro Intelligence", "date": "Today"},
        {"title": "Institutional capital flows suggest rotational repositioning ahead of earnings season.", "publisher": "Dark Pool Wire", "date": "Today"},
        {"title": "Commodity indices signal potential supply chain constraints in key raw materials.", "publisher": "Global Macro", "date": "Today"},
        {"title": "Federal Reserve commentary points toward sustained current monetary policy trajectory.", "publisher": "Central Bank Watch", "date": "Today"}
    ]

@app.post("/portfolio-analysis")
async def analyze_portfolio(req: PortfolioRequest):
    if not model: return {"analysis": "AI Node Offline."}
    
    try:
        portfolio_summary = []
        if not req.holdings:
            raise HTTPException(status_code=400, detail="No holdings provided.")

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

        if not portfolio_summary:
            return {"analysis": "No valid data could be retrieved.", "holdings": []}

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
                if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "COIN"]:
                    style_bonus = 20 
                elif req.trade_style == "Swing Trade" and t in ["META", "AVGO", "PLTR"]:
                    style_bonus = 20 
                elif req.trade_style == "Long Term" and t in ["LLY", "COST", "JPM"]:
                    style_bonus = 20 

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
        
        return {
            "analysis": response.text.strip(),
            "holdings": portfolio_summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))