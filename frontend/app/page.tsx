"use client";
import React, { useState, useEffect, useRef } from "react";
import { supabase } from "./lib/supabase";
import Link from "next/link";

// 🚨 PRODUCTION URL
const BACKEND_URL = "https://tradebotics-api.onrender.com";

// --- HIGH-FIDELITY UI COMPONENTS ---

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
      script.innerHTML = JSON.stringify({ "autosize": true, "symbol": `NASDAQ:${symbol}`, "interval": "D", "theme": "dark", "style": "1", "locale": "en", "container_id": "tv_chart" });
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

// --- MARKETING LANDING PAGE ---
function MarketingLanding({ onLoginClick, onRegisterClick }: { onLoginClick: () => void, onRegisterClick: () => void }) {
    const [demoTicker, setDemoTicker] = useState("");
    const [demoResult, setDemoResult] = useState<any>(null);
    const [demoLoading, setDemoLoading] = useState(false);

    const runDemoScan = async () => {
        if(!demoTicker) return;
        setDemoLoading(true);
        setDemoResult(null);
        
        try {
            const res = await fetch(`${BACKEND_URL}/analyze/${demoTicker.toUpperCase()}`);
            const data = await res.json();
            
            if (res.ok) {
                const trend = data.tech_score > 75 ? "bullish accumulation" : "consolidation";
                const verdict = `${data.company_name} is currently trading at $${data.price}. Initial scans indicate ${trend} with an aggregate Quant Score of ${data.score}. Technical momentum scores ${data.tech_score}/100 while institutional fundamental DNA scores ${data.fund_score}/100.`;
                
                setDemoResult({
                    ticker: data.ticker,
                    price: data.price,
                    score: data.score,
                    verdict: verdict
                });
            } else {
                setDemoResult({
                    ticker: demoTicker.toUpperCase(),
                    score: "N/A",
                    verdict: "Asset scan failed. Please verify the ticker symbol is a standard US equity."
                });
            }
        } catch (error) {
            setDemoResult({
                ticker: demoTicker.toUpperCase(),
                score: "ERR",
                verdict: "Terminal connection offline. Please try again."
            });
        }
        setDemoLoading(false);
    };

    const testimonials = [
        { name: "Marcus T.", title: "Quant Trader", img: "https://randomuser.me/api/portraits/men/32.jpg", quote: "The Tactical Exit Strategy alone saved my portfolio during the last tech correction. It accurately predicted the NVDA pullback three days before the broader market reacted." },
        { name: "Sarah J.", title: "Retail Investor", img: "https://randomuser.me/api/portraits/women/44.jpg", quote: "Having fundamental DNA and real-time global sentiment synthesized into a single terminal is a game changer. I don't execute a trade without running it through TradeBotics first." },
        { name: "David L.", title: "Swing Trader", img: "https://randomuser.me/api/portraits/men/68.jpg", quote: "The Portfolio Intelligence mapping helped me optimize my cost-basis across three different brokers. It acts like a silent, hyper-intelligent hedge fund manager." },
        { name: "Elena R.", title: "Risk Analyst", img: "https://randomuser.me/api/portraits/women/63.jpg", quote: "As a risk manager, the neural synthesis provides the exact probability matrices I need. The AI doesn't hallucinate; it strictly analyzes the math and historical tape." },
        { name: "James K.", title: "Proprietary Trader", img: "https://randomuser.me/api/portraits/men/85.jpg", quote: "I migrated from Bloomberg to TradeBotics because of the AI integrations. It filters the noise and gives me definitive strike zones instantly without the bloat." },
        { name: "Aisha M.", title: "Family Office Director", img: "https://randomuser.me/api/portraits/women/12.jpg", quote: "The automated portfolio sync completely eliminated my need for manual tracking. I see my exact P&L dynamically adjusted against AI price targets every morning." }
    ];

    return (
        <div className="min-h-screen bg-[#020617] text-slate-300 font-sans overflow-x-hidden selection:bg-blue-500/30">
            <style dangerouslySetInnerHTML={{__html: `
                @keyframes scroll {
                    0% { transform: translateX(0); }
                    100% { transform: translateX(calc(-50% - 1rem)); }
                }
                .animate-scroll {
                    animation: scroll 40s linear infinite;
                }
                .animate-scroll:hover {
                    animation-play-state: paused;
                }
            `}} />

            <nav className="w-full border-b border-slate-800/50 bg-[#020617]/80 backdrop-blur-md fixed top-0 z-50">
                <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
                    <h1 className="text-2xl font-black text-white tracking-tighter">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
                    <div className="flex items-center gap-6">
                        <button onClick={onLoginClick} className="text-xs font-black uppercase tracking-widest text-slate-400 hover:text-white transition-colors hidden md:block">Operative Login</button>
                        <button onClick={onRegisterClick} className="bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black px-6 py-3 rounded-full uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(59,130,246,0.2)]">Request Clearance</button>
                    </div>
                </div>
            </nav>

            <section className="pt-40 pb-20 px-6 max-w-7xl mx-auto flex flex-col lg:flex-row items-center gap-16">
                <div className="flex-1 space-y-8 text-center lg:text-left z-10">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-black uppercase tracking-widest mb-4">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" /> Live: Enterprise Node Online
                    </div>
                    <h2 className="text-5xl lg:text-7xl font-black text-white leading-[1.1] tracking-tighter">
                        Institutional-Grade <span className="text-blue-500">AI Analytics.</span><br/>Retail Edge.
                    </h2>
                    <p className="text-lg text-slate-400 leading-relaxed max-w-xl mx-auto lg:mx-0">
                        TradeBotics AI synthesizes global news, technical indicators, and fundamental DNA in seconds to calculate definitive strike zones and tactical exit strategies.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start">
                        <button onClick={onRegisterClick} className="w-full sm:w-auto bg-white text-[#020617] px-8 py-4 rounded-full font-black text-xs uppercase tracking-[0.2em] hover:bg-slate-200 transition-colors">Start Free Trial</button>
                        <button onClick={onLoginClick} className="w-full sm:w-auto bg-slate-900 border border-slate-700 text-white px-8 py-4 rounded-full font-black text-xs uppercase tracking-[0.2em] hover:border-blue-500 transition-colors">Sign In</button>
                    </div>
                </div>

                <div className="flex-1 w-full max-w-md relative">
                    <div className="absolute inset-0 bg-blue-600/20 blur-[100px] rounded-full pointer-events-none" />
                    <div className="bg-slate-900/60 border border-slate-800 p-8 rounded-[40px] shadow-2xl backdrop-blur-xl relative z-10">
                        <p className="text-[10px] font-black text-blue-500 uppercase tracking-[0.3em] mb-6 text-center">Free Public Pulse Scan</p>
                        
                        <div className="flex gap-2 mb-6">
                            <input value={demoTicker} onChange={(e) => setDemoTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runDemoScan()} placeholder="ENTER TICKER..." className="flex-1 bg-slate-950 border border-slate-800 rounded-2xl px-4 py-3 text-white font-black outline-none focus:border-blue-500 text-lg transition-colors" />
                            <button onClick={runDemoScan} className="bg-blue-600 hover:bg-blue-500 text-white px-6 rounded-2xl font-black text-[10px] uppercase tracking-widest transition-colors">
                                {demoLoading ? "..." : "SCAN"}
                            </button>
                        </div>

                        {demoLoading && (
                            <div className="py-10 flex flex-col items-center">
                                <div className="w-8 h-8 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-4" />
                                <p className="text-[10px] text-blue-500 uppercase font-black tracking-widest animate-pulse">Running Neural Synthesis...</p>
                            </div>
                        )}

                        {demoResult && !demoLoading && (
                            <div className="bg-[#020617] border border-blue-500/30 rounded-3xl p-6 animate-in zoom-in-95 fade-in text-center">
                                <p className="text-3xl font-black text-white mb-1">{demoResult.ticker}</p>
                                {demoResult.price && <p className="text-xs font-bold text-slate-400 mb-4 bg-slate-900/50 inline-block px-3 py-1 rounded-lg border border-slate-800">LIVE PRICE: ${demoResult.price}</p>}
                                <div className="flex items-center justify-center gap-2 mb-4">
                                    <span className="text-blue-500 font-black text-2xl">{demoResult.score}</span>
                                    <span className="text-[10px] text-slate-500 font-bold uppercase">Quant Score</span>
                                </div>
                                <p className="text-sm text-slate-300 italic border-l-2 border-blue-500 pl-3 text-left leading-relaxed mb-6">
                                    "{demoResult.verdict}"
                                </p>
                                <button onClick={onRegisterClick} className="w-full bg-blue-600/10 hover:bg-blue-600 border border-blue-500/50 hover:border-transparent text-blue-400 hover:text-white py-3 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all">
                                    Unlock Full AI Deep Dive
                                </button>
                            </div>
                        )}
                        {!demoResult && !demoLoading && (
                            <p className="text-center text-slate-500 text-xs italic font-medium px-4">Input any US equity ticker to experience a fractional execution of our proprietary AI scoring model.</p>
                        )}
                    </div>
                </div>
            </section>

            <section className="border-t border-slate-800/50 bg-[#060b1f] py-24 overflow-hidden">
                <div className="flex flex-col items-center justify-center mb-16 px-6 text-center">
                    <div className="flex gap-1 text-blue-500 text-2xl mb-4 drop-shadow-[0_0_10px_rgba(59,130,246,0.8)]">
                        ★★★★★
                    </div>
                    <h3 className="text-3xl font-black text-white tracking-tighter uppercase mb-2">Operative Testimonials</h3>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Trusted by over 4,500+ Institutional & Retail Operatives</p>
                </div>
                
                <div className="flex overflow-hidden w-full relative group">
                    <div className="absolute top-0 left-0 w-32 h-full bg-gradient-to-r from-[#060b1f] to-transparent z-10 pointer-events-none" />
                    <div className="absolute top-0 right-0 w-32 h-full bg-gradient-to-l from-[#060b1f] to-transparent z-10 pointer-events-none" />
                    
                    <div className="flex gap-8 min-w-max animate-scroll">
                        {[...testimonials, ...testimonials].map((t, i) => (
                            <div key={i} className="bg-slate-900/40 border border-slate-800 p-8 rounded-[32px] text-left flex flex-col w-[400px] shrink-0 whitespace-normal hover:border-blue-500/50 transition-colors shadow-xl">
                                <div className="flex items-center gap-1 text-blue-500 mb-4 text-lg">★★★★★</div>
                                <p className="text-slate-300 text-sm leading-relaxed mb-6 flex-1">"{t.quote}"</p>
                                <div className="flex items-center gap-4 border-t border-slate-800/50 pt-6">
                                    <img src={t.img} alt={t.name} className="w-10 h-10 rounded-full border border-slate-700" />
                                    <div>
                                        <p className="text-[10px] font-black uppercase text-white tracking-widest">{t.name}</p>
                                        <p className="text-[9px] font-bold uppercase text-slate-500 tracking-widest">{t.title}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            <section className="py-24 max-w-7xl mx-auto px-6">
                 <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                    <div>
                        <div className="w-12 h-12 bg-blue-500/10 rounded-2xl flex items-center justify-center mb-6 border border-blue-500/20"><span className="text-blue-500 text-xl">🧠</span></div>
                        <h4 className="text-xl font-black text-white mb-4">Neural Market Synthesis</h4>
                        <p className="text-slate-400 text-sm leading-relaxed">We aggregate millions of data points from global news wires, SEC filings, and technical indicators to provide a definitive 1-100 Quant Score for any asset.</p>
                    </div>
                    <div>
                        <div className="w-12 h-12 bg-orange-500/10 rounded-2xl flex items-center justify-center mb-6 border border-orange-500/20"><span className="text-orange-500 text-xl">🎯</span></div>
                        <h4 className="text-xl font-black text-white mb-4">Tactical Strike Zones</h4>
                        <p className="text-slate-400 text-sm leading-relaxed">Remove emotion from your entries and exits. The AI calculates precise trailing targets and stop-loss floors based on real-time volatility profiles.</p>
                    </div>
                    <div>
                        <div className="w-12 h-12 bg-purple-500/10 rounded-2xl flex items-center justify-center mb-6 border border-purple-500/20"><span className="text-purple-500 text-xl">💼</span></div>
                        <h4 className="text-xl font-black text-white mb-4">Portfolio Intelligence</h4>
                        <p className="text-slate-400 text-sm leading-relaxed">Securely sync your current holdings to the terminal. Our AI acts as a dedicated risk manager, analyzing your specific exposure and cost-basis.</p>
                    </div>
                 </div>
            </section>
            
            <footer className="border-t border-slate-800/50 py-10 text-center">
                <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
            </footer>
        </div>
    );
}

// --- MAIN TERMINAL APPLICATION ---

export default function Home() {
  const [user, setUser] = useState<any>(null);
  const [userProfile, setUserProfile] = useState<any>(null); 
  
  const [showAuth, setShowAuth] = useState(false);
  const [currentView, setCurrentView] = useState<'landing' | 'terminal'>('landing'); 
  
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState(""); 
  const [isSignUp, setIsSignUp] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false); 
  const [data, setData] = useState<any>(null);
  const [globalNews, setGlobalNews] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(false); 
  const [isAnalyzing, setIsAnalyzing] = useState(false); 
  const [toastMessage, setToastMessage] = useState<string | null>(null); 
  
  const [ticker, setTicker] = useState("");
  const [confirmedTicker, setConfirmedTicker] = useState("");
  
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [portfolioVault, setPortfolioVault] = useState<any[]>([]);
  const [isRefreshingWatchlist, setIsRefreshingWatchlist] = useState(false); 
  
  const [currentPosition, setCurrentPosition] = useState<any | null>(null);

  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [deepDiveResult, setDeepDiveResult] = useState<string | null>(null);

  useEffect(() => {
    const checkUser = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        const { data: profile } = await supabase.from('profiles').select('*').eq('id', user.id).single();
        setUserProfile(profile);
      }
      setUser(user);
      if (localStorage.getItem('termsAccepted') === 'true') { setHasAcceptedTerms(true); }
    };
    checkUser();
  }, []);

  useEffect(() => {
    if (user && userProfile?.status !== 'pending' && hasAcceptedTerms) {
      fetchWatchlist(user.id);
      fetchPortfolioVault(user.id);
      fetchGlobalNews();
    }
  }, [user, userProfile, hasAcceptedTerms]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500); 
  };

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
      if (password !== confirmPassword) {
          showToast("Passwords do not match.");
          setAuthLoading(false);
          return;
      }
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) showToast(error.message); 
      else showToast("Registration received. Please check your email to verify your account.");
    } else {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
          if (error.message.includes("Email not confirmed")) {
              showToast("Access Denied: Email not verified. Please check your inbox.");
          } else { showToast(error.message); }
      } else {
          const { data: profile } = await supabase.from('profiles').select('*').eq('id', data.user.id).single();
          setUserProfile(profile);
          setUser(data.user);
      }
    }
    setAuthLoading(false);
  };

  const handleSignOut = async () => { 
    await supabase.auth.signOut(); 
    setUser(null); 
    setUserProfile(null);
    setShowAuth(false); 
    setCurrentView('landing');
    setHasAcceptedTerms(false); 
    localStorage.removeItem('termsAccepted');
  };

  // --- LEDGER FETCHING LOGIC ---

  const fetchWatchlist = async (userId: string) => { 
    const { data } = await supabase.from('watchlist').select('*').eq('user_id', userId).order('created_at', { ascending: false }); 
    if (data) setWatchlist(data); 
  };

  const fetchPortfolioVault = async (userId: string) => { 
    const { data } = await supabase.from('portfolio').select('*').eq('user_id', userId); 
    if (data) {
        const aggregated = data.reduce((acc: any, curr: any) => {
            if (!acc[curr.ticker]) {
                acc[curr.ticker] = { ticker: curr.ticker, total_shares: 0, total_cost_dollars: 0 };
            }
            const shares = parseFloat(curr.shares);
            const cost = parseFloat(curr.cost_basis);
            acc[curr.ticker].total_shares += shares;
            acc[curr.ticker].total_cost_dollars += (shares * cost);
            return acc;
        }, {});

        const formattedVault = Object.values(aggregated).map((pos: any) => ({
            ticker: pos.ticker,
            shares: pos.total_shares,
            avg_cost: pos.total_shares > 0 ? (pos.total_cost_dollars / pos.total_shares).toFixed(2) : 0
        })).sort((a:any, b:any) => a.ticker.localeCompare(b.ticker));
        
        setPortfolioVault(formattedVault); 
    }
  };

  const runAnalysis = async (t?: string) => {
    const target = t || ticker;
    if (!target) return;
    setLoading(true);

    const position = portfolioVault.find(p => p.ticker === target);
    setCurrentPosition(position || null);

    try {
      const res = await fetch(`${BACKEND_URL}/analyze/${target}`);
      const result = await res.json();
      if (res.ok) { setData(result); setConfirmedTicker(target); }
      else { showToast(`Terminal Error: ${result.detail || "Scan Failed."}`); }
    } catch { showToast("Backend Offline. Check Connection."); }
    setLoading(false);
  };

  // --- WATCHLIST ACTIONS ---
  
  const addToWatchlist = async () => {
    if (!user || !data) return;
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
    if (!user) return;
    
    const { data: deletedRow, error } = await supabase
      .from('watchlist')
      .delete()
      .eq('user_id', user.id)
      .eq('ticker', removeTicker)
      .select();
      
    if (error) {
        showToast("Delete Error: " + error.message);
    } else if (!deletedRow || deletedRow.length === 0) {
        showToast("ERROR: Check Supabase DELETE Permissions.");
    } else {
        showToast(`${removeTicker} REMOVED FROM WATCHLIST`);
        fetchWatchlist(user.id);
    }
  };

  const handleRefreshWatchlist = async () => {
    if (!user || watchlist.length === 0) return;
    setIsRefreshingWatchlist(true);
    showToast("Refreshing Quant Scores...");
    
    try {
        const updatePromises = watchlist.map(async (item) => {
            const res = await fetch(`${BACKEND_URL}/analyze/${item.ticker}`);
            if (res.ok) {
                const fetchedData = await res.json();
                await supabase
                    .from('watchlist')
                    .update({ score: fetchedData.score })
                    .eq('user_id', user.id)
                    .eq('ticker', item.ticker);
            }
        });
        
        await Promise.all(updatePromises);
        await fetchWatchlist(user.id);
        showToast("Watchlist Scores Updated.");
    } catch (error) {
        showToast("Failed to refresh some scores.");
    }
    setIsRefreshingWatchlist(false);
  };

  const runDeepDive = async (mode: string) => {
    if (!data) return;
    setDeepDiveResult(null);
    setIsAnalyzing(true); 
    try {
        const res = await fetch(`${BACKEND_URL}/translate`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                ticker: confirmedTicker, mode, 
                data_context: { 
                    score: data.score, 
                    price: data.price, 
                    stance: data.holding_analysis?.status,
                    fundamentals: data.fundamentals, 
                    rsi: data.ledger?.find((l:any) => l.factor.toLowerCase().includes("momentum"))?.val || "N/A",
                    news_titles: data.news?.map((n:any)=>n.title).join(" | "),
                    full_portfolio: portfolioVault
                } 
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

  // --- PRE-AUTH ROUTING VIEWS ---

  if (!user && !showAuth) {
      return <MarketingLanding 
          onLoginClick={() => { setIsSignUp(false); setShowAuth(true); }} 
          onRegisterClick={() => { setIsSignUp(true); setShowAuth(true); }} 
      />;
  }

  if (!user && showAuth) return (
    <main className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-6 relative">
      <button onClick={() => setShowAuth(false)} className="absolute top-8 left-8 text-slate-500 font-bold hover:text-white transition-colors text-sm">← Back to Home</button>
      {toastMessage && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-10 py-6 rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center mb-3"><div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" /></div>
              <p className="text-white font-black uppercase tracking-widest text-sm text-center">{toastMessage}</p>
           </div>
        </div>
      )}
      <div className="w-full max-w-md bg-slate-900/40 border border-slate-800 p-10 rounded-[48px] shadow-2xl text-center z-10">
        <h1 className="text-4xl font-black text-white tracking-tighter mb-2">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
        
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-8">
            {isSignUp ? "New Operative Registration" : "Operative Login"}
        </p>

        <form onSubmit={handleAuth} className="space-y-4 text-left">
          {isSignUp ? (
            <>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-4 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Official Email Address" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-4 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Create Access Key (Password)" minLength={6} required />
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-4 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Confirm Access Key" minLength={6} required />
            </>
          ) : (
            <>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-5 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Personnel ID (Email)" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-5 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Access Key (Password)" required />
            </>
          )}
          <button type="submit" disabled={authLoading} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-black py-5 rounded-2xl uppercase tracking-widest text-xs transition-colors mt-4">
            {isSignUp ? "Submit Clearance Request" : "Access Terminal"}
          </button>
        </form>
        <button onClick={() => { setIsSignUp(!isSignUp); setPassword(""); setConfirmPassword(""); setEmail(""); }} className="w-full mt-6 text-[10px] text-slate-400 uppercase font-bold hover:text-white transition-colors">
            {isSignUp ? "← Return to Login" : "Request Access"}
        </button>
      </div>
      {/* 🚨 UPDATED COPYRIGHT */}
      <div className="absolute bottom-6 w-full text-center pointer-events-none">
          <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
      </div>
    </main>
  );

  if (user && userProfile?.status === 'pending') return (
    <main className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-6 relative">
      <div className="w-full max-w-md bg-slate-900/40 border border-orange-500/50 p-10 rounded-[48px] shadow-2xl text-center animate-in fade-in zoom-in-95 z-10">
        <div className="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <div className="w-6 h-6 border-4 border-orange-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <h2 className="text-2xl font-black text-white mb-4 uppercase tracking-widest">Clearance Pending</h2>
        <p className="text-slate-400 text-sm leading-relaxed mb-8">
            Your email has been verified. However, an administrator must manually approve your clearance before terminal access is granted.
        </p>
        <button onClick={handleSignOut} className="text-[10px] uppercase font-black text-slate-500 hover:text-white transition-all tracking-widest border border-slate-800 px-6 py-3 rounded-full hover:bg-slate-800">
            Sign Out
        </button>
      </div>
      {/* 🚨 UPDATED COPYRIGHT */}
      <div className="absolute bottom-6 w-full text-center pointer-events-none">
          <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
      </div>
    </main>
  );

  if (!hasAcceptedTerms) return (
    <main className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-6 relative">
      <div className="w-full max-w-lg bg-[#0f172a] border border-slate-800 rounded-[32px] p-10 shadow-2xl relative z-10">
        <div className="flex justify-between items-center mb-8">
            <h2 className="text-xl font-bold text-white flex items-center gap-3">⚖️ Terms of Service & Legal Disclaimer</h2>
            <button onClick={handleSignOut} className="text-slate-500 text-xl font-bold">×</button>
        </div>
        <div className="space-y-6 max-h-[60vh] overflow-y-auto pr-4 custom-scrollbar">
            <p className="text-sm font-bold text-white mb-6">Please read and accept the following terms before accessing the TradeBotics Terminal:</p>
            <div><p className="text-white font-black text-sm mb-2">1. No Financial Advice</p><p className="text-slate-400 text-[13px] leading-relaxed">TradeBotics AI is strictly an educational and analytical software tool. We are not registered financial advisors.</p></div>
            <div><p className="text-white font-black text-sm mb-2">2. Assumption of Risk</p><p className="text-slate-400 text-[13px] leading-relaxed">Trading in financial markets involves a high degree of risk and may not be suitable for all investors. You may lose some or all of your initial investment.</p></div>
            <div><p className="text-white font-black text-sm mb-2">3. Limitation of Liability</p><p className="text-slate-400 text-[13px] leading-relaxed">By accessing this platform, you expressly agree that TradeBotics AI bears absolutely no legal responsibility or liability for any financial losses.</p></div>
            <div><p className="text-white font-black text-sm mb-2">4. Data Accuracy</p><p className="text-slate-400 text-[13px] leading-relaxed">While we strive for high-fidelity accuracy, market data is inherently volatile. Information reflects official exchange closes and aggregated sources, which may be delayed.</p></div>
        </div>
        <button onClick={handleAcceptTerms} className="w-full bg-red-600 hover:bg-red-500 text-white font-black py-4 mt-8 rounded-xl uppercase tracking-widest text-[11px] transition-all">I Agree & Accept Terms</button>
      </div>
      {/* 🚨 UPDATED COPYRIGHT */}
      <div className="absolute bottom-6 w-full text-center pointer-events-none">
          <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
      </div>
    </main>
  );

  // --- LOGGED-IN CORE RENDERING ---

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 flex flex-col font-sans relative">
      
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
      `}} />

      {/* GLOBAL TOAST & LOADING MODALS */}
      {toastMessage && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-10 py-6 rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center mb-3">
                 <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
              </div>
              <p className="text-white font-black uppercase tracking-widest text-sm text-center">{toastMessage}</p>
           </div>
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 z-[120] bg-[#020617]/90 backdrop-blur-md flex flex-col items-center justify-center">
           <div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-6" />
           <p className="text-blue-500 font-black tracking-[0.4em] uppercase text-xs animate-pulse">Initializing Terminal...</p>
        </div>
      )}

      {isAnalyzing && (
        <div className="fixed inset-0 z-[120] bg-[#020617]/90 backdrop-blur-md flex flex-col items-center justify-center">
           <div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-6" />
           <p className="text-blue-500 font-black tracking-[0.4em] uppercase text-xs animate-pulse">Neural Synthesis in Progress...</p>
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

      {/* OPERATIVE COMMAND HUB */}
      {currentView === 'landing' ? (
        
        <div className="min-h-screen bg-[#020617] text-slate-300 font-sans selection:bg-blue-500/30 flex flex-col absolute inset-0 z-50">
            
            <nav className="w-full border-b border-slate-800/50 bg-[#020617]/80 backdrop-blur-md fixed top-0 z-50">
                <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
                    <h1 className="text-2xl font-black text-white tracking-tighter">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
                    <div className="flex items-center gap-6">
                        <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-bold hidden sm:block">Operative // {user?.email?.split('@')[0]}</span>
                        <button onClick={handleSignOut} className="text-[10px] border border-slate-800 px-6 py-2.5 rounded-full font-black uppercase tracking-widest text-slate-400 hover:text-red-500 hover:border-red-500 hover:bg-red-500/10 transition-colors">
                            Sign Out
                        </button>
                    </div>
                </div>
            </nav>

            <div className="flex flex-col items-center justify-center flex-1 max-w-5xl mx-auto w-full text-center px-6 pt-32 pb-20 animate-in fade-in zoom-in-95 duration-500">
                <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mb-6 border border-blue-500/30 shadow-[0_0_30px_rgba(59,130,246,0.15)]">
                    <div className="w-6 h-6 bg-blue-500 rounded-full animate-pulse" />
                </div>
                <h2 className="text-4xl md:text-6xl font-black text-white tracking-tighter mb-6">OPERATIVE <span className="text-blue-500">COMMAND HUB</span></h2>
                <p className="text-slate-400 text-sm md:text-base leading-relaxed max-w-2xl mb-12">
                    Welcome to the central interface. Select a module below to proceed. Access the Intelligence Terminal for real-time market synthesis, or manage your holdings in the Portfolio Vault.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">
                    <div onClick={() => setCurrentView('terminal')} className="bg-slate-900/40 border border-slate-800 p-10 rounded-[40px] hover:border-blue-500/50 hover:bg-slate-900/80 transition-all cursor-pointer group text-left relative overflow-hidden flex flex-col h-full">
                        <div className="absolute top-0 right-0 w-40 h-40 bg-blue-600/10 rounded-full blur-3xl group-hover:bg-blue-600/30 transition-all" />
                        <div className="w-12 h-12 bg-slate-950 border border-slate-800 rounded-2xl flex items-center justify-center mb-6 group-hover:border-blue-500/30 transition-colors">
                            <span className="text-blue-500 text-xl">🌐</span>
                        </div>
                        <h3 className="text-2xl font-black text-white mb-3 group-hover:text-blue-400 transition-colors">Intelligence Terminal</h3>
                        <p className="text-slate-400 text-sm leading-relaxed mb-10 flex-1">Access real-time AI market synthesis, quant scores, and interactive asset screening to execute precision trades.</p>
                        <button className="w-full py-4 bg-slate-950 border border-slate-800 rounded-xl text-[10px] font-black uppercase tracking-widest text-slate-300 group-hover:bg-blue-600 group-hover:border-blue-500 group-hover:text-white transition-all shadow-lg flex justify-center items-center gap-2">
                            Launch Terminal <span className="text-lg leading-none">→</span>
                        </button>
                    </div>

                    <Link href="/portfolio" className="bg-slate-900/40 border border-slate-800 p-10 rounded-[40px] hover:border-purple-500/50 hover:bg-slate-900/80 transition-all cursor-pointer group text-left relative overflow-hidden flex flex-col h-full block">
                        <div className="absolute top-0 right-0 w-40 h-40 bg-purple-600/10 rounded-full blur-3xl group-hover:bg-purple-600/30 transition-all" />
                        <div className="w-12 h-12 bg-slate-950 border border-slate-800 rounded-2xl flex items-center justify-center mb-6 group-hover:border-purple-500/30 transition-colors">
                            <span className="text-purple-500 text-xl">💼</span>
                        </div>
                        <h3 className="text-2xl font-black text-white mb-3 group-hover:text-purple-400 transition-colors">Portfolio Intelligence</h3>
                        <p className="text-slate-400 text-sm leading-relaxed mb-10 flex-1">Sync your live holdings to the neural vault to receive personalized exit strategies and accurate cost-basis mapping.</p>
                        <button className="w-full py-4 bg-slate-950 border border-slate-800 rounded-xl text-[10px] font-black uppercase tracking-widest text-slate-300 group-hover:bg-purple-600 group-hover:border-purple-500 group-hover:text-white transition-all shadow-lg flex justify-center items-center gap-2">
                            Initialize Vault <span className="text-lg leading-none">→</span>
                        </button>
                    </Link>
                </div>
            </div>
            
            {/* 🚨 UPDATED COPYRIGHT */}
            <footer className="border-t border-slate-800/50 py-8 text-center w-full mt-auto relative z-10 bg-[#020617]">
                <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
            </footer>
        </div>

      ) : (

        <div className="p-6 flex flex-col flex-1">
          <TickerTape />
          
          <div className="flex justify-between items-center mb-12">
            <div>
                <h1 className="text-5xl font-black text-white tracking-tighter cursor-pointer hover:text-blue-500 transition-colors" onClick={() => setCurrentView('landing')}>
                    TRADEBOTICS<span className="text-blue-500">AI</span>
                </h1>
                <p className="text-[9px] uppercase tracking-[0.5em] text-slate-400 italic">Operative // {user?.email?.split('@')[0]}</p>
            </div>
            
            <div className="flex gap-4 items-center">
              <button onClick={() => setCurrentView('landing')} className="hidden lg:flex items-center gap-3 px-6 py-3 bg-slate-900/50 border border-slate-800 rounded-full hover:border-blue-500/50 transition-all group">
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">← Return to Hub</span>
              </button>
              
              <div className="flex gap-3 bg-slate-900/80 p-3 rounded-[24px] border border-slate-800 focus-within:border-blue-500/50">
                <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runAnalysis()} className="bg-transparent border-none text-white font-black w-48 px-4 outline-none text-lg" placeholder="TICKER..." />
                <button onClick={() => runAnalysis()} className="bg-blue-600 text-white px-10 py-4 rounded-xl font-black text-xs uppercase hover:bg-blue-500">{loading ? "..." : "SCAN"}</button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-12 gap-8 flex-1">
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

              {/* 🚨 RESTORED: Institutional DNA Block */}
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
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-6 text-center flex items-center justify-center gap-2">
                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></span>
                    Portfolio Vault
                </p>
                <div className="space-y-3 max-h-[250px] overflow-y-auto custom-scrollbar pr-2">
                  {portfolioVault.length > 0 ? portfolioVault.map((item, i) => (
                    <button key={i} onClick={() => runAnalysis(item.ticker)} className="w-full flex justify-between items-center p-4 rounded-2xl bg-slate-950 border border-slate-800 hover:border-blue-500/50 transition-all group text-left">
                      <div>
                        <span className="font-black text-white text-lg block mb-1">{item.ticker}</span>
                        <span className="text-[9px] font-bold text-slate-500 uppercase">{item.shares} Shares</span>
                      </div>
                      <div className="text-right">
                        <span className="text-[9px] font-black text-slate-400 block mb-1 uppercase">Avg Cost</span>
                        <span className="text-xs font-black text-white">${item.avg_cost}</span>
                      </div>
                    </button>
                  )) : (
                    <p className="text-center text-xs font-bold text-slate-600 uppercase tracking-widest mt-6">Vault Empty.<br/>Sync via Hub.</p>
                  )}
                </div>
              </div>

              <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 shadow-inner">
                <div className="flex justify-between items-center mb-6 px-1">
                   <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Secured Watchlist</p>
                   <button onClick={handleRefreshWatchlist} disabled={isRefreshingWatchlist || watchlist.length === 0} className="text-slate-500 hover:text-blue-500 disabled:opacity-50 transition-colors" title="Refresh Scores">
                      <svg className={`w-3.5 h-3.5 ${isRefreshingWatchlist ? 'animate-spin text-blue-500' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                   </button>
                </div>
                
                <div className="space-y-3 max-h-[250px] overflow-y-auto custom-scrollbar pr-2">
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
                  <button onClick={() => runDeepDive('strike_zone')} className="w-full bg-blue-600 hover:bg-blue-500 py-5 rounded-[32px] font-black text-xs uppercase tracking-[0.3em] transition-all shadow-xl shadow-blue-600/20">🎯 Calculate AI-Powered Entry Zone</button>
                </>
              )}
            </div>

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

                      {currentPosition && (
                          <div className={`mb-8 p-6 border rounded-3xl ${((data.price - currentPosition.avg_cost) * currentPosition.shares) >= 0 ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
                              <p className="text-[10px] font-black uppercase mb-4 text-slate-400">Vault Position Data</p>
                              <div className="flex justify-between items-end mb-4">
                                  <div>
                                      <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Live P&L</p>
                                      <p className={`text-2xl font-black font-mono ${((data.price - currentPosition.avg_cost) * currentPosition.shares) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                          ${((data.price - currentPosition.avg_cost) * currentPosition.shares).toFixed(2)}
                                      </p>
                                  </div>
                                  <div className="text-right">
                                      <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Return</p>
                                      <p className={`text-sm font-black ${data.price >= currentPosition.avg_cost ? 'text-green-500' : 'text-red-500'}`}>
                                          {(((data.price - currentPosition.avg_cost) / currentPosition.avg_cost) * 100).toFixed(2)}%
                                      </p>
                                  </div>
                              </div>
                          </div>
                      )}

                      <div className="grid grid-cols-2 gap-8 border-t border-slate-800 pt-8 mb-8">
                         <div><p className="text-[9px] font-bold text-slate-400 uppercase mb-2">24H Volume</p><p className="text-white font-black text-sm">{data.volume}</p></div>
                         <div><p className="text-[9px] font-bold text-slate-400 uppercase mb-2">Rel Surge</p><p className="text-blue-400 font-black text-sm">{data.vol_surge}</p></div>
                      </div>

                      {data.holding_analysis && (
                        <div className="mb-8 p-6 bg-orange-500/5 border border-orange-500/10 rounded-3xl">
                          <div className="flex justify-between items-center mb-4"><p className="text-[10px] font-black text-orange-500 uppercase">Exit Stance</p><span className="text-white font-black text-xs uppercase">{data.holding_analysis.status}</span></div>
                          <p className="text-slate-300 text-[11px] italic mb-6 border-l border-slate-800 pl-3">"{data.holding_analysis.guidance}"</p>
                          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800">
                              <div><p className="text-[8px] font-bold text-slate-400 uppercase mb-1">Stop</p><p className="text-white font-mono font-black text-xs">${data.holding_analysis.stop_loss}</p></div>
                              <div><p className="text-[8px] font-bold text-slate-400 uppercase mb-1">Target</p><p className="text-white font-mono font-black text-xs">${data.holding_analysis.trailing_target}</p></div>
                          </div>
                        </div>
                      )}

                      <button onClick={() => runDeepDive('verdict')} className="w-full mb-4 bg-blue-900/30 border border-blue-500/50 py-3 rounded-xl text-blue-400 font-black text-[10px] uppercase tracking-widest hover:bg-blue-600 hover:text-white transition-all shadow-[0_0_15px_rgba(59,130,246,0.15)]">
                        Execute AI Analysis Verdict
                      </button>
                      
                      <div className="mb-10 p-5 bg-blue-500/5 border-l-2 border-blue-500 rounded-r-2xl min-h-[50px]">
                          <p className="text-slate-200 text-sm font-bold italic leading-relaxed">"{data.ai_tactical}"</p>
                      </div>

                    </>
                 ) : ( <p className="text-slate-600 font-bold uppercase text-[10px] tracking-widest italic text-center">Scan required...</p> )}
              </div>

              <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 flex flex-col h-[600px] overflow-hidden shrink-0">
                 <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-6 text-center">AI Intelligence Wire</p>
                 
                 <button onClick={() => runDeepDive('sentiment')} className="w-full mb-6 bg-blue-900/30 border border-blue-500/50 py-4 rounded-2xl text-blue-400 font-black text-[10px] uppercase tracking-widest hover:bg-blue-600 hover:text-white transition-all shadow-[0_0_15px_rgba(59,130,246,0.15)]">
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
          
          {/* 🚨 UPDATED COPYRIGHT */}
          <footer className="border-t border-slate-800/50 pt-8 mt-12 text-center w-full">
              <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
          </footer>
        </div>
      )}

    </main>
  );
}