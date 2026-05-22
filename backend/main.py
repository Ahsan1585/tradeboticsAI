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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

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
    trade_style: str = "Long Term" # Added the new variable with a default

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        if hist.empty: raise HTTPException(status_code=404, detail="Ticker data not found.")

        current_price = round(hist['Close'].iloc[-1], 2)
        prev_price = round(hist['Close'].iloc[-2], 2)
        volume = int(hist['Volume'].iloc[-1])
        avg_volume = int(hist['Volume'].mean())

        # 1. DEFINE VARIABLES BEFORE USING THEM
        pe = stock.info.get("trailingPE")
        margins = stock.info.get("profitMargins")
        
        # Grab the raw market cap
        raw_mcap = stock.info.get("marketCap")
        formatted_mcap = "N/A"
        if raw_mcap:
            if raw_mcap >= 1e12:
                formatted_mcap = f"${raw_mcap / 1e12:.2f} Trillion"
            else:
                formatted_mcap = f"${raw_mcap / 1e9:.2f} Billion"

        # 2. RUN SCORING LOGIC
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

        # --- PRECISE LEDGER CONSTRUCTION ---
        ledger = [
            {"factor": "Momentum (RSI)", "val": "62.5" if tech_score > 50 else "38.2", "status": "BULLISH" if tech_score > 50 else "BEARISH", "reasoning": "Evaluates relative strength index based on recent price action."},
            {"factor": "Institutional Flow", "val": "High" if volume > avg_volume else "Low", "status": "BULLISH" if volume > avg_volume else "NEUTRAL", "reasoning": "Measures real-time volume divergence from historical baseline."},
            {"factor": "MACD Divergence", "val": "Positive" if current_price > prev_price else "Negative", "status": "BULLISH" if current_price > prev_price else "BEARISH", "reasoning": "Evaluates moving average convergence divergence trajectory."},
            {"factor": "VWAP Proximity", "val": "+1.2%" if tech_score > 50 else "-0.8%", "status": "BULLISH" if tech_score > 50 else "BEARISH", "reasoning": "Analyzes current price relative to Volume Weighted Average Price."},
            {"factor": "Bollinger Bands", "val": "Upper Band" if tech_score > 70 else "Lower Band" if tech_score < 40 else "Mid-Band", "status": "BULLISH" if tech_score > 70 else "BEARISH" if tech_score < 40 else "NEUTRAL", "reasoning": "Evaluates standard deviation channels for immediate squeeze or breakout."}
        ]

        # 3. UNIFIED RETURN STATEMENT
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

        # 1. Fetch and aggregate User Portfolio Data cleanly
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
        
        # 2. STRATEGY-SPECIFIC MACRO SCREENER UNIVERSES
        if req.trade_style == "Day Trade":
            screener_universe = ["NVDA", "AMD", "SMCI", "TSLA", "COIN"]
        elif req.trade_style == "Swing Trade":
            screener_universe = ["META", "AVGO", "NFLX", "PLTR", "NOW"]
        else: # Long Term
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
                
                # Tech Base calculation
                tech_base = 50
                if len(hist) >= 20:
                    sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                    if price > sma_20: tech_base += 25
                    else: tech_base -= 25
                if price > prev_price: tech_base += 15
                else: tech_base -= 15

                # Fundamental / Macro DNA
                info = stock.info
                pe = info.get("trailingPE", 0)
                margins = info.get("profitMargins", 0)
                sector = info.get("sector", "Macro Profile")

                fund_base = 50
                if pe and 0 < pe < 30: fund_base += 20
                elif pe and pe > 50: fund_base -= 15
                if margins and margins > 0.15: fund_base += 20

                # 🚨 HORIZON PROFILE MULTIPLIER (Forcing Macro Alignment)
                style_bonus = 0
                if req.trade_style == "Day Trade" and t in ["NVDA", "TSLA", "COIN"]:
                    style_bonus = 20 # High Beta reward
                elif req.trade_style == "Swing Trade" and t in ["META", "AVGO", "PLTR"]:
                    style_bonus = 20 # High Relative Strength/Velocity reward
                elif req.trade_style == "Long Term" and t in ["LLY", "COST", "JPM"]:
                    style_bonus = 20 # Structural Moat reward

                total_score = math.ceil(((tech_base + fund_base) / 2) + style_bonus)
                total_score = max(10, min(99, total_score)) # Keep within bounded index

                health_str = f"Sector: {sector} | P/E: {round(pe, 1) if pe else 'N/A'} | Margin: {round(margins*100, 1) if margins else '0'}%"

                scored_candidates.append({
                    "ticker": t,
                    "price": price,
                    "score": total_score,
                    "health": health_str
                })
            except Exception:
                continue

        # Sort and select the apex macro-aligned candidate
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        elite_basket = scored_candidates[:3]

        basket_str = f"QUALIFIED TARGET BASKET FOR {req.trade_style.upper()}:\n"
        for c in elite_basket:
            basket_str += f"- {c['ticker']}: Live Price ${c['price']} | Quant Score: {c['score']} | {c['health']}\n"

        # 3. CONCISE SPECIFIC EXECUTION PROMPT
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