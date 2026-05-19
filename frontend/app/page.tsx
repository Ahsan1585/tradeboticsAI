// Find your 'runDeepDive' function and replace it with:
const runMasterAnalysis = async () => {
    if (!data) return;
    setDeepDiveResult(null);
    setIsAnalyzing(true); 
    try {
        const res = await fetch(`${BACKEND_URL}/translate`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                ticker: confirmedTicker, 
                data_context: { 
                    score: data.score, 
                    price: data.price, 
                    fundamentals: data.fundamentals, 
                    ledger: data.ledger,
                    user_shares: currentPosition?.shares || 0,
                    user_avg_cost: currentPosition?.avg_cost || 0
                } 
            })
        });
        const result = await res.json();
        setDeepDiveResult(result.analysis);
    } catch { showToast("AI Node Error."); }
    setIsAnalyzing(false); 
};

// ... Then in your JSX, update the button trigger:
<button 
    onClick={() => runMasterAnalysis()} 
    className="w-full bg-blue-600 hover:bg-blue-500 py-6 rounded-[32px] font-black text-xs uppercase tracking-[0.2em] transition-all shadow-xl shadow-blue-600/20 text-white"
>
    🧠 RUN AI ANALYSIS
</button>