"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import TradeTicket from "../components/TradeTicket";

const BACKEND_URL = "https://tradebotics-api.onrender.com";

// --- DYNAMIC CHART COMPONENT ---
function PortfolioChart({ totalValue, totalProfitLoss }: { totalValue: number, totalProfitLoss: number }) {
  const [timeframe, setTimeframe] = useState("1M");
  const timeframes = ["1D", "1W", "1M", "1Y", "ALL"];
  
  const isNeutral = totalProfitLoss === 0;
  const isProfit = totalProfitLoss > 0;
  const isLoss = totalProfitLoss < 0;

  let colorClass = "text-blue-500";
  let arrow = "→";
  let sign = "";
  let strokeColor = "#3b82f6"; 
  let gradientStart = "rgba(59, 130, 246, 0.3)";
  let gradientEnd = "rgba(59, 130, 246, 0)";
  let fillPath = "M0,250 L0,150 L1000,150 L1000,250 Z"; // Flat Line
  let strokePath = "M0,150 L1000,150";

  if (isProfit) {
      colorClass = "text-emerald-400";
      arrow = "↗";
      sign = "+";
      strokeColor = "#10b981";
      gradientStart = "rgba(16, 185, 129, 0.3)";
      gradientEnd = "rgba(16, 185, 129, 0)";
      fillPath = "M0,250 L0,180 L200,170 L400,130 L600,140 L800,80 L1000,60 L1000,250 Z"; 
      strokePath = "M0,180 L200,170 L400,130 L600,140 L800,80 L1000,60";
  } else if (isLoss) {
      colorClass = "text-rose-400";
      arrow = "↘";
      sign = "-";
      strokeColor = "#e11d48";
      gradientStart = "rgba(225, 29, 72, 0.3)";
      gradientEnd = "rgba(225, 29, 72, 0)";
      fillPath = "M0,250 L0,60 L200,80 L400,140 L600,130 L800,170 L1000,180 L1000,250 Z"; 
      strokePath = "M0,60 L200,80 L400,140 L600,130 L800,170 L1000,180";
  }

  return (
    <div className="bg-[#0B0F19] border border-slate-800 rounded-[40px] p-8 shadow-2xl relative overflow-hidden transition-all duration-500 h-full flex flex-col">
      <div 
        className="absolute top-0 left-0 w-full h-full opacity-30 pointer-events-none transition-all duration-500" 
        style={{ background: `linear-gradient(to bottom, ${gradientStart}, transparent)` }} 
      />
      
      <div className="flex justify-between items-start mb-8 relative z-10">
        <div>
          <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Net Liquidation Value</p>
          <h2 className="text-4xl lg:text-5xl font-black text-white tracking-tighter">${totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</h2>
          <p className={`text-sm font-bold ${colorClass} mt-2 flex items-center gap-1 transition-colors duration-500`}>
            <span className="text-lg leading-none">{arrow}</span> {sign}${Math.abs(totalProfitLoss).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} (All Time)
          </p>
        </div>
        
        <div className="hidden sm:flex gap-1 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
          {timeframes.map(tf => (
            <button 
              key={tf} 
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-2 rounded-lg text-[9px] font-black tracking-widest transition-all ${timeframe === tf ? "bg-slate-700 text-white" : "text-slate-500 hover:text-slate-300"}`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      <div className="w-full flex-1 relative z-10 flex items-end min-h-[250px]">
        <svg viewBox="0 0 1000 250" className="w-full h-full preserve-3d transition-all duration-500" preserveAspectRatio="none">
          <defs>
            <linearGradient id="chartGradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={gradientStart} />
              <stop offset="100%" stopColor={gradientEnd} />
            </linearGradient>
          </defs>
          <path d={fillPath} fill="url(#chartGradient)" className="transition-all duration-700 ease-in-out" />
          <path d={strokePath} fill="none" stroke={strokeColor} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" className="transition-all duration-700 ease-in-out" />
        </svg>
      </div>
    </div>
  );
}

export default function VaultPage() {
  const router = useRouter();
  
  // 🚀 Added search state back
  const [searchTicker, setSearchTicker] = useState("");
  
  const [userEmail, setUserEmail] = useState("");
  const [virtualCash, setVirtualCash] = useState(0);
  const [tokens, setTokens] = useState(0);
  const [isAuthorized, setIsAuthorized] = useState(false);
  
  const [holdings, setHoldings] = useState<any[]>([]);
  const [liveData, setLiveData] = useState<any>({});
  const [loading, setLoading] = useState(true);
  
  const [selectedAsset, setSelectedAsset] = useState<any | null>(null);
  const [showTradeTicket, setShowTradeTicket] = useState(false);
  const [tradeType, setTradeType] = useState<"BUY" | "SELL">("BUY");
  
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // 🚀 Search Execution Handler
  const handleSearch = () => {
    if (!searchTicker.trim()) return;
    router.push(`/terminal?ticker=${searchTicker.trim().toUpperCase()}`);
  };

  const loadPortfolio = async () => {
    setLoading(true);
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error || !session) {
      router.push("/");
      return;
    }
    
    setIsAuthorized(true);
    setUserEmail(session.user.email || "Operative");

    const { data: profile } = await supabase.from("profiles").select("virtual_cash_balance, ai_token_balance").eq("id", session.user.id).single();
    if (profile) {
      setVirtualCash(profile.virtual_cash_balance);
      setTokens(profile.ai_token_balance);
    }

    const { data: portfolioData } = await supabase.from("portfolio").select("*").eq("user_id", session.user.id);
    if (portfolioData) {
      setHoldings(portfolioData);
      
      const liveUpdates: any = {};
      // 🚀 FRONTEND OPTIMIZATION: Stagger the requests to prevent hitting the Yahoo/Backend rate limit
      for (const item of portfolioData) {
        try {
          const res = await fetch(`${BACKEND_URL}/analyze/${item.ticker}?user_id=${session.user.id}`);
          if (res.ok) {
            liveUpdates[item.ticker] = await res.json();
          }
          // Wait 250ms between each asset request
          await new Promise(resolve => setTimeout(resolve, 250));
        } catch (e) {
          console.warn(`Failed to fetch live data for ${item.ticker}`);
        }
      }
      setLiveData(liveUpdates);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadPortfolio();
  }, [router]);

  const handleExecuteTrade = async (type: "BUY" | "SELL", amount: number, mode: "DOLLARS" | "SHARES") => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session || !selectedAsset) return;

    try {
        const res = await fetch(`${BACKEND_URL}/execute-trade`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: session.user.id, ticker: selectedAsset.ticker, trade_type: type, amount: amount, mode: mode })
        });
        const result = await res.json();
        
        if (res.ok) { 
            showToast(result.message); 
            setShowTradeTicket(false);

            // 🚀 1. OPTIMISTIC CASH UPDATE: Instantly set virtual cash to the exact number the backend just calculated
            if (result.remaining_cash !== undefined) {
                setVirtualCash(result.remaining_cash);
            }

            // 🚀 2. OPTIMISTIC VAULT UPDATE: Instantly adjust the shares in the UI grid
            setHoldings(prev => prev.map(h => {
                if (h.ticker === selectedAsset.ticker) {
                    // Calculate exact shares executed
                    const executedShares = mode === "SHARES" ? amount : (amount / result.execution_price);
                    return {
                        ...h,
                        shares: type === "SELL" ? h.shares - executedShares : h.shares + executedShares
                    };
                }
                return h;
            }).filter(h => h.shares > 0.0001)); // Instantly remove the card if shares hit 0

            // 3. Clear selected asset drawer if fully sold
            if (type === "SELL" && mode === "SHARES" && amount === selectedAsset.shares) {
                setSelectedAsset(null); 
            }
            
            // 4. Background Sync: Silently re-sync with Supabase 1.5 seconds later to ensure total alignment
            setTimeout(() => {
                loadPortfolio(); 
            }, 1500);

        } 
        else { showToast(`Trade Error: ${result.detail}`); }
    } catch (error) { showToast("Execution Offline."); }
  };

  const calculateTotals = () => {
    let totalStockValue = 0;
    let totalCostBasis = 0;

    holdings.forEach(h => {
        const currentPrice = liveData[h.ticker]?.price || h.cost_basis;
        totalStockValue += (h.shares * currentPrice);
        totalCostBasis += (h.shares * h.cost_basis);
    });

    const netAccountValue = virtualCash + totalStockValue;
    const totalProfitLoss = Number((totalStockValue - totalCostBasis).toFixed(2));

    return { totalStockValue, totalCostBasis, netAccountValue, totalProfitLoss };
  };

  const { totalStockValue, totalCostBasis, netAccountValue, totalProfitLoss } = calculateTotals();

  if (!isAuthorized || loading) {
    return <main className="min-h-screen bg-[#020617] flex items-center justify-center"><div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin" /></main>;
  }

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 flex flex-col font-sans relative overflow-x-hidden pb-20">
      
      {toastMessage && (
        <div className="fixed top-24 left-1/2 -translate-x-1/2 z-[150] pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-8 py-4 rounded-full shadow-2xl animate-in slide-in-from-top-4 fade-in flex items-center gap-3">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <p className="text-white font-black uppercase tracking-widest text-xs">{toastMessage}</p>
           </div>
        </div>
      )}

      {/* HEADER */}
      <header className="w-full flex justify-between items-center p-6 border-b border-slate-800/50 bg-[#020617]/80 backdrop-blur-md z-50 sticky top-0">
        <h1 className="text-3xl font-black text-white tracking-tighter cursor-pointer" onClick={() => router.push('/hub')}>
            TRADEBOTICS<span className="text-blue-500">AI</span>
        </h1>
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
          <button onClick={() => router.push('/hub')} className="text-[10px] font-black uppercase tracking-widest bg-slate-800/50 hover:bg-slate-800 text-slate-400 hover:text-white px-5 py-2.5 rounded-full transition-colors">
            Hub
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto w-full px-6 mt-12 flex flex-col gap-12">
        
        {/* 🚀 PROMINENT HERO SEARCH BAR */}
        <div className="flex w-full bg-[#0B0F19] p-3 rounded-full border border-slate-800 focus-within:border-blue-500/50 shadow-xl transition-all group">
          <div className="pl-6 flex items-center justify-center text-slate-600 group-focus-within:text-blue-500 transition-colors">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input 
            value={searchTicker} 
            onChange={(e) => setSearchTicker(e.target.value)} 
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()} 
            className="flex-1 bg-transparent border-none text-white font-black px-6 outline-none text-xl uppercase placeholder:text-slate-700 placeholder:normal-case placeholder:font-medium" 
            placeholder="Search assets to deploy your virtual cash..." 
          />
          <button 
            onClick={handleSearch} 
            className="bg-blue-600 text-white px-10 py-4 rounded-full font-black text-[10px] uppercase tracking-widest hover:bg-blue-500 shadow-[0_0_20px_rgba(37,99,235,0.3)] hover:shadow-[0_0_30px_rgba(37,99,235,0.5)] transition-all"
          >
            SCAN & BUY
          </button>
        </div>

        {/* 🚀 2-COLUMN HERO SECTION */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            {/* Left: The Chart */}
            <div className="lg:col-span-8">
                <PortfolioChart totalValue={netAccountValue} totalProfitLoss={totalProfitLoss} />
            </div>

            {/* Right: The Breakdown Panels */}
            <div className="lg:col-span-4 flex flex-col gap-6">
                
                {/* Panel 1: Purchasing Power & Assets */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-[40px] p-8 flex-1 flex flex-col justify-center relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-[40px] pointer-events-none" />
                    
                    <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6 border-b border-slate-800/50 pb-4">Account Breakdown</h3>
                    
                    <div className="space-y-6">
                        <div className="flex justify-between items-end">
                            <div>
                                <p className="text-[9px] font-bold text-slate-400 uppercase mb-1">Purchasing Power (Cash)</p>
                                <p className="text-2xl font-mono font-black text-emerald-400">${virtualCash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                            </div>
                        </div>

                        <div className="flex justify-between items-end border-t border-slate-800/50 pt-6">
                            <div>
                                <p className="text-[9px] font-bold text-slate-400 uppercase mb-1">Invested Assets (Market Value)</p>
                                <p className="text-xl font-mono font-black text-white">${totalStockValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Panel 2: AI Pulse / Stats */}
                <div className="bg-[#020617] border border-blue-500/20 rounded-[40px] p-8 shadow-[inset_0_0_20px_rgba(59,130,246,0.05)]">
                     <div className="flex items-center gap-3 mb-6">
                         <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                         <h3 className="text-[10px] font-black text-blue-500 uppercase tracking-[0.3em]">AI Portfolio Pulse</h3>
                     </div>
                     <div className="grid grid-cols-2 gap-4">
                         <div>
                             <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Active Positions</p>
                             <p className="text-2xl font-black text-white">{holdings.length}</p>
                         </div>
                         <div>
                             <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Largest Holding</p>
                             <p className="text-xl font-black text-white">
                                {holdings.length > 0 ? holdings.reduce((prev, current) => ((current.shares * (liveData[current.ticker]?.price || current.cost_basis)) > (prev.shares * (liveData[prev.ticker]?.price || prev.cost_basis))) ? current : prev).ticker : "N/A"}
                             </p>
                         </div>
                     </div>
                </div>

            </div>
        </div>

        {/* HOLDINGS GRID */}
        <div>
            <h3 className="text-2xl font-black text-white uppercase tracking-widest mb-6 border-b border-slate-800 pb-4">Current Holdings</h3>
            
            {holdings.length === 0 ? (
                <div className="bg-slate-900/30 border border-slate-800 p-12 rounded-[32px] text-center">
                    <p className="text-slate-500 font-bold uppercase tracking-widest">Your vault is empty.</p>
                    <button onClick={() => router.push('/terminal')} className="mt-6 bg-blue-600 text-white px-8 py-3 rounded-full font-black text-[10px] uppercase tracking-widest hover:bg-blue-500 transition-colors">Find Assets</button>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {holdings.map((h: any, i: number) => {
                        const live = liveData[h.ticker];
                        const currentPrice = live ? live.price : h.cost_basis;
                        const totalCost = h.shares * h.cost_basis;
                        const totalMarketValue = h.shares * currentPrice;
                        const profitLoss = Number((totalMarketValue - totalCost).toFixed(2));
                        
                        const percentReturn = totalCost > 0 ? ((profitLoss / totalCost) * 100) : 0;
                        const isNeutral = profitLoss === 0;
                        const isProfit = profitLoss > 0;
                        
                        let cardColorClass = "text-blue-500 bg-blue-500/10";
                        if (isProfit) cardColorClass = "text-emerald-400 bg-emerald-500/10";
                        else if (!isNeutral) cardColorClass = "text-rose-400 bg-rose-500/10";

                        return (
                            <div 
                                key={i} 
                                onClick={() => setSelectedAsset(h)}
                                className="bg-slate-900/40 border border-slate-800 p-6 rounded-[32px] hover:border-blue-500/50 hover:bg-slate-900/80 transition-all cursor-pointer group relative overflow-hidden"
                            >
                                <div className="flex justify-between items-start mb-6">
                                    <div>
                                        <h4 className="text-3xl font-black text-white">{h.ticker}</h4>
                                        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">{h.shares.toFixed(2)} Shares</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-xl font-mono font-black text-white">${totalMarketValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                                    </div>
                                </div>
                                
                                <div className="flex justify-between items-end border-t border-slate-800/50 pt-4">
                                    <div>
                                        <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Total Return</p>
                                        <p className={`text-sm font-mono font-black px-2 py-0.5 rounded-md ${cardColorClass}`}>
                                            {isProfit ? '+' : ''}${profitLoss.toFixed(2)}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Return %</p>
                                        <p className={`text-sm font-mono font-black ${cardColorClass} px-2 py-0.5 rounded-md`}>
                                            {isProfit ? '+' : ''}{percentReturn.toFixed(2)}%
                                        </p>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
      </div>

      {/* 🚨 ASSET DETAILS MODAL (DRAWER) */}
      {selectedAsset && (
          <div className="fixed inset-0 z-[100] flex items-center justify-end bg-[#020617]/80 backdrop-blur-sm transition-all animate-in fade-in">
              <div className="w-full max-w-xl h-full bg-[#0B0F19] border-l border-slate-800 flex flex-col shadow-2xl animate-in slide-in-from-right-full duration-300">
                  
                  {/* Modal Header */}
                  <div className="p-8 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 shrink-0">
                      <div>
                          <div className="flex items-center gap-3 mb-2"><div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" /><p className="text-[10px] font-black uppercase text-blue-500 tracking-widest">Asset Details</p></div>
                          <h2 className="text-4xl font-black text-white">{selectedAsset.ticker}</h2>
                          <p className="text-xs font-bold text-slate-500 mt-1 uppercase tracking-widest">{liveData[selectedAsset.ticker]?.company_name || 'Loading Profile...'}</p>
                      </div>
                      <button onClick={() => setSelectedAsset(null)} className="w-10 h-10 bg-slate-800 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 transition-colors">✕</button>
                  </div>

                  <div className="flex-1 overflow-y-auto p-8 custom-scrollbar space-y-8">
                      
                      {/* Performance Metrics */}
                      <div className="grid grid-cols-2 gap-4">
                        {(() => {
                            const live = liveData[selectedAsset.ticker];
                            const currentPrice = live ? live.price : selectedAsset.cost_basis;
                            const assetTotalValue = selectedAsset.shares * currentPrice;
                            
                            // Calculate P&L and Percentage
                            const totalCostBasis = selectedAsset.shares * selectedAsset.cost_basis;
                            const profitLoss = Number((assetTotalValue - totalCostBasis).toFixed(2));
                            const percentReturn = totalCostBasis !== 0 ? (profitLoss / totalCostBasis) * 100 : 0;
                            
                            const isNeutral = profitLoss === 0;
                            const isProfit = profitLoss > 0;
                            const isLoss = profitLoss < 0;
                            
                            let textClass = "text-blue-500";
                            if (isProfit) textClass = "text-emerald-400";
                            else if (isLoss) textClass = "text-rose-400";

                            const diversification = netAccountValue > 0 ? ((assetTotalValue / netAccountValue) * 100).toFixed(1) : "0.0";

                            return (
                                <>
                                    <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl">
                                        <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Live Price</p>
                                        <p className="text-2xl font-mono font-black text-white">${currentPrice.toFixed(2)}</p>
                                    </div>
                                    
                                    {/* Updated Total Return Box */}
                                    <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl">
                                        <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Total Return</p>
                                        <p className={`text-2xl font-mono font-black ${textClass}`}>
                                            {isProfit ? '+' : ''}${profitLoss.toFixed(2)}
                                            <span className="text-xs block opacity-80 mt-0.5">
                                                {isProfit ? '+' : ''}{percentReturn.toFixed(2)}%
                                            </span>
                                        </p>
                                    </div>

                                    <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl">
                                        <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Shares Owned</p>
                                        <p className="text-lg font-mono font-black text-white">{selectedAsset.shares.toFixed(4)}</p>
                                    </div>
                                    <div className="bg-slate-900/50 border border-slate-800 p-5 rounded-2xl">
                                        <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Portfolio Weight</p>
                                        <p className="text-lg font-mono font-black text-blue-400">{diversification}%</p>
                                    </div>
                                </>
                            );
                        })()}
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-4 pt-4 border-t border-slate-800">
                          <button 
                            onClick={() => { setTradeType("BUY"); setShowTradeTicket(true); }}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white py-4 rounded-xl font-black text-xs uppercase tracking-widest transition-colors shadow-[0_0_15px_rgba(16,185,129,0.2)]"
                          >
                              Buy More
                          </button>
                          <button 
                            onClick={() => { setTradeType("SELL"); setShowTradeTicket(true); }}
                            className="flex-1 bg-rose-600 hover:bg-rose-500 text-white py-4 rounded-xl font-black text-xs uppercase tracking-widest transition-colors shadow-[0_0_15px_rgba(225,29,72,0.2)]"
                          >
                              Sell
                          </button>
                      </div>

                      {/* Company & News Section */}
                      <div className="pt-8 border-t border-slate-800">
                          <h3 className="text-sm font-black text-white uppercase tracking-widest mb-6">Latest Intelligence</h3>
                          <div className="space-y-4">
                              {liveData[selectedAsset.ticker]?.news ? (
                                  liveData[selectedAsset.ticker].news.map((article: any, i: number) => (
                                      <div key={i} className="bg-slate-950 border border-slate-800 p-5 rounded-2xl">
                                          <p className="text-sm font-bold text-slate-200 mb-3">{article.title}</p>
                                          <div className="flex justify-between items-center">
                                              <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider">{article.publisher} • {article.date}</p>
                                              
                                              {article.summary ? (
                                                 <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest bg-emerald-500/10 px-2 py-1 rounded">Synthesized</span>
                                              ) : (
                                                <button 
                                                    onClick={() => summarizeNews(article)}
                                                    disabled={isSummarizing}
                                                    className="text-[9px] font-black text-blue-400 uppercase tracking-widest bg-blue-900/30 hover:bg-blue-600 hover:text-white px-3 py-1.5 rounded-lg border border-blue-500/50 transition-all disabled:opacity-50"
                                                >
                                                    {isSummarizing ? 'Running...' : 'Summarize (1 Token)'}
                                                </button>
                                              )}
                                          </div>
                                          
                                          {/* Injected Summary Block */}
                                          {article.summary && (
                                              <div className="mt-4 pt-4 border-t border-slate-800">
                                                  <p className="text-sm text-slate-300 italic leading-relaxed border-l-2 border-emerald-500 pl-3">
                                                      "{article.summary}"
                                                  </p>
                                              </div>
                                          )}
                                      </div>
                                  ))
                              ) : (
                                  <p className="text-xs text-slate-500 italic">No recent intelligence found for this asset.</p>
                              )}
                          </div>
                      </div>

                  </div>
              </div>
          </div>
      )}

      {/* RE-USED TRADE TICKET MODAL */}
      {showTradeTicket && selectedAsset && (
          <TradeTicket
              ticker={selectedAsset.ticker}
              currentPrice={Number(liveData[selectedAsset.ticker]?.price || selectedAsset.cost_basis)}
              buyingPower={Number(virtualCash)}
              currentShares={Number(selectedAsset.shares)}
              onClose={() => setShowTradeTicket(false)}
              onExecute={(amount: any, mode: any) => handleExecuteTrade(tradeType as "BUY" | "SELL", Number(amount), mode as "DOLLARS" | "SHARES")}
          />
      )}

    </main>
  );
}