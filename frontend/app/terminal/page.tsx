"use client";
import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";

// Pointing to local backend for testing
const BACKEND_URL = "https://tradebotics-api.onrender.com";

// --- WIDGET COMPONENTS ---
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
        "colorTheme": "dark", "isTransparent": true, "displayMode": "adaptive", "locale": "en"
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
      script.innerHTML = JSON.stringify({ "autosize": true, "symbol": symbol, "interval": "D", "theme": "dark", "style": "1", "locale": "en", "container_id": "tv_chart" });
      container.current.appendChild(script);
    }
  }, [symbol]);
  return <div className="w-full h-[450px] bg-slate-950 rounded-[32px] overflow-hidden border border-slate-800 shadow-2xl" ref={container}><div id="tv_chart" className="w-full h-full" /></div>;
}

function Stat({ label, val, color = "text-white" }: { label: string, val: string, color?: string }) {
  return (
    <div className="flex justify-between items-end border-b border-slate-800/50 pb-2 group hover:border-blue-500/30 transition-all">
      <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] group-hover:text-blue-500/50 transition-colors">{label}</p>
      <p className={`${color} font-black text-lg tracking-tight`}>{val}</p>
    </div>
  );
}

// --- MAIN TERMINAL PAGE ---
export default function TerminalPage() {
  const router = useRouter();
  
  // 🚨 SECURITY STATE
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [userEmail, setUserEmail] = useState("");

  const [data, setData] = useState<any>(null);
  const [globalNews, setGlobalNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false); 
  const [isAnalyzing, setIsAnalyzing] = useState(false); 
  const [toastMessage, setToastMessage] = useState<string | null>(null); 
  
  const [ticker, setTicker] = useState("");
  const [confirmedTicker, setConfirmedTicker] = useState("");
  
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [isRefreshingWatchlist, setIsRefreshingWatchlist] = useState(false); 
  const [deepDiveResult, setDeepDiveResult] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);

  // 🚨 SECURITY GUARD: Verify Clearance
  useEffect(() => {
      const verifyClearance = async () => {
          const { data: { session }, error } = await supabase.auth.getSession();
          if (error || !session) {
              console.warn("Unauthorized access attempt. Redirecting to gateway.");
              router.push('/'); 
          } else {
              setIsAuthorized(true);
              setUserEmail(session.user.email || "OPERATIVE");
              fetchWatchlist(session.user.id);
              fetchGlobalNews();
          }
      };
      verifyClearance();
  }, [router]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500); 
  };

  const fetchWatchlist = async (userId: string) => { 
    const { data } = await supabase.from('watchlist').select('*').eq('user_id', userId).order('created_at', { ascending: false }); 
    if (data) setWatchlist(data); 
  };

  const runAnalysis = async (t?: string) => {
    const target = t || ticker;
    if (!target) return;
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/analyze/${target}`);
      const result = await res.json();
      if (res.ok) { setData(result); setConfirmedTicker(target); }
      else { showToast(`Terminal Error: ${result.detail || "Scan Failed."}`); }
    } catch { showToast("Backend Offline. Check Connection."); }
    setLoading(false);
  };

  const addToWatchlist = async () => {
    if (!data) return;
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { error } = await supabase.from('watchlist').insert([{ 
        user_id: user.id, 
        ticker: confirmedTicker, 
        score: data.score 
    }]);
    if (error) showToast("Watchlist Error: " + error.message);
    else {
        showToast(`${confirmedTicker} ADDED TO WATCHLIST`);
        fetchWatchlist(user.id);
    }
  };

  const removeFromWatchlist = async (removeTicker: string, e: React.MouseEvent) => {
    e.stopPropagation(); 
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    
    const { error } = await supabase.from('watchlist').delete().eq('user_id', user.id).eq('ticker', removeTicker);
    if (error) showToast("Delete Error: " + error.message);
    else {
        showToast(`${removeTicker} REMOVED FROM WATCHLIST`);
        fetchWatchlist(user.id);
    }
  };

  const handleRefreshWatchlist = async () => {
    if (watchlist.length === 0) return;
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    setIsRefreshingWatchlist(true);
    showToast("Refreshing Quant Scores...");
    
    try {
        const updatePromises = watchlist.map(async (item) => {
            const res = await fetch(`${BACKEND_URL}/analyze/${item.ticker}`);
            if (res.ok) {
                const fetchedData = await res.json();
                await supabase.from('watchlist').update({ score: fetchedData.score }).eq('user_id', user.id).eq('ticker', item.ticker);
            }
        });
        await Promise.all(updatePromises);
        await fetchWatchlist(user.id);
        showToast("Watchlist Scores Updated.");
    } catch (error) { showToast("Failed to refresh some scores."); }
    setIsRefreshingWatchlist(false);
  };

  const runMasterAnalysis = async () => {
    if (!data) return;
    setDeepDiveResult(null);
    setIsAnalyzing(true); 
    try {
        const res = await fetch(`${BACKEND_URL}/translate`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                ticker: confirmedTicker,
                data_context: { score: data.score, price: data.price, fundamentals: data.fundamentals, ledger: data.ledger } 
            })
        });
        const result = await res.json();
        setDeepDiveResult(result.analysis);
    } catch { showToast("AI Node Error."); }
    setIsAnalyzing(false); 
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
    } catch { setSelectedArticle({ ...item, summary: ["Failed to retrieve summary."] }); }
    setIsSummarizing(false);
  };

  const fetchGlobalNews = async () => { 
    try { 
      const res = await fetch(`${BACKEND_URL}/market-briefing`); 
      if (res.ok) setGlobalNews(await res.json()); 
    } catch { console.warn("Briefing offline."); } 
  };
  
  const newsToDisplay = data?.news?.length > 0 ? data.news : globalNews;

  // 🚨 LOADING INTERCEPT
  if (!isAuthorized) {
      return (
          <main className="min-h-screen bg-[#020617] flex items-center justify-center">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin" />
                  <p className="text-[10px] text-blue-500 font-black uppercase tracking-widest animate-pulse">Verifying Clearance...</p>
              </div>
          </main>
      );
  }

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 flex flex-col font-sans relative">
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
      `}} />

      {/* GLOBAL TOAST & MODALS */}
      {toastMessage && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-10 py-6 rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center mb-3"><div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" /></div>
              <p className="text-white font-black uppercase tracking-widest text-sm text-center">{toastMessage}</p>
           </div>
        </div>
      )}

      {(loading || isAnalyzing) && (
        <div className="fixed inset-0 z-[120] bg-[#020617]/90 backdrop-blur-md flex flex-col items-center justify-center">
           <div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-6" />
           <p className="text-blue-500 font-black tracking-[0.4em] uppercase text-xs animate-pulse">
               {loading ? "Initializing Scan..." : "Neural Synthesis in Progress..."}
           </p>
        </div>
      )}

      {deepDiveResult && !isAnalyzing && (
        <div className="fixed inset-0 z-[110] bg-black/95 backdrop-blur-xl flex items-center justify-center p-4">
            <div className="w-full max-w-2xl max-h-[90vh] bg-slate-900 border border-blue-500/30 p-10 rounded-[48px] shadow-2xl flex flex-col overflow-hidden">
              <div className="flex items-center gap-3 mb-8 shrink-0"><div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" /><p className="text-[10px] font-black uppercase tracking-[0.4em] text-blue-500">AI Deep Dive Analysis</p></div>
              <div className="overflow-y-auto custom-scrollbar flex-1 mb-10 pr-2"><p className="text-white text-lg font-medium leading-relaxed italic whitespace-pre-wrap">"{deepDiveResult}"</p></div>
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

      <div className="p-6 flex flex-col flex-1">
        <TickerTape />
        
        {/* NAV HEADER */}
        <div className="flex justify-between items-center mb-12">
          <div>
              <h1 className="text-5xl font-black text-white tracking-tighter cursor-pointer hover:text-blue-500 transition-colors" onClick={() => router.push('/hub')}>
                  TRADEBOTICS<span className="text-blue-500">AI</span>
              </h1>
              <p className="text-[9px] uppercase tracking-[0.5em] text-slate-400 italic">Operative // {userEmail.split('@')[0]}</p>
          </div>
          
          <div className="flex gap-4 items-center">
            <button onClick={() => { setData(null); setTicker(""); setConfirmedTicker(""); }} className="flex items-center gap-3 px-6 py-3 bg-slate-900/50 border border-slate-800 rounded-full hover:border-blue-500/50 transition-all group">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">Market Pulse</span>
            </button>

            <button onClick={() => router.push('/hub')} className="hidden lg:flex items-center gap-3 px-6 py-3 bg-slate-900/50 border border-slate-800 rounded-full hover:border-blue-500/50 transition-all group">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">← Return to Hub</span>
            </button>
            
            <div className="flex gap-3 bg-slate-900/80 p-3 rounded-[24px] border border-slate-800 focus-within:border-blue-500/50">
              <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runAnalysis()} className="bg-transparent border-none text-white font-black w-48 px-4 outline-none text-lg" placeholder="TICKER..." />
              <button onClick={() => runAnalysis()} className="bg-blue-600 text-white px-10 py-4 rounded-xl font-black text-xs uppercase hover:bg-blue-500">SCAN</button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-8 flex-1">
          {/* LEFT PANEL */}
          <div className="col-span-12 lg:col-span-3 space-y-8">
            
            {data && (
              <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 shadow-inner relative group animate-in fade-in">
                <button onClick={addToWatchlist} className="absolute top-6 right-6 opacity-0 group-hover:opacity-100 bg-blue-600 hover:bg-blue-500 text-white text-[9px] font-black px-4 py-2 rounded-full transition-all">ADD TO WATCHLIST</button>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Total Quant Score</p>
                <div className="text-[120px] font-black text-white leading-none tracking-tighter mb-4">{data.score}</div>
                <div className="grid grid-cols-2 gap-4 border-t border-slate-800 pt-8">
                  <div><p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Tech</p><p className="text-white font-black text-sm">{data.tech_score}/100</p></div>
                  <div><p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Fund</p><p className="text-white font-black text-sm">{data.fund_score}/100</p></div>
                </div>
              </div>
            )}

            {data?.fundamentals && (
              <div className="bg-[#020617] border border-blue-500/20 rounded-[40px] p-10 shadow-[inset_0_0_20px_rgba(59,130,246,0.05)] animate-in fade-in">
                  <p className="text-[11px] font-black text-blue-500 uppercase tracking-[0.4em] mb-10 opacity-80">Institutional DNA</p>
                  <div className="space-y-8">
                      <Stat label="P/E Ratio" val={data.fundamentals.pe_ratio} />
                      <Stat label="Debt/Equity" val={data.fundamentals.debt_equity} />
                      <Stat label="Profit Margin" val={data.fundamentals.margin} />
                      <Stat label="Sentiment" val={data.fundamentals.sentiment} color="text-blue-500" />
                      <Stat label="Cash Flow" val={data.fundamentals.cash_flow} />
                  </div>
              </div>
            )}

            <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 shadow-inner">
              <div className="flex justify-between items-center mb-6 px-1">
                 <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Secured Watchlist</p>
                 <button onClick={handleRefreshWatchlist} disabled={isRefreshingWatchlist || watchlist.length === 0} className="text-slate-500 hover:text-blue-500 disabled:opacity-50 transition-colors" title="Refresh Scores">
                    <svg className={`w-3.5 h-3.5 ${isRefreshingWatchlist ? 'animate-spin text-blue-500' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                 </button>
              </div>
              
              <div className="space-y-3 max-h-[350px] overflow-y-auto custom-scrollbar pr-2">
                {watchlist?.map((item, i) => (
                  <div key={i} className="flex gap-2 w-full group">
                    <button onClick={() => runAnalysis(item.ticker)} className="flex-1 flex justify-between items-center p-4 rounded-2xl bg-slate-950 border border-slate-800 hover:border-blue-500/50 transition-all">
                      <span className="font-black text-white text-lg">{item.ticker}</span>
                      <span className="text-[10px] font-bold text-slate-500">{item.score} PTS</span>
                    </button>
                    <button onClick={(e) => removeFromWatchlist(item.ticker, e)} className="px-4 rounded-2xl bg-slate-950 border border-slate-800 hover:bg-red-500/10 hover:border-red-500 hover:text-red-500 text-slate-600 transition-all font-black text-xs">✕</button>
                  </div>
                ))}
                {watchlist.length === 0 && (
                    <p className="text-center text-xs font-bold text-slate-600 uppercase tracking-widest mt-6">Watchlist Empty.</p>
                )}
              </div>
            </div>

          </div>

          {/* MIDDLE PANEL */}
          <div className="col-span-12 lg:col-span-6 flex flex-col gap-8">
            {!data ? (
                <div className="flex flex-col gap-8 h-full"><div className="bg-slate-900/30 border border-slate-800 p-10 rounded-[48px] text-center"><h3 className="text-3xl font-bold text-white uppercase tracking-widest">Market Pulse</h3></div><MarketScreener /></div>
            ) : (
              <>
                <TradingViewWidget symbol={confirmedTicker} />
                <div className="grid grid-cols-1 gap-4">
                  {data.ledger?.map((item: any, i: number) => (
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
                
              </>
            )}
          </div>

          {/* RIGHT PANEL */}
          <div className="col-span-12 lg:col-span-3 space-y-8">
            <div className="bg-slate-900 border border-slate-800 rounded-[40px] p-10 shadow-2xl">
               <div className="flex items-center gap-3 mb-10 text-blue-500"><div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse" /><p className="text-[10px] font-black uppercase tracking-[0.3em]">AI Market Intercept</p></div>
               {data ? (
                  <>
                    <div className="mb-8">
                       <p className="text-[10px] font-black text-slate-400 uppercase mb-2">Current Price</p>
                       <p className="text-7xl font-mono font-black text-white tracking-tighter mb-4">${data.price}</p>
                       <p className="text-[10px] font-black text-blue-400 uppercase tracking-widest bg-blue-500/10 px-3 py-2 rounded-lg inline-block">{data.company_name}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-8 border-t border-slate-800 pt-8 mb-8">
                       <div><p className="text-[9px] font-bold text-slate-400 uppercase mb-2">24H Volume</p><p className="text-white font-black text-sm">{data.volume}</p></div>
                       <div><p className="text-[9px] font-bold text-slate-400 uppercase mb-2">Rel Surge</p><p className="text-blue-400 font-black text-sm">{data.vol_surge}</p></div>
                    </div>

                    <button 
                        onClick={() => runMasterAnalysis()} 
                        disabled={isAnalyzing}
                        className="w-full mb-4 bg-blue-600 border border-blue-500 py-3 rounded-xl text-white font-black text-[10px] uppercase tracking-widest hover:bg-blue-500 hover:text-white transition-all shadow-[0_0_15px_rgba(59,130,246,0.3)] disabled:opacity-50"
                    >
                        {isAnalyzing ? "🧠 ANALYZING..." : "🧠 RUN AI ANALYSIS"}
                    </button>
                    
                    <div className="mb-10 p-5 bg-blue-500/5 border-l-2 border-blue-500 rounded-r-2xl min-h-[50px]">
                        <p className="text-slate-200 text-sm font-bold italic leading-relaxed">
                            "{data.ai_tactical || "Market conditions currently being synthesized by the neural engine. Please wait for signal calibration."}"
                        </p>
                    </div>

                  </>
               ) : ( <p className="text-slate-600 font-bold uppercase text-[10px] tracking-widest italic text-center">Scan required...</p> )}
            </div>

            <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 flex flex-col h-[600px] overflow-hidden shrink-0">
               <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-6 text-center">AI Intelligence Wire</p>
               
               <button onClick={() => runMasterAnalysis()} className="w-full mb-6 bg-blue-900/30 border border-blue-500/50 py-4 rounded-2xl text-blue-400 font-black text-[10px] uppercase tracking-widest hover:bg-blue-600 hover:text-white transition-all shadow-[0_0_15px_rgba(59,130,246,0.15)]">
                  🌐 Global AI Sentiment Check
               </button>

               <div className="space-y-4 overflow-y-auto custom-scrollbar flex-1">
                  {newsToDisplay.map((item: any, i: number) => (
                      <div key={i} onClick={() => handleArticleClick(item)} className="bg-slate-950 border border-slate-800 p-5 rounded-3xl cursor-pointer hover:border-blue-500/50 group transition-all">
                          <p className="text-sm font-bold text-slate-200 group-hover:text-blue-400 leading-snug line-clamp-3">{item.title}</p>
                          <div className="flex justify-between items-center mt-4 pt-4 border-t border-slate-800/30">
                              <p className="text-[9px] font-black text-slate-400 group-hover:text-slate-200 uppercase">
                                  {item.publisher} {item.date ? `• ${item.date}` : ""}
                              </p>
                              <span className="text-[8px] bg-blue-600/10 text-blue-500 px-2 py-0.5 rounded-full uppercase font-black">AI Synthesis</span>
                          </div>
                      </div>
                  ))}
               </div>
            </div>
          </div>

        </div>
        
        <footer className="border-t border-slate-800/50 pt-8 mt-12 text-center w-full">
            <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
        </footer>
      </div>

    </main>
  );
}