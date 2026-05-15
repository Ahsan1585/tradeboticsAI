"use client";
import React, { useState, useEffect, useRef } from "react";
import { supabase } from "./lib/supabase";
import Link from "next/link";

// 🚨 HARDWIRED PRODUCTION URL (Eliminates Browser Security Pop-up)
const BACKEND_URL = "https://tradebotics-api.onrender.com";

// --- UI COMPONENTS (Defined outside Home for stability) ---

function TickerTape() {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (container.current && container.current.children.length === 0) {
      const script = document.createElement("script");
      script.src = "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
      script.async = true;
      script.innerHTML = JSON.stringify({
        "symbols": [
          { "proName": "FOREXCOM:SPX500", "title": "S&P 500" },
          { "proName": "NASDAQ:NVDA", "title": "Nvidia" },
          { "proName": "NASDAQ:AAPL", "title": "Apple" },
          { "proName": "NASDAQ:TSLA", "title": "Tesla" },
          { "proName": "NYSE:F", "title": "Ford" }
        ],
        "colorTheme": "dark",
        "isTransparent": true,
        "displayMode": "adaptive",
        "locale": "en"
      });
      container.current.appendChild(script);
    }
  }, []);
  return <div ref={container} className="w-full mb-8 opacity-60" />;
}

function MarketScreener() {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (container.current && container.current.children.length === 0) {
      const script = document.createElement("script");
      script.src = "https://s3.tradingview.com/external-embedding/embed-widget-screener.js";
      script.async = true;
      script.innerHTML = JSON.stringify({ "width": "100%", "height": "800", "defaultColumn": "overview", "defaultScreen": "most_active", "market": "america", "showToolbar": true, "colorTheme": "dark", "locale": "en", "isTransparent": true });
      container.current.appendChild(script);
    }
  }, []);
  return <div className="w-full bg-slate-900/10 rounded-[32px] border border-slate-800 min-h-[800px] overflow-hidden" ref={container} />;
}

function TradingViewWidget({ symbol }: { symbol: string }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (container.current && symbol) {
      container.current.innerHTML = "";
      const script = document.createElement("script");
      script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
      script.async = true;
      script.innerHTML = JSON.stringify({ "autosize": true, "symbol": `NASDAQ:${symbol}`, "interval": "D", "theme": "dark", "style": "1", "locale": "en", "container_id": "tv_chart" });
      container.current.appendChild(script);
    }
  }, [symbol]);
  return <div className="w-full h-[450px] bg-slate-950 rounded-[32px] overflow-hidden border border-slate-800 shadow-2xl" ref={container}><div id="tv_chart" className="w-full h-full" /></div>;
}

function Stat({ label, val, color = "text-white" }: { label: string, val: string, color?: string }) {
  return (<div className="flex justify-between items-center"><p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{label}</p><p className={`${color} font-black text-sm`}>{val}</p></div>);
}

// --- MAIN TERMINAL APPLICATION ---

