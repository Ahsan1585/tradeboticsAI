"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export default function PortfolioPage() {
    const router = useRouter();
    
    // Auth & State
    const [isAuthorized, setIsAuthorized] = useState(false);
    const [userId, setUserId] = useState("");
    const [userEmail, setUserEmail] = useState("");
    
    // Portfolio Data
    const [portfolio, setPortfolio] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [toastMessage, setToastMessage] = useState<string | null>(null);

    // Add New Asset State
    const [newTicker, setNewTicker] = useState("");
    const [newShares, setNewShares] = useState("");
    const [newCost, setNewCost] = useState("");
    const [isAdding, setIsAdding] = useState(false);

    // Edit Asset State
    const [editingTicker, setEditingTicker] = useState<string | null>(null);
    const [editShares, setEditShares] = useState("");
    const [editCost, setEditCost] = useState("");

    // AI Analysis State
    const [tradeStyle, setTradeStyle] = useState("Long Term");
    const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // 🚨 NEURAL AUTHORIZATION STATE
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
            }
        };
        verifyClearance();
    }, [router]);

    const showToast = (msg: string) => {
        setToastMessage(msg);
        setTimeout(() => setToastMessage(null), 3500);
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
                shares: pos.total_shares,
                avg_cost: pos.total_shares > 0 ? (pos.total_cost_dollars / pos.total_shares).toFixed(2) : 0
            })).sort((a: any, b: any) => a.ticker.localeCompare(b.ticker));
            
            setPortfolio(formattedVault);
        }
        setLoading(false);
    };

    const handleAddAsset = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newTicker || !newShares || !newCost) return;
        setIsAdding(true);

        const { error } = await supabase.from('portfolio').insert([{
            user_id: userId,
            ticker: newTicker.toUpperCase(),
            shares: parseFloat(newShares),
            cost_basis: parseFloat(newCost)
        }]);

        if (error) {
            showToast("Database Error: " + error.message);
        } else {
            showToast(`${newTicker.toUpperCase()} secured in Vault.`);
            setNewTicker(""); setNewShares(""); setNewCost("");
            fetchPortfolio(userId);
        }
        setIsAdding(false);
    };

    const handleDeleteAsset = async (ticker: string) => {
        const { error } = await supabase.from('portfolio').delete().eq('user_id', userId).eq('ticker', ticker);
        if (error) {
            showToast("Error liquidating asset: " + error.message);
        } else {
            showToast(`${ticker} liquidated from Vault.`);
            fetchPortfolio(userId);
        }
    };

    const handleStartEdit = (item: any) => {
        setEditingTicker(item.ticker);
        setEditShares(item.shares.toString());
        setEditCost(item.avg_cost.toString());
    };

    const handleSaveEdit = async () => {
        if (!editingTicker) return;
        
        await supabase.from('portfolio').delete().eq('user_id', userId).eq('ticker', editingTicker);
        
        const { error } = await supabase.from('portfolio').insert([{
            user_id: userId,
            ticker: editingTicker,
            shares: parseFloat(editShares),
            cost_basis: parseFloat(editCost)
        }]);

        if (error) {
            showToast("Update Error: " + error.message);
        } else {
            showToast(`${editingTicker} parameters updated.`);
            setEditingTicker(null);
            fetchPortfolio(userId);
        }
    };

    const runPortfolioAnalysis = async () => {
        if (portfolio.length === 0) {
            showToast("Vault is empty. Add assets to analyze.");
            return;
        }
        setIsAnalyzing(true);
        setAiAnalysis(null);
        try {
            // 🚨 APPENDED user_id TO URL
            const res = await fetch(`${BACKEND_URL}/portfolio-analysis?user_id=${userId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ holdings: portfolio, trade_style: tradeStyle })
            });
            const result = await res.json();
            
            if (res.ok) {
                setAiAnalysis(result.analysis);
            } else {
                // 🚨 INTERCEPT EMPTY WALLET (402 ERROR)
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

    if (!isAuthorized) return <main className="min-h-screen bg-[#020617] flex items-center justify-center"><div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin" /></main>;

    return (
        <main className="min-h-screen bg-[#020617] text-slate-300 font-sans p-6 md:p-12 relative overflow-x-hidden">
            
            {/* INJECTED GLOBAL SCROLLBAR STYLES */}
            <style dangerouslySetInnerHTML={{__html: `
                .custom-scrollbar::-webkit-scrollbar { width: 6px; }
                .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
            `}} />

            {/* TOAST NOTIFICATION */}
            {toastMessage && (
                <div className="fixed inset-0 z-[150] flex items-center justify-center pointer-events-none">
                <div className="bg-slate-900 border border-blue-500/50 px-10 py-6 rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in zoom-in-95 fade-in duration-300 flex flex-col items-center">
                    <p className="text-white font-black uppercase tracking-widest text-sm text-center">{toastMessage}</p>
                </div>
                </div>
            )}

            {/* HEADER */}
            <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center mb-12 gap-6">
                <div>
                    <h1 className="text-5xl font-black text-white tracking-tighter cursor-pointer hover:text-blue-500 transition-colors" onClick={() => router.push('/hub')}>
                        TRADEBOTICS<span className="text-blue-500">AI</span>
                    </h1>
                    <p className="text-[10px] uppercase tracking-[0.5em] text-slate-400 italic mt-2">Operative Vault // {userEmail.split('@')[0]}</p>
                </div>
                <button onClick={() => router.push('/hub')} className="flex items-center gap-3 px-6 py-3 bg-slate-900/50 border border-slate-800 rounded-full hover:border-blue-500/50 transition-all group">
                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 group-hover:text-white">← Return to Hub</span>
                </button>
            </div>

            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
                
                {/* LEFT PANEL: INVENTORY MANAGEMENT */}
                <div className="lg:col-span-7 flex flex-col gap-8">
                    
                    {/* ASSET ENTRY FORM */}
                    <div className="bg-slate-900/40 border border-slate-800 p-8 rounded-[40px] shadow-2xl">
                        <p className="text-[11px] font-black text-blue-500 uppercase tracking-[0.4em] mb-6">Register Asset</p>
                        <form onSubmit={handleAddAsset} className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 w-full">
                            <input type="text" placeholder="TICKER" value={newTicker} onChange={(e) => setNewTicker(e.target.value)} required className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-4 py-4 text-white font-black outline-none focus:border-blue-500 uppercase" />
                            <input type="number" step="any" placeholder="SHARES" value={newShares} onChange={(e) => setNewShares(e.target.value)} required className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-4 py-4 text-white font-black outline-none focus:border-blue-500" />
                            <input type="number" step="any" placeholder="AVG COST" value={newCost} onChange={(e) => setNewCost(e.target.value)} required className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-4 py-4 text-white font-black outline-none focus:border-blue-500" />
                            <button type="submit" disabled={isAdding} className="w-full bg-blue-600 hover:bg-blue-500 text-white px-8 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest transition-all">
                                {isAdding ? "..." : "ADD"}
                            </button>
                        </form>
                    </div>

                    {/* CURRENT INVENTORY LEDGER */}
                    <div className="bg-slate-900/40 border border-slate-800 p-8 rounded-[40px] shadow-2xl min-h-[400px]">
                        <div className="flex justify-between items-center mb-6 border-b border-slate-800/50 pb-4">
                            <p className="text-[11px] font-black text-slate-400 uppercase tracking-[0.4em]">Current Inventory</p>
                            <span className="text-[10px] bg-slate-800 text-slate-400 px-3 py-1 rounded-full font-bold uppercase">{portfolio.length} Assets</span>
                        </div>

                        {loading ? (
                            <div className="flex justify-center items-center h-40"><div className="w-8 h-8 border-2 border-slate-800 border-t-blue-500 rounded-full animate-spin" /></div>
                        ) : portfolio.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-40 text-slate-600">
                                <span className="text-4xl mb-2">💼</span>
                                <p className="font-bold uppercase tracking-widest text-[10px]">Vault is Empty</p>
                            </div>
                        ) : (
                            <div className="space-y-3 overflow-y-auto max-h-[500px] pr-2 custom-scrollbar">
                                {portfolio.map((item, i) => (
                                    <div key={i} className="bg-slate-950 border border-slate-800 p-5 rounded-3xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 group hover:border-slate-700 transition-all">
                                        
                                        {/* Display Mode vs Edit Mode */}
                                        {editingTicker === item.ticker ? (
                                            <div className="flex-1 flex flex-col sm:flex-row gap-3">
                                                <div className="w-24 bg-slate-900 flex items-center justify-center rounded-xl border border-slate-800"><span className="font-black text-white">{item.ticker}</span></div>
                                                <input type="number" step="any" value={editShares} onChange={(e) => setEditShares(e.target.value)} className="w-full sm:w-24 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white font-black text-sm outline-none focus:border-blue-500" placeholder="Shares" />
                                                <input type="number" step="any" value={editCost} onChange={(e) => setEditCost(e.target.value)} className="w-full sm:w-32 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white font-black text-sm outline-none focus:border-blue-500" placeholder="Avg Cost" />
                                                <div className="flex gap-2">
                                                    <button onClick={handleSaveEdit} className="bg-emerald-500/20 text-emerald-500 hover:bg-emerald-500 hover:text-white px-4 rounded-xl font-black text-[10px] uppercase transition-all">Save</button>
                                                    <button onClick={() => setEditingTicker(null)} className="bg-slate-800 text-slate-400 hover:text-white px-4 rounded-xl font-black text-[10px] uppercase transition-all">Cancel</button>
                                                </div>
                                            </div>
                                        ) : (
                                            <>
                                                <div className="flex items-center gap-6">
                                                    <div className="w-16 h-16 bg-slate-900 rounded-2xl flex items-center justify-center border border-slate-800 shrink-0">
                                                        <span className="font-black text-white text-xl">{item.ticker}</span>
                                                    </div>
                                                    <div>
                                                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Total Shares</p>
                                                        <p className="text-xl font-black text-white">{item.shares}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Avg Cost</p>
                                                        <p className="text-xl font-black text-white">${item.avg_cost}</p>
                                                    </div>
                                                </div>
                                                
                                                <div className="flex items-center gap-2 opacity-100 sm:opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button onClick={() => handleStartEdit(item)} className="px-4 py-2 bg-slate-800 hover:bg-blue-600 text-slate-400 hover:text-white rounded-xl font-black text-[10px] uppercase tracking-widest transition-all">Modify</button>
                                                    <button onClick={() => handleDeleteAsset(item.ticker)} className="px-4 py-2 bg-slate-800 hover:bg-red-500/20 text-slate-400 hover:text-red-500 border hover:border-red-500 border-transparent rounded-xl font-black text-[10px] uppercase tracking-widest transition-all">Liquidate</button>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* RIGHT PANEL: AI ANALYSIS ENGINE */}
                <div className="lg:col-span-5 flex flex-col gap-8">
                    <div className="bg-[#020617] border border-purple-500/30 p-8 rounded-[40px] shadow-[inset_0_0_30px_rgba(168,85,247,0.05)] h-full flex flex-col">
                        <div className="flex items-center gap-3 mb-8">
                            <div className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-pulse" />
                            <p className="text-[11px] font-black uppercase tracking-[0.4em] text-purple-500">Neural Portfolio Synthesis</p>
                        </div>

                        <div className="mb-8">
                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Target Horizon Profile</p>
                            <div className="flex flex-wrap gap-2">
                                {["Day Trade", "Swing Trade", "Long Term"].map(style => (
                                    <button 
                                        key={style} 
                                        onClick={() => setTradeStyle(style)}
                                        className={`px-4 py-2 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all ${tradeStyle === style ? 'bg-purple-600 text-white border border-purple-500' : 'bg-slate-900 border border-slate-800 text-slate-500 hover:text-white'}`}
                                    >
                                        {style}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 🚨 TRIGGER AUTH MODAL FOR PORTFOLIO SCAN (5 TOKENS) */}
                        <button 
                            onClick={() => setAuthModal({
                                isOpen: true,
                                title: "Portfolio Rotation Matrix",
                                cost: 5,
                                actionName: "AUTHORIZE ROTATION",
                                onConfirm: runPortfolioAnalysis
                            })}
                            disabled={isAnalyzing || portfolio.length === 0}
                            className="w-full bg-purple-600 border border-purple-500 hover:bg-purple-500 py-4 rounded-2xl text-white font-black text-[10px] uppercase tracking-widest transition-all shadow-[0_0_25px_rgba(168,85,247,0.5)] disabled:opacity-50 disabled:bg-purple-600/20 disabled:text-purple-400 mb-8"
                        >
                            {isAnalyzing ? "Processing Matrix..." : "Execute Rotation Scan"}
                        </button>

                        <div className="flex-1 bg-slate-950 border border-slate-800 rounded-3xl p-6 overflow-y-auto custom-scrollbar relative">
                            {isAnalyzing ? (
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <div className="w-8 h-8 border-2 border-slate-800 border-t-purple-500 rounded-full animate-spin mb-4" />
                                    <p className="text-[9px] text-purple-500 uppercase font-black tracking-widest animate-pulse">Calculating Alpha...</p>
                                </div>
                            ) : aiAnalysis ? (
                                <div className="prose prose-invert max-w-none text-sm font-medium leading-relaxed">
                                    <style dangerouslySetInnerHTML={{__html: `
                                        .prose h3 { color: #a855f7; font-size: 12px; text-transform: uppercase; letter-spacing: 0.2em; font-weight: 900; margin-top: 1.5rem; margin-bottom: 0.5rem; }
                                        .prose ul { list-style-type: none; padding: 0; }
                                        .prose li { position: relative; padding-left: 1.5rem; margin-bottom: 0.5rem; color: #cbd5e1; }
                                        .prose li::before { content: "→"; position: absolute; left: 0; color: #a855f7; font-weight: 900; }
                                        .prose strong { color: #fff; }
                                    `}} />
                                    <div dangerouslySetInnerHTML={{ __html: aiAnalysis.replace(/\n/g, '<br/>') }} />
                                </div>
                            ) : (
                                <p className="text-slate-600 text-xs italic text-center mt-10">Analysis offline. Awaiting execution command.</p>
                            )}
                        </div>
                    </div>
                </div>

            </div>

            {/* 🚨 NEURAL AUTHORIZATION MODAL */}
            {authModal.isOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/90 backdrop-blur-md">
                    <div className="bg-[#0B0F19] border border-red-900/50 rounded-xl shadow-[0_0_40px_rgba(220,38,38,0.15)] w-full max-w-sm overflow-hidden relative">
                        
                        <div className="p-4 border-b border-red-900/30 bg-red-950/20 flex items-center gap-3">
                            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>
                            <h2 className="text-xs font-bold text-red-500 uppercase tracking-[0.2em]">Bandwidth Authorization Required</h2>
                        </div>

                        <div className="p-6 text-center space-y-4">
                            <p className="text-sm text-slate-300 font-mono">
                                Executing the <span className="text-white font-bold">{authModal.title}</span> protocol will consume standard neural bandwidth.
                            </p>
                            
                            <div className="py-4 bg-slate-900/50 rounded-lg border border-slate-800 flex flex-col items-center justify-center">
                                <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Compute Cost</p>
                                <p className="text-3xl font-mono text-purple-400 font-bold">-{authModal.cost} TOKENS</p>
                            </div>
                        </div>

                        <div className="flex border-t border-slate-800">
                            <button 
                                onClick={() => setAuthModal({ ...authModal, isOpen: false })}
                                className="flex-1 py-4 text-xs font-bold text-slate-500 hover:text-white uppercase tracking-widest hover:bg-slate-800/50 transition-colors">
                                Abort
                            </button>
                            <button 
                                onClick={() => {
                                    setAuthModal({ ...authModal, isOpen: false });
                                    authModal.onConfirm(); 
                                }}
                                className="flex-1 py-4 text-xs font-bold text-red-400 hover:text-red-300 uppercase tracking-widest hover:bg-red-950/30 transition-colors border-l border-slate-800">
                                {authModal.actionName}
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </main>
    );
}