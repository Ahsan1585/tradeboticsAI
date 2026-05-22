"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";

// Pointing to your local backend for testing. 
// Change to "https://tradebotics-api.onrender.com" when deploying.
const BACKEND_URL = "https://tradebotics-api.onrender.com";

export default function PortfolioPage() {
    const router = useRouter();
    
    // Auth & Security State
    const [isAuthorized, setIsAuthorized] = useState(false);

    // Data State
    const [holdings, setHoldings] = useState<any[]>([]);
    const [analysis, setAnalysis] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    
    // Form & Strategy State
    const [ticker, setTicker] = useState("");
    const [shares, setShares] = useState("");
    const [cost, setCost] = useState("");
    const [tradeStyle, setTradeStyle] = useState("Long Term");

    // --- SECURITY GUARD ---
    useEffect(() => {
        const verifyClearance = async () => {
            const { data: { session }, error } = await supabase.auth.getSession();
            
            if (error || !session) {
                console.warn("Unauthorized access attempt. Redirecting to gateway.");
                router.push('/'); 
            } else {
                setIsAuthorized(true); 
                fetchHoldings(session.user.id);
            }
        };

        verifyClearance();
    }, [router]);

    const fetchHoldings = async (userId: string) => {
        setLoading(true);
        const { data } = await supabase.from('portfolio').select('*').eq('user_id', userId);
        if (data) setHoldings(data);
        setLoading(false);
    };

    const addAsset = async () => {
        if (!ticker || !shares || !cost) return;
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;
        await supabase.from('portfolio').insert([{ user_id: user.id, ticker, shares, cost_basis: cost }]);
        setTicker(""); setShares(""); setCost("");
        fetchHoldings(user.id);
    };

    const runPortfolioAnalysis = async () => {
        if (holdings.length === 0) {
            setAnalysis("Vault is empty. Add assets to begin neural risk management.");
            return;
        }
        
        setIsAnalyzing(true);
        try {
            console.log(`DEBUG: Fetching ${BACKEND_URL}/portfolio-analysis for ${tradeStyle}`);
            const res = await fetch(`${BACKEND_URL}/portfolio-analysis`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ holdings, trade_style: tradeStyle }) 
            });
            
            if (!res.ok) {
                const errorData = await res.text();
                console.error("Backend Error:", errorData);
                throw new Error(errorData);
            }
            
            const data = await res.json();
            setAnalysis(data.analysis || "Analysis complete but no data returned.");
        } catch (e: any) { 
            console.error("CRITICAL ERROR:", e);
            setAnalysis(`System Error: ${e.message}`);
        }
        setIsAnalyzing(false);
    };

    // --- LOADING INTERCEPT ---
    // This MUST be right here, before the main return, to prevent the UI flash
    if (!isAuthorized) {
        return (
            <main className="min-h-screen bg-[#020617] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-16 h-16 border-4 border-slate-800 border-t-purple-500 rounded-full animate-spin" />
                    <p className="text-[10px] text-purple-500 font-black uppercase tracking-widest animate-pulse">Verifying Clearance...</p>
                </div>
            </main>
        );
    }

    // --- MAIN DASHBOARD RENDER ---
    return (
        <main className="min-h-screen bg-[#020617] text-slate-300 p-8 flex flex-col relative">
            
            {/* INJECTED STYLES FOR THEME-MATCHED SCROLLBAR */}
            <style dangerouslySetInnerHTML={{__html: `
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: #0f172a; 
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #334155; 
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: #475569; 
                }
            `}} />

            {/* Subtle Purple Background Glow */}
            <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full bg-purple-900/10 blur-[120px] pointer-events-none"></div>

            <div className="max-w-7xl mx-auto w-full relative z-10">
                
                {/* TOP NAVIGATION / HUB LINK ONLY */}
                <div className="flex justify-between items-center mb-12 border-b border-slate-800/50 pb-6">
                    <div className="select-none">
                        <span className="text-4xl font-black tracking-[-0.08em] text-white">
                            TRADEBOTICS<span className="text-blue-500">AI</span>
                        </span>
                    </div>
                    <Link href="/hub" className="text-[10px] font-black text-slate-400 hover:text-white uppercase tracking-widest transition-colors flex items-center gap-2 bg-slate-900 px-6 py-3 rounded-xl border border-slate-800 hover:border-slate-600 shadow-sm">
                        <span>←</span> Return to Hub
                    </Link>
                </div>

                {/* --- HERO SECTION --- */}
                <div className="mb-12">
                    <h1 className="text-5xl font-black text-white tracking-tighter mb-4 uppercase">PORTFOLIO VAULT</h1>
                    <p className="text-slate-400 max-w-xl text-lg italic border-l-2 border-purple-500 pl-4">
                        "Your aggregate exposure is constantly shifting. This module synthesizes your holdings against live market data to identify rotation opportunities and institutional-grade risk profiles."
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    
                    {/* LEFT COLUMN: MANAGEMENT */}
                    <div className="lg:col-span-1 space-y-8">
                        <div className="bg-slate-900/40 border border-slate-800 p-8 rounded-[40px] shadow-2xl">
                            <h2 className="text-[11px] font-black text-white uppercase tracking-widest mb-6">Vault Management</h2>
                            <div className="space-y-4">
                                <input placeholder="TICKER" className="w-full bg-slate-950 border border-slate-800 p-4 rounded-2xl outline-none focus:border-purple-500 text-white font-bold transition-colors" onChange={(e) => setTicker(e.target.value.toUpperCase())} value={ticker}/>
                                <input placeholder="SHARES" className="w-full bg-slate-950 border border-slate-800 p-4 rounded-2xl outline-none focus:border-purple-500 text-white font-bold transition-colors" onChange={(e) => setShares(e.target.value)} value={shares}/>
                                <input placeholder="AVG COST" className="w-full bg-slate-950 border border-slate-800 p-4 rounded-2xl outline-none focus:border-purple-500 text-white font-bold transition-colors" onChange={(e) => setCost(e.target.value)} value={cost}/>
                                <button onClick={addAsset} className="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-4 rounded-2xl uppercase tracking-widest text-[10px] transition-all shadow-[0_0_15px_rgba(147,51,234,0.3)]">Register Asset</button>
                            </div>
                        </div>

                        <div className="bg-slate-900/40 border border-slate-800 p-8 rounded-[40px] shadow-2xl">
                            <h2 className="text-[11px] font-black text-white uppercase tracking-widest mb-6">Current Inventory</h2>
                            <div className="space-y-2 max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
                                {holdings.map((h, i) => (
                                    <div key={i} className="flex justify-between items-center bg-slate-950 p-4 rounded-2xl border border-slate-800 group hover:border-purple-500/50 transition-colors">
                                        <span className="font-black text-white group-hover:text-purple-400 transition-colors">{h.ticker}</span>
                                        <span className="text-[10px] font-bold text-slate-500">{h.shares} @ ${h.cost_basis}</span>
                                    </div>
                                ))}
                                {holdings.length === 0 && !loading ? (
                                    <p className="text-slate-600 text-xs text-center font-bold uppercase tracking-widest mt-4">Vault is empty.</p>
                                ) : null}
                            </div>
                        </div>
                    </div>

                    {/* RIGHT COLUMN: AI INTELLIGENCE */}
                    <div className="lg:col-span-2 bg-slate-900/40 border border-slate-800 p-10 rounded-[40px] shadow-2xl flex flex-col">
                        <div className="flex justify-between items-center mb-10">
                            <div className="flex items-center gap-4">
                                <h2 className="text-[11px] font-black text-white uppercase tracking-widest">Neural Risk Synthesis</h2>
                                <select 
                                    value={tradeStyle}
                                    onChange={(e) => setTradeStyle(e.target.value)}
                                    className="bg-slate-950 border border-slate-700 text-slate-300 text-[10px] font-bold uppercase rounded-lg px-3 py-1.5 outline-none focus:border-purple-500 cursor-pointer transition-colors"
                                >
                                    <option value="Day Trade">Day Trade</option>
                                    <option value="Swing Trade">Swing Trade</option>
                                    <option value="Long Term">Long Term</option>
                                </select>
                            </div>
                            <button 
                                onClick={runPortfolioAnalysis} 
                                disabled={isAnalyzing || holdings.length === 0} 
                                className="bg-purple-600 px-8 py-3 rounded-xl text-[10px] font-black text-white hover:bg-purple-500 disabled:opacity-50 transition-all shadow-[0_0_15px_rgba(147,51,234,0.3)]"
                            >
                                {isAnalyzing ? "SYNTHESIZING..." : "INITIATE RISK ANALYSIS"}
                            </button>
                        </div>
                        
                        <div className="flex-1 bg-slate-950 p-8 rounded-3xl border border-slate-800 overflow-y-auto custom-scrollbar min-h-[500px] pr-4">
                            {analysis ? (
                                <div className="text-slate-300 leading-relaxed whitespace-pre-wrap max-w-none font-medium">
                                    {analysis}
                                </div>
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center text-slate-600 text-center">
                                    <span className="text-4xl mb-4 grayscale opacity-50">🛡️</span>
                                    <p className="font-black uppercase tracking-widest text-xs">Terminal Standby</p>
                                    <p className="text-[10px] mt-2 max-w-xs font-bold leading-relaxed">Add assets to your inventory and initiate analysis to receive your multi-factor portfolio risk assessment.</p>
                                </div>
                            )}
                        </div>

                        {/* HIGH-VISIBILITY LEGAL DISCLAIMER */}
                        <div className="mt-6 bg-[#0f172a] border border-slate-700/50 p-4 rounded-xl flex items-center justify-center gap-3 shadow-inner">
                            <span className="text-amber-500 text-lg">⚠️</span>
                            <p className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
                                Intelligence provided for educational purposes only. Not financial advice.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            
            <footer className="border-t border-slate-800/50 py-8 text-center w-full mt-auto relative z-10">
                <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
            </footer>
        </main>
    );
}