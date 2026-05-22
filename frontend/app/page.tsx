"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "./lib/supabase";

// 🚨 PRODUCTION URL (Change to http://127.0.0.1:8000 for local testing)
const BACKEND_URL = "https://tradebotics-api.onrender.com";

// --- MARKETING LANDING PAGE ---
function MarketingLanding({ onLoginClick, onRegisterClick }: { onLoginClick: () => void, onRegisterClick: () => void }) {
    const [demoTicker, setDemoTicker] = useState("");
    const [demoResult, setDemoResult] = useState<any>(null);
    const [demoLoading, setDemoLoading] = useState(false);

    const runDemoScan = async () => {
        if(!demoTicker) return;
        setDemoLoading(true);
        setDemoResult(null);
        
        try {
            const res = await fetch(`${BACKEND_URL}/analyze/${demoTicker.toUpperCase()}`);
            const data = await res.json();
            
            if (res.ok) {
                const trend = data.tech_score > 75 ? "bullish accumulation" : "consolidation";
                const verdict = `${data.company_name} is currently trading at $${data.price}. Initial scans indicate ${trend} with an aggregate Quant Score of ${data.score}. Technical momentum scores ${data.tech_score}/100 while institutional fundamental DNA scores ${data.fund_score}/100.`;
                
                setDemoResult({
                    ticker: data.ticker,
                    price: data.price,
                    score: data.score,
                    verdict: verdict
                });
            } else {
                setDemoResult({
                    ticker: demoTicker.toUpperCase(),
                    score: "N/A",
                    verdict: "Asset scan failed. Please verify the ticker symbol is a standard US equity."
                });
            }
        } catch (error) {
            setDemoResult({
                ticker: demoTicker.toUpperCase(),
                score: "ERR",
                verdict: "Terminal connection offline. Please try again."
            });
        }
        setDemoLoading(false);
    };

    const testimonials = [
        { name: "Marcus T.", title: "Quant Trader", img: "https://randomuser.me/api/portraits/men/32.jpg", quote: "The Tactical Exit Strategy alone saved my portfolio during the last tech correction. It accurately predicted the NVDA pullback three days before the broader market reacted." },
        { name: "Sarah J.", title: "Retail Investor", img: "https://randomuser.me/api/portraits/women/44.jpg", quote: "Having fundamental DNA and real-time global sentiment synthesized into a single terminal is a game changer. I don't execute a trade without running it through TradeBotics first." },
        { name: "David L.", title: "Swing Trader", img: "https://randomuser.me/api/portraits/men/68.jpg", quote: "The Portfolio Intelligence mapping helped me optimize my cost-basis across three different brokers. It acts like a silent, hyper-intelligent hedge fund manager." },
        { name: "Elena R.", title: "Risk Analyst", img: "https://randomuser.me/api/portraits/women/63.jpg", quote: "As a risk manager, the neural synthesis provides the exact probability matrices I need. The AI doesn't hallucinate; it strictly analyzes the math and historical tape." },
        { name: "James K.", title: "Proprietary Trader", img: "https://randomuser.me/api/portraits/men/85.jpg", quote: "I migrated from Bloomberg to TradeBotics because of the AI integrations. It filters the noise and gives me definitive strike zones instantly without the bloat." },
        { name: "Aisha M.", title: "Family Office Director", img: "https://randomuser.me/api/portraits/women/12.jpg", quote: "The automated portfolio sync completely eliminated my need for manual tracking. I see my exact P&L dynamically adjusted against AI price targets every morning." }
    ];

    return (
        <div className="min-h-screen bg-[#020617] text-slate-300 font-sans overflow-x-hidden selection:bg-blue-500/30">
            <style dangerouslySetInnerHTML={{__html: `
                @keyframes scroll {
                    0% { transform: translateX(0); }
                    100% { transform: translateX(calc(-50% - 1rem)); }
                }
                .animate-scroll {
                    animation: scroll 40s linear infinite;
                }
                .animate-scroll:hover {
                    animation-play-state: paused;
                }
            `}} />

            <nav className="w-full border-b border-slate-800/50 bg-[#020617]/80 backdrop-blur-md fixed top-0 z-50">
                <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
                    <h1 className="text-2xl font-black text-white tracking-tighter">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
                    <div className="flex items-center gap-6">
                        <button onClick={onLoginClick} className="text-xs font-black uppercase tracking-widest text-slate-400 hover:text-white transition-colors hidden md:block">Operative Login</button>
                        <button onClick={onRegisterClick} className="bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black px-6 py-3 rounded-full uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(59,130,246,0.2)]">Request Clearance</button>
                    </div>
                </div>
            </nav>

            <section className="pt-40 pb-20 px-6 max-w-7xl mx-auto flex flex-col lg:flex-row items-center gap-16">
                <div className="flex-1 space-y-8 text-center lg:text-left z-10">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-black uppercase tracking-widest mb-4">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" /> Live: Enterprise Node Online
                    </div>
                    <h2 className="text-5xl lg:text-7xl font-black text-white leading-[1.1] tracking-tighter">
                        Institutional-Grade <span className="text-blue-500">AI Analytics.</span><br/>Retail Edge.
                    </h2>
                    <p className="text-lg text-slate-400 leading-relaxed max-w-xl mx-auto lg:mx-0">
                        TradeBotics AI synthesizes global news, technical indicators, and fundamental DNA in seconds to calculate definitive strike zones and tactical exit strategies.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start">
                        <button onClick={onRegisterClick} className="w-full sm:w-auto bg-white text-[#020617] px-8 py-4 rounded-full font-black text-xs uppercase tracking-[0.2em] hover:bg-slate-200 transition-colors">Start Free Trial</button>
                        <button onClick={onLoginClick} className="w-full sm:w-auto bg-slate-900 border border-slate-700 text-white px-8 py-4 rounded-full font-black text-xs uppercase tracking-[0.2em] hover:border-blue-500 transition-colors">Sign In</button>
                    </div>
                </div>

                <div className="flex-1 w-full max-w-md relative">
                    <div className="absolute inset-0 bg-blue-600/20 blur-[100px] rounded-full pointer-events-none" />
                    <div className="bg-slate-900/60 border border-slate-800 p-8 rounded-[40px] shadow-2xl backdrop-blur-xl relative z-10">
                        <p className="text-[10px] font-black text-blue-500 uppercase tracking-[0.3em] mb-6 text-center">Free Public Pulse Scan</p>
                        
                        <div className="flex gap-2 mb-6">
                            <input value={demoTicker} onChange={(e) => setDemoTicker(e.target.value.toUpperCase())} onKeyDown={(e) => e.key === 'Enter' && runDemoScan()} placeholder="ENTER TICKER..." className="flex-1 bg-slate-950 border border-slate-800 rounded-2xl px-4 py-3 text-white font-black outline-none focus:border-blue-500 text-lg transition-colors" />
                            <button onClick={runDemoScan} className="bg-blue-600 hover:bg-blue-500 text-white px-6 rounded-2xl font-black text-[10px] uppercase tracking-widest transition-colors">
                                {demoLoading ? "..." : "SCAN"}
                            </button>
                        </div>

                        {demoLoading && (
                            <div className="py-10 flex flex-col items-center">
                                <div className="w-8 h-8 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-4" />
                                <p className="text-[10px] text-blue-500 uppercase font-black tracking-widest animate-pulse">Running Neural Synthesis...</p>
                            </div>
                        )}

                        {demoResult && !demoLoading && (
                            <div className="bg-[#020617] border border-blue-500/30 rounded-3xl p-6 animate-in zoom-in-95 fade-in text-center">
                                <p className="text-3xl font-black text-white mb-1">{demoResult.ticker}</p>
                                {demoResult.price && <p className="text-xs font-bold text-slate-400 mb-4 bg-slate-900/50 inline-block px-3 py-1 rounded-lg border border-slate-800">LIVE PRICE: ${demoResult.price}</p>}
                                <div className="flex items-center justify-center gap-2 mb-4">
                                    <span className="text-blue-500 font-black text-2xl">{demoResult.score}</span>
                                    <span className="text-[10px] text-slate-500 font-bold uppercase">Quant Score</span>
                                </div>
                                <p className="text-sm text-slate-300 italic border-l-2 border-blue-500 pl-3 text-left leading-relaxed mb-6">
                                    "{demoResult.verdict}"
                                </p>
                                <button onClick={onRegisterClick} className="w-full bg-blue-600/10 hover:bg-blue-600 border border-blue-500/50 hover:border-transparent text-blue-400 hover:text-white py-3 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all">
                                    Unlock Full AI Deep Dive
                                </button>
                            </div>
                        )}
                        {!demoResult && !demoLoading && (
                            <p className="text-center text-slate-500 text-xs italic font-medium px-4">Input any US equity ticker to experience a fractional execution of our proprietary AI scoring model.</p>
                        )}
                    </div>
                </div>
            </section>

            <section className="border-t border-slate-800/50 bg-[#060b1f] py-24 overflow-hidden">
                <div className="flex flex-col items-center justify-center mb-16 px-6 text-center">
                    <div className="flex gap-1 text-blue-500 text-2xl mb-4 drop-shadow-[0_0_10px_rgba(59,130,246,0.8)]">
                        ★★★★★
                    </div>
                    <h3 className="text-3xl font-black text-white tracking-tighter uppercase mb-2">Operative Testimonials</h3>
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Trusted by over 4,500+ Institutional & Retail Operatives</p>
                </div>
                
                <div className="flex overflow-hidden w-full relative group">
                    <div className="absolute top-0 left-0 w-32 h-full bg-gradient-to-r from-[#060b1f] to-transparent z-10 pointer-events-none" />
                    <div className="absolute top-0 right-0 w-32 h-full bg-gradient-to-l from-[#060b1f] to-transparent z-10 pointer-events-none" />
                    
                    <div className="flex gap-8 min-w-max animate-scroll">
                        {[...testimonials, ...testimonials].map((t, i) => (
                            <div key={i} className="bg-slate-900/40 border border-slate-800 p-8 rounded-[32px] text-left flex flex-col w-[400px] shrink-0 whitespace-normal hover:border-blue-500/50 transition-colors shadow-xl">
                                <div className="flex items-center gap-1 text-blue-500 mb-4 text-lg">★★★★★</div>
                                <p className="text-slate-300 text-sm leading-relaxed mb-6 flex-1">"{t.quote}"</p>
                                <div className="flex items-center gap-4 border-t border-slate-800/50 pt-6">
                                    <img src={t.img} alt={t.name} className="w-10 h-10 rounded-full border border-slate-700" />
                                    <div>
                                        <p className="text-[10px] font-black uppercase text-white tracking-widest">{t.name}</p>
                                        <p className="text-[9px] font-bold uppercase text-slate-500 tracking-widest">{t.title}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            <section className="py-24 max-w-7xl mx-auto px-6">
                 <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                    <div>
                        <div className="w-12 h-12 bg-blue-500/10 rounded-2xl flex items-center justify-center mb-6 border border-blue-500/20"><span className="text-blue-500 text-xl">🧠</span></div>
                        <h4 className="text-xl font-black text-white mb-4">Neural Market Synthesis</h4>
                        <p className="text-slate-400 text-sm leading-relaxed">We aggregate millions of data points from global news wires, SEC filings, and technical indicators to provide a definitive 1-100 Quant Score for any asset.</p>
                    </div>
                    <div>
                        <div className="w-12 h-12 bg-orange-500/10 rounded-2xl flex items-center justify-center mb-6 border border-orange-500/20"><span className="text-orange-500 text-xl">🎯</span></div>
                        <h4 className="text-xl font-black text-white mb-4">Tactical Strike Zones</h4>
                        <p className="text-slate-400 text-sm leading-relaxed">Remove emotion from your entries and exits. The AI calculates precise trailing targets and stop-loss floors based on real-time volatility profiles.</p>
                    </div>
                    <div>
                        <div className="w-12 h-12 bg-purple-500/10 rounded-2xl flex items-center justify-center mb-6 border border-purple-500/20"><span className="text-purple-500 text-xl">💼</span></div>
                        <h4 className="text-xl font-black text-white mb-4">Portfolio Intelligence</h4>
                        <p className="text-slate-400 text-sm leading-relaxed">Securely sync your current holdings to the terminal. Our AI acts as a dedicated risk manager, analyzing your specific exposure and cost-basis.</p>
                    </div>
                 </div>
            </section>
            
            <footer className="border-t border-slate-800/50 py-10 text-center">
                <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
            </footer>
        </div>
    );
}

// --- MAIN APP ENTRY ---
export default function Home() {
  const router = useRouter(); 
  const [user, setUser] = useState<any>(null);
  const [userProfile, setUserProfile] = useState<any>(null); 
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  
  const [showAuth, setShowAuth] = useState(false);
  
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState(""); 
  const [isSignUp, setIsSignUp] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  
  const [toastMessage, setToastMessage] = useState<string | null>(null); 

  useEffect(() => {
    const checkUser = async () => {
      setIsAuthChecking(true);
      const { data: { session }, error } = await supabase.auth.getSession();
      
      if (error) {
          console.warn("Auth Token Corrupted. Purging local cache.");
          await supabase.auth.signOut();
          setUser(null);
          setUserProfile(null);
      } else if (session) {
          setUser(session.user);
          const { data: profile } = await supabase.from('profiles').select('*').eq('id', session.user.id).single();
          setUserProfile(profile);
          
          if (profile?.status !== 'pending') {
              router.push('/hub');
          }
      }
      setIsAuthChecking(false);
    };
    
    checkUser();

    const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === 'SIGNED_OUT') {
          setUser(null);
          setUserProfile(null);
      } else if (session && (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED')) {
          setUser(session.user);
          const { data: profile } = await supabase.from('profiles').select('*').eq('id', session.user.id).single();
          setUserProfile(profile);
          
          if (event === 'SIGNED_IN' && profile?.status !== 'pending') {
              router.push('/hub');
          }
      }
    });

    return () => {
      authListener.subscription.unsubscribe();
    };
  }, [router]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500); 
  };

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    if (isSignUp) {
      if (password !== confirmPassword) {
          showToast("Passwords do not match.");
          setAuthLoading(false);
          return;
      }
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) showToast(error.message); 
      else showToast("Registration received. Please check your email to verify your account.");
    } else {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
          if (error.message.includes("Email not confirmed")) {
              showToast("Access Denied: Email not verified. Please check your inbox.");
          } else { showToast(error.message); }
      } else {
          const { data: profile } = await supabase.from('profiles').select('*').eq('id', data.user.id).single();
          setUserProfile(profile);
          setUser(data.user);
      }
    }
    setAuthLoading(false);
  };

  const handleSignOut = async () => { 
    await supabase.auth.signOut(); 
    setUser(null); 
    setUserProfile(null);
    setShowAuth(false); 
  };

  if (isAuthChecking) {
      return <main className="min-h-screen bg-[#020617]"></main>; // Blank screen while verifying token to prevent flashing
  }

  // If they are logged in and approved, they are about to be redirected to /hub. Show loader.
  if (user && userProfile?.status !== 'pending') {
      return (
          <main className="min-h-screen bg-[#020617] flex items-center justify-center">
             <div className="w-16 h-16 border-4 border-slate-800 border-t-blue-500 rounded-full animate-spin mb-6" />
          </main>
      );
  }

  if (!user && !showAuth) {
      return <MarketingLanding 
          onLoginClick={() => { setIsSignUp(false); setShowAuth(true); }} 
          onRegisterClick={() => { setIsSignUp(true); setShowAuth(true); }} 
      />;
  }

  if (!user && showAuth) return (
    <main className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-6 relative">
      <button onClick={() => setShowAuth(false)} className="absolute top-8 left-8 text-slate-500 font-bold hover:text-white transition-colors text-sm">← Back to Home</button>
      {toastMessage && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center pointer-events-none">
           <div className="bg-slate-900 border border-blue-500/50 px-10 py-6 rounded-3xl shadow-[0_0_40px_rgba(59,130,246,0.3)] animate-in zoom-in-95 fade-in duration-300 flex flex-col items-center">
              <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center mb-3"><div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" /></div>
              <p className="text-white font-black uppercase tracking-widest text-sm text-center">{toastMessage}</p>
           </div>
        </div>
      )}
      <div className="w-full max-w-md bg-slate-900/40 border border-slate-800 p-10 rounded-[48px] shadow-2xl text-center z-10">
        <h1 className="text-4xl font-black text-white tracking-tighter mb-2">TRADEBOTICS<span className="text-blue-500">AI</span></h1>
        
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-8">
            {isSignUp ? "New Operative Registration" : "Operative Login"}
        </p>

        <form onSubmit={handleAuth} className="space-y-4 text-left">
          {isSignUp ? (
            <>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-4 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Official Email Address" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-4 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Create Access Key (Password)" minLength={6} required />
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-4 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Confirm Access Key" minLength={6} required />
            </>
          ) : (
            <>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-5 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Personnel ID (Email)" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-6 py-5 text-white outline-none focus:border-blue-500 transition-colors" placeholder="Access Key (Password)" required />
            </>
          )}
          <button type="submit" disabled={authLoading} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-black py-5 rounded-2xl uppercase tracking-widest text-xs transition-colors mt-4">
            {isSignUp ? "Submit Clearance Request" : "Access Terminal"}
          </button>
        </form>
        <button onClick={() => { setIsSignUp(!isSignUp); setPassword(""); setConfirmPassword(""); setEmail(""); }} className="w-full mt-6 text-[10px] text-slate-400 uppercase font-bold hover:text-white transition-colors">
            {isSignUp ? "← Return to Login" : "Request Access"}
        </button>
      </div>
      <div className="absolute bottom-6 w-full text-center pointer-events-none">
          <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
      </div>
    </main>
  );

  if (user && userProfile?.status === 'pending') return (
    <main className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-6 relative">
      <div className="w-full max-w-md bg-slate-900/40 border border-orange-500/50 p-10 rounded-[48px] shadow-2xl text-center animate-in fade-in zoom-in-95 z-10">
        <div className="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <div className="w-6 h-6 border-4 border-orange-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <h2 className="text-2xl font-black text-white mb-4 uppercase tracking-widest">Clearance Pending</h2>
        <p className="text-slate-400 text-sm leading-relaxed mb-8">
            Your email has been verified. However, an administrator must manually approve your clearance before terminal access is granted.
        </p>
        <button onClick={handleSignOut} className="text-[10px] uppercase font-black text-slate-500 hover:text-white transition-all tracking-widest border border-slate-800 px-6 py-3 rounded-full hover:bg-slate-800">
            Sign Out
        </button>
      </div>
      <div className="absolute bottom-6 w-full text-center pointer-events-none">
          <p className="text-[10px] uppercase tracking-[0.2em] font-black text-slate-600">© 2026 TradeBotics AI. All Systems Operational.</p>
      </div>
    </main>
  );

  return null;
}