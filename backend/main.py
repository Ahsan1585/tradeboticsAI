from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai

load_dotenv()
gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_key) if gemini_key else None
finnhub_key = os.getenv("FINNHUB_API_KEY")

app = FastAPI(title="TradeBotics AI Terminal", version="16.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranslationRequest(BaseModel):
    ticker: str
    mode: str
    data_context: dict

class NewsRequest(BaseModel):
    title: str
    ticker: str
    content: str = ""

# --- 🛡️ DUAL MEMORY CACHE (15 MINUTES) ---
scanned_data_cache = {}
ai_translation_cache = {}
CACHE_LIFETIME_SECONDS = 900 

# --- 🧠 DETERMINISTIC REASONING ---
def get_detailed_reasoning(factor, status, ticker):
    reasoning = {
        "Market Anchor": {"Bullish": "50-day SMA is above 200-day (Golden Cross). The long-term trend is strong.", "Bearish": "Price is below the Death Cross (50/200 SMA). The structural trend is weak."},
        "Momentum": {"Oversold": f"RSI is below 40. {ticker} is statistically exhausted. High chance of a bounce.", "Neutral": "Momentum is in the 'Safe Zone'. The trend is stable.", "Overbought": "RSI exceeds 70. Momentum is peaking; high risk of a price drop."},
        "Capital Flow": {"Accumulation": "OBV is rising. Professional investors are buying the stock.", "Distribution": "OBV is declining. Large investors are selling on rallies."},
        "Trend Velocity": {"Bullish": "MACD Histogram is expanding. Price acceleration is increasing.", "Bearish": "Negative MACD divergence. Price speed is slowing down."},
        "Volatility Range": {"Value Zone": f"Testing Lower Bollinger Band. Historically, {ticker} is 'cheap' here.", "Normal": "Price is within standard daily limits.", "Overextended": "Price is piercing the Upper Bollinger Band."}
    }
    return reasoning.get(factor, {}).get(status, "Analyzing market data...")

def extract_news(ticker=None):
    if not finnhub_key: return []
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start_date}&to={end_date}&token={finnhub_key}" if ticker else f"https://finnhub.io/api/v1/news?category=general&token={finnhub_key}"
    try:
        res = requests.get(url, timeout=5).json()[:4]
        return [{"title": n.get("headline", "Market Update"), "publisher": n.get("source", "Wire"), "link": n.get("url", "#"), "content": n.get("summary", "")} for n in res if n.get("headline")]
    except: return []

# --- 🕰️ FULL YEAR AI CONFIDENCE BACKTEST ---
def run_confidence_check(ticker, df):
    signals = []
    if len(df) < 70: return {"win_rate": "N/A", "avg_gain": "N/A", "total_signals": 0}
    for i in range(50, len(df)-20):
        window = df.iloc[i]
        if window.get('RSI_14', 50) < 55 and window['Close'] > window.get('SMA_50', 0):
            future_price = df.iloc[i + 20]['Close']
            signals.append(((future_price - window['Close']) / window['Close']) * 100)
    if not signals: return {"win_rate": "N/A", "avg_gain": "N/A", "total_signals": 0}
    win_rate = (len([s for s in signals if s > 0]) / len(signals)) * 100
    avg_gain = sum(signals) / len(signals)
    prefix = "+" if avg_gain > 0 else ""
    return {"win_rate": f"{round(win_rate, 0)}%", "avg_gain": f"{prefix}{round(avg_gain, 1)}%", "total_signals": len(signals)}

