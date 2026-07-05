"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import { apiFetch } from "../lib/config";
import TradeTicket from "../components/TradeTicket";
import ThemeToggle from "../components/ThemeToggle";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import StatTile from "../components/ui/StatTile";

// --- DYNAMIC CHART COMPONENT ---
function PortfolioChart({ totalValue, totalProfitLoss }: { totalValue: number, totalProfitLoss: number }) {
  const [timeframe, setTimeframe] = useState("1M");
  const timeframes = ["1D", "1W", "1M", "1Y", "ALL"];

  const isProfit = totalProfitLoss > 0;
  const isLoss = totalProfitLoss < 0;

  let colorClass = "text-accent";
  let arrow = "→";
  let sign = "";
  let strokeColor = "#3b82f6";
  let gradientStart = "rgba(59, 130, 246, 0.3)";
  let gradientEnd = "rgba(59, 130, 246, 0)";
  let fillPath = "M0,250 L0,150 L1000,150 L1000,250 Z";
  let strokePath = "M0,150 L1000,150";

  if (isProfit) {
      colorClass = "text-gain";
      arrow = "↗";
      sign = "+";
      strokeColor = "#10b981";
      gradientStart = "rgba(16, 185, 129, 0.3)";
      gradientEnd = "rgba(16, 185, 129, 0)";
      fillPath = "M0,250 L0,180 L200,170 L400,130 L600,140 L800,80 L1000,60 L1000,250 Z";
      strokePath = "M0,180 L200,170 L400,130 L600,140 L800,80 L1000,60";
  } else if (isLoss) {
      colorClass = "text-loss";
      arrow = "↘";
      sign = "-";
      strokeColor = "#ef4444";
      gradientStart = "rgba(239, 68, 68, 0.3)";
      gradientEnd = "rgba(239, 68, 68, 0)";
      fillPath = "M0,250 L0,60 L200,80 L400,140 L600,130 L800,170 L1000,180 L1000,250 Z";
      strokePath = "M0,60 L200,80 L400,140 L600,130 L800,170 L1000,180";
  }

  return (
    <Card className="p-5 md:p-8 relative overflow-hidden transition-all duration-500 h-full flex flex-col">
      <div
        className="absolute top-0 left-0 w-full h-full opacity-30 pointer-events-none transition-all duration-500"
        style={{ background: `linear-gradient(to bottom, ${gradientStart}, transparent)` }}
      />

      <div className="flex justify-between items-start mb-6 md:mb-8 relative z-10">
        <div>
          <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest mb-1 md:mb-2">Account Value</p>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-black text-text-primary tracking-tighter">${totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</h2>
          <p className={`text-xs md:text-sm font-bold ${colorClass} mt-1 md:mt-2 flex items-center gap-1 transition-colors duration-500`}>
            <span className="text-base md:text-lg leading-none">{arrow}</span> {sign}${Math.abs(totalProfitLoss).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} (All Time)
          </p>
        </div>

        <div className="hidden sm:flex gap-1 bg-bg-surface-hover p-1.5 rounded-xl border border-border">
          {timeframes.map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-2 rounded-lg text-[9px] font-black tracking-widest transition-all cursor-pointer ${timeframe === tf ? "bg-bg-surface text-text-primary" : "text-text-secondary hover:text-text-primary"}`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      <div className="w-full flex-1 relative z-10 flex items-end min-h-[180px] md:min-h-[250px]">
        <svg viewBox="0 0 1000 250" className="w-full h-full transition-all duration-500" preserveAspectRatio="none" aria-hidden="true">
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
    </Card>
  );
}

export default function VaultPage() {
  const router = useRouter();
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
    setUserEmail(session.user.email || "Investor");

    const { data: profile } = await supabase.from("profiles").select("virtual_cash_balance, ai_token_balance").eq("id", session.user.id).single();
    if (profile) {
      setVirtualCash(profile.virtual_cash_balance);
      setTokens(profile.ai_token_balance);
    }

    const { data: portfolioData } = await supabase.from("portfolio").select("*").eq("user_id", session.user.id);
    if (portfolioData) {
      setHoldings(portfolioData);

      const liveUpdates: any = {};
      for (const item of portfolioData) {
        try {
          const res = await apiFetch(`/analyze/${item.ticker}`);
          if (res.ok) {
            liveUpdates[item.ticker] = await res.json();
          }
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
        const res = await apiFetch(`/execute-trade`, {
            method: "POST",
            body: JSON.stringify({ ticker: selectedAsset.ticker, trade_type: type, amount: amount, mode: mode })
        });
        const result = await res.json();

        if (res.ok) {
            showToast(result.message);
            setShowTradeTicket(false);

            if (result.remaining_cash !== undefined) {
                setVirtualCash(result.remaining_cash);
            }

            setHoldings(prev => prev.map(h => {
                if (h.ticker === selectedAsset.ticker) {
                    const executedShares = mode === "SHARES" ? amount : (amount / result.execution_price);
                    return {
                        ...h,
                        shares: type === "SELL" ? h.shares - executedShares : h.shares + executedShares
                    };
                }
                return h;
            }).filter(h => h.shares > 0.0001));

            if (type === "SELL" && mode === "SHARES" && amount === selectedAsset.shares) {
                setSelectedAsset(null);
            }

            setTimeout(() => {
                loadPortfolio();
            }, 1500);

        }
        else { showToast(`Trade Error: ${result.detail}`); }
    } catch (error) { showToast("Execution Offline."); }
  };

  const summarizeNews = async (article: any) => {
    if (!selectedAsset) return;
    setIsSummarizing(true);
    try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const res = await apiFetch(`/summarize`, {
          method: "POST",
          body: JSON.stringify({ title: article.title, ticker: selectedAsset.ticker, content: article.content || "" })
        });

        const result = await res.json();
        if (res.ok) {
            showToast("Summary ready.");
            setLiveData((prev: any) => ({
                ...prev,
                [selectedAsset.ticker]: {
                    ...prev[selectedAsset.ticker],
                    news: prev[selectedAsset.ticker].news.map((n: any) =>
                        n.title === article.title ? { ...n, summary: result.summary } : n
                    )
                }
            }));
            setTokens(result.remaining_tokens);
        } else {
            showToast(res.status === 402 ? "Out of AI tokens. Add more to continue." : "Summary failed.");
        }
    } catch { showToast("Network Error."); }
    setIsSummarizing(false);
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

    // All-time P&L uses the $100k starting paper-trading balance as the benchmark.
    const STARTING_BALANCE = 100000;
    const totalProfitLoss = Number((netAccountValue - STARTING_BALANCE).toFixed(2));

    return { totalStockValue, totalCostBasis, netAccountValue, totalProfitLoss };
  };

  const { totalStockValue, totalCostBasis, netAccountValue, totalProfitLoss } = calculateTotals();

  if (!isAuthorized || loading) {
    return <main className="min-h-screen bg-bg-primary flex items-center justify-center p-4"><div className="w-12 h-12 md:w-16 md:h-16 border-4 border-border border-t-accent rounded-full animate-spin" /></main>;
  }

  return (
    <main className="min-h-screen bg-bg-primary text-text-secondary flex flex-col font-sans relative overflow-x-hidden pb-20">

      {toastMessage && (
        <div className="fixed inset-x-4 top-4 md:inset-0 md:top-24 md:left-1/2 md:-translate-x-1/2 z-[150] pointer-events-none flex justify-center">
           <Card className="px-6 py-4 md:px-8 md:py-4 rounded-2xl md:rounded-full shadow-lg animate-in slide-in-from-top-4 fade-in flex items-center gap-3">
              <div className="w-2 h-2 bg-accent rounded-full shrink-0" />
              <p className="text-text-primary font-black uppercase tracking-widest text-[10px] md:text-xs text-center">{toastMessage}</p>
           </Card>
        </div>
      )}

      {/* HEADER */}
      <header className="w-full flex flex-col md:flex-row justify-between items-center p-4 md:p-6 border-b border-border bg-bg-primary/90 backdrop-blur z-50 sticky top-0 gap-4 md:gap-0">
        <div className="w-full flex justify-between items-center md:w-auto">
           <h1 className="text-2xl md:text-3xl font-black text-text-primary tracking-tighter cursor-pointer" onClick={() => router.push('/hub')}>
              TRADEBOTICS<span className="text-accent">AI</span>
           </h1>
           <Button variant="ghost" size="sm" onClick={() => router.push('/hub')} className="md:hidden rounded-full">
              Hub
           </Button>
        </div>

        <div className="flex items-center gap-4 w-full md:w-auto justify-between md:justify-end">
          <div className="flex items-center gap-4 md:gap-6 bg-bg-surface px-5 md:px-6 py-2 rounded-xl md:rounded-full border border-border w-full md:w-auto justify-center">
            <div className="text-right border-r border-border pr-4 md:pr-6">
              <p className="text-[9px] text-text-secondary uppercase tracking-widest font-bold">Cash</p>
              <p className="text-xs md:text-sm font-mono font-black text-gain">${virtualCash.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            </div>
            <div className="text-right">
              <p className="text-[9px] text-text-secondary uppercase tracking-widest font-bold">AI Tokens</p>
              <p className="text-xs md:text-sm font-mono font-black text-accent">{tokens}</p>
            </div>
          </div>
          <ThemeToggle className="hidden md:flex" />
          <Button variant="ghost" size="sm" onClick={() => router.push('/hub')} className="hidden md:block rounded-full">
            Hub
          </Button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto w-full px-4 md:px-6 mt-6 md:mt-12 flex flex-col gap-8 md:gap-12">

        {/* SEARCH BAR */}
        <div className="flex w-full bg-bg-surface p-2 md:p-3 rounded-full border border-border focus-within:border-accent/50 shadow-sm transition-all group">
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
            placeholder="Search a ticker to buy..."
            aria-label="Search ticker"
          />
          <Button onClick={handleSearch} size="md" className="shrink-0">
            Buy
          </Button>
        </div>

        {/* HERO: CHART + BREAKDOWN */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            <div className="lg:col-span-8">
                <PortfolioChart totalValue={netAccountValue} totalProfitLoss={totalProfitLoss} />
            </div>

            <div className="lg:col-span-4 flex flex-col gap-6">
                <Card className="p-5 md:p-8 flex-1 flex flex-col justify-center">
                    <h3 className="text-[10px] font-black text-text-secondary uppercase tracking-widest mb-4 md:mb-6 border-b border-border pb-3 md:pb-4">Account Breakdown</h3>
                    <div className="space-y-4 md:space-y-6">
                        <div>
                            <p className="text-[9px] font-bold text-text-secondary uppercase mb-1">Cash Available</p>
                            <p className="text-xl md:text-2xl font-mono font-black text-gain">${virtualCash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                        </div>
                        <div className="border-t border-border pt-4 md:pt-6">
                            <p className="text-[9px] font-bold text-text-secondary uppercase mb-1">Invested (Market Value)</p>
                            <p className="text-lg md:text-xl font-mono font-black text-text-primary">${totalStockValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                        </div>
                    </div>
                </Card>

                <Card className="p-5 md:p-8">
                     <h3 className="text-[10px] font-black text-accent uppercase tracking-[0.3em] mb-4 md:mb-6">Portfolio at a Glance</h3>
                     <div className="grid grid-cols-2 gap-4">
                         <StatTile label="Positions" value={String(holdings.length)} />
                         <StatTile
                            label="Largest Holding"
                            value={holdings.length > 0 ? holdings.reduce((prev, current) => ((current.shares * (liveData[current.ticker]?.price || current.cost_basis)) > (prev.shares * (liveData[prev.ticker]?.price || prev.cost_basis))) ? current : prev).ticker : "N/A"}
                         />
                     </div>
                </Card>
            </div>
        </div>

        {/* HOLDINGS GRID */}
        <div>
            <h3 className="text-xl md:text-2xl font-black text-text-primary tracking-tight mb-4 md:mb-6 border-b border-border pb-3 md:pb-4">Current Holdings</h3>

            {holdings.length === 0 ? (
                <Card className="p-8 md:p-12 text-center">
                    <p className="text-text-secondary font-bold uppercase tracking-widest text-[10px] md:text-xs">You don't own any positions yet.</p>
                    <Button onClick={() => router.push('/terminal')} className="mt-4 md:mt-6">Find Assets</Button>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
                    {holdings.map((h: any, i: number) => {
                        const live = liveData[h.ticker];
                        const currentPrice = live ? live.price : h.cost_basis;
                        const totalCost = h.shares * h.cost_basis;
                        const totalMarketValue = h.shares * currentPrice;
                        const profitLoss = Number((totalMarketValue - totalCost).toFixed(2));

                        const percentReturn = totalCost > 0 ? ((profitLoss / totalCost) * 100) : 0;
                        const isProfit = profitLoss > 0;
                        const isNeutral = profitLoss === 0;
                        const badgeTone: "gain" | "loss" | "neutral" = isProfit ? "gain" : isNeutral ? "neutral" : "loss";

                        return (
                            <Card
                                key={i}
                                interactive
                                onClick={() => setSelectedAsset(h)}
                                className="p-5 md:p-6"
                            >
                                <div className="flex justify-between items-start mb-3 md:mb-4">
                                    <div>
                                        <h4 className="text-2xl md:text-3xl font-black text-text-primary">{h.ticker}</h4>
                                        <p className="text-[10px] font-black text-text-secondary uppercase tracking-widest mt-1">{h.shares.toFixed(2)} Shares</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] font-bold text-text-secondary uppercase mb-0.5">Market Value</p>
                                        <p className="text-lg md:text-xl font-mono font-black text-text-primary">${totalMarketValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                                    </div>
                                </div>

                                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-bg-primary border border-border rounded-xl px-3 py-2 md:px-4 md:py-2.5 mb-3 md:mb-4 font-mono text-[10px] md:text-xs text-text-secondary gap-1 sm:gap-0">
                                  <div>Avg Cost: <span className="text-text-primary font-bold">${Number(h.cost_basis).toFixed(2)}</span></div>
                                  <div>Live: <span className="text-text-primary font-bold">${Number(currentPrice).toFixed(2)}</span></div>
                                </div>

                                <div className="flex justify-between items-end border-t border-border pt-3 md:pt-4">
                                    <div>
                                        <p className="text-[9px] font-bold text-text-secondary uppercase mb-1">Total Return</p>
                                        <Badge tone={badgeTone}>{isProfit ? '+' : ''}${profitLoss.toFixed(2)}</Badge>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] font-bold text-text-secondary uppercase mb-1">Return %</p>
                                        <Badge tone={badgeTone}>{isProfit ? '+' : ''}{percentReturn.toFixed(2)}%</Badge>
                                    </div>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
      </div>

      {/* ASSET DETAILS DRAWER */}
      {selectedAsset && (
          <div className="fixed inset-0 z-[100] flex items-center justify-end bg-black/50 backdrop-blur-sm transition-all animate-in fade-in">
              <div className="w-full max-w-xl h-full bg-bg-primary border-l border-border flex flex-col shadow-2xl animate-in slide-in-from-right-full duration-300">

                  <div className="p-5 md:p-8 border-b border-border flex justify-between items-center bg-bg-surface shrink-0">
                      <div>
                          <div className="flex items-center gap-2 md:gap-3 mb-1 md:mb-2"><div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-accent rounded-full" /><p className="text-[10px] font-black uppercase text-accent tracking-widest">Asset Details</p></div>
                          <h2 className="text-2xl md:text-4xl font-black text-text-primary">{selectedAsset.ticker}</h2>
                          <p className="text-xs font-bold text-text-secondary mt-1 uppercase tracking-widest truncate max-w-[200px] sm:max-w-xs">{liveData[selectedAsset.ticker]?.company_name || 'Loading profile...'}</p>
                      </div>
                      <button
                        onClick={() => setSelectedAsset(null)}
                        aria-label="Close asset details"
                        className="w-8 h-8 md:w-10 md:h-10 bg-bg-surface-hover rounded-full flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors shrink-0 cursor-pointer"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                  </div>

                  <div className="flex-1 overflow-y-auto p-5 md:p-8 custom-scrollbar space-y-6 md:space-y-8">

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
                        {(() => {
                            const live = liveData[selectedAsset.ticker];
                            const currentPrice = live ? live.price : selectedAsset.cost_basis;
                            const assetTotalValue = selectedAsset.shares * currentPrice;

                            const totalCostBasis = selectedAsset.shares * selectedAsset.cost_basis;
                            const profitLoss = Number((assetTotalValue - totalCostBasis).toFixed(2));
                            const percentReturn = totalCostBasis !== 0 ? (profitLoss / totalCostBasis) * 100 : 0;

                            const isProfit = profitLoss > 0;
                            const isLoss = profitLoss < 0;

                            let textClass = "text-accent";
                            if (isProfit) textClass = "text-gain";
                            else if (isLoss) textClass = "text-loss";

                            const diversification = netAccountValue > 0 ? ((assetTotalValue / netAccountValue) * 100).toFixed(1) : "0.0";

                            return (
                                <>
                                    <StatTile label="Live Price" value={`$${currentPrice.toFixed(2)}`} />
                                    <div className="bg-bg-surface border border-border p-4 md:p-5 rounded-2xl">
                                        <p className="text-[9px] font-bold text-text-secondary uppercase mb-1">Total Return</p>
                                        <p className={`text-xl md:text-2xl font-mono font-black ${textClass}`}>
                                            {isProfit ? '+' : ''}${profitLoss.toFixed(2)}
                                            <span className="text-[10px] block opacity-80 mt-0.5">
                                                {isProfit ? '+' : ''}{percentReturn.toFixed(2)}%
                                            </span>
                                        </p>
                                    </div>
                                    <StatTile label="Average Cost" value={`$${Number(selectedAsset.cost_basis).toFixed(2)}`} accentClassName="text-accent" />
                                    <StatTile label="Position Market Value" value={`$${assetTotalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`} />
                                    <StatTile label="Shares Owned" value={selectedAsset.shares.toFixed(4)} />
                                    <StatTile label="Portfolio Weight" value={`${diversification}%`} accentClassName="text-accent" />
                                </>
                            );
                        })()}
                      </div>

                      <div className="flex gap-3 md:gap-4 pt-4 border-t border-border">
                          <button
                            onClick={() => { setTradeType("BUY"); setShowTradeTicket(true); }}
                            className="flex-1 bg-gain hover:opacity-90 text-white py-3 md:py-4 rounded-xl font-black text-xs uppercase tracking-widest transition-opacity cursor-pointer"
                          >
                              Buy More
                          </button>
                          <button
                            onClick={() => { setTradeType("SELL"); setShowTradeTicket(true); }}
                            className="flex-1 bg-loss hover:opacity-90 text-white py-3 md:py-4 rounded-xl font-black text-xs uppercase tracking-widest transition-opacity cursor-pointer"
                          >
                              Sell
                          </button>
                      </div>

                      <div className="pt-6 md:pt-8 border-t border-border">
                          <h3 className="text-sm font-black text-text-primary uppercase tracking-widest mb-4 md:mb-6">Latest News</h3>
                          <div className="space-y-3 md:space-y-4">
                              {liveData[selectedAsset.ticker]?.news ? (
                                  liveData[selectedAsset.ticker].news.map((article: any, i: number) => (
                                      <div key={i} className="bg-bg-surface border border-border p-4 md:p-5 rounded-2xl">
                                          <p className="text-sm font-bold text-text-primary mb-3">{article.title}</p>
                                          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 sm:gap-0">
                                              <p className="text-[9px] font-black text-text-secondary uppercase tracking-wider">{article.publisher} · {article.date}</p>

                                              {article.summary ? (
                                                 <Badge tone="gain">Summarized</Badge>
                                              ) : (
                                                <button
                                                    onClick={() => summarizeNews(article)}
                                                    disabled={isSummarizing}
                                                    className="text-[9px] font-black text-accent uppercase tracking-widest bg-accent/10 hover:bg-accent hover:text-white px-3 py-1.5 rounded-lg border border-accent/30 transition-all disabled:opacity-50 cursor-pointer"
                                                >
                                                    {isSummarizing ? 'Running...' : 'Summarize (1 Token)'}
                                                </button>
                                              )}
                                          </div>

                                          {article.summary && (
                                              <div className="mt-3 md:mt-4 pt-3 md:pt-4 border-t border-border">
                                                  <p className="text-sm text-text-secondary italic leading-relaxed border-l-2 border-gain pl-3">
                                                      "{article.summary}"
                                                  </p>
                                              </div>
                                          )}
                                      </div>
                                  ))
                              ) : (
                                  <p className="text-xs text-text-secondary italic">No recent news found for this asset.</p>
                              )}
                          </div>
                      </div>

                  </div>
              </div>
          </div>
      )}

      {showTradeTicket && selectedAsset && (
          <TradeTicket
              ticker={selectedAsset.ticker}
              currentPrice={Number(liveData[selectedAsset.ticker]?.price || selectedAsset.cost_basis)}
              buyingPower={Number(virtualCash)}
              currentShares={Number(selectedAsset.shares)}
              onClose={() => setShowTradeTicket(false)}
              onExecute={(type: any, amount: any, mode: any) => handleExecuteTrade(type, Number(amount), mode)}
          />
      )}

    </main>
  );
}
