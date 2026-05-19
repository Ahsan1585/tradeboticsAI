"use client";
import React, { useState, useEffect, useRef } from "react";
import { supabase } from "../lib/supabase";
import Link from "next/link";

// 🚨 PRODUCTION URL (Change to http://localhost:8000 for local testing)
const BACKEND_URL = "https://tradebotics-api.onrender.com";

export default function PortfolioPage() {
  const [user, setUser] = useState<any>(null);
  const [mode, setMode] = useState<'csv' | 'manual'>('manual');
  
  // State for Manual Entry
  const [manualEntries, setManualEntries] = useState([{ ticker: "", shares: "", cost: "" }]);
  
  // State for CSV Entry
  const [parsedCsvData, setParsedCsvData] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // State for existing portfolio holdings (Individual Tax Lots)
  const [existingHoldings, setExistingHoldings] = useState<any[]>([]);

  const [loading, setLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // State: Dead Capital Reallocator
  const [swapThesis, setSwapThesis] = useState<any>(null);
  const [isGeneratingSwap, setIsGeneratingSwap] = useState<string | null>(null);

  // 🚨 FIXED: Auth Error Failsafe added here as well
  useEffect(() => {
    const checkUser = async () => {
      const { data: { session }, error } = await supabase.auth.getSession();
      
      if (error) {
          console.warn("Auth Token Corrupted. Purging local cache.");
          await supabase.auth.signOut();
          setUser(null);
          return;
      }
      
      if (session) {
        setUser(session.user);
        fetchHoldings(session.user.id);
      } else {
        setUser(null);
      }
    };
    
    checkUser();
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500); 
  };

  const fetchHoldings = async (userId: string) => {
    const { data, error } = await supabase
        .from('portfolio')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false });
    
    if (data) {
        setExistingHoldings(data);
    }
  };

  const deleteHolding = async (id: string) => {
      if (!user) return;
      
      const { error } = await supabase
          .from('portfolio')
          .delete()
          .eq('id', id)
          .eq('user_id', user.id);
          
      if (error) {
          showToast(`Delete Error: ${error.message}`);
      } else {
          showToast("Tax lot purged from Vault.");
          fetchHoldings(user.id); 
      }
  };

  const runSwapThesis = async (id: string, ticker: string, shares: number) => {
      setIsGeneratingSwap(id);
      setSwapThesis(null);
      
      try {
          const analyzeRes = await fetch(`${BACKEND_URL}/analyze/${ticker}`);
          if (!analyzeRes.ok) throw new Error("Failed to pull live pricing.");
          const analyzeData = await analyzeRes.json();

          const res = await fetch(`${BACKEND_URL}/swap-thesis`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                  ticker: ticker,
                  shares: shares,
                  price: analyzeData.price
              })
          });
          
          if (res.ok) {
              const result = await res.json();
              setSwapThesis({ ...result, original_ticker: ticker });
              window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
          } else {
              showToast("Swap Analysis Failed.");
          }
      } catch {
          showToast("Network Error: Could not generate swap thesis.");
      }
      setIsGeneratingSwap(null);
  };

  // --- MANUAL ENTRY LOGIC ---
  const handleManualChange = (index: number, field: string, value: string) => {
    const newEntries = [...manualEntries];
    newEntries[index] = { ...newEntries[index], [field]: value.toUpperCase() };
    setManualEntries(newEntries);
  };

  const addManualRow = () => {
    setManualEntries([...manualEntries, { ticker: "", shares: "", cost: "" }]);
  };

  const removeManualRow = (index: number) => {
    const newEntries = manualEntries.filter((_, i) => i !== index);
    if (newEntries.length === 0) setManualEntries([{ ticker: "", shares: "", cost: "" }]);
    else setManualEntries(newEntries);
  };

  // --- CSV ENTRY LOGIC ---
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const lines = text.split('\n');
      const parsed = [];
      
      for (let i = 1; i < lines.length; i++) {
        const row = lines[i].split(',');
        if (row.length >= 3 && row[0].trim() !== '') {
          parsed.push({
            ticker: row[0].replace(/['"]/g, '').trim().toUpperCase(),
            shares: row[1].replace(/['"]/g, '').trim(),
            cost: row[2].replace(/['"]/g, '').trim(),
          });
        }
      }
      setParsedCsvData(parsed);
      if (parsed.length > 0) showToast(`Parsed ${parsed.length} assets from CSV.`);
    };
    reader.readAsText(file);
  };

  // --- SYNC TO DATABASE LOGIC ---
  const syncToVault = async () => {
    if (!user) {
        showToast("Authentication Error: Please log in.");
        return;
    }

    setLoading(true);
    const dataToSync = mode === 'manual' ? manualEntries : parsedCsvData;
    
    const validData = dataToSync.filter(item => item.ticker && item.shares && item.cost);

    if (validData.length === 0) {
        showToast("Vault Error: No valid data to sync.");
        setLoading(false);
        return;
    }

    const insertPayload = validData.map(item => ({
        user_id: user.id,
        ticker: item.ticker,
        shares: parseFloat(item.shares),
        cost_basis: parseFloat(item.cost)
    }));

    const { error } = await supabase.from('portfolio').insert(insertPayload);

    if (error) {
        showToast(`Sync Failed: ${error.message}`);
    } else {
        showToast(`SUCCESS: ${validData.length} assets synced to Neural Vault.`);
        setManualEntries([{ ticker: "", shares: "", cost: "" }]);
        setParsedCsvData([]);
        fetchHoldings(user.id); 
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 font-sans selection:bg-blue-500/30 flex flex-col">
      
      {/* Toast Notifications */}
      {toastMessage && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-10 py-6 rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center mb-3"><div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" /></div>
              <p className="text-white font-black uppercase tracking-widest text-sm text-center">{toastMessage}</p>
           </div>
        </div>
      )}

      {/* Navbar */}
      <nav className="w-full border-b border-slate-800/50 bg-[#020617]/80 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
              <h1 className="text-2xl font-black text-white tracking-tighter">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
              <Link href="/">
                <button className="border border-slate-800 text-slate-400 hover:text-white hover:border-blue-500 text-[10px] font-black px-6 py-3 rounded-full uppercase tracking-widest transition-all">
                    Return to Terminal
                </button>
              </Link>
          </div>
      </nav>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-6 pt-20 flex-1 w-full">
          
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 mb-16">
            {/* LEFT COLUMN: Instructions */}
            <div className="space-y-8">
                <div className="flex items-center gap-3 text-blue-500">
                    <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse" />
                    <p className="text-[10px] font-black uppercase tracking-[0.3em]">Neural Vault Ingestion</p>
                </div>
                
                <h2 className="text-5xl font-black text-white leading-tight tracking-tighter">
                    Synchronize Your<br/>Portfolio.
                </h2>
                
                <p className="text-slate-400 text-lg leading-relaxed max-w-lg">
                    Standard market scans only tell you what the market is doing. By securely uploading your portfolio's current state, TradeBotics AI transitions from a scanner to a fiduciary intelligence engine.
                </p>

                <div className="bg-slate-900/40 border border-slate-800 rounded-[32px] p-8 max-w-lg shadow-inner">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-6 pb-4 border-b border-slate-800">How to unlock tailored intelligence:</p>
                    <div className="space-y-6">
                        <div className="flex gap-4">
                            <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-500 flex items-center justify-center font-black text-xs shrink-0">1</div>
                            <p className="text-slate-300 text-sm leading-relaxed"><strong className="text-white">Export your Data.</strong> Download your current positions as a standard CSV file from your brokerage, or enter them manually.</p>
                        </div>
                        <div className="flex gap-4">
                            <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-500 flex items-center justify-center font-black text-xs shrink-0">2</div>
                            <p className="text-slate-300 text-sm leading-relaxed"><strong className="text-white">Upload to the Vault.</strong> Drag and drop the file into the secure ingestion zone or fill out the matrix.</p>
                        </div>
                        <div className="flex gap-4">
                            <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-500 flex items-center justify-center font-black text-xs shrink-0">3</div>
                            <p className="text-slate-300 text-sm leading-relaxed"><strong className="text-white">Activate AI Overlays.</strong> TradeBotics will map your exact cost basis against real-time market structures to provide personalized stop-losses.</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* RIGHT COLUMN: Interactive Ingestion Zone */}
            <div className="border-2 border-dashed border-slate-800 rounded-[40px] p-2 relative overflow-hidden bg-slate-900/20 flex flex-col min-h-[600px]">
                
                <div className="flex bg-slate-900 p-2 rounded-[32px] mb-6 shrink-0 relative z-10 mx-6 mt-6">
                    <button onClick={() => setMode('manual')} className={`flex-1 py-3 text-[10px] font-black uppercase tracking-widest rounded-3xl transition-all ${mode === 'manual' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-white'}`}>Manual Entry</button>
                    <button onClick={() => setMode('csv')} className={`flex-1 py-3 text-[10px] font-black uppercase tracking-widest rounded-3xl transition-all ${mode === 'csv' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-white'}`}>CSV Upload</button>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar px-6 pb-6 z-10 flex flex-col">
                    
                    {mode === 'manual' ? (
                        <div className="flex-1 flex flex-col">
                            <div className="grid grid-cols-12 gap-2 mb-4 text-[9px] font-black uppercase text-slate-500 tracking-widest px-2">
                                <div className="col-span-4">Ticker</div>
                                <div className="col-span-3">Shares</div>
                                <div className="col-span-4">Avg Cost ($)</div>
                                <div className="col-span-1 text-center">Act</div>
                            </div>
                            
                            <div className="space-y-3 flex-1">
                                {manualEntries.map((entry, idx) => (
                                    <div key={idx} className="grid grid-cols-12 gap-2 group animate-in fade-in zoom-in-95">
                                        <input value={entry.ticker} onChange={(e) => handleManualChange(idx, 'ticker', e.target.value)} placeholder="AAPL" className="col-span-4 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white font-black outline-none focus:border-blue-500 transition-colors uppercase" />
                                        <input value={entry.shares} onChange={(e) => handleManualChange(idx, 'shares', e.target.value)} placeholder="100" type="number" step="any" className="col-span-3 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white font-medium outline-none focus:border-blue-500 transition-colors" />
                                        <input value={entry.cost} onChange={(e) => handleManualChange(idx, 'cost', e.target.value)} placeholder="150.25" type="number" step="any" className="col-span-4 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white font-medium outline-none focus:border-blue-500 transition-colors" />
                                        <button onClick={() => removeManualRow(idx)} className="col-span-1 flex items-center justify-center bg-slate-900 border border-slate-800 rounded-xl text-slate-600 hover:text-red-500 hover:border-red-500 transition-colors font-black">✕</button>
                                    </div>
                                ))}
                            </div>

                            <button onClick={addManualRow} className="mt-4 w-full py-4 border border-dashed border-slate-700 rounded-xl text-[10px] font-black uppercase text-slate-500 hover:text-white hover:border-slate-500 transition-colors">+ Add Position</button>
                        </div>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-center">
                            <div className="w-20 h-20 bg-slate-900 border border-slate-800 rounded-3xl flex items-center justify-center mb-6 shadow-xl text-3xl">📄</div>
                            <h3 className="text-2xl font-black text-white mb-2">Upload Data File</h3>
                            <p className="text-slate-400 text-sm mb-8">Expected format: Ticker, Shares, Cost Basis</p>
                            
                            <input type="file" accept=".csv" ref={fileInputRef} onChange={handleFileUpload} className="hidden" />
                            
                            {parsedCsvData.length > 0 ? (
                                <div className="w-full bg-slate-950 border border-slate-800 rounded-2xl p-4 text-left">
                                    <div className="flex justify-between items-center mb-4">
                                        <p className="text-xs font-black text-blue-500 uppercase">Data Extracted Successfully</p>
                                        <button onClick={() => setParsedCsvData([])} className="text-[9px] text-slate-500 hover:text-white uppercase font-bold">Clear</button>
                                    </div>
                                    <div className="max-h-40 overflow-y-auto space-y-2 custom-scrollbar">
                                        {parsedCsvData.map((row, i) => (
                                            <div key={i} className="flex justify-between text-sm border-b border-slate-800/50 pb-1">
                                                <span className="font-black text-white">{row.ticker}</span>
                                                <span className="text-slate-400">{row.shares} shares @ ${row.cost}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <button onClick={() => fileInputRef.current?.click()} className="bg-slate-800 hover:bg-slate-700 text-white px-8 py-4 rounded-full font-black text-[10px] uppercase tracking-widest transition-colors shadow-lg">
                                    Select CSV File
                                </button>
                            )}
                        </div>
                    )}

                </div>

                <div className="p-6 bg-slate-900/80 backdrop-blur-md border-t border-slate-800 rounded-b-[38px] z-20">
                    <button 
                        onClick={syncToVault}
                        disabled={loading || (mode === 'manual' ? !manualEntries[0].ticker : parsedCsvData.length === 0)}
                        className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-black py-5 rounded-2xl uppercase tracking-[0.2em] text-xs transition-all shadow-[0_0_20px_rgba(59,130,246,0.15)] disabled:shadow-none"
                    >
                        {loading ? "Syncing..." : "Sync Portfolio to Vault"}
                    </button>
                </div>
                
            </div>
        </div>

        {/* The Dead Capital Reallocator Thesis Display */}
        {swapThesis && (
            <div className="bg-[#020617] border-2 border-purple-500/50 rounded-[40px] p-10 mb-8 shadow-[0_0_50px_rgba(168,85,247,0.1)] relative overflow-hidden animate-in fade-in zoom-in-95">
                <div className="absolute top-0 right-0 w-64 h-64 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />
                
                <div className="flex justify-between items-start mb-6">
                    <div className="flex items-center gap-3">
                        <div className="w-3 h-3 bg-purple-500 rounded-full animate-pulse shadow-[0_0_10px_#a855f7]" />
                        <h3 className="text-xl font-black text-white uppercase tracking-widest">Tactical Sector Swap Analysis</h3>
                    </div>
                    <button onClick={() => setSwapThesis(null)} className="text-slate-500 hover:text-white font-black text-xs uppercase tracking-widest transition-colors">Close</button>
                </div>

                <p className="text-lg text-slate-300 leading-relaxed italic mb-10 border-l-2 border-purple-500 pl-4 relative z-10">"{swapThesis.thesis}"</p>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-6 relative z-10 border-t border-slate-800/50 pt-8">
                    <div><p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Liquidating</p><p className="text-white font-black text-xl">{swapThesis.original_ticker}</p></div>
                    <div><p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Freed Capital</p><p className="text-white font-mono font-black text-xl">${swapThesis.freed_capital.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p></div>
                    <div className="bg-purple-500/10 px-4 py-2 rounded-xl border border-purple-500/20"><p className="text-[10px] font-bold text-purple-400 uppercase tracking-widest mb-1">Target Asset</p><p className="text-white font-black text-xl">{swapThesis.target_ticker}</p></div>
                    <div className="bg-purple-500/10 px-4 py-2 rounded-xl border border-purple-500/20"><p className="text-[10px] font-bold text-purple-400 uppercase tracking-widest mb-1">New Quant Score</p><p className="text-white font-black text-xl">{swapThesis.target_score}</p></div>
                </div>
            </div>
        )}

        {/* Existing Holdings Viewer & Editor */}
        <div className="bg-slate-900/30 border border-slate-800 rounded-[40px] p-10 shadow-2xl relative z-10">
            <h3 className="text-2xl font-black text-white mb-8 tracking-tighter">Current Vault Holdings</h3>
            
            {existingHoldings.length === 0 ? (
                <div className="text-center py-10 border-2 border-dashed border-slate-800 rounded-[24px]">
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">No assets synchronized yet.</p>
                </div>
            ) : (
                <div className="overflow-x-auto custom-scrollbar">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="border-b border-slate-800 text-[10px] uppercase tracking-widest text-slate-500">
                                <th className="pb-4 font-black px-4">Date Synced</th>
                                <th className="pb-4 font-black px-4">Asset Ticker</th>
                                <th className="pb-4 font-black px-4">Position Size</th>
                                <th className="pb-4 font-black px-4">Cost Basis</th>
                                <th className="pb-4 font-black text-right px-4">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {existingHoldings.map((item) => (
                                <tr key={item.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors group">
                                    <td className="py-4 px-4 text-xs text-slate-500 font-medium">
                                        {new Date(item.created_at).toLocaleDateString()}
                                    </td>
                                    <td className="py-4 px-4">
                                        <span className="font-black text-white text-lg bg-slate-950 border border-slate-800 px-3 py-1 rounded-lg">{item.ticker}</span>
                                    </td>
                                    <td className="py-4 px-4 font-medium text-slate-300">
                                        {item.shares} <span className="text-[10px] text-slate-500 uppercase tracking-widest ml-1">Shares</span>
                                    </td>
                                    <td className="py-4 px-4 font-mono font-medium text-white">
                                        ${item.cost_basis}
                                    </td>
                                    <td className="py-4 px-4 text-right space-x-2">
                                        <button 
                                            onClick={() => runSwapThesis(item.id, item.ticker, item.shares)} 
                                            disabled={isGeneratingSwap === item.id}
                                            className="text-purple-400 hover:text-white bg-purple-900/20 px-4 py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest border border-purple-500/30 hover:bg-purple-600 transition-all opacity-50 group-hover:opacity-100 disabled:opacity-30"
                                        >
                                            {isGeneratingSwap === item.id ? "Analyzing..." : "Find Sector Swap"}
                                        </button>

                                        <button 
                                            onClick={() => deleteHolding(item.id)} 
                                            className="text-slate-500 hover:text-red-500 bg-slate-950 px-4 py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest border border-slate-800 hover:border-red-500 transition-all opacity-50 group-hover:opacity-100"
                                        >
                                            Purge
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>

      </div>
      
      <footer className="border-t border-slate-800/50 py-8 mt-12 text-center w-full">
          <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
      </footer>
    </main>
  );
}