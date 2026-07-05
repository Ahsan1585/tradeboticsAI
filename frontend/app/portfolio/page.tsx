"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import { apiFetch } from "../lib/config";
import DOMPurify from "isomorphic-dompurify";
import ThemeToggle from "../components/ThemeToggle";

export default function PortfolioPage() {
    const router = useRouter();
    
    // Auth & State
    const [isAuthorized, setIsAuthorized] = useState(false);
    const [userId, setUserId] = useState("");
    const [userEmail, setUserEmail] = useState("");
    
    // Search State
    const [searchTicker, setSearchTicker] = useState("");

    // Portfolio Data
    const [portfolio, setPortfolio] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [toastMessage, setToastMessage] = useState<string | null>(null);

    // AI Analysis State
    const [tradeStyle, setTradeStyle] = useState("Long Term");
    const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // NEURAL AUTHORIZATION STATE
    const [authModal, setAuthModal] = useState({
        isOpen: false,
        title: "",
        cost: 0,
        actionName: "",
        onConfirm: () => {}
    });

    useEffect(() => {
        const verifyClearance = async () => {
            const { data: { session }, error } = await supabase.auth.getSession();
            if (error || !session) {
                router.push('/');
            } else {
                setIsAuthorized(true);
                setUserId(session.user.id);
                setUserEmail(session.user.email || "OPERATIVE");
                fetchPortfolio(session.user.id);
                
                // 🚀 BROWSER CACHE CHECK: Load saved analysis for this user on mount
                const savedAnalysis = localStorage.getItem(`portfolio_analysis_${session.user.id}`);
                const savedStyle = localStorage.getItem(`portfolio_style_${session.user.id}`);
                
                if (savedAnalysis) {
                    setAiAnalysis(savedAnalysis);
                }
                if (savedStyle) {
                    setTradeStyle(savedStyle);
                }
            }
        };
        verifyClearance();
    }, [router]);

    const showToast = (msg: string) => {
        setToastMessage(msg);
        setTimeout(() => setToastMessage(null), 3500);
    };

    const handleSearch = () => {
        if (!searchTicker.trim()) return;
        router.push(`/terminal?ticker=${searchTicker.trim().toUpperCase()}`);
    };

    // 🚀 CACHE SWEEP LOGIC: Call this function when the user actively logs out
    const handleLogout = async () => {
        localStorage.removeItem(`portfolio_analysis_${userId}`);
        localStorage.removeItem(`portfolio_style_${userId}`);
        await supabase.auth.signOut();
        router.push('/');
    };

    const fetchPortfolio = async (uid: string) => {
        setLoading(true);
        const { data, error } = await supabase.from('portfolio').select('*').eq('user_id', uid);
        
        if (error) {
            showToast("Failed to sync vault.");
        } else if (data) {
            const aggregated = data.reduce((acc: any, curr: any) => {
                const t = curr.ticker.toUpperCase();
                if (!acc[t]) acc[t] = { ticker: t, total_shares: 0, total_cost_dollars: 0 };
                const shares = parseFloat(curr.shares);
                const cost = parseFloat(curr.cost_basis);
                acc[t].total_shares += shares;
                acc[t].total_cost_dollars += (shares * cost);
                return acc;
            }, {});

            const formattedVault = Object.values(aggregated).map((pos: any) => ({
                ticker: pos.ticker,
                shares: parseFloat(pos.total_shares.toFixed(2)),
                avg_cost: pos.total_shares > 0 ? (pos.total_cost_dollars / pos.total_shares).toFixed(2) : 0
            })).sort((a: any, b: any) => a.ticker.localeCompare(b.ticker));
            
            setPortfolio(formattedVault);
        }
        setLoading(false);
    };

    const runPortfolioAnalysis = async () => {
        if (portfolio.length === 0) {
            showToast("Vault is empty. Add assets to analyze.");
            return;
        }
        setIsAnalyzing(true);
        setAiAnalysis(null);
        try {
            const res = await apiFetch(`/portfolio-analysis`, {
                method: "POST",
                body: JSON.stringify({ holdings: portfolio, trade_style: tradeStyle })
            });
            const result = await res.json();
            
            if (res.ok) {
                // Update UI state
                setAiAnalysis(result.analysis);
                
                // 🚀 SAVE TO BROWSER MEMORY
                localStorage.setItem(`portfolio_analysis_${userId}`, result.analysis);
                localStorage.setItem(`portfolio_style_${userId}`, tradeStyle);
                
            } else {
                if (res.status === 402) {
                    showToast("NEURAL BANDWIDTH DEPLETED. RECHARGE REQUIRED.");
                } else {
                    showToast("AI Engine Error: " + result.detail);
                }
            }
        } catch (error) {
            showToast("Backend Offline. Check connection.");
        }
        setIsAnalyzing(false);
    };

    if (!isAuthorized) return <main className="min-h-screen bg-bg-primary flex items-center justify-center"><div className="w-16 h-16 border-4 border-border border-t-accent rounded-full animate-spin" /></main>;

    return (
        <main className="min-h-screen bg-bg-primary text-text-secondary font-sans p-4 sm:p-6 md:p-12 relative overflow-x-hidden">
            
            {/* INJECTED GLOBAL SCROLLBAR STYLES */}
            <style dangerouslySetInnerHTML={{__html: `
                .custom-scrollbar::-webkit-scrollbar { width: 4px; }
                @media (min-width: 768px) { .custom-scrollbar::-webkit-scrollbar { width: 6px; } }
                .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
            `}} />

            {/* TOAST NOTIFICATION */}
            {toastMessage && (
                <div className="fixed inset-x-4 top-4 md:inset-0 md:top-0 z-[150] flex items-start md:items-center justify-center pointer-events-none">
                    <div className="bg-bg-surface border border-accent/50 px-6 py-4 md:px-10 md:py-6 rounded-2xl md:rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in slide-in-from-top-4 md:zoom-in-95 fade-in duration-300 flex flex-col items-center">
                        <p className="text-text-primary font-black uppercase tracking-widest text-[10px] md:text-sm text-center">{toastMessage}</p>
                    </div>
                </div>
            )}

            {/* RESPONSIVE HEADER */}
            <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center mb-8 md:mb-10 gap-4 md:gap-6">
                <div>
                    <h1 className="text-4xl md:text-5xl font-black text-text-primary tracking-tighter cursor-pointer hover:text-accent transition-colors" onClick={() => router.push('/hub')}>
                        TRADEBOTICS<span className="text-accent">AI</span>
                    </h1>
                    <p className="text-[8px] md:text-[10px] uppercase tracking-[0.4em] md:tracking-[0.5em] text-text-secondary italic mt-1 md:mt-2">
                        Quantitative Command Console // {userEmail.split('@')[0]}
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <ThemeToggle />
                    <button onClick={() => router.push('/hub')} className="w-full md:w-auto flex justify-center items-center gap-3 px-6 py-3 bg-bg-surface border border-border rounded-xl md:rounded-full hover:border-accent/50 transition-all group">
                        <span className="text-[10px] font-black uppercase tracking-[0.2em] text-text-secondary group-hover:text-text-primary">← Return to Hub</span>
                    </button>
                </div>
            </div>

            {/* RESPONSIVE VALUE BANNER */}
            <div className="max-w-6xl mx-auto mb-8 md:mb-10 bg-bg-primary border border-accent/10 rounded-[24px] md:rounded-[32px] p-6 md:p-8 relative overflow-hidden shadow-xl">
                <div className="absolute top-0 right-0 w-48 h-48 md:w-64 md:h-64 bg-accent/5 rounded-full blur-[40px] md:blur-[60px] pointer-events-none" />
                <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div className="max-w-3xl">
                        <div className="flex items-center gap-2 mb-2 md:mb-3">
                            <div className="w-1.5 h-1.5 bg-accent rounded-full animate-ping" />
                            <span className="text-[8px] md:text-[10px] font-black uppercase text-accent tracking-[0.2em] md:tracking-[0.3em]">Institutional Grade Allocation Engine</span>
                        </div>
                        <h2 className="text-xl md:text-2xl font-black text-text-primary uppercase tracking-tight mb-2">Your Virtual Quantitative Engine</h2>
                        <p className="text-xs md:text-sm text-text-secondary leading-relaxed font-medium">
                            Track your live capital and let the AI do the heavy lifting. Run a Rotation Scan to get instant, data-driven recommendations on what to buy, sell, or hold to grow your wealth safely.
                        </p>
                    </div>
                </div>
            </div>

            {/* RESPONSIVE SEARCH BAR */}
            <div className="max-w-6xl mx-auto mb-8 md:mb-10 flex w-full bg-bg-primary p-2 md:p-3 rounded-full border border-border focus-within:border-accent/50 shadow-xl transition-all group">
                <div className="pl-4 md:pl-6 flex items-center justify-center text-text-secondary group-focus-within:text-accent transition-colors shrink-0">
                    <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </div>
                <input 
                    value={searchTicker} 
                    onChange={(e) => setSearchTicker(e.target.value)} 
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()} 
                    className="flex-1 bg-transparent border-none text-text-primary font-black px-3 md:px-6 outline-none text-base md:text-xl uppercase placeholder:text-text-secondary placeholder:normal-case placeholder:font-medium min-w-0" 
                    placeholder="Search assets to structure alternative trade scenarios..." 
                />
                <button 
                    onClick={handleSearch} 
                    className="bg-accent text-white px-5 md:px-10 py-3 md:py-4 rounded-full font-black text-[9px] md:text-[10px] uppercase tracking-widest hover:bg-accent-hover shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all shrink-0"
                >
                    SCAN & TRADE
                </button>
            </div>

            {/* RESPONSIVE GRID LAYOUT */}
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8">
                
                {/* LEFT PANEL: READ-ONLY INVENTORY OVERVIEW */}
                <div className="lg:col-span-7 flex flex-col gap-6 md:gap-8 order-2 lg:order-1">
                    <div className="bg-bg-surface border border-border p-5 md:p-8 rounded-[32px] md:rounded-[40px] shadow-2xl min-h-[400px] md:min-h-[500px] flex flex-col">
                        <div className="flex justify-between items-center mb-4 md:mb-6 border-b border-border pb-4">
                            <p className="text-[9px] md:text-[11px] font-black text-text-secondary uppercase tracking-[0.3em] md:tracking-[0.4em]">Active Portfolio Allocations</p>
                            <span className="text-[9px] md:text-[10px] bg-bg-surface-hover text-text-secondary px-2 md:px-3 py-1 rounded-full font-bold uppercase">{portfolio.length} Positions</span>
                        </div>

                        {loading ? (
                            <div className="flex justify-center items-center h-40 flex-1"><div className="w-6 h-6 md:w-8 md:h-8 border-2 border-border border-t-accent rounded-full animate-spin" /></div>
                        ) : portfolio.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-40 text-text-secondary flex-1">
                                <span className="text-3xl md:text-4xl mb-2">💼</span>
                                <p className="font-bold uppercase tracking-widest text-[9px] md:text-[10px]">No Capital Allocated</p>
                            </div>
                        ) : (
                            <div className="space-y-2 md:space-y-3 overflow-y-auto max-h-[400px] md:max-h-[550px] pr-1 md:pr-2 custom-scrollbar flex-1">
                                {portfolio.map((item, i) => (
                                    <div 
                                        key={i} 
                                        onClick={() => router.push(`/terminal?ticker=${item.ticker}`)}
                                        className="bg-bg-primary border border-border p-4 md:p-5 rounded-2xl md:rounded-3xl flex items-center justify-between gap-3 md:gap-4 cursor-pointer hover:border-accent/50 hover:bg-bg-surface-hover/80 transition-all group shadow-sm hover:shadow-[0_0_20px_rgba(59,130,246,0.1)]"
                                    >
                                        <div className="flex items-center gap-3 sm:gap-6 w-full justify-between sm:justify-start">
                                            <div className="w-12 h-12 md:w-16 md:h-16 bg-bg-surface rounded-xl md:rounded-2xl flex items-center justify-center border border-border shrink-0 group-hover:border-accent/50 transition-colors">
                                                <span className="font-black text-text-primary text-base md:text-xl group-hover:text-accent transition-colors">{item.ticker}</span>
                                            </div>
                                            <div className="flex-1 flex justify-between sm:justify-start sm:gap-12 px-2 sm:px-0">
                                                <div className="text-left sm:text-left">
                                                    <p className="text-[9px] md:text-[10px] font-bold text-text-secondary uppercase tracking-widest mb-1">Quantity</p>
                                                    <p className="text-base md:text-xl font-mono font-black text-text-primary">{item.shares.toFixed(2)}</p>
                                                </div>
                                                <div className="text-right sm:text-left">
                                                    <p className="text-[9px] md:text-[10px] font-bold text-text-secondary uppercase tracking-widest mb-1">Avg Price Basis</p>
                                                    <p className="text-base md:text-xl font-mono font-black text-text-primary">${item.avg_cost}</p>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div className="hidden sm:flex text-text-secondary group-hover:text-accent transition-colors pr-2 md:pr-4 shrink-0">
                                            <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                            </svg>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* RIGHT PANEL: AI ANALYSIS ENGINE */}
                <div className="lg:col-span-5 flex flex-col gap-6 md:gap-8 order-1 lg:order-2">
                    <div className="bg-bg-primary border border-purple-500/30 p-6 md:p-8 rounded-[32px] md:rounded-[40px] shadow-[inset_0_0_30px_rgba(168,85,247,0.05)] h-full flex flex-col">
                        <div className="flex items-center gap-2 md:gap-3 mb-6 md:mb-8">
                            <div className="w-2 h-2 md:w-2.5 md:h-2.5 bg-purple-500 rounded-full animate-pulse" />
                            <p className="text-[9px] md:text-[11px] font-black uppercase tracking-[0.3em] md:tracking-[0.4em] text-purple-500">Neural Portfolio Synthesis</p>
                        </div>

                        <div className="mb-6 md:mb-8">
                            <p className="text-[9px] md:text-[10px] font-black text-text-secondary uppercase tracking-widest mb-3">Target Horizon Profile</p>
                            <div className="flex flex-wrap gap-2">
                                {["Day Trade", "Swing Trade", "Long Term"].map(style => (
                                    <button 
                                        key={style} 
                                        onClick={() => setTradeStyle(style)}
                                        className={`px-3 md:px-4 py-2 rounded-lg md:rounded-xl font-black text-[9px] md:text-[10px] uppercase tracking-wider md:tracking-widest transition-all flex-1 sm:flex-none text-center ${tradeStyle === style ? 'bg-purple-600 text-text-primary border border-purple-500' : 'bg-bg-surface border border-border text-text-secondary hover:text-text-primary'}`}
                                    >
                                        {style}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* TRIGGER AUTH MODAL FOR PORTFOLIO SCAN (5 TOKENS) */}
                        <button 
                            onClick={() => setAuthModal({
                                isOpen: true,
                                title: "Portfolio Rotation Matrix",
                                cost: 5,
                                actionName: "AUTHORIZE ROTATION",
                                onConfirm: runPortfolioAnalysis
                            })}
                            disabled={isAnalyzing || portfolio.length === 0}
                            className="w-full bg-purple-600 border border-purple-500 hover:bg-purple-500 py-3 md:py-4 rounded-xl md:rounded-2xl text-text-primary font-black text-[9px] md:text-[10px] uppercase tracking-widest transition-all shadow-[0_0_25px_rgba(168,85,247,0.5)] disabled:opacity-50 disabled:bg-purple-600/20 disabled:text-purple-400 mb-6 md:mb-8"
                        >
                            {isAnalyzing ? "Processing Matrix..." : "Execute Rotation Scan"}
                        </button>

                        <div className="flex-1 bg-bg-primary border border-border rounded-2xl md:rounded-3xl p-5 md:p-6 overflow-y-auto custom-scrollbar relative min-h-[250px] md:min-h-[300px]">
                            {isAnalyzing ? (
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <div className="w-6 h-6 md:w-8 md:h-8 border-2 border-border border-t-purple-500 rounded-full animate-spin mb-3 md:mb-4" />
                                    <p className="text-[8px] md:text-[9px] text-purple-500 uppercase font-black tracking-widest animate-pulse">Calculating Alpha...</p>
                                </div>
                            ) : aiAnalysis ? (
                                <div className="prose prose-invert max-w-none text-xs md:text-sm font-medium leading-relaxed">
                                    <style dangerouslySetInnerHTML={{__html: `
                                        .prose h3 { color: #a855f7; font-size: 11px; text-transform: uppercase; letter-spacing: 0.2em; font-weight: 900; margin-top: 1.25rem; margin-bottom: 0.5rem; }
                                        @media (min-width: 768px) { .prose h3 { font-size: 12px; margin-top: 1.5rem; } }
                                        .prose ul { list-style-type: none; padding: 0; }
                                        .prose li { position: relative; padding-left: 1.25rem; margin-bottom: 0.5rem; color: #cbd5e1; }
                                        @media (min-width: 768px) { .prose li { padding-left: 1.5rem; } }
                                        .prose li::before { content: "→"; position: absolute; left: 0; color: #a855f7; font-weight: 900; }
                                        .prose strong { color: #fff; }
                                    `}} />
                                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(aiAnalysis) }} />
                                </div>
                            ) : (
                                <p className="text-text-secondary text-[10px] md:text-xs italic text-center mt-8 md:mt-10">Analysis offline. Awaiting execution command.</p>
                            )}
                        </div>
                    </div>
                </div>

            </div>

            {/* NEURAL AUTHORIZATION MODAL */}
            {authModal.isOpen && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-bg-primary">
                    <div className="bg-bg-primary border border-loss/40 rounded-2xl shadow-[0_0_40px_rgba(220,38,38,0.15)] w-full max-w-sm overflow-hidden relative">
                        
                        <div className="p-3 md:p-4 border-b border-loss/30 bg-loss/20 flex items-center gap-2 md:gap-3">
                            <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-loss rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>
                            <h2 className="text-[10px] md:text-xs font-bold text-loss uppercase tracking-[0.2em]">Bandwidth Auth Required</h2>
                        </div>

                        <div className="p-5 md:p-6 text-center space-y-4">
                            <p className="text-xs md:text-sm text-text-secondary font-mono leading-relaxed">
                                Executing the <span className="text-text-primary font-bold">{authModal.title}</span> protocol will consume standard neural bandwidth.
                            </p>
                            
                            <div className="py-3 md:py-4 bg-bg-surface rounded-xl border border-border flex flex-col items-center justify-center">
                                <p className="text-[9px] md:text-[10px] text-text-secondary uppercase tracking-widest mb-1">Compute Cost</p>
                                <p className="text-2xl md:text-3xl font-mono text-purple-400 font-bold">-{authModal.cost} TOKENS</p>
                            </div>
                        </div>

                        <div className="flex border-t border-border">
                            <button 
                                onClick={() => setAuthModal({ ...authModal, isOpen: false })}
                                className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-text-secondary hover:text-text-primary uppercase tracking-widest hover:bg-bg-surface-hover/50 transition-colors">
                                Abort
                            </button>
                            <button 
                                onClick={() => {
                                    setAuthModal({ ...authModal, isOpen: false });
                                    authModal.onConfirm(); 
                                }}
                                className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-loss hover:text-loss uppercase tracking-widest hover:bg-loss/30 transition-colors border-l border-border">
                                {authModal.actionName}
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </main>
    );
}