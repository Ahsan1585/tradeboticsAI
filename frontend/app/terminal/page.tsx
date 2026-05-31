"use client";
import React, { useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "../lib/supabase";
import TradeTicket from "../components/TradeTicket"; 

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
  return <div ref={container} className="w-full mb-4 lg:mb-8 opacity-60" />;
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
  return <div className="w-full h-[350px] lg:h-[450px] bg-slate-950 rounded-[24px] lg:rounded-[32px] overflow-hidden border border-slate-800 shadow-2xl" ref={container}><div id="tv_chart" className="w-full h-full" /></div>;
}

function Stat({ label, val, color = "text-white" }: { label: string, val: string, color?: string }) {
  return (
    <div className="flex justify-between items-end border-b border-slate-800/50 pb-2 group hover:border-blue-500/30 transition-all">
      <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] group-hover:text-blue-500/50 transition-colors">{label}</p>
      <p className={`${color} font-black text-base lg:text-lg tracking-tight text-right`}>{val}</p>
    </div>
  );
}

// --- MAIN TERMINAL PAGE COMPONENT ---
function TerminalContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initializedRef = useRef(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [loadingText, setLoadingText] = useState("Initializing Matrix...");
  
  // 🚨 NEURAL AUTHORIZATION STATE
  const [authModal, setAuthModal] = useState({
      isOpen: false,
      title: "",
      cost: 0,
      actionName: "",
      onConfirm: () => {}
  });

  // 🚨 TRADING ENGINE STATE
  const [showTradeTicket, setShowTradeTicket] = useState(false);
  const [virtualCash, setVirtualCash] = useState(0);
  const [currentShares, setCurrentShares] = useState(0);
  
  // 🚨 SECURITY STATE
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [userId, setUserId] = useState("");
  
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
  const [exitStrategyResult, setExitStrategyResult] = useState<string | null>(null);
  const [isGeneratingExit, setIsGeneratingExit] = useState(false);

  // 🚨 NEW SCREENER ENGINE STATES
  const [horizon, setHorizon] = useState("Swing Trade");
  const [risk, setRisk] = useState("Moderate");
  const [screenerResults, setScreenerResults] = useState<any[]>([]);
  const [isScanning, setIsScanning] = useState(false);

  useEffect(() => {
      if (!userId) return;
      const savedScreenerData = localStorage.getItem(`screener_analysis_${userId}`);
      if (savedScreenerData) {
          setScreenerResults(JSON.parse(savedScreenerData));
      }
  }, [userId]);

  const executeMarketScan = async () => {
        setIsScanning(true);
        setScreenerResults([]);
        setScanProgress(0);
        setLoadingText("Compiling 170-Asset Universe...");

        const phrases = [
            "Extracting Real-Time Pricing...",
            "Calculating Technical Moving Averages...",
            "Scoring Fundamental P/E Ratios...",
            "Applying Risk Tolerance Modifiers...",
            "Executing Proprietary Quant Matrix...",
            "Isolating Top Alpha Candidates..."
        ];

        let currentProgress = 0;
        let phraseIndex = 0;

        const progressInterval = setInterval(() => {
            currentProgress += 1;
            if (currentProgress >= 99) {
                currentProgress = 99; 
            }
            setScanProgress(currentProgress);

            if (currentProgress % 15 === 0 && phraseIndex < phrases.length) {
                setLoadingText(phrases[phraseIndex]);
                phraseIndex++;
            }
        }, 165); 

        try {
            const res = await fetch(`${BACKEND_URL}/run-screener`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ trade_style: horizon, risk_level: risk })
            });
            const responseData = await res.json();
            
            clearInterval(progressInterval); 
            setScanProgress(100); 

            if (res.ok) {
                setTimeout(() => {
                    setScreenerResults(responseData.results);
                    if (userId) localStorage.setItem(`screener_analysis_${userId}`, JSON.stringify(responseData.results));
                    showToast(`Matrix Online: ${responseData.results.length} Candidates Found.`);
                    setIsScanning(false);
                }, 500);
            } else {
                showToast("Matrix Scan Failed.");
                setIsScanning(false);
            }
        } catch (error) {
            clearInterval(progressInterval);
            showToast("Network pipeline disrupted.");
            setIsScanning(false);
        }
    };

  const handleExecuteTrade = async (tradeType: "BUY" | "SELL", amount: number, mode: "DOLLARS" | "SHARES") => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      try {
          const res = await fetch(`${BACKEND_URL}/execute-trade`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ user_id: session.user.id, ticker: confirmedTicker, trade_type: tradeType, amount: amount, mode: mode })
          });
          const result = await res.json();
          if (res.ok) {
              setVirtualCash(result.remaining_cash);
              showToast(result.message);
              runAnalysis(confirmedTicker); 
          } else showToast(`Trade Error: ${result.detail}`);
      } catch (error) { showToast("Execution Offline. Check Connection."); }
  };

  useEffect(() => {
      const verifyClearance = async () => {
          const { data: { session }, error } = await supabase.auth.getSession();
          if (error || !session) {
              router.push('/'); 
          } else {
              setIsAuthorized(true);
              setUserId(session.user.id);
              setUserEmail(session.user.email || "OPERATIVE");
              fetchWatchlist(session.user.id);
              fetchGlobalNews();
              const { data: profile } = await supabase.from('profiles').select('virtual_cash_balance').eq('id', session.user.id).single();
              if (profile) setVirtualCash(profile.virtual_cash_balance);
          }
      };
      verifyClearance();
  }, [router]);

  useEffect(() => {
      if (initializedRef.current || !isAuthorized) return;
      const urlTicker = searchParams.get('ticker');
      if (urlTicker) {
          setTicker(urlTicker);
          runAnalysis(urlTicker);
          initializedRef.current = true; 
      }
  }, [searchParams, isAuthorized]); 

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
    setExitStrategyResult(null); 
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { showToast("Unauthorized Access."); setLoading(false); return; }

      const res = await fetch(`${BACKEND_URL}/analyze/${target}?user_id=${session.user.id}`);
      const result = await res.json();
      
      if (res.ok) { 
          setData(result); setConfirmedTicker(target);
          const { data: portfolio } = await supabase.from('portfolio').select('shares').eq('user_id', session.user.id).eq('ticker', target).maybeSingle();
          setCurrentShares(portfolio ? portfolio.shares : 0);
      } else { 
          if (res.status === 402) showToast("NEURAL BANDWIDTH DEPLETED. RECHARGE REQUIRED.");
          else showToast(`Terminal Error: ${result.detail || "Scan Failed."}`);
      }
    } catch { showToast("Backend Offline. Check Connection."); }
    setLoading(false);
  };

  const removeFromWatchlist = async (removeTicker: string, e: React.MouseEvent) => {
    e.stopPropagation(); 
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    const { error } = await supabase.from('watchlist').delete().eq('user_id', user.id).eq('ticker', removeTicker);
    if (error) showToast("Delete Error: " + error.message);
    else { showToast(`${removeTicker} REMOVED`); fetchWatchlist(user.id); }
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
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const res = await fetch(`${BACKEND_URL}/translate?user_id=${session.user.id}`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: confirmedTicker, data_context: { score: data.score, price: data.price, fundamentals: data.fundamentals, ledger: data.ledger } })
        });
        const result = await res.json();
        if (res.ok) setDeepDiveResult(result.analysis);
        else {
            if (res.status === 402) showToast("NEURAL BANDWIDTH DEPLETED.");
            else showToast(`Terminal Error: ${result.detail || "Synthesis Failed."}`);
        }
    } catch { showToast("AI Node Error. Check Connection."); }
    setIsAnalyzing(false); 
  };

  const runExitStrategy = async () => {
    if (!data || !confirmedTicker) return; 
    setIsGeneratingExit(true); setExitStrategyResult(null);
    try {
        const res = await fetch(`${BACKEND_URL}/exit-strategy?user_id=${userId}`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: confirmedTicker, data_context: data })
        });
        const result = await res.json();
        if (res.ok) setExitStrategyResult(result.analysis);
        else {
            if (res.status === 402) showToast("NEURAL BANDWIDTH DEPLETED.");
            else showToast("AI Engine Error: " + result.detail);
        }
    } catch (error) { showToast("Backend Offline. Check connection."); }
    setIsGeneratingExit(false);
  };

  const handleArticleClick = async (item: any) => {
    setSelectedArticle({ ...item, summary: null });
    setIsSummarizing(true);
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const res = await fetch(`${BACKEND_URL}/summarize?user_id=${session.user.id}`, { 
          method: "POST", headers: { "Content-Type": "application/json" }, 
          body: JSON.stringify({ title: item.title, ticker: confirmedTicker || "Macro", content: item.content || "" }) 
        });
        const result = await res.json();
        if (res.ok) setSelectedArticle({ ...item, summary: result.summary });
        else {
            if (res.status === 402) { showToast("NEURAL BANDWIDTH DEPLETED."); setSelectedArticle(null); } 
            else setSelectedArticle({ ...item, summary: ["Synthesis Failed."] });
        }
    } catch { setSelectedArticle({ ...item, summary: ["Failed to retrieve summary."] }); }
    setIsSummarizing(false);
  };

  const triggerArticleAnalysis = (item: any) => {
      setAuthModal({ isOpen: true, title: "News Synthesis", cost: 1, actionName: "DECRYPT ARTICLE", onConfirm: () => handleArticleClick(item) });
  };

  const addToWatchlist = async () => {
      if (!data || !data.ticker) return;
      const isDuplicate = watchlist.some((item: any) => item.ticker === data.ticker);
      if (isDuplicate) { showToast(`${data.ticker} is already secured.`); return; }
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      try {
          const { data: newRow, error } = await supabase.from('watchlist').insert([{ user_id: session.user.id, ticker: data.ticker }]).select().single();
          if (error) {
              if (error.code === '23505') showToast(`${data.ticker} is already in watchlist.`);
              else throw error;
          } else {
              showToast(`${data.ticker} secured in Watchlist.`);
              setWatchlist((prevWatchlist: any) => [...prevWatchlist, newRow]); 
          }
      } catch (error) { showToast(`Error saving ${data.ticker}.`); }
  };

  const fetchGlobalNews = async () => { 
    try { const res = await fetch(`${BACKEND_URL}/market-briefing`); if (res.ok) setGlobalNews(await res.json()); } catch { console.warn("Briefing offline."); } 
  };

  if (!isAuthorized) {
      return (
          <main className="min-h-screen bg-[#020617] flex items-center justify-center p-4">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin" />
                  <p className="text-[10px] text-blue-500 font-black uppercase tracking-widest animate-pulse">Verifying Clearance...</p>
              </div>
          </main>
      );
  }

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 flex flex-col font-sans relative overflow-x-hidden">
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        @media (min-width: 768px) { .custom-scrollbar::-webkit-scrollbar { width: 6px; } }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
      `}} />

      {/* GLOBAL TOAST */}
      {toastMessage && (
        <div className="fixed inset-x-4 top-4 md:inset-0 md:top-0 z-[150] flex items-start md:items-center justify-center pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-6 py-4 md:px-10 md:py-6 rounded-2xl md:rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in slide-in-from-top-4 md:zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <div className="hidden md:flex w-8 h-8 bg-blue-500/20 rounded-full items-center justify-center mb-3"><div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" /></div>
              <p className="text-white font-black uppercase tracking-widest text-[10px] md:text-sm text-center">{toastMessage}</p>
           </div>
        </div>
      )}

      {/* TRADE TICKET MODAL */}
      {showTradeTicket && data && (
          <TradeTicket
              ticker={data.ticker}
              currentPrice={data.price}
              buyingPower={virtualCash}
              currentShares={currentShares}
              onClose={() => setShowTradeTicket(false)}
              onExecute={handleExecuteTrade}
          />
      )}

      {(loading || isAnalyzing) && (
        <div className="fixed inset-0 z-[120] bg-[#020617]/90 backdrop-blur-md flex flex-col items-center justify-center p-4">
           <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-6" />
           <p className="text-blue-500 font-black tracking-[0.3em] md:tracking-[0.4em] uppercase text-[10px] md:text-xs animate-pulse text-center">
               {loading ? "Initializing Scan..." : "Neural Synthesis in Progress..."}
           </p>
        </div>
      )}

      {deepDiveResult && !isAnalyzing && (
        <div className="fixed inset-0 z-[110] bg-black/95 backdrop-blur-xl flex items-center justify-center p-3 md:p-4">
            <div className="w-full max-w-2xl max-h-[95vh] md:max-h-[90vh] bg-slate-900 border border-blue-500/30 p-6 md:p-10 rounded-[32px] md:rounded-[48px] shadow-2xl flex flex-col overflow-hidden">
              <div className="flex items-center gap-3 mb-6 md:mb-8 shrink-0"><div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" /><p className="text-[10px] font-black uppercase tracking-[0.4em] text-blue-500">AI Deep Dive Analysis</p></div>
              <div className="overflow-y-auto custom-scrollbar flex-1 mb-6 md:mb-10 pr-2">
                  <p className="text-slate-200 text-sm md:text-lg font-medium leading-relaxed italic whitespace-pre-wrap">"{deepDiveResult}"</p>
              </div>
              <button onClick={() => setDeepDiveResult(null)} className="w-full bg-slate-800 py-4 rounded-xl md:rounded-2xl font-black text-[10px] uppercase tracking-widest hover:text-white transition-colors shrink-0">Close Briefing</button>
            </div>
        </div>
      )}

      {selectedArticle && (
        <div className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center p-3 md:p-4">
            <div className="w-full max-w-3xl max-h-[95vh] md:max-h-[85vh] bg-[#020617] border border-blue-500/30 rounded-[32px] md:rounded-[40px] overflow-hidden flex flex-col shadow-2xl">
              <div className="p-6 md:p-8 border-b border-slate-800 bg-slate-900/40 shrink-0 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-3 mb-2 md:mb-4">
                        <div className={`w-2 h-2 ${isSummarizing ? 'bg-orange-500' : 'bg-blue-500'} rounded-full animate-pulse`} />
                        <p className="text-[10px] font-black uppercase text-blue-500">AI Synthesis</p>
                    </div>
                    <h2 className="text-lg md:text-2xl font-bold text-white line-clamp-2 md:line-clamp-none">{selectedArticle?.title}</h2>
                </div>
                <button onClick={() => setSelectedArticle(null)} className="text-slate-400 font-black text-[10px] uppercase bg-slate-800 px-4 py-2 rounded-full h-fit self-end md:self-auto shrink-0">Close</button>
              </div>
              <div className="p-6 md:p-8 bg-slate-950 overflow-y-auto flex-1 custom-scrollbar">
                 {isSummarizing ? (
                     <div className="space-y-4 animate-pulse">
                         <div className="h-4 bg-slate-800 rounded w-full"></div>
                         <div className="h-4 bg-slate-800 rounded w-5/6"></div>
                         <div className="h-4 bg-slate-800 rounded w-4/6"></div>
                     </div>
                 ) : (
                     <div className="space-y-4 md:space-y-6">
                         {selectedArticle?.summary?.map((p: string, i: number) => <p key={i} className="text-slate-300 leading-relaxed text-sm md:text-base">{p}</p>)}
                     </div>
                 )}
              </div>
            </div>
        </div>
      )}

      {/* MOBILE-OPTIMIZED MAIN PADDING */}
      <div className="p-3 md:p-6 flex flex-col flex-1">
        <TickerTape />
        
        {/* RESPONSIVE NAV HEADER */}
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 mb-8 md:mb-12">
          <div>
              <h1 className="text-3xl md:text-5xl font-black text-white tracking-tighter cursor-pointer hover:text-blue-500 transition-colors" onClick={() => router.push('/hub')}>
                  TRADEBOTICS<span className="text-blue-500">AI</span>
              </h1>
              <p className="text-[9px] uppercase tracking-[0.5em] text-slate-400 italic mt-1 md:mt-2">Operative // {userEmail.split('@')[0]}</p>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-3 w-full xl:w-auto items-stretch sm:items-center">
            <div className="flex gap-2">
                <button onClick={() => { setData(null); setTicker(""); setConfirmedTicker(""); }} className="flex-1 sm:flex-none justify-center flex items-center gap-2 px-4 md:px-6 py-3 md:py-3 bg-slate-900/50 border border-slate-800 rounded-xl md:rounded-full hover:border-blue-500/50 transition-all group">
                    <span className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">Alpha Screener</span>
                </button>
                <button onClick={() => router.push('/hub')} className="hidden sm:flex items-center gap-3 px-6 py-3 bg-slate-900/50 border border-slate-800 rounded-full hover:border-blue-500/50 transition-all group">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">← Hub</span>
                </button>
            </div>
            
            <div className="flex gap-2 w-full sm:w-auto bg-slate-900/80 p-2 md:p-3 rounded-xl md:rounded-[24px] border border-slate-800 focus-within:border-blue-500/50">
              <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runAnalysis()} className="bg-transparent border-none text-white font-black w-full sm:w-32 md:w-48 px-3 outline-none text-base md:text-lg" placeholder="TICKER..." />
              <button onClick={() => runAnalysis()} className="bg-blue-600 text-white px-6 md:px-10 py-3 md:py-4 rounded-lg md:rounded-xl font-black text-[10px] md:text-xs uppercase hover:bg-blue-500 transition-colors shrink-0">SCAN</button>
            </div>
          </div>
        </div>

        {/* RESPONSIVE GRID LAYOUT */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 flex-1">
          
          {/* LEFT PANEL (Responsive) */}
          <div className="col-span-1 lg:col-span-3 space-y-6 lg:space-y-8 flex flex-col order-2 lg:order-1">
            
            {data && (
              <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] md:rounded-[40px] p-6 lg:p-8 shadow-inner relative group animate-in fade-in">
                <button onClick={addToWatchlist} className="absolute top-4 right-4 lg:top-6 lg:right-6 lg:opacity-0 group-hover:opacity-100 bg-blue-600 hover:bg-blue-500 text-white text-[9px] font-black px-3 py-1.5 lg:px-4 lg:py-2 rounded-full transition-all">ADD</button>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Total Quant Score</p>
                <div className="text-7xl lg:text-[120px] font-black text-white leading-none tracking-tighter mb-4 lg:mb-4">{data.score}</div>
                <div className="grid grid-cols-2 gap-4 border-t border-slate-800 pt-4 lg:pt-8">
                  <div><p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Tech</p><p className="text-white font-black text-xs md:text-sm">{data.tech_score}/100</p></div>
                  <div><p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Fund</p><p className="text-white font-black text-xs md:text-sm">{data.fund_score}/100</p></div>
                </div>
              </div>
            )}

            {data?.fundamentals && (
              <div className="bg-[#020617] border border-blue-500/20 rounded-[32px] md:rounded-[40px] p-6 lg:p-10 shadow-[inset_0_0_20px_rgba(59,130,246,0.05)] animate-in fade-in">
                  <p className="text-[10px] lg:text-[11px] font-black text-blue-500 uppercase tracking-[0.3em] lg:tracking-[0.4em] mb-6 lg:mb-10 opacity-80">Institutional DNA</p>
                  <div className="space-y-4 lg:space-y-8">
                      <Stat label="P/E Ratio" val={data.fundamentals.pe_ratio} />
                      <Stat label="Debt/Equity" val={data.fundamentals.debt_equity} />
                      <Stat label="Profit Margin" val={data.fundamentals.margin} />
                      <Stat label="Sentiment" val={data.fundamentals.sentiment} color="text-blue-500" />
                      <Stat label="Cash Flow" val={data.fundamentals.cash_flow} />
                  </div>
              </div>
            )}

            <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] md:rounded-[40px] p-6 lg:p-8 shadow-inner">
              <div className="flex justify-between items-center mb-4 lg:mb-6 px-1">
                 <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Secured Watchlist</p>
                 <button onClick={handleRefreshWatchlist} disabled={isRefreshingWatchlist || watchlist.length === 0} className="text-slate-500 hover:text-blue-500 disabled:opacity-50 transition-colors p-2" title="Refresh Scores">
                    <svg className={`w-4 h-4 lg:w-3.5 lg:h-3.5 ${isRefreshingWatchlist ? 'animate-spin text-blue-500' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                 </button>
              </div>
              
              <div className="space-y-2 lg:space-y-3 max-h-[300px] lg:max-h-[350px] overflow-y-auto custom-scrollbar pr-1 lg:pr-2">
                {watchlist?.map((item, i) => (
                  <div key={i} className="flex gap-2 w-full group">
                    <button onClick={() => runAnalysis(item.ticker)} className="flex-1 flex justify-between items-center p-3 lg:p-4 rounded-xl lg:rounded-2xl bg-slate-950 border border-slate-800 hover:border-blue-500/50 transition-all">
                      <span className="font-black text-white text-base lg:text-lg">{item.ticker}</span>
                      <span className="text-[9px] lg:text-[10px] font-bold text-slate-500">{item.score} PTS</span>
                    </button>
                    <button onClick={(e) => removeFromWatchlist(item.ticker, e)} className="px-3 lg:px-4 rounded-xl lg:rounded-2xl bg-slate-950 border border-slate-800 hover:bg-red-500/10 hover:border-red-500 hover:text-red-500 text-slate-600 transition-all font-black text-xs">✕</button>
                  </div>
                ))}
                {watchlist.length === 0 && (
                    <p className="text-center text-[10px] font-bold text-slate-600 uppercase tracking-widest mt-6">Watchlist Empty.</p>
                )}
              </div>
            </div>

          </div>

          {/* MIDDLE PANEL (Responsive) */}
          <div className="col-span-1 lg:col-span-6 flex flex-col gap-6 lg:gap-8 order-1 lg:order-2">
            {!data ? (
                // 🚀 NATIVE ALPHA SCREENER (Fluid Height on Mobile)
                <div className="bg-slate-900/40 border border-slate-800/80 rounded-[32px] md:rounded-[40px] p-5 md:p-8 lg:p-10 shadow-2xl backdrop-blur-md flex flex-col h-auto min-h-[500px] lg:h-[800px]">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 lg:mb-8 border-b border-slate-800/50 pb-4 lg:pb-6">
                        <div>
                            <h3 className="text-xl lg:text-2xl font-black text-white tracking-tight uppercase">Alpha Screener</h3>
                            <p className="text-[9px] lg:text-[10px] text-blue-500 font-bold uppercase tracking-[0.2em] mt-1">Proprietary Index Matrix</p>
                        </div>
                        <button 
                            onClick={executeMarketScan} 
                            disabled={isScanning}
                            className="w-full sm:w-auto px-6 py-4 sm:py-3 bg-white hover:bg-slate-200 text-slate-950 rounded-xl lg:rounded-2xl font-black text-[10px] uppercase tracking-widest disabled:opacity-50 transition-all"
                        >
                            {isScanning ? "Scanning..." : "Execute Matrix"}
                        </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 lg:gap-6 mb-6 lg:mb-8 bg-slate-950/60 p-4 lg:p-6 rounded-2xl lg:rounded-3xl border border-slate-800/60 shrink-0">
                        <div>
                            <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-3">Target Horizon</p>
                            <div className="flex gap-2">
                                {["Day Trade", "Swing Trade", "Long Term"].map((h) => (
                                    <button
                                        key={h} onClick={() => setHorizon(h)}
                                        className={`flex-1 py-3 rounded-lg lg:rounded-xl font-bold text-[9px] uppercase tracking-wider transition-all border text-center ${horizon === h ? 'bg-blue-600 border-blue-500 text-white shadow-[0_0_15px_rgba(37,99,235,0.2)]' : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'}`}
                                    >
                                        {h.split(' ')[0]}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-3">Risk Profile</p>
                            <div className="flex gap-2">
                                {["Conservative", "Moderate", "Aggressive"].map((r) => (
                                    <button
                                        key={r} onClick={() => setRisk(r)}
                                        className={`flex-1 py-3 rounded-lg lg:rounded-xl font-bold text-[9px] uppercase tracking-wider transition-all border text-center truncate px-1 ${risk === r ? (r === 'Aggressive' ? 'bg-red-900/40 border-red-500 text-red-200' : r === 'Conservative' ? 'bg-emerald-900/40 border-emerald-500 text-emerald-200' : 'bg-purple-900/40 border-purple-500 text-purple-200') : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'}`}
                                    >
                                        {r.substring(0, 3)}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 bg-slate-950/40 border border-slate-800/50 rounded-2xl lg:rounded-3xl overflow-hidden flex flex-col relative min-h-[300px]">
                        {isScanning ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#020617]/90 backdrop-blur-md z-10 px-6 lg:px-10">
                                <div className="w-full max-w-sm">
                                    <div className="flex justify-between items-end mb-3">
                                        <p className="text-[8px] lg:text-[10px] text-blue-500 font-black uppercase tracking-widest animate-pulse truncate mr-2">
                                            {loadingText}
                                        </p>
                                        <p className="text-xl lg:text-2xl font-mono font-black text-white">
                                            {scanProgress}%
                                        </p>
                                    </div>
                                    <div className="w-full h-1.5 lg:h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                                        <div 
                                            className="h-full bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)] transition-all duration-200 ease-out"
                                            style={{ width: `${scanProgress}%` }}
                                        />
                                    </div>
                                    <div className="mt-4 lg:mt-6 space-y-1 h-12 overflow-hidden opacity-50">
                                        <p className="text-[7px] lg:text-[8px] font-mono text-slate-500">[{new Date().toISOString()}] INITIALIZING MULTI-THREAD MATRIX</p>
                                        {scanProgress > 20 && <p className="text-[7px] lg:text-[8px] font-mono text-emerald-500">[{new Date().toISOString()}] SUCCESS: 170 UNIQUE ASSETS ISOLATED</p>}
                                    </div>
                                </div>
                            </div>
                        ) : screenerResults.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-600 p-6 text-center">
                                <span className="text-3xl lg:text-4xl mb-4">📡</span>
                                <p className="font-black uppercase tracking-[0.2em] text-[9px] lg:text-[10px]">Awaiting Execution Parameters</p>
                            </div>
                        ) : (
                            <div className="flex flex-col h-full">
                                <div className="grid grid-cols-12 gap-2 lg:gap-4 bg-slate-900/40 px-4 lg:px-6 py-3 lg:py-4 border-b border-slate-800/80 text-[8px] lg:text-[9px] font-black uppercase tracking-widest text-slate-500">
                                    <div className="col-span-4 lg:col-span-4">Asset</div>
                                    <div className="col-span-4 lg:col-span-4 text-right">Valuation</div>
                                    <div className="col-span-4 lg:col-span-4 text-right text-blue-400">Score</div>
                                </div>
                                <div className="overflow-y-auto custom-scrollbar flex-1 pb-4">
                                    {screenerResults.map((stock, idx) => (
                                        <div 
                                            key={stock.ticker}
                                            onClick={() => { setTicker(stock.ticker); runAnalysis(stock.ticker); }}
                                            className="grid grid-cols-12 gap-2 lg:gap-4 px-4 lg:px-6 py-3 lg:py-4 items-center border-b border-slate-800/30 hover:bg-slate-900/60 cursor-pointer group transition-colors"
                                        >
                                            <div className="col-span-4 lg:col-span-4 flex items-center gap-2 lg:gap-3">
                                                <span className="hidden sm:inline-block text-[10px] text-slate-600 font-mono w-4">{idx + 1}</span>
                                                <div className="bg-slate-900 border border-slate-800 px-2 py-1 lg:px-3 lg:py-1.5 rounded-lg group-hover:border-blue-500/50 transition-colors">
                                                    <span className="font-black text-white text-[10px] lg:text-xs">{stock.ticker}</span>
                                                </div>
                                            </div>
                                            <div className="col-span-4 lg:col-span-4 text-right">
                                                <p className="text-xs lg:text-sm font-mono font-bold text-slate-300">${stock.price.toFixed(2)}</p>
                                            </div>
                                            <div className="col-span-4 lg:col-span-4 flex justify-end">
                                                <div className="bg-blue-950/30 border border-blue-900/30 px-2 lg:px-3 py-1 rounded-md text-center">
                                                    <span className="text-xs lg:text-sm font-black font-mono text-blue-400">{stock.score}</span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
              <>
                <TradingViewWidget symbol={confirmedTicker} />
                <div className="grid grid-cols-1 gap-4">
                  {data.ledger?.map((item: any, i: number) => (
                    <div key={i} className="bg-slate-900/30 border border-slate-800/50 p-6 lg:p-8 rounded-[32px] lg:rounded-[40px] flex flex-col sm:flex-row justify-between items-start transition-all hover:border-slate-600 gap-4 sm:gap-0">
                      <div className="flex-1 w-full">
                          <div className="flex justify-between items-start sm:items-center mb-3 sm:mb-4">
                              <div>
                                  <p className="text-white font-black text-lg lg:text-xl">{item.factor}</p>
                                  <p className="text-[10px] lg:text-[11px] text-blue-500 font-bold uppercase mt-1">{item.status}</p>
                              </div>
                              <span className="text-white font-black text-lg lg:text-xl">{item.val}</span>
                          </div>
                          <p className="text-slate-400 text-xs lg:text-sm italic border-l-2 border-slate-800 pl-3 lg:pl-4 leading-relaxed font-medium">"{item.reasoning}"</p>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* RIGHT PANEL (Responsive) */}
          <div className="col-span-1 lg:col-span-3 space-y-6 lg:space-y-8 order-3">
            
            <div className="bg-slate-900 border border-slate-800 rounded-[32px] md:rounded-[40px] p-6 lg:p-10 shadow-2xl">
               <div className="flex items-center gap-3 mb-6 lg:mb-10 text-blue-500"><div className="w-2 h-2 lg:w-2.5 lg:h-2.5 bg-blue-500 rounded-full animate-pulse" /><p className="text-[9px] lg:text-[10px] font-black uppercase tracking-[0.3em]">AI Market Intercept</p></div>
               {data ? (
                 <>
                    {/* PAPER TRADING EXECUTION TRIGGER */}
                    <button 
                        onClick={() => setShowTradeTicket(true)}
                        className="w-full mb-6 lg:mb-8 bg-emerald-600 border border-emerald-500 py-4 rounded-xl lg:rounded-2xl text-white font-black text-base lg:text-lg uppercase tracking-widest hover:bg-emerald-500 transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                    >
                        TRADE {data.ticker}
                    </button>
                    <div className="mb-6 lg:mb-8">
                       <p className="text-[9px] lg:text-[10px] font-black text-slate-400 uppercase mb-2">Current Price</p>
                       <p className="text-5xl lg:text-7xl font-mono font-black text-white tracking-tighter mb-3 lg:mb-4">${data.price}</p>
                       <p className="text-[9px] lg:text-[10px] font-black text-blue-400 uppercase tracking-widest bg-blue-500/10 px-3 py-1.5 lg:py-2 rounded-lg inline-block">{data.company_name}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-4 lg:gap-8 border-t border-slate-800 pt-6 lg:pt-8 mb-6 lg:mb-8">
                       <div><p className="text-[8px] lg:text-[9px] font-bold text-slate-400 uppercase mb-1 lg:mb-2">24H Volume</p><p className="text-white font-black text-xs lg:text-sm">{data.volume}</p></div>
                       <div><p className="text-[8px] lg:text-[9px] font-bold text-slate-400 uppercase mb-1 lg:mb-2">Rel Surge</p><p className="text-blue-400 font-black text-xs lg:text-sm">{data.vol_surge}</p></div>
                    </div>

                    {/* ACTION BUTTONS: STACKED DESIGN */}
                    <div className="flex flex-col gap-3 lg:gap-4 mb-6">
                        {/* 1. Tactical Deep Dive Button */}
                        <button 
                            onClick={() => setAuthModal({ isOpen: true, title: "Tactical Deep Dive", cost: 3, actionName: "INITIATE SCAN", onConfirm: runMasterAnalysis })}
                            disabled={isAnalyzing || !data}
                            className="w-full bg-blue-900/20 border border-blue-500/40 hover:bg-blue-900/40 hover:border-blue-400 py-4 lg:py-5 px-4 lg:px-6 rounded-xl lg:rounded-2xl transition-all shadow-[0_0_20px_rgba(37,99,235,0.1)] disabled:opacity-50 flex items-center justify-between group"
                        >
                            <div className="flex items-center gap-3 lg:gap-4">
                                {isAnalyzing ? <div className="w-2.5 h-2.5 lg:w-3 lg:h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" /> : <div className="w-2 h-2 lg:w-2.5 lg:h-2.5 bg-blue-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.8)]" />}
                                <span className="text-blue-100 font-black text-[10px] sm:text-xs lg:text-sm uppercase tracking-widest text-left leading-tight">
                                    {isAnalyzing ? "Synthesizing..." : "Tactical Deep Dive"}
                                </span>
                            </div>
                            <div className="bg-slate-950 border border-blue-900/50 px-2 lg:px-3 py-1 lg:py-1.5 rounded-lg text-[9px] lg:text-[10px] font-mono font-bold text-blue-400 shrink-0">
                                -3 TKN
                            </div>
                        </button>

                        {/* 2. Quantitative Risk Button */}
                        <button 
                            onClick={() => setAuthModal({ isOpen: true, title: "Quantitative Risk Protocol", cost: 2, actionName: "GENERATE EXIT STRATEGY", onConfirm: runExitStrategy })}
                            disabled={isGeneratingExit || !data}
                            className="w-full bg-red-900/20 border border-red-500/40 hover:bg-red-900/40 hover:border-red-400 py-4 lg:py-5 px-4 lg:px-6 rounded-xl lg:rounded-2xl transition-all shadow-[0_0_20px_rgba(239,68,68,0.1)] disabled:opacity-50 flex items-center justify-between group"
                        >
                            <div className="flex items-center gap-3 lg:gap-4">
                                {isGeneratingExit ? <div className="w-2.5 h-2.5 lg:w-3 lg:h-3 border-2 border-red-500 border-t-transparent rounded-full animate-spin" /> : <div className="w-2 h-2 lg:w-2.5 lg:h-2.5 bg-red-500 rounded-full shadow-[0_0_8px_rgba(239,68,68,0.8)]" />}
                                <span className="text-red-100 font-black text-[10px] sm:text-xs lg:text-sm uppercase tracking-widest text-left leading-tight">
                                    {isGeneratingExit ? "Calculating..." : "Exit Strategy"}
                                </span>
                            </div>
                            <div className="bg-slate-950 border border-red-900/50 px-2 lg:px-3 py-1 lg:py-1.5 rounded-lg text-[9px] lg:text-[10px] font-mono font-bold text-red-400 shrink-0">
                                -2 TKN
                            </div>
                        </button>
                    </div>
                    
                    <div className="mb-4 lg:mb-6 p-4 lg:p-5 bg-blue-500/5 border-l-2 border-blue-500 rounded-r-xl lg:rounded-r-2xl min-h-[50px]">
                        <p className="text-slate-200 text-xs lg:text-sm font-bold italic leading-relaxed">
                            "{data.ai_tactical || "Market conditions currently being synthesized by the neural engine. Please wait for signal calibration."}"
                        </p>
                    </div>

                    {/* EXIT STRATEGY OUTPUT DISPLAY */}
                    {exitStrategyResult && (
                        <div className="mb-8 lg:mb-10 bg-slate-950 border border-red-500/30 rounded-2xl lg:rounded-3xl p-5 lg:p-6 shadow-[inset_0_0_20px_rgba(239,68,68,0.05)] relative overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <button onClick={() => setExitStrategyResult(null)} className="absolute top-3 right-3 lg:top-4 lg:right-4 text-slate-500 hover:text-white transition-colors p-2">
                                <svg className="w-4 h-4 lg:w-5 lg:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                            <div className="flex items-center gap-2 mb-4">
                                <div className="w-1.5 h-1.5 lg:w-2 lg:h-2 bg-red-500 rounded-full animate-pulse" />
                                <p className="text-[9px] lg:text-[10px] font-black uppercase tracking-[0.3em] text-red-500 pr-6">Quantitative Risk Protocol</p>
                            </div>
                            <div className="prose prose-invert max-w-none text-xs lg:text-sm font-medium leading-relaxed">
                                <style dangerouslySetInnerHTML={{__html: `
                                    .prose h3 { display: none; }
                                    .prose ul { list-style-type: none; padding: 0; margin: 0; }
                                    .prose li { position: relative; padding-left: 1.25rem; margin-bottom: 0.75rem; color: #cbd5e1; background: rgba(15, 23, 42, 0.5); padding: 0.75rem; padding-left: 1.75rem; border-radius: 0.5rem; line-height: 1.5; }
                                    @media (min-width: 1024px) { .prose li { padding-left: 2rem; } }
                                    .prose li::before { content: "→"; position: absolute; left: 0.5rem; top: 0.75rem; color: #f87171; font-weight: 900; }
                                    .prose strong { color: #fff; font-size: 1.05em; display: block; margin-bottom: 0.25rem; }
                                `}} />
                                <div dangerouslySetInnerHTML={{ __html: exitStrategyResult }} />
                            </div>
                        </div>
                    )}
                 </>
               ) : ( <p className="text-slate-600 font-bold uppercase text-[9px] lg:text-[10px] tracking-widest italic text-center">Scan required...</p> )}
            </div>

            <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] md:rounded-[40px] p-6 lg:p-8 flex flex-col h-auto min-h-[400px] lg:h-[600px] overflow-hidden shrink-0">
               <p className="text-[10px] lg:text-[11px] font-black text-slate-400 uppercase tracking-widest mb-4 lg:mb-6 text-center">AI Intelligence Wire</p>

               <div className="space-y-3 lg:space-y-4 overflow-y-auto custom-scrollbar flex-1 pr-1 lg:pr-2">
                  {((data && data.news && data.news.length > 0) ? data.news : globalNews).map((item: any, i: number) => (
                      <div key={i} onClick={() => triggerArticleAnalysis(item)} className="bg-slate-950 border border-slate-800 p-4 lg:p-5 rounded-2xl lg:rounded-3xl cursor-pointer hover:border-blue-500/50 group transition-all">
                          <p className="text-xs lg:text-sm font-bold text-slate-200 group-hover:text-blue-400 leading-snug line-clamp-3">
                            {item.title}
                          </p>
                          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mt-3 lg:mt-4 pt-3 lg:pt-4 border-t border-slate-800/30 gap-2 sm:gap-0">
                              <p className="text-[8px] lg:text-[9px] font-black text-slate-400 group-hover:text-slate-200 uppercase tracking-wider">
                                  {item.publisher} {item.date ? `• ${item.date}` : ""}
                              </p>
                              <span className="text-[7px] lg:text-[8px] bg-blue-600/10 text-blue-500 px-2 py-1 rounded-full uppercase font-black tracking-wider">
                                  AI Synthesis
                              </span>
                          </div>
                      </div>
                  ))}
               </div>
            </div>

          </div>
        </div>
        
        <footer className="border-t border-slate-800/50 pt-6 lg:pt-8 mt-8 lg:mt-12 text-center w-full">
            <p className="text-[9px] lg:text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
        </footer>
      </div>

      {/* 🚨 NEURAL AUTHORIZATION MODAL */}
      {authModal.isOpen && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-slate-950/90 backdrop-blur-md">
              <div className="bg-[#0B0F19] border border-red-900/50 rounded-2xl shadow-[0_0_40px_rgba(220,38,38,0.15)] w-full max-w-sm overflow-hidden relative">
                  <div className="p-3 md:p-4 border-b border-red-900/30 bg-red-950/20 flex items-center gap-2 md:gap-3">
                      <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>
                      <h2 className="text-[10px] md:text-xs font-bold text-red-500 uppercase tracking-[0.2em]">Bandwidth Auth Required</h2>
                  </div>
                  <div className="p-5 md:p-6 text-center space-y-4">
                      <p className="text-xs md:text-sm text-slate-300 font-mono leading-relaxed">
                          Executing the <span className="text-white font-bold">{authModal.title}</span> protocol will consume standard neural bandwidth.
                      </p>
                      <div className="py-3 md:py-4 bg-slate-900/50 rounded-xl border border-slate-800 flex flex-col items-center justify-center">
                          <p className="text-[9px] md:text-[10px] text-slate-500 uppercase tracking-widest mb-1">Compute Cost</p>
                          <p className="text-2xl md:text-3xl font-mono text-purple-400 font-bold">-{authModal.cost} TOKENS</p>
                      </div>
                  </div>
                  <div className="flex border-t border-slate-800">
                      <button onClick={() => setAuthModal({ ...authModal, isOpen: false })} className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-slate-500 hover:text-white uppercase tracking-widest hover:bg-slate-800/50 transition-colors">
                          Abort
                      </button>
                      <button onClick={() => { setAuthModal({ ...authModal, isOpen: false }); authModal.onConfirm(); }} className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-blue-400 hover:text-white uppercase tracking-widest hover:bg-blue-600 transition-colors border-l border-slate-800">
                          {authModal.actionName}
                      </button>
                  </div>
              </div>
          </div>
      )}

    </main>
  );
 } 
 
export default function TerminalPage() {
  return (
    <React.Suspense fallback={
      <div className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-4 md:mb-6" />
        <p className="text-[9px] md:text-[10px] text-blue-500 font-black uppercase tracking-widest animate-pulse text-center">
          Establishing Secure Link...
        </p>
      </div>
    }>
      <TerminalContent />
    </React.Suspense>
  );
}