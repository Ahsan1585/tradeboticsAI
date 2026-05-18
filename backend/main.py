from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import os
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
    (Left completely intact per your instructions)
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
        total_score = round((tech_score + fund_score) / 2)
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
                {"factor": "Institutional Flow", "val": "High", "status": "BULLISH", "reasoning": "Dark pool block trades detected above the 20-day moving average."}
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
    🚨 ENTERPRISE AI DEEP DIVE ENGINE 🚨
    Now aggregates massive portfolio JSONs into a token-efficient Python string.
    """
    if not model:
        return {"analysis": "AI Node Offline: Missing API Key."}

    try:
        # Build the Base Context
        prompt = f"Act as an elite quantitative institutional risk manager. Provide a highly analytical briefing on {req.ticker} focusing on '{req.mode}'.\n\n"
        
        prompt += f"CURRENT MARKET CONTEXT:\n"
        prompt += f"- Current Price: ${req.data_context.get('price', 'N/A')}\n"
        prompt += f"- Quant Score: {req.data_context.get('score', 'N/A')}\n"

        # 🚨 THE NEW PYTHON AGGREGATOR (Saves thousands of API tokens)
        full_portfolio = req.data_context.get("full_portfolio", [])
        
        if full_portfolio:
            # 1. Calculate the user's Total Invested Capital mathematically
            total_invested = sum(float(pos.get("shares", 0)) * float(pos.get("avg_cost", 0)) for pos in full_portfolio)
            num_positions = len(full_portfolio)
            
            # 2. Check if they own the specific stock they are analyzing
            target_pos = next((pos for pos in full_portfolio if pos.get("ticker") == req.ticker), None)
            
            prompt += f"\n🚨 FIDUCIARY PORTFOLIO CONTEXT 🚨\n"
            prompt += f"The user's total invested capital across {num_positions} tracked assets is roughly ${total_invested:,.2f}.\n"
            
            if target_pos:
                shares = float(target_pos.get("shares", 0))
                avg_cost = float(target_pos.get("avg_cost", 0))
                pos_value = shares * avg_cost
                weight = (pos_value / total_invested * 100) if total_invested > 0 else 0
                
                # Compress the massive JSON into a single concise sentence for Gemini
                prompt += f"They currently hold {shares} shares of {req.ticker} at an average cost basis of ${avg_cost:,.2f}. "
                prompt += f"This specific asset represents {weight:.1f}% of their total portfolio exposure.\n"
                prompt += "You MUST mathematically incorporate their specific cost basis and portfolio weighting into your advice. If they are over-exposed, suggest risk management. Give precise tactical advice on whether to hold, trim, add, or exit.\n"
            else:
                prompt += f"The user does NOT currently own {req.ticker} in their Vault. Frame your advice around whether this represents a safe new entry given their existing market exposure.\n"
        else:
             prompt += "\nPORTFOLIO CONTEXT:\nThe user's Vault is currently empty. Frame your advice around whether this asset represents a safe new entry point based on risk/reward.\n"

        prompt += "\nOUTPUT FORMAT: Provide a concise, highly analytical, 2-paragraph briefing. Speak directly to the operative using stark, professional financial terminology. Remove all standard AI fluff and generic legal disclaimers."

        # Execute AI Call
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