# --- 🤖 PHASE 2: ON-DEMAND AI ENDPOINTS (TOKEN SPEND) ---
@app.post("/translate")
def translate_to_retail(req: TranslationRequest):
    if not client: return {"analysis": "AI Engine Offline."}
    
    cache_key = f"{req.ticker}_{req.mode}"
    current_time = time.time()
    if cache_key in ai_translation_cache:
        cached_item = ai_translation_cache[cache_key]
        if current_time - cached_item['timestamp'] < CACHE_LIFETIME_SECONDS:
            return {"analysis": cached_item['text']}

    ctx = req.data_context
    
    prompts = {
        "sentiment": f"Analyze the following news headlines for {req.ticker}: {ctx.get('news_titles')}. Declare emotion as 'FEAR-DRIVEN' or 'GREED-DRIVEN'. Provide 2 bullet points and a 1-sentence strategic takeaway. Use 2026 context.",
        "strike_zone": f"Technical entry check for {req.ticker}. Price: ${ctx.get('price')}, RSI: {ctx.get('rsi')}. Calculate a specific entry price for a good deal.",
        "verdict": f"""Provide a definitive AI Verdict for {req.ticker}. 
        Live Price: ${ctx.get('price')}. Quant Score: {ctx.get('score')}/200. Stance: {ctx.get('stance')}. 
        P/E Ratio: {ctx.get('fundamentals', {}).get('pe_ratio', 'N/A')}. 
        Support Level: ${ctx.get('stop_loss', 'N/A')}. Target: ${ctx.get('trailing_target', 'N/A')}.
        News: {ctx.get('news_titles')}.

        VERDICT LOGIC:
        - Score > 130 AND Stance 'BUY' -> Output '**AI VERDICT: GREEN LIGHT**'.
        - Score > 130 AND Stance 'HOLD' -> Output '**AI VERDICT: YELLOW LIGHT**'.
        - Stance 'REDUCE' or 'TRIM' -> Output '**AI VERDICT: RED LIGHT**'.

        CONTENT RULES:
        1. Start with the Verdict.
        2. If YELLOW, describe as 'Elite Asset, Awaiting Tactical Entry'.
        3. MANDATORY FOR YELLOW: Define a specific 'GREEN ENTRY TARGET' price (cross-reference the Support Level or suggest a 5% dip from current price) that would transition this ticker to a GREEN LIGHT.
        4. Citations: Use a 2026 headline or the P/E ratio for the 'Hard Data Reason'. No 2024 data."""
    }
    
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompts.get(req.mode, "Analyze stock."))
        ai_text = res.text.strip()
        ai_translation_cache[cache_key] = {'timestamp': current_time, 'text': ai_text}
        return {"analysis": ai_text}
    except: return {"analysis": "AI synchronization error."}

@app.post("/summarize")
def summarize_article(req: NewsRequest):
    if not client: return {"summary": ["Offline."]}
    try:
        res = client.models.generate_content(model='gemini-2.5-flash', contents=f"Analyze this news for {req.ticker}. Headline: '{req.title}'. Write 2 simple paragraphs.")
        return {"summary": [p.strip() for p in res.text.strip().split('\n') if p.strip()]}
    except: return {"summary": ["Error creating AI summary."]}

@app.get("/market-briefing")
def get_briefing(): return extract_news()

