"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase"; 

export default function TermsModal() {
    const [showTerms, setShowTerms] = useState(false);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        const checkTermsAcceptance = async () => {
            const { data: { user } } = await supabase.auth.getUser();
            
            if (user) {
                // USING SESSION STORAGE: Wipes automatically when the browser/tab is closed
                const hasAccepted = sessionStorage.getItem(`tos_accepted_${user.id}`);
                
                if (!hasAccepted) {
                    setShowTerms(true);
                }
            }
            setLoading(false);
        };

        checkTermsAcceptance();
    }, []);

    const handleAccept = async () => {
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            // Log the acceptance to the active session only
            sessionStorage.setItem(`tos_accepted_${user.id}`, "true");
            setShowTerms(false);
        }
    };

    const handleDecline = async () => {
        // 1. Destroy the Supabase session
        await supabase.auth.signOut();
        // 2. Clear any lingering session storage just in case
        sessionStorage.clear();
        // 3. Route back to the landing page
        router.push("/");
    };

    if (loading || !showTerms) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-sm p-4">
            <div className="bg-slate-900 border border-slate-700 w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-300">
                
                {/* Header */}
                <div className="p-6 border-b border-slate-800 bg-slate-950">
                    <h2 className="text-2xl font-black text-white uppercase tracking-widest">
                        TradeBotics<span className="text-blue-500">AI</span> Legal Terms
                    </h2>
                    <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-bold">Mandatory User Agreement</p>
                </div>

                {/* Terms Content - Scrollable */}
                <div className="p-6 overflow-y-auto custom-scrollbar flex-1 text-sm text-slate-300 leading-relaxed space-y-4">
                    <p><strong>Last Updated: May 2026</strong></p>
                    <p>Welcome to TradeBotics AI. Before accessing the neural risk synthesis dashboard and market intelligence tools, you must read and agree to our updated Terms of Service and Privacy Policy.</p>
                    
                    <h3 className="text-white font-bold mt-4">1. Educational Purposes Only</h3>
                    <p>The quantitative data, AI critiques, and tactical verdicts provided by TradeBotics AI are strictly for educational and informational purposes. TradeBotics AI is not a registered financial advisor. You acknowledge that all trading involves risk and past performance is not indicative of future results.</p>

                    <h3 className="text-white font-bold mt-4">2. Data Processing and AI Training</h3>
                    <p>By using this platform, you consent to the processing of your portfolio data by our algorithmic models. Your anonymized interaction data may be utilized to refine and train future iterations of the TradeBotics AI models.</p>

                    <h3 className="text-white font-bold mt-4">3. Limitation of Liability</h3>
                    <p>Under no circumstances shall TradeBotics AI or its operators be held liable for any direct, indirect, or consequential financial losses resulting from the use of, or inability to use, the platform's insights.</p>
                </div>

                {/* Footer Actions */}
                <div className="p-6 border-t border-slate-800 bg-slate-950 flex justify-end gap-4">
                    <button 
                        onClick={handleDecline} 
                        className="px-6 py-3 text-xs font-bold text-slate-400 hover:text-white uppercase tracking-widest transition-colors"
                    >
                        Decline & Exit
                    </button>
                    <button 
                        onClick={handleAccept}
                        className="bg-blue-600 hover:bg-blue-500 text-white font-black px-8 py-3 rounded-lg uppercase tracking-widest text-xs transition-colors shadow-lg shadow-blue-900/50"
                    >
                        I Accept & Agree
                    </button>
                </div>
            </div>
        </div>
    );
}