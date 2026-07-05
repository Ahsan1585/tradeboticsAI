"use client";
import React, { useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "../lib/supabase";
import { apiFetch } from "../lib/config";
import TradeTicket from "../components/TradeTicket";
import DOMPurify from "isomorphic-dompurify";
import ThemeToggle from "../components/ThemeToggle";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import StatTile from "../components/ui/StatTile";

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
  return <div className="w-full h-[350px] lg:h-[450px] bg-bg-primary rounded-[24px] lg:rounded-[32px] overflow-hidden border border-border shadow-sm" ref={container}><div id="tv_chart" className="w-full h-full" /></div>;
}

function Stat({ label, val, color = "text-text-primary" }: { label: string, val: string, color?: string }) {
  return (
    <div className="flex justify-between items-end border-b border-border pb-2">
      <p className="text-[10px] font-black text-text-secondary uppercase tracking-[0.2em]">{label}</p>
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
  const [loadingText, setLoadingText] = useState("Initializing...");

  // AUTHORIZATION MODAL STATE
  const [authModal, setAuthModal] = useState({
      isOpen: false,
      title: "",
      cost: 0,
      actionName: "",
      onConfirm: () => {}
  });

  // TRADING ENGINE STATE
  const [showTradeTicket, setShowTradeTicket] = useState(false);
  const [virtualCash, setVirtualCash] = useState(0);
  const [currentShares, setCurrentShares] = useState(0);

  // AUTH STATE
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

  // SCREENER STATE
  const [horizon, setHorizon] = useState("Swing Trade");
  const [risk, setRisk] = useState("Medium");
  const [activeSector, setActiveSector] = useState("ALL");
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
        setLoadingText("Scanning the market...");

        const phrases = [
            "Pulling real-time pricing...",
            "Calculating moving averages...",
            "Scoring fundamentals...",
            "Applying your risk profile...",
            "Ranking top candidates...",
            "Finalizing results..."
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
            const res = await apiFetch(`/run-screener`, {
                method: "POST",
                body: JSON.stringify({ trade_style: horizon, risk_level: risk })
            });
            const responseData = await res.json();

            clearInterval(progressInterval);
            setScanProgress(100);

            if (res.ok) {
                setTimeout(() => {
                    setScreenerResults(responseData.results);
                    if (userId) localStorage.setItem(`screener_analysis_${userId}`, JSON.stringify(responseData.results));
                    showToast(`Found ${responseData.results.length} candidates.`);
                    setIsScanning(false);
                }, 500);
            } else {
                showToast("Scan failed. Please try again.");
                setIsScanning(false);
            }
        } catch (error) {
            clearInterval(progressInterval);
            showToast("Network error. Check your connection.");
            setIsScanning(false);
        }
    };

  const handleExecuteTrade = async (tradeType: "BUY" | "SELL", amount: number, mode: "DOLLARS" | "SHARES") => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      try {
          const res = await apiFetch(`/execute-trade`, {
              method: "POST",
              body: JSON.stringify({ ticker: confirmedTicker, trade_type: tradeType, amount: amount, mode: mode })
          });
          const result = await res.json();
          if (res.ok) {
              setVirtualCash(result.remaining_cash);
              showToast(result.message);
              runAnalysis(confirmedTicker);
          } else showToast(`Trade Error: ${result.detail}`);
      } catch (error) { showToast("Execution failed. Check your connection."); }
  };

  useEffect(() => {
      const verifyClearance = async () => {
          const { data: { session }, error } = await supabase.auth.getSession();
          if (error || !session) {
              router.push('/');
          } else {
              setIsAuthorized(true);
              setUserId(session.user.id);
              setUserEmail(session.user.email || "Investor");
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
      if (!session) { showToast("Please sign in again."); setLoading(false); return; }

      const res = await apiFetch(`/analyze/${target}`);
      const result = await res.json();

      if (res.ok) {
          setData(result); setConfirmedTicker(target);
          const { data: portfolio } = await supabase.from('portfolio').select('shares').eq('user_id', session.user.id).eq('ticker', target).maybeSingle();
          setCurrentShares(portfolio ? portfolio.shares : 0);
      } else {
          if (res.status === 402) showToast("Out of AI tokens. Add more to continue.");
          else showToast(`Error: ${result.detail || "Scan failed."}`);
      }
    } catch { showToast("Backend offline. Check your connection."); }
    setLoading(false);
  };

  const removeFromWatchlist = async (removeTicker: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    const { error } = await supabase.from('watchlist').delete().eq('user_id', user.id).eq('ticker', removeTicker);
    if (error) showToast("Delete Error: " + error.message);
    else { showToast(`${removeTicker} removed`); fetchWatchlist(user.id); }
  };

  const handleRefreshWatchlist = async () => {
    if (watchlist.length === 0) return;
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    setIsRefreshingWatchlist(true);
    showToast("Refreshing scores...");
    try {
        const updatePromises = watchlist.map(async (item) => {
            const res = await apiFetch(`/analyze/${item.ticker}`);
            if (res.ok) {
                const fetchedData = await res.json();
                await supabase.from('watchlist').update({ score: fetchedData.score }).eq('user_id', user.id).eq('ticker', item.ticker);
            }
        });
        await Promise.all(updatePromises);
        await fetchWatchlist(user.id);
        showToast("Watchlist updated.");
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
        const res = await apiFetch(`/translate`, {
            method: "POST",
            body: JSON.stringify({ ticker: confirmedTicker, data_context: { score: data.score, price: data.price, fundamentals: data.fundamentals, ledger: data.ledger } })
        });
        const result = await res.json();
        if (res.ok) setDeepDiveResult(result.analysis);
        else {
            if (res.status === 402) showToast("Out of AI tokens.");
            else showToast(`Error: ${result.detail || "Analysis failed."}`);
        }
    } catch { showToast("AI service error. Check your connection."); }
    setIsAnalyzing(false);
  };

  const runExitStrategy = async () => {
    if (!data || !confirmedTicker) return;
    setIsGeneratingExit(true); setExitStrategyResult(null);
    try {
        const res = await apiFetch(`/exit-strategy`, {
            method: "POST",
            body: JSON.stringify({ ticker: confirmedTicker, data_context: data })
        });
        const result = await res.json();
        if (res.ok) setExitStrategyResult(result.analysis);
        else {
            if (res.status === 402) showToast("Out of AI tokens.");
            else showToast("AI Engine Error: " + result.detail);
        }
    } catch (error) { showToast("Backend offline. Check your connection."); }
    setIsGeneratingExit(false);
  };

  const handleArticleClick = async (item: any) => {
    setSelectedArticle({ ...item, summary: null });
    setIsSummarizing(true);
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const res = await apiFetch(`/summarize`, {
          method: "POST",
          body: JSON.stringify({ title: item.title, ticker: confirmedTicker || "Macro", content: item.content || "" })
        });
        const result = await res.json();
        if (res.ok) setSelectedArticle({ ...item, summary: result.summary });
        else {
            if (res.status === 402) { showToast("Out of AI tokens."); setSelectedArticle(null); }
            else setSelectedArticle({ ...item, summary: ["Summary failed."] });
        }
    } catch { setSelectedArticle({ ...item, summary: ["Failed to retrieve summary."] }); }
    setIsSummarizing(false);
  };

  const triggerArticleAnalysis = (item: any) => {
      setAuthModal({ isOpen: true, title: "News Summary", cost: 1, actionName: "Summarize Article", onConfirm: () => handleArticleClick(item) });
  };

  const addToWatchlist = async () => {
      if (!data || !data.ticker) return;
      const isDuplicate = watchlist.some((item: any) => item.ticker === data.ticker);
      if (isDuplicate) { showToast(`${data.ticker} is already in your watchlist.`); return; }
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      try {
          const { data: newRow, error } = await supabase.from('watchlist').insert([{ user_id: session.user.id, ticker: data.ticker }]).select().single();
          if (error) {
              if (error.code === '23505') showToast(`${data.ticker} is already in watchlist.`);
              else throw error;
          } else {
              showToast(`${data.ticker} added to watchlist.`);
              setWatchlist((prevWatchlist: any) => [...prevWatchlist, newRow]);
          }
      } catch (error) { showToast(`Error saving ${data.ticker}.`); }
  };

  const fetchGlobalNews = async () => {
    try { const res = await apiFetch(`/market-briefing`); if (res.ok) setGlobalNews(await res.json()); } catch { console.warn("Briefing offline."); }
  };

  // --- DERIVED SCREENER STATE (Pulse Cards & Filtering) ---
  const filteredScreenerResults = screenerResults.filter(stock => {
      if (activeSector === "ALL") return true;
      if (!stock.sector) return false; // Hide stocks with unknown sectors from specific tabs

      // Handle the Yahoo Finance "Financial Services" naming mismatch
      let searchTerm = activeSector.toLowerCase();
      if (activeSector === "Financials") searchTerm = "financial";

      return stock.sector.toLowerCase().includes(searchTerm);
  });

  const topAlpha = screenerResults.length > 0 ? [...screenerResults].sort((a, b) => (b.score || 0) - (a.score || 0))[0] : null;
  const topGrowth = screenerResults.length > 1 ? [...screenerResults].sort((a, b) => (b.tech_score || 0) - (a.tech_score || 0))[0] : null;
  const topValue = screenerResults.length > 2 ? [...screenerResults].sort((a, b) => (b.fund_score || 0) - (a.fund_score || 0))[0] : null;

  if (!isAuthorized) {
      return (
          <main className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-border border-t-accent rounded-full animate-spin" />
                  <p className="text-[10px] text-accent font-black uppercase tracking-widest animate-pulse">Loading...</p>
              </div>
          </main>
      );
  }

  return (
    <main className="min-h-screen bg-bg-primary text-text-secondary flex flex-col font-sans relative overflow-x-hidden">

      {/* GLOBAL TOAST */}
      {toastMessage && (
        <div className="fixed inset-x-4 top-4 md:inset-0 md:top-0 z-[150] flex items-start md:items-center justify-center pointer-events-none">
           <Card className="px-6 py-4 md:px-10 md:py-6 rounded-2xl md:rounded-3xl shadow-lg animate-in slide-in-from-top-4 md:zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <p className="text-text-primary font-black uppercase tracking-widest text-[10px] md:text-sm text-center">{toastMessage}</p>
           </Card>
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
        <div className="fixed inset-0 z-[120] bg-bg-primary/90 flex flex-col items-center justify-center p-4">
           <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-border border-t-accent rounded-full animate-spin mb-6" />
           <p className="text-accent font-black tracking-widest uppercase text-[10px] md:text-xs animate-pulse text-center">
               {loading ? "Loading..." : "Running analysis..."}
           </p>
        </div>
      )}

      {/* AI DEEP DIVE DRAWER */}
      {deepDiveResult && !isAnalyzing && (
        <div className="fixed inset-0 z-[110] bg-black/60 flex justify-end animate-in fade-in duration-300">
            <div className="w-full md:w-[450px] lg:w-[500px] h-full bg-bg-primary border-l border-border shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
                <div className="p-6 md:p-8 border-b border-border flex justify-between items-center bg-bg-surface shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-2 h-2 bg-accent rounded-full" />
                        <p className="text-[10px] font-black uppercase tracking-[0.4em] text-accent">AI Deep Dive</p>
                    </div>
                    <button onClick={() => setDeepDiveResult(null)} aria-label="Close" className="text-text-secondary hover:text-text-primary transition-colors cursor-pointer">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>
                <div className="p-6 md:p-8 overflow-y-auto custom-scrollbar flex-1">
                    <div className="prose prose-sm max-w-none text-sm md:text-base font-medium leading-relaxed">
                        <style dangerouslySetInnerHTML={{__html: `
                            .prose h3 { color: var(--text-primary); font-size: 1.1em; margin-top: 1.5em; margin-bottom: 0.75em; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 900; }
                            .prose h4 { color: var(--text-secondary); font-size: 0.9em; margin-top: 1.5em; margin-bottom: 0.75em; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 800; }
                            .prose ul { padding-left: 0; list-style-type: none; margin-bottom: 1.5em; }
                            .prose li { position: relative; padding-left: 1.5rem; margin-bottom: 0.75rem; color: var(--text-secondary); display: block; }
                            .prose li::before { content: "→"; position: absolute; left: 0; color: var(--accent); font-weight: 900; }
                            .prose strong { color: var(--text-primary); }
                            .prose p { color: var(--text-secondary); margin-bottom: 1em; }
                            .prose hr { border-color: var(--border-color); margin: 2em 0; }
                        `}} />
                        <div dangerouslySetInnerHTML={{
                            __html: DOMPurify.sanitize(deepDiveResult
                                .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                .replace(/^---$/gim, '<hr/>')
                                .replace(/^\* (.*$)/gim, '<li>$1</li>')
                                .replace(/\n\n/g, '<br/><br/>')
                                .replace(/\*(LEGAL DISCLAIMER:.*?)\*/gim, '<em class="text-[9px] leading-tight text-text-secondary block mt-8 border-t border-border pt-4">$1</em>'))
                        }} />
                    </div>
                </div>
            </div>
        </div>
      )}

      {selectedArticle && (
        <div className="fixed inset-0 z-[100] bg-black/70 flex items-center justify-center p-3 md:p-4">
            <Card className="w-full max-w-3xl max-h-[95vh] md:max-h-[85vh] overflow-hidden flex flex-col">
              <div className="p-6 md:p-8 border-b border-border bg-bg-surface shrink-0 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-3 mb-2 md:mb-4">
                        <div className={`w-2 h-2 ${isSummarizing ? 'bg-warn' : 'bg-accent'} rounded-full`} />
                        <p className="text-[10px] font-black uppercase text-accent">AI Summary</p>
                    </div>
                    <h2 className="text-lg md:text-2xl font-bold text-text-primary line-clamp-2 md:line-clamp-none">{selectedArticle?.title}</h2>
                </div>
                <Button variant="secondary" size="sm" onClick={() => setSelectedArticle(null)} className="rounded-full h-fit self-end md:self-auto shrink-0">Close</Button>
              </div>
              <div className="p-6 md:p-8 bg-bg-primary overflow-y-auto flex-1 custom-scrollbar">
                 {isSummarizing ? (
                     <div className="space-y-4 animate-pulse">
                         <div className="h-4 bg-bg-surface-hover rounded w-full"></div>
                         <div className="h-4 bg-bg-surface-hover rounded w-5/6"></div>
                         <div className="h-4 bg-bg-surface-hover rounded w-4/6"></div>
                     </div>
                 ) : (
                     <div className="space-y-4 md:space-y-6">
                         {selectedArticle?.summary?.map((p: string, i: number) => <p key={i} className="text-text-secondary leading-relaxed text-sm md:text-base">{p}</p>)}
                     </div>
                 )}
              </div>
            </Card>
        </div>
      )}

      {/* MAIN LAYOUT */}
      <div className="p-3 md:p-6 flex flex-col flex-1">
        <TickerTape />

        {/* NAV HEADER */}
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 mb-8 md:mb-12">
          <div>
              <h1 className="text-3xl md:text-5xl font-black text-text-primary tracking-tighter cursor-pointer hover:text-accent transition-colors" onClick={() => router.push('/hub')}>
                  TRADEBOTICS<span className="text-accent">AI</span>
              </h1>
              <p className="text-xs text-text-secondary mt-1 md:mt-2">{userEmail.split('@')[0]}</p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 w-full xl:w-auto items-stretch sm:items-center">
            <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => { setData(null); setTicker(""); setConfirmedTicker(""); }} className="rounded-xl md:rounded-full flex-1 sm:flex-none">
                    Screener
                </Button>
                <Button variant="secondary" size="sm" onClick={() => router.push('/hub')} className="hidden sm:flex rounded-full">
                    ← Hub
                </Button>
                <Button variant="secondary" size="sm" onClick={() => router.push('/beginner')} className="rounded-full">
                    Simple Mode
                </Button>
                <ThemeToggle />
            </div>

            <div className="flex gap-2 w-full sm:w-auto bg-bg-surface p-2 md:p-3 rounded-xl md:rounded-[24px] border border-border focus-within:border-accent/50">
              <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runAnalysis()} className="bg-transparent border-none text-text-primary font-black w-full sm:w-32 md:w-48 px-3 outline-none text-base md:text-lg" placeholder="TICKER..." aria-label="Ticker symbol" />
              <Button onClick={() => runAnalysis()} size="md" className="rounded-lg md:rounded-xl shrink-0">Scan</Button>
            </div>
          </div>
        </div>

        {/* GRID LAYOUT */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 flex-1">

          {/* LEFT PANEL */}
          <div className="col-span-1 lg:col-span-3 space-y-6 lg:space-y-8 flex flex-col order-2 lg:order-1">

            {data && (
              <Card className="p-6 lg:p-8 relative group animate-in fade-in">
                <button onClick={addToWatchlist} className="absolute top-4 right-4 lg:top-6 lg:right-6 lg:opacity-0 group-hover:opacity-100 bg-accent hover:bg-accent-hover text-white text-[9px] font-black px-3 py-1.5 lg:px-4 lg:py-2 rounded-full transition-all cursor-pointer">ADD</button>
                <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest mb-2">Confidence Score</p>
                <div className="text-7xl lg:text-[100px] font-black text-text-primary leading-none tracking-tighter mb-4">{data.score}</div>
                <div className="grid grid-cols-2 gap-4 border-t border-border pt-4 lg:pt-6">
                  <StatTile label="Tech" value={`${data.tech_score}/100`} />
                  <StatTile label="Fund" value={`${data.fund_score}/100`} />
                </div>
              </Card>
            )}

            {data?.fundamentals && (
              <Card className="p-6 lg:p-10 animate-in fade-in">
                  <p className="text-[11px] font-black text-accent uppercase tracking-[0.3em] mb-6 lg:mb-8">Fundamentals</p>
                  <div className="space-y-4 lg:space-y-6">
                      <Stat label="P/E Ratio" val={data.fundamentals.pe_ratio} />
                      <Stat label="Debt/Equity" val={data.fundamentals.debt_equity} />
                      <Stat label="Profit Margin" val={data.fundamentals.margin} />
                      <Stat label="Insider Ownership" val={data.fundamentals.insider_ownership} />
                      <Stat label="Short Interest" val={data.fundamentals.short_interest} />
                      <Stat label="Sentiment" val={data.fundamentals.sentiment} color="text-accent" />
                      <Stat label="Cash Flow" val={data.fundamentals.cash_flow} />
                  </div>
              </Card>
            )}

            <Card className="p-6 lg:p-8">
              <div className="flex justify-between items-center mb-4 lg:mb-6 px-1">
                 <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest">Watchlist</p>
                 <button onClick={handleRefreshWatchlist} disabled={isRefreshingWatchlist || watchlist.length === 0} aria-label="Refresh watchlist scores" className="text-text-secondary hover:text-accent disabled:opacity-50 transition-colors p-2 cursor-pointer">
                    <svg className={`w-4 h-4 ${isRefreshingWatchlist ? 'animate-spin text-accent' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                 </button>
              </div>

              <div className="space-y-2 lg:space-y-3 max-h-[300px] lg:max-h-[350px] overflow-y-auto custom-scrollbar pr-1 lg:pr-2">
                {watchlist?.map((item, i) => (
                  <div key={i} className="flex gap-2 w-full group">
                    <button onClick={() => runAnalysis(item.ticker)} className="flex-1 flex justify-between items-center p-3 lg:p-4 rounded-xl lg:rounded-2xl bg-bg-primary border border-border hover:border-accent/50 transition-all cursor-pointer">
                      <span className="font-black text-text-primary text-base lg:text-lg">{item.ticker}</span>
                      <span className="text-[10px] font-bold text-text-secondary">{item.score} pts</span>
                    </button>
                    <button onClick={(e) => removeFromWatchlist(item.ticker, e)} aria-label={`Remove ${item.ticker} from watchlist`} className="px-3 lg:px-4 rounded-xl lg:rounded-2xl bg-bg-primary border border-border hover:bg-loss/10 hover:border-loss hover:text-loss text-text-secondary transition-all font-black text-xs cursor-pointer">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                ))}
                {watchlist.length === 0 && (
                    <p className="text-center text-[10px] font-bold text-text-secondary uppercase tracking-widest mt-6">Watchlist is empty.</p>
                )}
              </div>
            </Card>

          </div>

          {/* MIDDLE PANEL */}
          <div className="col-span-1 lg:col-span-6 flex flex-col gap-6 lg:gap-8 order-1 lg:order-2">
            {!data ? (
                // SCREENER
                <Card className="p-5 md:p-8 lg:p-10 flex flex-col h-auto min-h-[500px] lg:h-[800px]">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 lg:mb-8 border-b border-border pb-4 lg:pb-6">
                        <div>
                            <h3 className="text-xl lg:text-2xl font-black text-text-primary tracking-tight">Stock Screener</h3>
                            <p className="text-[10px] text-accent font-bold uppercase tracking-[0.2em] mt-1">Find your next trade</p>
                        </div>
                        <Button onClick={executeMarketScan} disabled={isScanning} className="w-full sm:w-auto rounded-xl lg:rounded-2xl">
                            {isScanning ? "Scanning..." : "Run Screener"}
                        </Button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 lg:gap-6 mb-6 lg:mb-8 bg-bg-primary p-4 lg:p-6 rounded-2xl lg:rounded-3xl border border-border shrink-0">
                        <div>
                            <p className="text-[9px] font-bold text-text-secondary uppercase tracking-widest mb-3">Time Horizon</p>
                            <div className="flex gap-2">
                                {["Day Trade", "Swing Trade", "Long Term"].map((h) => (
                                    <button
                                        key={h} onClick={() => setHorizon(h)}
                                        className={`flex-1 py-3 rounded-lg lg:rounded-xl font-bold text-[9px] uppercase tracking-wider transition-all border text-center cursor-pointer ${horizon === h ? 'bg-accent border-accent text-white' : 'bg-bg-surface border-border text-text-secondary hover:text-text-primary'}`}
                                    >
                                        {h.split(' ')[0]}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <p className="text-[9px] font-bold text-text-secondary uppercase tracking-widest mb-3">Risk Level</p>
                            <div className="flex gap-2">
                                {["Low", "Medium", "High"].map((r) => (
                                    <button
                                        key={r} onClick={() => setRisk(r)}
                                        className={`flex-1 py-3 rounded-lg lg:rounded-xl font-bold text-[9px] uppercase tracking-wider transition-all border text-center truncate px-1 cursor-pointer ${risk === r ? (r === 'High' ? 'bg-loss/10 border-loss text-loss' : r === 'Low' ? 'bg-gain/10 border-gain text-gain' : 'bg-accent/10 border-accent text-accent') : 'bg-bg-surface border-border text-text-secondary hover:text-text-primary'}`}
                                    >
                                        {r}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 bg-bg-primary border border-border rounded-2xl lg:rounded-3xl overflow-hidden flex flex-col relative min-h-[300px]">
                        {isScanning ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center bg-bg-primary/95 z-10 px-6 lg:px-10">
                                <div className="w-full max-w-sm">
                                    <div className="flex justify-between items-end mb-3">
                                        <p className="text-[10px] text-accent font-black uppercase tracking-widest animate-pulse truncate mr-2">
                                            {loadingText}
                                        </p>
                                        <p className="text-xl lg:text-2xl font-mono font-black text-text-primary">
                                            {scanProgress}%
                                        </p>
                                    </div>
                                    <div className="w-full h-1.5 lg:h-2 bg-bg-surface rounded-full overflow-hidden border border-border">
                                        <div
                                            className="h-full bg-accent transition-all duration-200 ease-out"
                                            style={{ width: `${scanProgress}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        ) : screenerResults.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-text-secondary p-6 text-center gap-3">
                                <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                                <p className="font-black uppercase tracking-[0.2em] text-[10px]">Run the screener to see results</p>
                            </div>
                        ) : (
                            <div className="flex flex-col h-full bg-bg-primary">
                                {/* PULSE CARDS */}
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-4 bg-bg-surface border-b border-border">
                                    {topAlpha && (
                                    <div onClick={() => { setTicker(topAlpha.ticker); runAnalysis(topAlpha.ticker); }} className="bg-bg-primary border border-accent/30 rounded-xl p-4 hover:border-accent transition-colors cursor-pointer shadow-sm group">
                                        <h4 className="text-[9px] font-bold text-text-secondary uppercase tracking-widest mb-2 group-hover:text-accent transition-colors">Top Pick</h4>
                                        <div className="flex justify-between items-end">
                                            <div>
                                                <h2 className="text-lg font-black text-text-primary leading-none">{topAlpha.ticker}</h2>
                                                <p className="text-[10px] font-mono font-bold text-text-secondary mt-1">${topAlpha.price?.toFixed(2)}</p>
                                            </div>
                                            <Badge tone="accent">{topAlpha.score}</Badge>
                                        </div>
                                    </div>
                                    )}

                                    {topGrowth && (
                                    <div onClick={() => { setTicker(topGrowth.ticker); runAnalysis(topGrowth.ticker); }} className="bg-bg-primary border border-border rounded-xl p-4 hover:border-accent/50 transition-colors cursor-pointer shadow-sm group">
                                        <h4 className="text-[9px] font-bold text-text-secondary uppercase tracking-widest mb-2 group-hover:text-text-primary transition-colors">Momentum</h4>
                                        <div className="flex justify-between items-end">
                                            <div>
                                                <h2 className="text-lg font-black text-text-primary leading-none">{topGrowth.ticker}</h2>
                                                <p className="text-[10px] font-mono font-bold text-text-secondary mt-1">${topGrowth.price?.toFixed(2)}</p>
                                            </div>
                                            <Badge tone="neutral">{topGrowth.score}</Badge>
                                        </div>
                                    </div>
                                    )}

                                    {topValue && (
                                    <div onClick={() => { setTicker(topValue.ticker); runAnalysis(topValue.ticker); }} className="bg-bg-primary border border-gain/30 rounded-xl p-4 hover:border-gain transition-colors cursor-pointer shadow-sm group hidden md:block">
                                        <h4 className="text-[9px] font-bold text-text-secondary uppercase tracking-widest mb-2 group-hover:text-gain transition-colors">Value Pick</h4>
                                        <div className="flex justify-between items-end">
                                            <div>
                                                <h2 className="text-lg font-black text-text-primary leading-none">{topValue.ticker}</h2>
                                                <p className="text-[10px] font-mono font-bold text-text-secondary mt-1">${topValue.price?.toFixed(2)}</p>
                                            </div>
                                            <Badge tone="gain">{topValue.score}</Badge>
                                        </div>
                                    </div>
                                    )}
                                </div>

                                {/* SECTOR FILTERS */}
                                <div className="flex space-x-2 px-4 py-3 border-b border-border overflow-x-auto custom-scrollbar bg-bg-surface shrink-0">
                                    {["ALL", "Technology", "Financials", "Healthcare", "Consumer", "Energy"].map(sector => (
                                        <button
                                            key={sector}
                                            onClick={() => setActiveSector(sector)}
                                            className={`px-3 py-1.5 rounded-full text-[9px] font-bold uppercase tracking-widest whitespace-nowrap transition-all cursor-pointer ${activeSector === sector ? 'bg-accent text-white' : 'bg-bg-surface border border-border text-text-secondary hover:text-text-primary hover:bg-bg-surface-hover'}`}
                                        >
                                            {sector}
                                        </button>
                                    ))}
                                </div>

                                <div className="grid grid-cols-12 gap-2 lg:gap-4 px-4 lg:px-6 py-3 border-b border-border text-[9px] font-black uppercase tracking-widest text-text-secondary shrink-0">
                                    <div className="col-span-5 lg:col-span-5">Asset</div>
                                    <div className="col-span-4 lg:col-span-3 text-right">Price</div>
                                    <div className="hidden lg:block lg:col-span-2 text-right">{horizon === "Long Term" ? "Fund Score" : "Tech Score"}</div>
                                    <div className="col-span-3 lg:col-span-2 text-right text-accent">Total</div>
                                </div>
                                <div className="overflow-y-auto custom-scrollbar flex-1 pb-4">
                                    {filteredScreenerResults.map((stock, idx) => {
                                        const isOverdrive = stock.score >= 90;
                                        return (
                                            <div
                                                key={stock.ticker}
                                                onClick={() => { setTicker(stock.ticker); runAnalysis(stock.ticker); }}
                                                className={`grid grid-cols-12 gap-2 lg:gap-4 px-4 lg:px-6 py-3 lg:py-4 items-center border-b border-border cursor-pointer group transition-all duration-200 ${isOverdrive ? 'bg-accent/10 hover:bg-accent/20 border-l-4 border-l-accent' : 'hover:bg-bg-surface-hover'}`}
                                            >
                                                <div className="col-span-5 lg:col-span-5 flex items-center gap-2 lg:gap-3">
                                                    <span className="hidden sm:inline-block text-[10px] text-text-secondary font-mono w-4">{idx + 1}</span>
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-black text-text-primary text-xs lg:text-sm">{stock.ticker}</span>
                                                            {isOverdrive && <span className="bg-accent/10 text-accent text-[8px] font-black tracking-widest uppercase px-1.5 py-0.5 rounded border border-accent/20 hidden md:block">High Conviction</span>}
                                                        </div>
                                                        <span className="text-[8px] font-bold text-text-secondary uppercase tracking-widest hidden lg:block mt-0.5">{stock.sector || "Equities"}</span>
                                                    </div>
                                                </div>
                                                <div className="col-span-4 lg:col-span-3 text-right">
                                                    <p className="text-xs lg:text-sm font-mono font-bold text-text-primary">${stock.price?.toFixed(2)}</p>
                                                </div>
                                                <div className="hidden lg:block lg:col-span-2 text-right">
                                                    <p className="text-[10px] font-mono font-bold text-text-secondary">
                                                        {horizon === "Long Term" ? stock.fund_score || '--' : stock.tech_score || '--'}
                                                    </p>
                                                </div>
                                                <div className="col-span-3 lg:col-span-2 flex justify-end">
                                                    <div className={`px-2 lg:px-3 py-1 rounded-md text-center border transition-all ${isOverdrive ? 'bg-accent border-accent text-white' : 'bg-accent/10 border-accent/30'}`}>
                                                        <span className={`text-xs lg:text-sm font-black font-mono ${isOverdrive ? 'text-white' : 'text-accent'}`}>{stock.score}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                    {filteredScreenerResults.length === 0 && (
                                        <div className="p-8 text-center text-text-secondary text-[10px] font-bold uppercase tracking-widest">No assets found in this sector.</div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </Card>
            ) : (
              <>
                <TradingViewWidget symbol={confirmedTicker} />
                <div className="grid grid-cols-1 gap-4">
                  {data.ledger?.map((item: any, i: number) => (
                    <Card key={i} className="p-6 lg:p-8">
                      <div className="flex justify-between items-start sm:items-center mb-3 sm:mb-4 gap-4">
                          <div>
                              <p className="text-text-primary font-black text-lg lg:text-xl">{item.factor}</p>
                              <p className="text-[11px] text-accent font-bold uppercase mt-1">{item.status}</p>
                          </div>
                          <span className="text-text-primary font-black text-lg lg:text-xl shrink-0">{item.val}</span>
                      </div>
                      <p className="text-text-secondary text-xs lg:text-sm italic border-l-2 border-border pl-3 lg:pl-4 leading-relaxed font-medium">"{item.reasoning}"</p>
                    </Card>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* RIGHT PANEL */}
          <div className="col-span-1 lg:col-span-3 space-y-6 lg:space-y-8 order-3">

            <Card className="p-6 lg:p-10">
               <div className="flex items-center gap-3 mb-6 lg:mb-8 text-accent">
                 <div className="w-2 h-2 bg-accent rounded-full" />
                 <p className="text-[10px] font-black uppercase tracking-[0.3em]">AI Analysis</p>
               </div>
               {data ? (
                 <>
                    <button
                        onClick={() => setShowTradeTicket(true)}
                        className="w-full mb-6 lg:mb-8 bg-gain py-4 rounded-xl lg:rounded-2xl text-white font-black text-base lg:text-lg uppercase tracking-widest hover:opacity-90 transition-opacity cursor-pointer"
                    >
                        Trade {data.ticker}
                    </button>

                    <div className="mb-6 lg:mb-8">
                       <p className="text-[10px] font-black text-text-secondary uppercase mb-2">Current Price</p>
                       <p className="text-5xl lg:text-6xl font-mono font-black text-text-primary tracking-tighter mb-3">${data.price}</p>
                       <p className="text-[10px] font-black text-accent uppercase tracking-widest bg-accent/10 px-3 py-1.5 lg:py-2 rounded-lg inline-block">{data.company_name}</p>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mt-4 mb-6 border-b border-border pb-5">
                        <span className="bg-bg-primary border border-border px-2 py-1 rounded text-[9px] font-bold text-text-secondary uppercase">
                            Tech: {data.tech_score}
                        </span>
                        <span className="bg-bg-primary border border-border px-2 py-1 rounded text-[9px] font-bold text-text-secondary uppercase">
                            Fund: {data.fund_score}
                        </span>
                        {data.ledger?.filter((item: any) => ["Consolidation Phase", "Short Squeeze Risk", "Options Flow", "Insider Conviction"].includes(item.factor) && item.status !== "BEARISH").map((booster: any, i: number) => (
                            <span key={i} className="bg-accent/10 border border-accent/30 text-accent px-2 py-1 rounded text-[9px] font-black tracking-wide uppercase">
                                {booster.factor}: {booster.val}
                            </span>
                        ))}
                    </div>

                    <div className="grid grid-cols-2 gap-4 lg:gap-8 border-t border-border pt-6 lg:pt-8 mb-6 lg:mb-8">
                       <StatTile label="24H Volume" value={data.volume} />
                       <StatTile label="Rel Surge" value={data.vol_surge} accentClassName="text-accent" />
                    </div>

                    <div className="flex flex-col gap-3 lg:gap-4 mb-6">
                        <button
                            onClick={() => setAuthModal({ isOpen: true, title: "Deep Dive Analysis", cost: 3, actionName: "Confirm & Run", onConfirm: runMasterAnalysis })}
                            disabled={isAnalyzing || !data}
                            className="w-full bg-accent/10 border border-accent/30 hover:bg-accent/20 py-4 lg:py-5 px-4 lg:px-6 rounded-xl lg:rounded-2xl transition-all disabled:opacity-50 flex items-center justify-between cursor-pointer"
                        >
                            <div className="flex items-center gap-3 lg:gap-4">
                                {isAnalyzing ? <div className="w-2.5 h-2.5 lg:w-3 lg:h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" /> : <div className="w-2 h-2 lg:w-2.5 lg:h-2.5 bg-accent rounded-full" />}
                                <span className="text-accent font-black text-[10px] sm:text-xs lg:text-sm uppercase tracking-widest text-left leading-tight">
                                    {isAnalyzing ? "Analyzing..." : "AI Deep Dive"}
                                </span>
                            </div>
                            <Badge tone="accent">-3</Badge>
                        </button>

                        <button
                            onClick={() => setAuthModal({ isOpen: true, title: "Exit Strategy", cost: 2, actionName: "Confirm & Run", onConfirm: runExitStrategy })}
                            disabled={isGeneratingExit || !data}
                            className="w-full bg-loss/10 border border-loss/30 hover:bg-loss/20 py-4 lg:py-5 px-4 lg:px-6 rounded-xl lg:rounded-2xl transition-all disabled:opacity-50 flex items-center justify-between cursor-pointer"
                        >
                            <div className="flex items-center gap-3 lg:gap-4">
                                {isGeneratingExit ? <div className="w-2.5 h-2.5 lg:w-3 lg:h-3 border-2 border-loss border-t-transparent rounded-full animate-spin" /> : <div className="w-2 h-2 lg:w-2.5 lg:h-2.5 bg-loss rounded-full" />}
                                <span className="text-loss font-black text-[10px] sm:text-xs lg:text-sm uppercase tracking-widest text-left leading-tight">
                                    {isGeneratingExit ? "Calculating..." : "Exit Strategy"}
                                </span>
                            </div>
                            <Badge tone="loss">-2</Badge>
                        </button>
                    </div>

                    <div className="mb-4 lg:mb-6 p-4 lg:p-5 bg-accent/5 border-l-2 border-accent rounded-r-xl lg:rounded-r-2xl min-h-[50px]">
                        <p className="text-text-primary text-xs lg:text-sm font-bold italic leading-relaxed">
                            "{data.ai_tactical || "Analysis in progress. Check back shortly."}"
                        </p>
                    </div>

                    {exitStrategyResult && (
                        <div className="mb-8 lg:mb-10 bg-bg-primary border border-loss/30 rounded-2xl lg:rounded-3xl p-5 lg:p-6 relative overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <button onClick={() => setExitStrategyResult(null)} aria-label="Close exit strategy" className="absolute top-3 right-3 lg:top-4 lg:right-4 text-text-secondary hover:text-text-primary transition-colors p-2 cursor-pointer">
                                <svg className="w-4 h-4 lg:w-5 lg:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                            </button>
                            <div className="flex items-center gap-2 mb-4">
                                <div className="w-1.5 h-1.5 lg:w-2 lg:h-2 bg-loss rounded-full" />
                                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-loss pr-6">Exit Strategy</p>
                            </div>
                            <div className="prose prose-sm max-w-none text-xs lg:text-sm font-medium leading-relaxed">
                                <style dangerouslySetInnerHTML={{__html: `
                                    .prose h3 { display: none; }
                                    .prose ul { list-style-type: none; padding: 0; margin: 0; }
                                    .prose li { position: relative; padding-left: 1.25rem; margin-bottom: 0.75rem; color: var(--text-secondary); background: var(--bg-surface); padding: 0.75rem; padding-left: 1.75rem; border-radius: 0.5rem; line-height: 1.5; }
                                    @media (min-width: 1024px) { .prose li { padding-left: 2rem; } }
                                    .prose li::before { content: "→"; position: absolute; left: 0.5rem; top: 0.75rem; color: var(--loss); font-weight: 900; }
                                    .prose strong { color: var(--text-primary); font-size: 1.05em; display: block; margin-bottom: 0.25rem; }
                                `}} />
                                <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(exitStrategyResult) }} />
                            </div>
                        </div>
                    )}
                 </>
               ) : ( <p className="text-text-secondary font-bold uppercase text-[10px] tracking-widest italic text-center">Scan a ticker to begin.</p> )}
            </Card>

            <Card className="p-6 lg:p-8 flex flex-col h-auto min-h-[400px] lg:h-[600px] overflow-hidden shrink-0">
               <p className="text-[11px] font-black text-text-secondary uppercase tracking-widest mb-4 lg:mb-6 text-center">Market News</p>

               <div className="space-y-3 lg:space-y-4 overflow-y-auto custom-scrollbar flex-1 pr-1 lg:pr-2">
                  {((data && data.news && data.news.length > 0) ? data.news : globalNews).map((item: any, i: number) => (
                      <div key={i} onClick={() => triggerArticleAnalysis(item)} className="bg-bg-primary border border-border p-4 lg:p-5 rounded-2xl lg:rounded-3xl cursor-pointer hover:border-accent/50 group transition-all">
                          <p className="text-xs lg:text-sm font-bold text-text-primary group-hover:text-accent leading-snug line-clamp-3">
                            {item.title}
                          </p>
                          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mt-3 lg:mt-4 pt-3 lg:pt-4 border-t border-border gap-2 sm:gap-0">
                              <p className="text-[9px] font-black text-text-secondary group-hover:text-text-primary uppercase tracking-wider">
                                  {item.publisher} {item.date ? `· ${item.date}` : ""}
                              </p>
                              <span className="text-[8px] bg-accent/10 text-accent px-2 py-1 rounded-full uppercase font-black tracking-wider">
                                  Summarize
                              </span>
                          </div>
                      </div>
                  ))}
               </div>
            </Card>

          </div>
        </div>

        <footer className="border-t border-border pt-6 lg:pt-8 mt-8 lg:mt-12 text-center w-full">
            <p className="text-[10px] uppercase tracking-widest font-black text-text-secondary">© 2026 TradeBotics AI</p>
        </footer>
      </div>

      {/* AUTHORIZATION MODAL */}
      {authModal.isOpen && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40">
              <Card className="w-full max-w-sm overflow-hidden">
                  <div className="p-3 md:p-4 border-b border-border bg-bg-surface-hover flex items-center gap-2 md:gap-3">
                      <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-accent rounded-full"></div>
                      <h2 className="text-[10px] md:text-xs font-bold text-text-primary uppercase tracking-[0.2em]">Confirm Token Usage</h2>
                  </div>
                  <div className="p-5 md:p-6 text-center space-y-4">
                      <p className="text-xs md:text-sm text-text-secondary leading-relaxed">
                          Running <span className="text-text-primary font-bold">{authModal.title}</span> will use AI tokens from your balance.
                      </p>
                      <div className="py-3 md:py-4 bg-bg-primary rounded-xl border border-border flex flex-col items-center justify-center">
                          <p className="text-[10px] text-text-secondary uppercase tracking-widest mb-1">Token Cost</p>
                          <p className="text-2xl md:text-3xl font-mono text-accent font-bold">-{authModal.cost} tokens</p>
                      </div>
                  </div>
                  <div className="flex border-t border-border">
                      <button onClick={() => setAuthModal({ ...authModal, isOpen: false })} className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-text-secondary hover:text-text-primary uppercase tracking-widest hover:bg-bg-surface-hover transition-colors cursor-pointer">
                          Cancel
                      </button>
                      <button onClick={() => { setAuthModal({ ...authModal, isOpen: false }); authModal.onConfirm(); }} className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-accent uppercase tracking-widest hover:bg-accent/10 transition-colors border-l border-border cursor-pointer">
                          {authModal.actionName}
                      </button>
                  </div>
              </Card>
          </div>
      )}

    </main>
  );
 }

export default function TerminalPage() {
  return (
    <React.Suspense fallback={
      <div className="min-h-screen bg-bg-primary flex flex-col items-center justify-center p-4">
        <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-border border-t-accent rounded-full animate-spin mb-4 md:mb-6" />
        <p className="text-[10px] text-accent font-black uppercase tracking-widest animate-pulse text-center">
          Loading...
        </p>
      </div>
    }>
      <TerminalContent />
    </React.Suspense>
  );
}