# --- 🔬 PHASE 1: DETERMINISTIC MASTER ENGINE (0 TOKENS) ---
@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    ticker = ticker.upper()
    current_time = time.time()
    
    if ticker in scanned_data_cache:
        cached_item = scanned_data_cache[ticker]
        if current_time - cached_item['timestamp'] < CACHE_LIFETIME_SECONDS:
            return cached_item['data']

    try:
        stock = yf.Ticker(ticker); info = stock.info; df = stock.history(period="1y")
        if df.empty or len(df) < 100: raise HTTPException(status_code=404, detail="Data Gap.")

        df.ta.rsi(append=True); df.ta.sma(length=50, append=True); df.ta.sma(length=200, append=True)
        df.ta.obv(append=True); df.ta.macd(append=True); df.ta.bbands(length=20, append=True)
        df = df.dropna(); latest = df.iloc[-1]; prev_5 = df.iloc[-5]
        
        tech_score = 0; ledger = []
        ma = "Bullish" if latest.get('SMA_50', 0) > latest.get('SMA_200', 0) else "Bearish"
        tech_score += 20 if ma == "Bullish" else 0
        ledger.append({"factor": "Market Anchor", "status": ma, "val": "50/200 Cross", "reasoning": get_detailed_reasoning("Market Anchor", ma, ticker)})

        rsi_v = latest.get('RSI_14', 50)
        rsi_s = "Oversold" if rsi_v < 40 else "Neutral" if rsi_v <= 70 else "Overbought"
        tech_score += 20 if rsi_s == "Oversold" else 10 if rsi_s == "Neutral" else 0
        ledger.append({"factor": "Momentum", "status": rsi_s, "val": f"{round(rsi_v,1)} RSI", "reasoning": get_detailed_reasoning("Momentum", rsi_s, ticker)})

        cf = "Accumulation" if latest.get('OBV', 0) > prev_5.get('OBV', 0) else "Distribution"
        tech_score += 20 if cf == "Accumulation" else 0
        ledger.append({"factor": "Capital Flow", "status": cf, "val": "OBV Trend", "reasoning": get_detailed_reasoning("Capital Flow", cf, ticker)})

        macd_line = latest.filter(like='MACD_').iloc[0] if not latest.filter(like='MACD_').empty else 0
        macd_sig = latest.filter(like='MACDs_').iloc[0] if not latest.filter(like='MACDs_').empty else 0
        tv = "Bullish" if macd_line > macd_sig else "Bearish"
        tech_score += 20 if tv == "Bullish" else 0
        ledger.append({"factor": "Trend Velocity", "status": tv, "val": "MACD Cross", "reasoning": get_detailed_reasoning("Trend Velocity", tv, ticker)})

        bbl = latest.filter(like='BBL_').iloc[0] if not latest.filter(like='BBL_').empty else 0
        bbu = latest.filter(like='BBU_').iloc[0] if not latest.filter(like='BBU_').empty else float('inf')
        vr = "Value Zone" if latest['Close'] <= bbl else "Overextended" if latest['Close'] >= bbu else "Normal"
        tech_score += 20 if vr == "Value Zone" else 10 if vr == "Normal" else 0
        ledger.append({"factor": "Volatility Range", "status": vr, "val": "Bollinger Bands", "reasoning": get_detailed_reasoning("Volatility Range", vr, ticker)})

        fund_score = 0
        pe = info.get('trailingPE') or info.get('forwardPE') or 0; dte = info.get('debtToEquity', 100) or 100
        margin = info.get('profitMargins', 0) or 0; fcf = info.get('freeCashflow', 0) or 0
        sent = info.get('recommendationKey', 'none')

        fund_score += 20 if 0 < pe < 25 else 10 if pe > 0 else 0
        fund_score += 20 if dte < 100 else 10 if dte < 200 else 0
        fund_score += 20 if margin > 0.10 else 10 if margin > 0 else 0
        fund_score += 20 if fcf > 0 else 0
        fund_score += 20 if sent in ['buy', 'strong_buy'] else 10 if sent == 'hold' else 0

        total_score = tech_score + fund_score

        holding_status = "HOLD"; exit_guidance = "Trend is intact."
        if rsi_v > 75: 
            holding_status = "TRIM PROFITS"; exit_guidance = "Overextended momentum."
        elif latest['Close'] < latest.get('SMA_50', 0):
            holding_status = "REDUCE POSITION"; exit_guidance = "Below 50-day support."

        # THE FIX: Restoring the Volume Calculations
        current_vol = info.get('volume', 0)
        avg_vol = info.get('averageVolume', 1)
        vol_surge = round((current_vol / avg_vol) * 100, 1) if avg_vol else 0

        final_result = {
            "symbol": ticker.upper(), "company_name": info.get('longName', ticker.upper()),
            "price": round(latest['Close'], 2), "volume": f"{current_vol:,}", "vol_surge": f"{vol_surge}%",
            "score": total_score, "tech_score": tech_score, "fund_score": fund_score,
            "confluence": "Institutional Buy 💎" if total_score >= 160 else "Strong Entry 🟢" if total_score >= 130 else "Neutral 🟡",
            "fundamentals": {"pe_ratio": round(pe, 2) if pe else "N/A", "debt_equity": f"{round(dte, 1)}%", "margin": f"{round(margin * 100, 1)}%", "sentiment": sent.upper().replace("_", " "), "cash_flow": "Positive ✅" if fcf > 0 else "Negative ⚠️"},
            "holding_analysis": {"status": holding_status, "guidance": exit_guidance, "stop_loss": round(min(latest.get('SMA_50', latest['Close']), latest['Close']) * 0.95, 2), "trailing_target": round(latest['Close'] * 1.1, 2)},
            "ledger": ledger, "confidence_proof": run_confidence_check(ticker, df),
            "ai_tactical": "Awaiting manual override. Click 'Execute AI Analysis Verdict' for neural synthesis.", "news": extract_news(ticker.upper())
        }
        scanned_data_cache[ticker] = {'timestamp': current_time, 'data': final_result}
        return final_result
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))