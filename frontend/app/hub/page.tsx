"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import TermsModal from "../components/TermsModal"; // 🚀 RESTORED IMPORT

export default function HubPage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [virtualCash, setVirtualCash] = useState<number>(0);
  const [tokens, setTokens] = useState<number>(0);
  const [userEmail, setUserEmail] = useState("");
  const [isAuthorized, setIsAuthorized] = useState(false);

  useEffect(() => {
    const loadUserData = async () => {
      const { data: { session }, error } = await supabase.auth.getSession();
      if (error || !session) {
        console.warn("Security Breach Detected: Unauthorized access attempt.");
        router.push("/");
        return;
      }
      
      setIsAuthorized(true);
      setUserEmail(session.user.email || "User");

      // Fetch balances for the header
      const { data: profile } = await supabase
        .from("profiles")
        .select("virtual_cash_balance, ai_token_balance")
        .eq("id", session.user.id)
        .single();

      if (profile) {
        setVirtualCash(profile.virtual_cash_balance);
        setTokens(profile.ai_token_balance);
      }
    };
    
    loadUserData();
  }, [router]);

  const handleScan = () => {
    if (!ticker.trim()) return;
    // Route them directly to the terminal with the ticker pre-loaded
    router.push(`/terminal?ticker=${ticker.toUpperCase()}`);
  };

  const handleSignOut = async () => {
    // 🚀 RESTORED OLD LOGIC: Clear the Terms of Service session storage
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
        sessionStorage.removeItem(`tos_accepted_${user.id}`);
    }
    
    await supabase.auth.signOut();
    router.push("/");
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
    <main className="min-h-screen bg-[#020617] text-slate-300 flex flex-col font-sans relative overflow-x-hidden">
      
      {/* 🚨 MANDATORY LEGAL GATE RESTORED */}
      <TermsModal />
      
      {/* 🚀 REDESIGNED HEADER: Balances moved to top right and minimized */}
      <header className="w-full flex justify-between items-center p-6 border-b border-slate-800/50 bg-[#020617]/80 backdrop-blur-md z-50">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter cursor-pointer" onClick={() => router.push('/hub')}>
            TRADEBOTICS<span className="text-blue-500">AI</span>
          </h1>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="hidden md:flex items-center gap-6 bg-slate-900/50 px-6 py-2 rounded-full border border-slate-800">
            <div className="text-right border-r border-slate-700 pr-6">
              <p className="text-[9px] text-slate-400 uppercase tracking-widest font-bold">Virtual Cash</p>
              <p className="text-sm font-mono font-black text-emerald-400">${virtualCash.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] text-slate-400 uppercase tracking-widest font-bold">AI Tokens</p>
              <p className="text-sm font-mono font-black text-purple-400">{tokens}</p>
            </div>
          </div>
          <button 
            onClick={handleSignOut}
            className="text-[10px] font-black uppercase tracking-widest bg-slate-800/50 hover:bg-slate-800 text-slate-400 hover:text-white px-5 py-2.5 rounded-full transition-colors"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* 🚀 THE HERO SECTION: Massive Search Bar for Immediate Action */}
      <div className="flex flex-col items-center justify-center mt-24 px-4 w-full max-w-4xl mx-auto z-10">
        <div className="text-center mb-10">
          <h2 className="text-5xl md:text-7xl font-black text-white tracking-tighter mb-6 leading-tight">
            Find your next <br className="hidden md:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">winning trade.</span>
          </h2>
          <p className="text-slate-400 text-lg md:text-xl font-medium max-w-2xl mx-auto">
            Type any stock ticker below to get instant, easy-to-understand AI insights and discover hidden market opportunities.
          </p>
        </div>

        <div className="flex w-full bg-[#0B0F19] p-3 rounded-full border-2 border-slate-800 focus-within:border-blue-500/50 shadow-[0_0_40px_rgba(59,130,246,0.1)] transition-all">
          <div className="pl-6 flex items-center justify-center text-slate-500">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input 
            value={ticker} 
            onChange={(e) => setTicker(e.target.value.toUpperCase())} 
            onKeyDown={(e) => e.key === 'Enter' && handleScan()} 
            className="flex-1 bg-transparent border-none text-white font-black px-6 outline-none text-2xl md:text-3xl placeholder:text-slate-700 uppercase" 
            placeholder="e.g. AAPL, TSLA, NVDA" 
          />
          <button 
            onClick={handleScan} 
            className="bg-blue-600 text-white px-8 md:px-14 py-4 md:py-5 rounded-full font-black text-sm md:text-lg uppercase tracking-widest hover:bg-blue-500 transition-all shadow-[0_0_20px_rgba(59,130,246,0.4)]"
          >
            Analyze
          </button>
        </div>
      </div>

      {/* 🚀 SIMPLIFIED RETAIL-FRIENDLY FEATURE CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto mt-24 px-6 pb-24 z-10">
        
        {/* Card 1 */}
        <div 
          onClick={() => router.push('/terminal')}
          className="bg-slate-900/40 border border-slate-800 p-8 rounded-[32px] hover:border-blue-500/40 hover:bg-slate-900/60 transition-all cursor-pointer group"
        >
          <div className="w-14 h-14 bg-blue-500/10 rounded-full flex items-center justify-center text-blue-400 text-2xl mb-6 group-hover:scale-110 transition-transform">
            🔍
          </div>
          <h3 className="text-2xl font-black text-white mb-3">AI Stock Scanner</h3>
          <p className="text-sm text-slate-400 leading-relaxed font-medium">
            Don't guess. Search any stock and let our AI break down the complex data into simple, actionable insights and easy-to-read scores.
          </p>
        </div>

        {/* Card 2 */}
        <div 
          onClick={() => router.push('/portfolio')}
          className="bg-slate-900/40 border border-slate-800 p-8 rounded-[32px] hover:border-purple-500/40 hover:bg-slate-900/60 transition-all cursor-pointer group"
        >
          <div className="w-14 h-14 bg-purple-500/10 rounded-full flex items-center justify-center text-purple-400 text-2xl mb-6 group-hover:scale-110 transition-transform">
            💼
          </div>
          <h3 className="text-2xl font-black text-white mb-3">Smart Portfolio</h3>
          <p className="text-sm text-slate-400 leading-relaxed font-medium">
            Track all your investments in one place. Let our AI monitor your holdings and suggest smart moves to help grow your wealth safely.
          </p>
        </div>

        {/* Card 3: UNLOCKED */}
<div 
  onClick={() => router.push('/vault')}
  className="bg-slate-900/40 border border-slate-800 p-8 rounded-[32px] hover:border-emerald-500/40 hover:bg-slate-900/60 transition-all cursor-pointer group relative overflow-hidden"
>
  <div className="w-14 h-14 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-400 text-2xl mb-6 group-hover:scale-110 transition-transform">
    🎮
  </div>
  <h3 className="text-2xl font-black text-white mb-3">Practice Trading</h3>
  <p className="text-sm text-slate-400 leading-relaxed font-medium">
    Learn the ropes without the risk. Practice buying and selling stocks with virtual money before you invest your real cash.
  </p>
</div>

      </div>

      {/* Decorative Background Glows */}
      <div className="fixed top-1/4 left-1/4 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
      <div className="fixed bottom-1/4 right-1/4 w-[600px] h-[600px] bg-purple-600/5 rounded-full blur-[150px] pointer-events-none mix-blend-screen" />
      
    </main>
  );
}