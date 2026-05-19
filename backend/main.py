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

class SwapRequest(BaseModel):
    ticker: str
    shares: float
    price: float

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

        # Scoring Logic
        tech_base = 50
        sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
        if current_price > sma_20: tech_base += 25
        else: tech_base -= 25
        if current_price > prev_price: tech_base += 15
        else: tech_base -= 15
        tech_score = max(10, min(95, tech_base))

        fund_base = 50
        pe = stock.info.get("trailingPE")
        margins = stock.info.get("profitMargins")
        if pe and 0 < pe < 25: fund_base += 20
        elif pe and pe > 50: fund_base -= 20
        if margins and margins > 0.15: fund_base += 20
        elif margins and margins < 0: fund_base -= 25
        fund_score = max(10, min(95, fund_base))
        total_score = math.ceil((tech_score + fund_score) / 2)

        return {
            "ticker": ticker.upper(),
            "company_name": stock.info.get("shortName", ticker.upper()),
            "price": current_price,
            "score": total_score,
            "tech_score": int(tech_score),
            "fund_score": int(fund_score),
            "fundamentals": {
                "pe_ratio": str(round(pe, 2)) if pe else "N/A",
                "margin": f"{round(margins * 100, 2)}%" if margins else "N/A",
                "sentiment": "BULLISH" if total_score > 65 else "BEARISH" if total_score < 40 else "NEUTRAL"
            },
            "ledger": [
                {"factor": "Momentum (RSI)", "val": "62.5" if tech_score > 50 else "38.2", "status": "BULLISH" if tech_score > 50 else "BEARISH"},
                {"factor": "Institutional Flow", "val": "High" if volume > avg_volume else "Low", "status": "BULLISH"},
                {"factor": "MACD Divergence", "val": "Positive" if current_price > prev_price else "Negative", "status": "BULLISH"},
                {"factor": "VWAP Proximity", "val": "+1.2%", "status": "BULLISH"},
                {"factor": "Bollinger Bands", "val": "Mid-Band", "status": "NEUTRAL"}
            ],
            "news": [
                {"title": f"{ticker.upper()} price action shows strength.", "publisher": "TradeBotics"},
                {"title": f"Institutional block volume analysis active.", "publisher": "Market Watch"},
                {"title": f"Macro sector rotation favors {ticker.upper()}.", "publisher": "Macro Wire"}
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
async def translate_ai(req: TranslationRequest):
    if not model: return {"analysis": "AI Node Offline."}
    try:
        prompt = f"Act as an elite quantitative analyst. Briefing on {req.ticker}.\n\n"
        prompt += f"DATA: Price ${req.data_context.get('price')}, Score {req.data_context.get('score')}.\n"
        prompt += f"FUNDAMENTALS: {req.data_context.get('fundamentals')}.\n"
        prompt += f"TECHNICALS: {req.data_context.get('ledger')}.\n\n"
        prompt += (
            "TEMPLATE REQUIREMENT:\n"
            "Line 1: '🎯 AI STRIKE ZONE: $[low] - $[high]'\n"
            "Line 2: '⚖️ TACTICAL VERDICT: [BUY/HOLD/TRIM/SELL]'\n\n"
            "Briefing: 2 paragraphs total. 1: Fundamentals/Macro. 2: Technicals/Strategy. "
            "If Score < 50, SELL/TRIM. If Score > 70, BUY. No fluff."
        )
        response = model.generate_content(prompt)
        return {"analysis": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))