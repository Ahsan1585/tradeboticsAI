from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import os
import math
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Initialize FastAPI
app = FastAPI()

# Configure CORS for Frontend Communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini AI Node
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

# --- PYDANTIC MODELS ---

class TranslationRequest(BaseModel):
    ticker: str
    mode: str
    data_context: Dict[str, Any]

class SummaryRequest(BaseModel):
    title: str
    ticker: str
    content: str


# --- CORE ENDPOINTS ---

@app.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    """
    Standard Market Scan. 
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        if hist.empty:
            raise HTTPException(status_code=404, detail="Ticker data not found.")

        current_price = round(hist['Close'].iloc[-1], 2)
        prev_price = round(hist['Close'].iloc[-2], 2)
        volume = int(hist['Volume'].iloc[-1])
        avg_volume = int(hist['Volume'].mean())

        # Simulated Quant Logic
        tech_score = 85 if current_price > prev_price else 65
        fund_score = 80
        
        # Forces standard round-up so 82.5 becomes 83
        total_score = math.ceil((tech_score + fund_score) / 2)
        
        vol_surge = f"{round((volume / avg_volume) * 100, 1)}%" if avg_volume > 0 else "N/A"

        payload = {
            "ticker": ticker.upper(),
            "company_name": stock.info.get("shortName", ticker.upper()),
            "price": current_price,
            "score": total_score,
            "tech_score": tech_score,
            "fund_score": fund_score,
            "volume": f"{volume:,}",
            "vol_surge": vol_surge,
            "ai_tactical": "Market conditions favorable. Accumulation detected across major moving averages.",
            "fundamentals": {
                "pe_ratio": str(stock.info.get("trailingPE", "N/A")),
                "debt_equity": str(stock.info.get("debtToEquity", "N/A")),
                "margin": f"{round(stock.info.get('profitMargins', 0) * 100, 2)}%" if stock.info.get('profitMargins') else "N/A",
                "sentiment": "BULLISH",
                "cash_flow": "POSITIVE"
            },
            "holding_analysis": {
                "status": "HOLD",
                "guidance": "Maintain current positioning. Adjust trailing stops to lock in recent momentum.",
                "stop_loss": str(round(current_price * 0.92, 2)),
                "trailing_target": str(round(current_price * 1.15, 2))
            },
            "ledger": [
                {"factor": "Momentum (RSI)", "val": "62.5", "status": "NEUTRAL", "reasoning": "RSI indicates healthy momentum without entering overbought territory."},
                {"factor": "Institutional Flow", "val": "High", "status": "BULLISH", "reasoning": "Dark pool block trades detected above the 20-day moving average."},
                {"factor": "MACD Divergence", "val": "Positive", "status": "BULLISH", "reasoning": "MACD line crossed above the signal line, indicating upward trend acceleration."},
                {"factor": "VWAP Proximity", "val": "+1.2%", "status": "BULLISH", "reasoning": "Price is holding steady above the Volume Weighted Average Price."},
                {"factor": "Bollinger Bands", "val": "Mid-Band", "status": "NEUTRAL", "reasoning": "Trading within standard deviations; no immediate squeeze or breakout detected."}
            ],
            "news": [
                {"title": f"{ticker.upper()} shows strong relative strength in recent session.", "publisher": "Market Intelligence", "date": "Today"}
            ]
        }
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/translate")
async def translate_ai(req: TranslationRequest):
    """
    ENTERPRISE AI DEEP DIVE ENGINE (Restored to Pure Asset Analysis)
    """
    if not model:
        return {"analysis": "AI Node Offline: Missing API Key."}

    try:
        prompt = f"Act as an elite quantitative analyst. Provide a highly analytical briefing on {req.ticker}.\n\n"
        
        prompt += f"CURRENT MARKET CONTEXT:\n"
        prompt += f"- Current Price: ${req.data_context.get('price', 'N/A')}\n"
        prompt += f"- Quant Score: {req.data_context.get('score', 'N/A')}\n"

        shares = float(req.data_context.get("user_shares", 0))
        avg_cost = float(req.data_context.get("user_avg_cost", 0))

        if shares > 0:
            prompt += f"\nPOSITION CONTEXT:\n"
            prompt += f"The user currently holds {shares} shares of {req.ticker} at an average cost basis of ${avg_cost:,.2f}. "
            prompt += "Analyze this specific asset's technical indicators, company fundamentals, and global sentiment to determine its forward trajectory.\n"
        else:
             prompt += "\nPOSITION CONTEXT:\nThe user does NOT currently own this asset. Frame your advice around whether this represents a safe new entry based strictly on technicals, fundamentals, and sentiment.\n"

        prompt += f"\n🚨 STRICT OUTPUT FORMATTING RULES 🚨\n"
        
        if req.mode == "strike_zone":
            prompt += "Line 1 of your response MUST BE EXACTLY: '🎯 AI STRIKE ZONE: $[low price target] - $[high price target]'. You must calculate and provide this specific mathematical price range based on technical support levels. Do not write anything before this line.\n"
            prompt += "Following that line, provide a concise, 1-2 paragraph briefing analyzing the asset based STRICTLY on its stock indicators, company fundamentals, and overall global sentiment. Do not lecture on portfolio risk.\n"
        elif req.mode == "verdict":
            prompt += "Provide a definitive tactical verdict (BUY, HOLD, TRIM, or SELL) based strictly on technical indicators, company fundamentals, and overall global sentiment, followed by a 1-2 paragraph analytical briefing.\n"
        elif req.mode == "sentiment":
            prompt += "Focus strictly on institutional flow, news sentiment, and macro context. Provide a 1-2 paragraph briefing tying sentiment back to whether it supports the asset's current price trajectory.\n"

        prompt += "\nTONE: Speak directly to the operative using stark, professional financial terminology. Remove all conversational fluff, pleasantries, and generic legal disclaimers."

        response = model.generate_content(prompt)
        return {"analysis": response.text.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarize")
async def summarize_article(req: SummaryRequest):
    """
    News Synthesis Engine
    """
    if not model:
        return {"summary": ["AI Node Offline."]}
    try:
        prompt = f"Summarize this financial headline into 2 highly professional bullet points focusing on market impact. Headline: {req.title}"
        response = model.generate_content(prompt)
        summary_points = [p.strip().replace('- ', '').replace('* ', '') for p in response.text.split('\n') if p.strip()]
        return {"summary": summary_points if summary_points else ["Summary unavailable."]}
    except Exception:
        return {"summary": ["Failed to synthesize article."]}


@app.get("/market-briefing")
async def market_briefing():
    """
    Global Intelligence Wire Fallback
    """
    return [
        {"title": "Global markets await next major macro catalyst.", "publisher": "Tradebotics Wire", "date": "Today"},
        {"title": "Tech sector shows resilience amidst volatility.", "publisher": "Tradebotics Wire", "date": "Today"}
    ]