export default function Home() {
  const [user, setUser] = useState<any>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false); 
  const [data, setData] = useState<any>(null);
  const [globalNews, setGlobalNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [ticker, setTicker] = useState("");
  const [confirmedTicker, setConfirmedTicker] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [deepDiveResult, setDeepDiveResult] = useState<string | null>(null);

  // 1. INITIAL LOAD: Check Auth and Local T&C Memory
  useEffect(() => {
    const checkUser = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
      if (localStorage.getItem('termsAccepted') === 'true') {
        setHasAcceptedTerms(true);
      }
    };
    checkUser();
  }, []);

  // 2. LIFECYCLE FIX: Auto-fetch data immediately upon authorized access
  useEffect(() => {
    if (user && hasAcceptedTerms) {
      fetchWatchlist(user.id);
      fetchGlobalNews();
    }
  }, [user, hasAcceptedTerms]);

  // --- CORE FUNCTIONS ---

  const handleAcceptTerms = async () => {
    if (!user) return;
    const { error } = await supabase.from('disclaimer_logs').insert([{ user_id: user.id, email: user.email, accepted_at: new Date().toISOString() }]);
    if (!error) {
      setHasAcceptedTerms(true);
      localStorage.setItem('termsAccepted', 'true');
    }
  };

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) alert(error.message); else alert("Check email for link.");
    } else {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) alert(error.message); else setUser(data.user);
    }
    setAuthLoading(false);
  };

  const handleSignOut = async () => { 
    await supabase.auth.signOut(); 
    setUser(null); 
    setHasAcceptedTerms(false); 
    setData(null); 
    localStorage.removeItem('termsAccepted');
  };

  const runAnalysis = async (t?: string) => {
    const target = t || ticker;
    if (!target) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/analyze/${target}`);
      const result = await res.json();
      if (res.ok) { setData(result); setConfirmedTicker(target); }
      else { alert(`Terminal: ${result.detail || "Error."}`); }
    } catch { alert("Backend Offline. Check Production URL configuration."); }
    setLoading(false);
  };

  const runDeepDive = async (mode: string) => {
    if (!data) return;
    setDeepDiveResult(null);
    try {
        const res = await fetch(`${BACKEND_URL}/translate`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                ticker: confirmedTicker, mode, 
                data_context: { 
                    score: data.score, price: data.price, 
                    stance: data.holding_analysis?.status,
                    fundamentals: data.fundamentals, 
                    rsi: data.ledger?.find((l:any)=>l.factor==="Momentum")?.val, 
                    news_titles: data.news?.map((n:any)=>n.title).join(" | ") 
                } 
            })
        });
        const result = await res.json();
        setDeepDiveResult(result.analysis);
    } catch { alert("AI node error."); }
  };

  const handleArticleClick = async (item: any) => {
    setSelectedArticle({ ...item, summary: null });
    setIsSummarizing(true);
    try {
        const res = await fetch(`${BACKEND_URL}/summarize`, { 
          method: "POST", headers: { "Content-Type": "application/json" }, 
          body: JSON.stringify({ title: item.title, ticker: confirmedTicker || "Macro", content: item.content || "" }) 
        });
        const result = await res.json();
        setSelectedArticle({ ...item, summary: result.summary });
    } catch {
        setSelectedArticle({ ...item, summary: ["Failed to retrieve summary from backend."] });
    }
    setIsSummarizing(false);
  };

  const fetchGlobalNews = async () => { 
    try { 
      const res = await fetch(`${BACKEND_URL}/market-briefing`); 
      if (res.ok) setGlobalNews(await res.json()); 
    } catch { console.warn("UAT Note: Global news briefing unavailable."); } 
  };

  const fetchWatchlist = async (userId: string) => { 
    const { data } = await supabase.from('watchlist').select('*').eq('user_id', userId).order('created_at', { ascending: false }); 
    if (data) setWatchlist(data); 
  };
  
  const newsToDisplay = data?.news?.length > 0 ? data.news : globalNews;

  // --- RENDERING LOGIC ---

  if (!user) return (
    <main className="min-h-screen bg-[#020617] flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-slate-900/40 border border-slate-800 p-10 rounded-[48px] shadow-2xl">
        <h1 className="text-4xl font-black text-white text-center mb-8 tracking-tighter">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
        <form onSubmit={handleAuth} className="space-y-6">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-5 text-white outline-none" placeholder="Personnel ID" required />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-5 text-white outline-none" placeholder="Access Key" required />
          <button type="submit" disabled={authLoading} className="w-full bg-blue-600 text-white font-black py-5 rounded-2xl uppercase tracking-widest text-xs">Access Terminal</button>
        </form>
        <button onClick={() => setIsSignUp(!isSignUp)} className="w-full mt-6 text-[10px] text-slate-400 uppercase font-bold">{isSignUp ? "Sign In" : "Request Access"}</button>
      </div>
    </main>
  );

  if (!hasAcceptedTerms) return (
    <main className="min-h-screen bg-[#020617] flex items-center justify-center p-6">
      <div className="w-full max-w-lg bg-[#0f172a] border border-slate-800 rounded-[32px] p-10 shadow-2xl relative">
        <div className="flex justify-between items-center mb-8">
            <h2 className="text-xl font-bold text-white flex items-center gap-3">⚖️ Terms of Service & Legal Disclaimer</h2>
            <button onClick={() => setUser(null)} className="text-slate-500 text-xl font-bold">×</button>
        </div>
        <div className="space-y-6 max-h-[60vh] overflow-y-auto pr-4 custom-scrollbar">
            <p className="text-sm font-bold text-white mb-6">Please read and accept the following terms before accessing the TradeBotics Terminal:</p>
            <div><p className="text-white font-black text-sm mb-2">1. No Financial Advice</p><p className="text-slate-400 text-[13px] leading-relaxed">TradeBotics AI is strictly an educational and analytical software tool.</p></div>
            <div><p className="text-white font-black text-sm mb-2">2. Assumption of Risk</p><p className="text-slate-400 text-[13px] leading-relaxed">Trading involves a high degree of risk. You may lose your initial investment.</p></div>
            <div><p className="text-white font-black text-sm mb-2">3. Limitation of Liability</p><p className="text-slate-400 text-[13px] leading-relaxed">TradeBotics AI bears no legal responsibility for any financial losses.</p></div>
            <div><p className="text-white font-black text-sm mb-2">4. Data Accuracy</p><p className="text-slate-400 text-[13px] leading-relaxed">Information reflects aggregated sources and may be delayed.</p></div>
        </div>
        <button onClick={handleAcceptTerms} className="w-full bg-red-600 hover:bg-red-500 text-white font-black py-4 mt-8 rounded-xl uppercase tracking-widest text-[11px]">I Agree & Accept Terms</button>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 p-6 flex flex-col font-sans relative">
      
      {/* MODALS: DEEP DIVE & NEWS */}
      {deepDiveResult && (
        <div className="fixed inset-0 z-[110] bg-black/95 backdrop-blur-xl flex items-center justify-center p-4">
            <div className="w-full max-w-2xl max-h-[90vh] bg-slate-900 border border-blue-500/30 p-10 rounded-[48px] shadow-2xl flex flex-col overflow-hidden">
              <div className="flex items-center gap-3 mb-8 shrink-0"><div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" /><p className="text-[10px] font-black uppercase tracking-[0.4em] text-blue-500">AI Deep Dive Analysis</p></div>
              <div className="overflow-y-auto custom-scrollbar flex-1 mb-10 pr-2">
                <p className="text-white text-lg font-medium leading-relaxed italic whitespace-pre-wrap">"{deepDiveResult}"</p>
              </div>
              <button onClick={() => setDeepDiveResult(null)} className="w-full bg-slate-800 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest hover:text-white transition-colors">Close Briefing</button>
            </div>
        </div>
      )}

      {selectedArticle && (
        <div className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center p-4">
            <div className="w-full max-w-3xl max-h-[85vh] bg-[#020617] border border-blue-500/30 rounded-[40px] overflow-hidden flex flex-col shadow-2xl">
              <div className="p-8 border-b border-slate-800 bg-slate-900/40 shrink-0 flex justify-between">
                <div><div className="flex items-center gap-3 mb-4"><div className={`w-2 h-2 ${isSummarizing ? 'bg-orange-500' : 'bg-blue-500'} rounded-full animate-pulse`} /><p className="text-[10px] font-black uppercase text-blue-500">AI Synthesis</p></div><h2 className="text-2xl font-bold text-white">{selectedArticle?.title}</h2></div>
                <button onClick={() => setSelectedArticle(null)} className="text-slate-400 font-black text-[10px] uppercase bg-slate-800 px-4 py-2 rounded-full h-fit">Close</button>
              </div>
              <div className="p-8 bg-slate-950 overflow-y-auto flex-1 custom-scrollbar">
                 {isSummarizing ? <div className="space-y-4 animate-pulse"><div className="h-4 bg-slate-800 rounded w-full"></div></div> : <div className="space-y-6">{selectedArticle?.summary?.map((p: string, i: number) => <p key={i} className="text-slate-300 leading-relaxed text-base">{p}</p>)}</div>}
              </div>
            </div>
        </div>
      )}

      <TickerTape />
      
      <div className="flex justify-between items-center mb-12">
        <div><h1 className="text-5xl font-black text-white tracking-tighter">TRADEBOTICS<span className="text-blue-500">AI</span></h1><p className="text-[9px] uppercase tracking-[0.5em] text-slate-400 italic">Operative // {user?.email?.split('@')[0]}</p></div>
        
        <Link href="/portfolio" className="hidden lg:flex items-center gap-3 px-6 py-3 bg-slate-900/50 border border-slate-800 rounded-full hover:border-blue-500/50 hover:bg-blue-900/10 transition-all group">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse group-hover:bg-blue-400" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">Portfolio Intelligence</span>
        </Link>

        <div className="flex gap-3 bg-slate-900/80 p-3 rounded-[24px] border border-slate-800 focus-within:border-blue-500/50">
          <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runAnalysis()} className="bg-transparent border-none text-white font-black w-48 px-4 outline-none text-lg" placeholder="TICKER..." />
          <button onClick={() => runAnalysis()} className="bg-blue-600 text-white px-10 py-4 rounded-xl font-black text-xs uppercase hover:bg-blue-500">{loading ? "..." : "SCAN"}</button>
          <button onClick={handleSignOut} className="text-[9px] border border-slate-800 px-5 rounded-full uppercase font-black text-slate-400 hover:bg-red-500/10 hover:border-red-500 hover:text-red-500 transition-all">Logout</button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-8 flex-1">
        
        {/* LEFT COLUMN: QUANT SCORE & WATCHLIST */}
        <div className="col-span-12 lg:col-span-3 space-y-8">
          {data && (
            <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 shadow-inner animate-in fade-in">
              <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Total Quant Score</p>
              <div className="text-[120px] font-black text-white leading-none tracking-tighter mb-4">{data?.score}</div>
              <div className="grid grid-cols-2 gap-4 border-t border-slate-800 pt-8">
                <div><p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Tech</p><p className="text-white font-black text-sm">{data?.tech_score}/100</p></div>
                <div><p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Fund</p><p className="text-white font-black text-sm">{data?.fund_score}/100</p></div>
              </div>
            </div>
          )}

          {data?.fundamentals && (
            <div className="bg-blue-600/5 border border-blue-500/20 rounded-[40px] p-8">
                <p className="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-6">Institutional DNA</p>
                <div className="space-y-6">
                    <Stat label="P/E Ratio" val={data?.fundamentals?.pe_ratio} />
                    <Stat label="Debt/Equity" val={data?.fundamentals?.debt_equity} />
                    <Stat label="Profit Margin" val={data?.fundamentals?.margin} />
                    <Stat label="Sentiment" val={data?.fundamentals?.sentiment} color="text-blue-400" />
                    <Stat label="Cash Flow" val={data?.fundamentals?.cash_flow} />
                </div>
            </div>
          )}

          <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 shadow-inner">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-6">Secured Watchlist</p>
            <div className="space-y-3 max-h-[350px] overflow-y-auto custom-scrollbar pr-2">
              {watchlist?.map((item, i) => (<button key={i} onClick={() => runAnalysis(item.ticker)} className="w-full flex justify-between p-4 rounded-2xl bg-slate-950 border border-slate-800 hover:border-blue-500/50 group transition-all"><span className="font-black text-white group-hover:text-blue-400 text-lg">{item.ticker}</span><span className="text-[10px] font-mono font-bold text-slate-500">{item.score} PTS</span></button>))}
            </div>
          </div>
        </div>

        {/* CENTER COLUMN: CHART & ANALYSIS LEDGER */}
        <div className="col-span-12 lg:col-span-6 flex flex-col gap-8">
          {!data ? (
              <div className="flex flex-col gap-8 h-full"><div className="bg-slate-900/30 border border-slate-800 p-10 rounded-[48px] text-center"><h3 className="text-3xl font-bold text-white uppercase tracking-widest">Market Pulse</h3></div><MarketScreener /></div>
          ) : (
            <>
              <TradingViewWidget symbol={confirmedTicker} />
              <div className="grid grid-cols-1 gap-4">
                {data?.ledger?.map((item: any, i: number) => (
                  <div key={i} className="bg-slate-900/30 border border-slate-800/50 p-8 rounded-[40px] flex justify-between items-start transition-all hover:border-slate-600">
                    <div className="flex-1">
                        <div className="flex justify-between items-center mb-4">
                            <div><p className="text-white font-black text-xl">{item.factor}</p><p className="text-[11px] text-blue-500 font-bold uppercase mt-1">{item.status}</p></div>
                            <span className="text-white font-black text-xl">{item.val}</span>
                        </div>
                        <p className="text-slate-400 text-sm italic border-l-2 border-slate-800 pl-4 leading-relaxed font-medium">"{item.reasoning}"</p>
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={() => runDeepDive('strike_zone')} className="w-full bg-blue-600 hover:bg-blue-500 py-5 rounded-[32px] font-black text-xs uppercase tracking-[0.3em] transition-all shadow-xl shadow-blue-600/20">🎯 Calculate AI-Powered Entry Zone</button>
            </>
          )}
        </div>

        {/* RIGHT COLUMN: INTERCEPT & NEWS WIRE */}
        <div className="col-span-12 lg:col-span-3 space-y-8">
          <div className="bg-slate-900 border border-slate-800 rounded-[40px] p-10 shadow-2xl">
             <div className="flex items-center gap-3 mb-10 text-blue-500"><div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse" /><p className="text-[10px] font-black uppercase tracking-[0.3em]">AI Market Intercept</p></div>
             {data ? (
                <>
                  <div className="mb-8">
                     <p className="text-[10px] font-black text-slate-400 uppercase mb-2">Current Price</p>
                     <p className="text-7xl font-mono font-black text-white tracking-tighter mb-4">${data?.price}</p>
                     <p className="text-[10px] font-black text-blue-400 uppercase tracking-widest bg-blue-500/10 px-3 py-2 rounded-lg inline-block">{data?.company_name}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-8 border-t border-slate-800 pt-8 mb-8">
                     <div><p className="text-[9px] font-bold text-slate-400 uppercase mb-2">24H Volume</p><p className="text-white font-black text-sm">{data?.volume}</p></div>
                     <div><p className="text-[9px] font-bold text-slate-400 uppercase mb-2">Rel Surge</p><p className="text-blue-400 font-black text-sm">{data?.vol_surge}</p></div>
                  </div>

                  {data?.holding_analysis && (
                    <div className="mb-8 p-6 bg-orange-500/5 border border-orange-500/10 rounded-3xl">
                      <div className="flex justify-between items-center mb-4"><p className="text-[10px] font-black text-orange-500 uppercase">Exit Stance</p><span className="text-white font-black text-xs uppercase">{data.holding_analysis.status}</span></div>
                      <p className="text-slate-300 text-[11px] italic mb-6 border-l border-slate-800 pl-3">"{data.holding_analysis.guidance}"</p>
                      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800">
                          <div><p className="text-[8px] font-bold text-slate-400 uppercase mb-1">Stop</p><p className="text-white font-mono font-black text-xs">${data.holding_analysis.stop_loss}</p></div>
                          <div><p className="text-[8px] font-bold text-slate-400 uppercase mb-1">Target</p><p className="text-white font-mono font-black text-xs">${data.holding_analysis.trailing_target}</p></div>
                      </div>
                    </div>
                  )}

                  <button onClick={() => runDeepDive('verdict')} className="w-full mb-4 bg-blue-600/10 border border-blue-500/20 py-3 rounded-xl text-blue-500 font-black text-[10px] uppercase tracking-widest hover:bg-blue-600 hover:text-white transition-all">Execute AI Analysis Verdict</button>
                  <div className="mb-10 p-5 bg-blue-500/5 border-l-2 border-blue-500 rounded-r-2xl min-h-[50px]">
                      <p className="text-slate-200 text-sm font-bold italic leading-relaxed">"{data?.ai_tactical}"</p>
                  </div>

                  <div className="p-8 bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-[32px] shadow-2xl relative overflow-hidden group">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-blue-600/10 rounded-full blur-3xl group-hover:bg-blue-600/20 transition-all" />
                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-3">Portfolio Intelligence</p>
                    <h3 className="text-white font-black text-xl mb-3">Tailor Your AI Experience.</h3>
                    <p className="text-slate-400 text-[12px] leading-relaxed mb-8">Upload your current portfolio data to unlock personalized exit strategies.</p>
                    <Link href="/portfolio">
                      <button className="w-full py-4 bg-slate-800 text-[10px] font-black uppercase tracking-widest rounded-xl hover:bg-blue-600 transition-all text-white border border-slate-700 hover:border-blue-500 shadow-lg">Sync Portfolio Data</button>
                    </Link>
                  </div>
                </>
             ) : (
                <p className="text-slate-600 font-bold uppercase text-[10px] tracking-widest italic text-center">Scan required...</p>
             )}
          </div>

          <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 flex flex-col h-[600px] overflow-hidden shrink-0">
             <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-6 text-center">AI Intelligence Wire</p>
             
             <button onClick={() => runDeepDive('sentiment')} className="w-full mb-6 bg-blue-600/10 border border-blue-500/20 py-4 rounded-2xl text-blue-500 font-black text-[10px] uppercase tracking-widest hover:bg-blue-600 hover:text-white transition-all shadow-blue-500/5">🌐 Global AI Sentiment Check</button>

             <div className="space-y-4 overflow-y-auto custom-scrollbar flex-1">
                {newsToDisplay.map((item: any, i: number) => (
                    <div key={i} onClick={() => handleArticleClick(item)} className="bg-slate-950 border border-slate-800 p-5 rounded-3xl cursor-pointer hover:border-blue-500/50 group transition-all">
                        <p className="text-sm font-bold text-slate-200 group-hover:text-blue-400 leading-snug line-clamp-3">{item.title}</p>
                        <div className="flex justify-between items-center mt-4 pt-4 border-t border-slate-800/30">
                            <p className="text-[9px] font-black text-slate-400 group-hover:text-slate-200 uppercase">{item.publisher}</p>
                            <span className="text-[8px] bg-blue-600/10 text-blue-500 px-2 py-0.5 rounded-full uppercase font-black">AI Synthesis</span>
                        </div>
                    </div>
                ))}
             </div>
          </div>
        </div>

      </div>
    </main>
  );
}