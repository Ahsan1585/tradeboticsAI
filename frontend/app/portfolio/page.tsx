"use client";

import { useState } from "react";
import Link from "next/link";

export default function PortfolioUpload() {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = () => {
    if (!file) return;
    alert(`Initiating AI ingestion for ${file.name}... (Backend wiring pending)`);
    // Future integration: Send to FastAPI to parse CSV and map to Supabase
  };

  return (
    <main className="min-h-screen bg-[#020617] text-slate-300 p-8 flex flex-col font-sans">
      
      {/* HEADER */}
      <div className="flex justify-between items-center mb-16">
        <Link href="/">
            <h1 className="text-4xl font-black text-white tracking-tighter hover:text-blue-400 transition-colors">
                TRADEBOTICS<span className="text-blue-500">AI</span>
            </h1>
        </Link>
        <Link href="/" className="text-[10px] border border-slate-800 px-6 py-3 rounded-full uppercase font-black text-slate-400 hover:text-white transition-all">
            Return to Terminal
        </Link>
      </div>

      <div className="max-w-4xl mx-auto w-full grid grid-cols-1 md:grid-cols-2 gap-12 mt-10">
        
        {/* LEFT: INSTRUCTIONS & VALUE PROP */}
        <div className="space-y-8">
            <div>
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse" />
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-blue-500">Neural Vault Ingestion</p>
                </div>
                <h2 className="text-4xl font-black text-white mb-6">Synchronize Your Portfolio.</h2>
                <p className="text-slate-400 leading-relaxed text-sm">
                    Standard market scans only tell you what the market is doing. By securely uploading your portfolio's current state, TradeBotics AI transitions from a scanner to a fiduciary intelligence engine.
                </p>
            </div>

            <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-[32px] space-y-4">
                <p className="text-[11px] font-black uppercase text-white tracking-widest border-b border-slate-800 pb-4 mb-4">How to unlock tailored intelligence:</p>
                
                <div className="flex gap-4 items-start">
                    <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-500 flex items-center justify-center font-black text-xs shrink-0 mt-0.5">1</div>
                    <p className="text-sm text-slate-400"><span className="text-slate-200 font-bold">Export your Data.</span> Download your current positions as a standard CSV file from your brokerage (Fidelity, Robinhood, Schwab, etc.).</p>
                </div>
                <div className="flex gap-4 items-start">
                    <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-500 flex items-center justify-center font-black text-xs shrink-0 mt-0.5">2</div>
                    <p className="text-sm text-slate-400"><span className="text-slate-200 font-bold">Upload to the Vault.</span> Drag and drop the file into the secure ingestion zone. We extract only tickers, shares, and cost basis.</p>
                </div>
                <div className="flex gap-4 items-start">
                    <div className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-500 flex items-center justify-center font-black text-xs shrink-0 mt-0.5">3</div>
                    <p className="text-sm text-slate-400"><span className="text-slate-200 font-bold">Activate AI Overlays.</span> TradeBotics will map your exact cost basis against real-time market structures to provide personalized stop-losses, target trims, and sector correlation warnings.</p>
                </div>
            </div>
        </div>

        {/* RIGHT: DRAG & DROP ZONE */}
        <div className="flex flex-col">
            <div 
                className={`flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-[40px] p-10 transition-all duration-300 ${dragActive ? 'border-blue-500 bg-blue-500/5' : 'border-slate-800 bg-slate-900/30 hover:border-slate-700'}`}
                onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
            >
                <div className="w-16 h-16 bg-slate-950 border border-slate-800 rounded-2xl flex items-center justify-center mb-6 shadow-xl">
                    <span className="text-2xl">📄</span>
                </div>
                <p className="text-white font-black text-lg mb-2">
                    {file ? file.name : "Drag & Drop CSV"}
                </p>
                <p className="text-slate-500 text-xs font-medium text-center max-w-[250px]">
                    {file ? `${(file.size / 1024).toFixed(1)} KB` : "Supports standard .csv exports from major brokerages."}
                </p>

                {file && (
                    <button onClick={handleUpload} className="mt-8 bg-blue-600 w-full py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest text-white shadow-lg shadow-blue-600/20 hover:bg-blue-500 transition-all">
                        Execute Import Protocol
                    </button>
                )}
            </div>
        </div>

      </div>
    </main>
  );
}