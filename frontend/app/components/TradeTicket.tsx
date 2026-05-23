"use client";
import React, { useState, useEffect } from "react";

interface TradeTicketProps {
    ticker: string;
    currentPrice: number;
    buyingPower: number;
    currentShares: number;
    onClose: () => void;
    onExecute: (type: "BUY" | "SELL", amount: number, mode: "DOLLARS" | "SHARES") => Promise<void>;
}

export default function TradeTicket({ ticker, currentPrice, buyingPower, currentShares, onClose, onExecute }: TradeTicketProps) {
    const [tradeType, setTradeType] = useState<"BUY" | "SELL">("BUY");
    const [inputMode, setInputMode] = useState<"DOLLARS" | "SHARES">("DOLLARS");
    const [inputValue, setInputValue] = useState("");
    const [phase, setPhase] = useState<"INPUT" | "REVIEW" | "PROCESSING" | "SUCCESS">("INPUT");

    // Dynamic color coding based on intent
    const themeColor = tradeType === "BUY" ? "emerald" : "rose";
    const themeBg = tradeType === "BUY" ? "bg-emerald-500" : "bg-rose-500";
    const themeText = tradeType === "BUY" ? "text-emerald-500" : "text-rose-500";
    const themeBorder = tradeType === "BUY" ? "border-emerald-500" : "border-rose-500";

    // Auto-calculations
    const parsedInput = parseFloat(inputValue) || 0;
    const estimatedShares = inputMode === "DOLLARS" ? parsedInput / currentPrice : parsedInput;
    const estimatedCost = inputMode === "SHARES" ? parsedInput * currentPrice : parsedInput;

    // Validation
    const hasInsufficientFunds = tradeType === "BUY" && estimatedCost > buyingPower;
    const hasInsufficientShares = tradeType === "SELL" && estimatedShares > currentShares;
    const isInvalid = parsedInput <= 0 || hasInsufficientFunds || hasInsufficientShares;

    const handleExecute = async () => {
        setPhase("PROCESSING");
        await onExecute(tradeType, parsedInput, inputMode);
        setPhase("SUCCESS");
        setTimeout(() => {
            onClose();
        }, 2000); // Close automatically after success
    };

    return (
        <div className="fixed inset-0 z-[200] bg-[#020617]/95 backdrop-blur-xl flex flex-col items-center justify-center p-4 animate-in fade-in zoom-in-95 duration-200">
            
            {/* TOP BAR / CLOSE */}
            <div className="absolute top-8 right-8">
                <button onClick={onClose} className="w-12 h-12 bg-slate-900 border border-slate-800 rounded-full flex items-center justify-center text-slate-400 hover:text-white transition-colors">
                    <span className="font-black text-xl">✕</span>
                </button>
            </div>

            {phase === "INPUT" && (
                <div className="w-full max-w-lg flex flex-col items-center">
                    
                    {/* ASSET HEADER */}
                    <h2 className="text-2xl font-black text-slate-400 uppercase tracking-widest mb-2">Trade {ticker}</h2>
                    <p className="text-4xl font-black text-white mb-12">${currentPrice.toFixed(2)}</p>

                    {/* TOGGLES */}
                    <div className="flex gap-4 mb-12 bg-slate-900 p-2 rounded-2xl border border-slate-800">
                        <button onClick={() => setTradeType("BUY")} className={`px-8 py-3 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all ${tradeType === "BUY" ? 'bg-emerald-500/20 text-emerald-500' : 'text-slate-500 hover:text-white'}`}>Buy</button>
                        <button onClick={() => setTradeType("SELL")} className={`px-8 py-3 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all ${tradeType === "SELL" ? 'bg-rose-500/20 text-rose-500' : 'text-slate-500 hover:text-white'}`}>Sell</button>
                    </div>

                    <div className="flex gap-4 mb-12">
                        <button onClick={() => setInputMode("DOLLARS")} className={`font-bold text-xs uppercase tracking-widest transition-colors ${inputMode === "DOLLARS" ? 'text-white border-b-2 border-white pb-1' : 'text-slate-600'}`}>In Dollars</button>
                        <button onClick={() => setInputMode("SHARES")} className={`font-bold text-xs uppercase tracking-widest transition-colors ${inputMode === "SHARES" ? 'text-white border-b-2 border-white pb-1' : 'text-slate-600'}`}>In Shares</button>
                    </div>

                    {/* MASSIVE INPUT */}
                    <div className="relative flex items-center justify-center w-full mb-6">
                        {inputMode === "DOLLARS" && <span className={`text-7xl font-black mr-2 ${inputValue ? 'text-white' : 'text-slate-800'}`}>$</span>}
                        <input 
                            type="number" 
                            placeholder="0"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            className={`bg-transparent outline-none text-center text-7xl font-black text-white w-full placeholder-slate-800 ${themeText}`}
                            autoFocus
                        />
                    </div>

                    {/* AUTO-CALCULATOR READOUT */}
                    <div className="h-10 mb-12 flex items-center justify-center">
                        {parsedInput > 0 && (
                            <p className="text-slate-400 font-bold uppercase tracking-widest text-[10px]">
                                {inputMode === "DOLLARS" 
                                    ? `≈ ${estimatedShares.toFixed(4)} Shares` 
                                    : `≈ $${estimatedCost.toFixed(2)} Total Cost`}
                            </p>
                        )}
                    </div>

                    {/* EXECUTION WARNINGS */}
                    <div className="h-8 mb-8">
                        {hasInsufficientFunds && <p className="text-rose-500 font-black uppercase text-[10px] tracking-widest animate-pulse">Insufficient Buying Power</p>}
                        {hasInsufficientShares && <p className="text-rose-500 font-black uppercase text-[10px] tracking-widest animate-pulse">Insufficient Shares Available</p>}
                    </div>

                    {/* REVIEW BUTTON */}
                    <button 
                        onClick={() => setPhase("REVIEW")}
                        disabled={isInvalid}
                        className={`w-full py-6 rounded-3xl font-black text-sm uppercase tracking-[0.2em] transition-all ${isInvalid ? 'bg-slate-900 text-slate-700 cursor-not-allowed' : `${themeBg} text-white shadow-[0_0_40px_rgba(0,0,0,0.5)] hover:scale-[1.02]`}`}
                    >
                        Review Order
                    </button>
                    
                    <p className="mt-8 text-[10px] font-bold text-slate-600 uppercase tracking-widest">Available Capital: ${buyingPower.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
                </div>
            )}

            {/* REVIEW / PROCESSING / SUCCESS PHASES */}
            {phase !== "INPUT" && (
                <div className="w-full max-w-md bg-slate-900 border border-slate-800 p-10 rounded-[48px] flex flex-col items-center text-center shadow-2xl animate-in slide-in-from-bottom-10">
                    
                    {phase === "SUCCESS" ? (
                        <>
                            <div className={`w-24 h-24 rounded-full ${themeBg} flex items-center justify-center mb-8 shadow-[0_0_50px_rgba(0,0,0,0.5)]`}>
                                <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={4} d="M5 13l4 4L19 7" /></svg>
                            </div>
                            <h3 className="text-3xl font-black text-white tracking-tighter mb-2">Order Executed</h3>
                            <p className="text-slate-400 font-medium">{tradeType} {estimatedShares.toFixed(4)} {ticker}</p>
                        </>
                    ) : (
                        <>
                            <p className={`text-[10px] font-black ${themeText} uppercase tracking-[0.4em] mb-8`}>Order Summary</p>
                            
                            <div className="w-full space-y-6 mb-12 text-left border-y border-slate-800 py-8">
                                <div className="flex justify-between items-center"><span className="text-slate-500 font-bold uppercase text-[10px] tracking-widest">Action</span><span className={`font-black text-sm ${themeText}`}>{tradeType} {ticker}</span></div>
                                <div className="flex justify-between items-center"><span className="text-slate-500 font-bold uppercase text-[10px] tracking-widest">Shares</span><span className="font-black text-white text-sm">{estimatedShares.toFixed(4)}</span></div>
                                <div className="flex justify-between items-center"><span className="text-slate-500 font-bold uppercase text-[10px] tracking-widest">Est. Cost</span><span className="font-black text-white text-sm">${estimatedCost.toFixed(2)}</span></div>
                            </div>

                            <button 
                                onClick={handleExecute}
                                disabled={phase === "PROCESSING"}
                                className={`w-full py-6 rounded-3xl font-black text-sm uppercase tracking-[0.2em] transition-all relative overflow-hidden ${themeBg} text-white hover:scale-[1.02] shadow-[0_0_30px_rgba(0,0,0,0.3)]`}
                            >
                                {phase === "PROCESSING" ? (
                                    <span className="flex items-center justify-center gap-3">
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        Transmitting...
                                    </span>
                                ) : (
                                    `Confirm ${tradeType}`
                                )}
                            </button>
                            {phase === "REVIEW" && <button onClick={() => setPhase("INPUT")} className="mt-6 text-[10px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors">Edit Order</button>}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}