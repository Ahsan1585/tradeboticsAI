"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase"; 
import TermsModal from "../components/TermsModal"; 

export default function HubPage() {
    const router = useRouter();
    const [isAuthorized, setIsAuthorized] = useState(false);

    // --- SECURITY GUARD: PREVENT UNAUTHORIZED ACCESS ---
    useEffect(() => {
        const verifyClearance = async () => {
            const { data: { session }, error } = await supabase.auth.getSession();
            
            if (error || !session) {
                console.warn("Security Breach Detected: Unauthorized access attempt.");
                router.push('/'); // Instantly kick them back to login
            } else {
                setIsAuthorized(true); // Grant access
            }
        };

        verifyClearance();
    }, [router]);

    const handleSignOut = async () => {
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            sessionStorage.removeItem(`tos_accepted_${user.id}`);
        }
        await supabase.auth.signOut();
        router.push('/'); 
    };

    // Keep the screen blank/loading while the security check runs
    if (!isAuthorized) {
        return (
            <main className="min-h-screen bg-[#020617] flex items-center justify-center">
                <div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-6" />
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-[#020617] text-slate-300 p-8 flex flex-col relative overflow-hidden">
            
            {/* MANDATORY LEGAL GATE */}
            <TermsModal />

            {/* Subtle Background Glow for a premium terminal feel */}
            <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full bg-blue-900/10 blur-[120px] pointer-events-none"></div>

            <div className="max-w-7xl mx-auto w-full relative z-10">
                
                {/* --- HEADER & BRANDING --- */}
                <div className="flex justify-between items-center mb-16 border-b border-slate-800/50 pb-6">
                    <div className="select-none">
                        <span className="text-4xl font-black tracking-[-0.08em] text-white">
                            TRADEBOTICS<span className="text-blue-500">AI</span>
                        </span>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        {/* System Status Indicator */}
                        <div className="flex items-center gap-3 bg-slate-900/80 border border-slate-800 px-4 py-2 rounded-xl backdrop-blur-md hidden sm:flex">
                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]"></div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Terminal Online</span>
                        </div>

                        {/* Sign Out Button */}
                        <button 
                            onClick={handleSignOut} 
                            className="text-[10px] border border-slate-800 bg-slate-900/80 px-6 py-2.5 rounded-xl font-black uppercase tracking-widest text-slate-400 hover:text-red-500 hover:border-red-500 hover:bg-red-500/10 transition-all backdrop-blur-md shadow-sm"
                        >
                            Sign Out
                        </button>
                    </div>
                </div>

                {/* --- HERO SECTION --- */}
                <div className="mb-20">
                    <h1 className="text-6xl md:text-7xl font-black text-white tracking-tighter mb-6 uppercase">
                        Operative Console
                    </h1>
                    <p className="text-slate-400 max-w-2xl text-lg italic border-l-2 border-blue-500 pl-4">
                        "Welcome to the central interface. Select a module below to initiate real-time market synthesis, analyze algorithmic order flow, or manage your aggregate risk architecture."
                    </p>
                </div>

                {/* --- MODULE LAUNCH GRID --- */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    
                    {/* MODULE 1: INTELLIGENCE TERMINAL (Active - Blue Accent) */}
                    <Link href="/terminal" className="group bg-slate-900/40 border border-slate-800 p-10 rounded-[40px] hover:bg-slate-900/80 hover:border-blue-500/50 transition-all duration-500 flex flex-col relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-b from-blue-600/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        
                        <div className="w-14 h-14 bg-blue-600/20 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform duration-300 border border-blue-500/30 relative z-10">
                            <span className="text-2xl">🌐</span>
                        </div>
                        <h2 className="text-2xl font-black text-white uppercase tracking-widest mb-4 relative z-10">Intelligence Terminal</h2>
                        <p className="text-sm text-slate-400 leading-relaxed mb-8 flex-1 relative z-10">
                            Deep dive algorithmic analysis on individual tickers. Extracts quantitative scores, fundamental DNA, and technical ledgers.
                        </p>
                        <div className="flex items-center gap-2 text-blue-500 text-xs font-black uppercase tracking-widest group-hover:gap-4 transition-all relative z-10">
                            Launch Module <span className="text-lg leading-none">→</span>
                        </div>
                    </Link>

                    {/* MODULE 2: PORTFOLIO VAULT (Active - Purple Accent) */}
                    <Link href="/portfolio" className="group bg-slate-900/40 border border-slate-800 p-10 rounded-[40px] hover:bg-slate-900/80 hover:border-purple-500/50 transition-all duration-500 flex flex-col relative overflow-hidden">
                        <div className="absolute inset-0 bg-gradient-to-b from-purple-600/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        
                        <div className="w-14 h-14 bg-purple-600/20 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform duration-300 border border-purple-500/30 relative z-10">
                            <span className="text-2xl">💼</span>
                        </div>
                        <h2 className="text-2xl font-black text-white uppercase tracking-widest mb-4 relative z-10">Portfolio Vault</h2>
                        <p className="text-sm text-slate-400 leading-relaxed mb-8 flex-1 relative z-10">
                            Comprehensive neural risk management. Synthesize your holdings against live market data to identify institutional rotation opportunities.
                        </p>
                        <div className="flex items-center gap-2 text-purple-500 text-xs font-black uppercase tracking-widest group-hover:gap-4 transition-all relative z-10">
                            Launch Module <span className="text-lg leading-none">→</span>
                        </div>
                    </Link>

                    {/* MODULE 3: PAPER TRADING & LEADERBOARD (Upcoming Enhancement) */}
                    <div className="group bg-slate-900/20 border border-slate-800/50 p-10 rounded-[40px] transition-all duration-300 flex flex-col opacity-60">
                        <div className="w-14 h-14 bg-slate-800/50 rounded-2xl flex items-center justify-center mb-8 border border-slate-700">
                            <span className="text-2xl text-slate-500 grayscale">🏆</span>
                        </div>
                        <h2 className="text-2xl font-black text-slate-500 uppercase tracking-widest mb-4">Paper Trading</h2>
                        <p className="text-sm text-slate-500 leading-relaxed mb-8 flex-1">
                            Upcoming enhancement. Execute risk-free neural strategies, track simulated P&L, and compete on the global operative leaderboard.
                        </p>
                        <div className="flex items-center gap-2 text-slate-600 text-xs font-black uppercase tracking-widest">
                            In Development <span>🚧</span>
                        </div>
                    </div>

                </div>
            </div>
        </main>
    );
}