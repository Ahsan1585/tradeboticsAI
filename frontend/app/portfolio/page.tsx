"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import { apiFetch } from "../lib/config";
import DOMPurify from "isomorphic-dompurify";
import ThemeToggle from "../components/ThemeToggle";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";

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

    // AUTHORIZATION MODAL STATE
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
                setUserEmail(session.user.email || "Investor");
                fetchPortfolio(session.user.id);

                // Load saved analysis for this user on mount
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
            showToast("Failed to load your portfolio.");
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
            showToast("Add a position before running analysis.");
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
                setAiAnalysis(result.analysis);
                localStorage.setItem(`portfolio_analysis_${userId}`, result.analysis);
                localStorage.setItem(`portfolio_style_${userId}`, tradeStyle);
            } else {
                if (res.status === 402) {
                    showToast("Out of AI tokens. Add more to continue.");
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

            <style dangerouslySetInnerHTML={{__html: `
                .custom-scrollbar::-webkit-scrollbar { width: 4px; }
                @media (min-width: 768px) { .custom-scrollbar::-webkit-scrollbar { width: 6px; } }
                .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 10px; }
            `}} />

            {toastMessage && (
                <div className="fixed inset-x-4 top-4 md:inset-0 md:top-0 z-[150] flex items-start md:items-center justify-center pointer-events-none">
                    <Card className="px-6 py-4 md:px-10 md:py-6 rounded-2xl md:rounded-3xl shadow-lg animate-in slide-in-from-top-4 md:zoom-in-95 fade-in duration-300 flex flex-col items-center">
                        <p className="text-text-primary font-black uppercase tracking-widest text-[10px] md:text-sm text-center">{toastMessage}</p>
                    </Card>
                </div>
            )}

            {/* HEADER */}
            <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center mb-8 md:mb-10 gap-4 md:gap-6">
                <div>
                    <h1 className="text-4xl md:text-5xl font-black text-text-primary tracking-tighter cursor-pointer hover:text-accent transition-colors" onClick={() => router.push('/hub')}>
                        TRADEBOTICS<span className="text-accent">AI</span>
                    </h1>
                    <p className="text-xs md:text-sm text-text-secondary mt-1 md:mt-2">
                        Portfolio · {userEmail.split('@')[0]}
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <ThemeToggle />
                    <Button variant="secondary" size="md" onClick={() => router.push('/hub')} className="rounded-xl md:rounded-full">
                        ← Hub
                    </Button>
                </div>
            </div>

            {/* VALUE BANNER */}
            <Card className="max-w-6xl mx-auto mb-8 md:mb-10 p-6 md:p-8">
                <div className="flex items-center gap-2 mb-2 md:mb-3">
                    <div className="w-1.5 h-1.5 bg-accent rounded-full" />
                    <span className="text-[10px] font-black uppercase text-accent tracking-[0.2em]">AI Portfolio Assistant</span>
                </div>
                <h2 className="text-xl md:text-2xl font-black text-text-primary tracking-tight mb-2">Track holdings, get a rebalancing plan</h2>
                <p className="text-xs md:text-sm text-text-secondary leading-relaxed max-w-3xl">
                    Track your positions and let the engine analyze them against your goals. Run an analysis to get a data-driven recommendation on what to buy, sell, or hold.
                </p>
            </Card>

            {/* SEARCH BAR */}
            <div className="max-w-6xl mx-auto mb-8 md:mb-10 flex w-full bg-bg-surface p-2 md:p-3 rounded-full border border-border focus-within:border-accent/50 shadow-sm transition-all group">
                <div className="pl-4 md:pl-6 flex items-center justify-center text-text-secondary group-focus-within:text-accent transition-colors shrink-0">
                    <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </div>
                <input
                    value={searchTicker}
                    onChange={(e) => setSearchTicker(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    className="flex-1 bg-transparent border-none text-text-primary font-black px-3 md:px-6 outline-none text-base md:text-xl uppercase placeholder:text-text-secondary placeholder:normal-case placeholder:font-medium min-w-0"
                    placeholder="Search a ticker to trade..."
                    aria-label="Search ticker"
                />
                <Button onClick={handleSearch} size="md" className="shrink-0">
                    Search
                </Button>
            </div>

            {/* GRID LAYOUT */}
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6 md:gap-8">

                {/* LEFT: HOLDINGS */}
                <div className="lg:col-span-7 order-2 lg:order-1">
                    <Card className="p-5 md:p-8 min-h-[400px] md:min-h-[500px] flex flex-col">
                        <div className="flex justify-between items-center mb-4 md:mb-6 border-b border-border pb-4">
                            <p className="text-[11px] font-black text-text-secondary uppercase tracking-[0.3em]">Your Holdings</p>
                            <span className="text-[10px] bg-bg-surface-hover text-text-secondary px-3 py-1 rounded-full font-bold uppercase">{portfolio.length} Positions</span>
                        </div>

                        {loading ? (
                            <div className="flex justify-center items-center h-40 flex-1"><div className="w-6 h-6 md:w-8 md:h-8 border-2 border-border border-t-accent rounded-full animate-spin" /></div>
                        ) : portfolio.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-40 text-text-secondary flex-1 gap-3">
                                <svg className="w-10 h-10 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7h-3V6a3 3 0 00-3-3h-4a3 3 0 00-3 3v1H4a1 1 0 00-1 1v10a2 2 0 002 2h14a2 2 0 002-2V8a1 1 0 00-1-1zM9 6a1 1 0 011-1h4a1 1 0 011 1v1H9V6z" />
                                </svg>
                                <p className="font-bold uppercase tracking-widest text-[10px]">No positions yet</p>
                            </div>
                        ) : (
                            <div className="space-y-2 md:space-y-3 overflow-y-auto max-h-[400px] md:max-h-[550px] pr-1 md:pr-2 custom-scrollbar flex-1">
                                {portfolio.map((item, i) => (
                                    <Card
                                        key={i}
                                        interactive
                                        onClick={() => router.push(`/terminal?ticker=${item.ticker}`)}
                                        className="bg-bg-primary p-4 md:p-5 flex items-center justify-between gap-3 md:gap-4"
                                    >
                                        <div className="flex items-center gap-3 sm:gap-6 w-full justify-between sm:justify-start">
                                            <div className="w-12 h-12 md:w-16 md:h-16 bg-bg-surface rounded-xl md:rounded-2xl flex items-center justify-center border border-border shrink-0">
                                                <span className="font-black text-text-primary text-base md:text-xl">{item.ticker}</span>
                                            </div>
                                            <div className="flex-1 flex justify-between sm:justify-start sm:gap-12 px-2 sm:px-0">
                                                <div>
                                                    <p className="text-[10px] font-bold text-text-secondary uppercase tracking-widest mb-1">Shares</p>
                                                    <p className="text-base md:text-xl font-mono font-black text-text-primary">{item.shares.toFixed(2)}</p>
                                                </div>
                                                <div className="text-right sm:text-left">
                                                    <p className="text-[10px] font-bold text-text-secondary uppercase tracking-widest mb-1">Avg Cost</p>
                                                    <p className="text-base md:text-xl font-mono font-black text-text-primary">${item.avg_cost}</p>
                                                </div>
                                            </div>
                                        </div>
                                        <svg className="hidden sm:block w-5 h-5 text-text-secondary shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                        </svg>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </Card>
                </div>

                {/* RIGHT: AI ANALYSIS */}
                <div className="lg:col-span-5 order-1 lg:order-2">
                    <Card className="p-6 md:p-8 h-full flex flex-col">
                        <div className="flex items-center gap-2 md:gap-3 mb-6 md:mb-8">
                            <div className="w-2 h-2 bg-accent rounded-full" />
                            <p className="text-[11px] font-black uppercase tracking-[0.3em] text-text-primary">AI Portfolio Analysis</p>
                        </div>

                        <div className="mb-6 md:mb-8">
                            <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest mb-3">Investment Horizon</p>
                            <div className="flex flex-wrap gap-2">
                                {["Day Trade", "Swing Trade", "Long Term"].map(style => (
                                    <button
                                        key={style}
                                        onClick={() => setTradeStyle(style)}
                                        className={`px-3 md:px-4 py-2 rounded-lg md:rounded-xl font-black text-[9px] md:text-[10px] uppercase tracking-wider transition-all flex-1 sm:flex-none text-center cursor-pointer ${tradeStyle === style ? 'bg-accent text-white border border-accent' : 'bg-bg-primary border border-border text-text-secondary hover:text-text-primary'}`}
                                    >
                                        {style}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <Button
                            variant="primary"
                            onClick={() => setAuthModal({
                                isOpen: true,
                                title: "Portfolio Analysis",
                                cost: 5,
                                actionName: "Confirm & Run",
                                onConfirm: runPortfolioAnalysis
                            })}
                            disabled={isAnalyzing || portfolio.length === 0}
                            className="w-full py-3 md:py-4 rounded-xl md:rounded-2xl text-xs mb-6 md:mb-8"
                        >
                            {isAnalyzing ? "Analyzing..." : "Run Analysis"}
                        </Button>

                        <div className="flex-1 bg-bg-primary border border-border rounded-2xl md:rounded-3xl p-5 md:p-6 overflow-y-auto custom-scrollbar relative min-h-[250px] md:min-h-[300px]">
                            {isAnalyzing ? (
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <div className="w-6 h-6 md:w-8 md:h-8 border-2 border-border border-t-accent rounded-full animate-spin mb-3 md:mb-4" />
                                    <p className="text-[9px] text-accent uppercase font-black tracking-widest">Analyzing your portfolio...</p>
                                </div>
                            ) : aiAnalysis ? (
                                <div className="prose prose-sm max-w-none text-xs md:text-sm font-medium leading-relaxed">
                                    <style dangerouslySetInnerHTML={{__html: `
                                        .prose h3 { color: var(--accent); font-size: 11px; text-transform: uppercase; letter-spacing: 0.2em; font-weight: 900; margin-top: 1.25rem; margin-bottom: 0.5rem; }
                                        .prose ul { list-style-type: none; padding: 0; }
                                        .prose li { position: relative; padding-left: 1.25rem; margin-bottom: 0.5rem; color: var(--text-secondary); }
                                        .prose li::before { content: "→"; position: absolute; left: 0; color: var(--accent); font-weight: 900; }
                                        .prose strong { color: var(--text-primary); }
                                    `}} />
                                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(aiAnalysis) }} />
                                </div>
                            ) : (
                                <p className="text-text-secondary text-[10px] md:text-xs italic text-center mt-8 md:mt-10">Run an analysis to see recommendations here.</p>
                            )}
                        </div>
                    </Card>
                </div>

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
                            <button
                                onClick={() => setAuthModal({ ...authModal, isOpen: false })}
                                className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-text-secondary hover:text-text-primary uppercase tracking-widest hover:bg-bg-surface-hover transition-colors cursor-pointer">
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    setAuthModal({ ...authModal, isOpen: false });
                                    authModal.onConfirm();
                                }}
                                className="flex-1 py-3 md:py-4 text-[10px] md:text-xs font-bold text-accent uppercase tracking-widest hover:bg-accent/10 transition-colors border-l border-border cursor-pointer">
                                {authModal.actionName}
                            </button>
                        </div>
                    </Card>
                </div>
            )}

        </main>
    );
}
