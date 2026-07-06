"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "./lib/supabase";
import { BACKEND_URL } from "./lib/config";
import ThemeToggle from "./components/ThemeToggle";
import Button from "./components/ui/Button";
import Card from "./components/ui/Card";

// --- MARKETING LANDING PAGE ---
function MarketingLanding({ onLoginClick, onRegisterClick }: { onLoginClick: () => void, onRegisterClick: () => void }) {
    const [demoTicker, setDemoTicker] = useState("");
    const [demoResult, setDemoResult] = useState<any>(null);
    const [demoLoading, setDemoLoading] = useState(false);
    const [trackRecord, setTrackRecord] = useState<any[]>([]);

    useEffect(() => {
        fetch(`${BACKEND_URL}/track-record`)
            .then((res) => res.json())
            .then((data) => setTrackRecord(data.tracks || []))
            .catch(() => setTrackRecord([]));
    }, []);

    const runDemoScan = async () => {
        if (!demoTicker) return;
        setDemoLoading(true);
        setDemoResult(null);

        try {
            const res = await fetch(`${BACKEND_URL}/analyze/${demoTicker.toUpperCase()}`);
            const data = await res.json();

            if (res.ok) {
                const trend = data.tech_score > 75 ? "bullish accumulation" : "consolidation";
                const verdict = `${data.company_name} is currently trading at $${data.price}. Initial scans indicate ${trend} with a score of ${data.score}. Technical momentum scores ${data.tech_score}/100 while fundamentals score ${data.fund_score}/100.`;
                setDemoResult({ ticker: data.ticker, price: data.price, score: data.score, verdict });
            } else {
                setDemoResult({ ticker: demoTicker.toUpperCase(), score: "N/A", verdict: "Couldn't find that ticker. Try a standard US equity symbol." });
            }
        } catch {
            setDemoResult({ ticker: demoTicker.toUpperCase(), score: "ERR", verdict: "Connection issue -- please try again." });
        }
        setDemoLoading(false);
    };

    return (
        <div className="min-h-screen bg-bg-primary text-text-primary font-sans overflow-x-hidden selection:bg-accent/30">
            <nav className="w-full border-b border-border bg-bg-primary/90 backdrop-blur-md fixed top-0 z-50">
                <div className="max-w-7xl mx-auto px-4 md:px-6 h-16 md:h-20 flex items-center justify-between">
                    <h1 className="text-xl md:text-2xl font-black tracking-tighter">TRADEBOTICS<span className="text-accent">AI</span></h1>
                    <div className="flex items-center gap-3 md:gap-4">
                        <ThemeToggle />
                        <button onClick={onLoginClick} className="text-[10px] md:text-xs font-black uppercase tracking-widest text-text-secondary hover:text-text-primary transition-colors hidden sm:block">Log In</button>
                        <Button onClick={onRegisterClick} size="sm">Start Free</Button>
                    </div>
                </div>
            </nav>

            <section className="pt-28 md:pt-40 pb-16 md:pb-20 px-4 md:px-6 max-w-7xl mx-auto flex flex-col lg:flex-row items-center gap-12 md:gap-16">
                <div className="flex-1 space-y-6 md:space-y-8 text-center lg:text-left z-10 w-full">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent text-[9px] md:text-[10px] font-black uppercase tracking-widest mb-2 md:mb-4">
                        7-Day Free Trial &middot; No Card Required
                    </div>
                    <h2 className="text-4xl sm:text-5xl lg:text-7xl font-black leading-[1.1] tracking-tighter">
                        Know what to invest in, <span className="text-accent">without the guesswork.</span>
                    </h2>
                    <p className="text-sm md:text-lg text-text-secondary leading-relaxed max-w-xl mx-auto lg:mx-0">
                        TradeBotics turns real technical data, hedge-fund filings, and insider trades into a
                        plain-English verdict on any stock -- with a stop-loss and target on every pick.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center gap-3 md:gap-4 justify-center lg:justify-start w-full sm:w-auto px-4 sm:px-0">
                        <Button onClick={onRegisterClick} size="lg" className="w-full sm:w-auto">Start Free Trial</Button>
                        <Button onClick={onLoginClick} variant="secondary" size="lg" className="w-full sm:w-auto">Log In</Button>
                    </div>
                </div>

                <div className="flex-1 w-full max-w-md relative mt-8 lg:mt-0">
                    <Card className="p-6 md:p-8 relative z-10">
                        <p className="text-[9px] md:text-[10px] font-black text-accent uppercase tracking-[0.3em] mb-4 md:mb-6 text-center">Try It Free -- No Signup</p>

                        <div className="flex flex-col sm:flex-row gap-2 mb-6">
                            <input
                                value={demoTicker}
                                onChange={(e) => setDemoTicker(e.target.value.toUpperCase())}
                                onKeyDown={(e) => e.key === "Enter" && runDemoScan()}
                                placeholder="Enter a ticker, e.g. AAPL"
                                className="flex-1 bg-bg-primary border border-border rounded-xl px-4 py-3 md:py-4 font-black outline-none focus:border-accent text-base md:text-lg transition-colors text-center sm:text-left"
                            />
                            <Button onClick={runDemoScan} className="w-full sm:w-auto">{demoLoading ? "..." : "Scan"}</Button>
                        </div>

                        {demoLoading && (
                            <div className="py-8 md:py-10 flex flex-col items-center">
                                <div className="w-6 h-6 md:w-8 md:h-8 border-4 border-border border-t-accent rounded-full animate-spin mb-3 md:mb-4" />
                                <p className="text-[9px] md:text-[10px] text-accent uppercase font-black tracking-widest animate-pulse text-center">Analyzing...</p>
                            </div>
                        )}

                        {demoResult && !demoLoading && (
                            <div className="bg-bg-primary border border-accent/30 rounded-2xl p-5 md:p-6 text-center">
                                <p className="text-2xl md:text-3xl font-black mb-1">{demoResult.ticker}</p>
                                {demoResult.price && <p className="text-[10px] md:text-xs font-bold text-text-secondary mb-4 bg-bg-surface inline-block px-3 py-1 rounded-lg border border-border">${demoResult.price}</p>}
                                <div className="flex items-center justify-center gap-2 mb-4">
                                    <span className="text-accent font-black text-xl md:text-2xl">{demoResult.score}</span>
                                    <span className="text-[9px] md:text-[10px] text-text-secondary font-bold uppercase">Score</span>
                                </div>
                                <p className="text-xs md:text-sm text-text-secondary italic border-l-2 border-accent pl-3 text-left leading-relaxed mb-6">
                                    &ldquo;{demoResult.verdict}&rdquo;
                                </p>
                                <Button onClick={onRegisterClick} className="w-full">Get The Full Picture</Button>
                            </div>
                        )}
                        {!demoResult && !demoLoading && (
                            <p className="text-center text-text-secondary text-[10px] md:text-xs italic font-medium px-2 md:px-4">Type any US stock ticker to see a real, live sample of our scoring model.</p>
                        )}
                    </Card>
                </div>
            </section>

            <section className="border-t border-border bg-bg-surface py-16 md:py-24">
                <div className="flex flex-col items-center justify-center mb-10 md:mb-14 px-4 md:px-6 text-center">
                    <h3 className="text-2xl md:text-3xl font-black tracking-tighter uppercase mb-2">Our Live Track Record</h3>
                    <p className="text-text-secondary font-bold uppercase tracking-widest text-[9px] md:text-[10px]">Every signal logged before we know the outcome. No cherry-picking.</p>
                </div>

                <div className="max-w-5xl mx-auto px-4 md:px-6">
                    {trackRecord.length === 0 ? (
                        <p className="text-text-secondary text-center text-sm py-6">
                            Track record is building -- resolved trades will appear here as signals play out.
                        </p>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
                            {trackRecord.map((t: any) => (
                                <Card key={`${t.horizon}-${t.engine_version}`} className="p-6 text-center">
                                    <p className="text-[9px] font-bold uppercase text-text-secondary tracking-widest mb-2">{t.horizon} track</p>
                                    <p className={`text-3xl font-black mb-1 ${t.hit_rate >= 55 ? "text-gain" : t.hit_rate >= 45 ? "text-warn" : "text-loss"}`}>{t.hit_rate}%</p>
                                    <p className="text-[10px] text-text-secondary uppercase tracking-wide">Hit Rate &middot; {t.total_resolved} resolved trades</p>
                                </Card>
                            ))}
                        </div>
                    )}
                    <p className="text-[10px] text-text-secondary text-center mt-6">
                        <a href="/track-record" className="underline hover:text-text-primary">See the full track record &rarr;</a>
                    </p>
                </div>
            </section>

            <section className="py-16 md:py-24 max-w-7xl mx-auto px-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-12 text-center md:text-left">
                    <div className="flex flex-col items-center md:items-start">
                        <div className="w-12 h-12 bg-accent/10 rounded-2xl flex items-center justify-center mb-4 md:mb-6 border border-accent/20">
                            <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        </div>
                        <h4 className="text-lg md:text-xl font-black mb-3 md:mb-4">Honest, Deterministic Signals</h4>
                        <p className="text-text-secondary text-xs md:text-sm leading-relaxed">Real technical indicators and market-regime checks compute a transparent verdict -- the AI narrates it, it never invents it.</p>
                    </div>
                    <div className="flex flex-col items-center md:items-start">
                        <div className="w-12 h-12 bg-warn/10 rounded-2xl flex items-center justify-center mb-4 md:mb-6 border border-warn/20">
                            <svg className="w-6 h-6 text-warn" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 9.75a2.25 2.25 0 114.5 0 2.25 2.25 0 01-4.5 0zM12 3a9 9 0 100 18 9 9 0 000-18zm0 4.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9z" />
                            </svg>
                        </div>
                        <h4 className="text-lg md:text-xl font-black mb-3 md:mb-4">Built-In Exit Plan</h4>
                        <p className="text-text-secondary text-xs md:text-sm leading-relaxed">Every BUY ships with an ATR-based stop and target, so you always know when to walk away -- winning or losing.</p>
                    </div>
                    <div className="flex flex-col items-center md:items-start">
                        <div className="w-12 h-12 bg-accent/10 rounded-2xl flex items-center justify-center mb-4 md:mb-6 border border-accent/20">
                            <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21h18M4 21V9l8-6 8 6v12M9 21v-6h6v6" />
                            </svg>
                        </div>
                        <h4 className="text-lg md:text-xl font-black mb-3 md:mb-4">See What Smart Money Is Doing</h4>
                        <p className="text-text-secondary text-xs md:text-sm leading-relaxed">We track hedge-fund 13F filings and insider trades directly from SEC EDGAR, so you know when the pros are buying too.</p>
                    </div>
                </div>
            </section>

            <footer className="border-t border-border py-8 md:py-10 text-center">
                <p className="text-[9px] md:text-[10px] uppercase tracking-[0.2em] font-black text-text-secondary">© 2026 TradeBotics AI</p>
            </footer>
        </div>
    );
}

/// --- MAIN APP ENTRY ---
export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);

  const [showAuth, setShowAuth] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

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
      else showToast("Account created! Check your email to verify, then log in to start your free trial.");
    } else {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
          if (error.message.includes("Email not confirmed")) {
              showToast("Please verify your email before logging in.");
          } else { showToast(error.message); }
      } else {
          setUser(data.user);
          router.push('/hub');
      }
    }
    setAuthLoading(false);
  };

  if (user) {
      return (
          <main className="min-h-screen bg-bg-primary flex items-center justify-center">
             <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-border border-t-accent rounded-full animate-spin mb-6" />
          </main>
      );
  }

  if (!showAuth) {
      return <MarketingLanding
          onLoginClick={() => { setIsSignUp(false); setShowAuth(true); }}
          onRegisterClick={() => { setIsSignUp(true); setShowAuth(true); }}
      />;
  }

  return (
    <main className="min-h-screen bg-bg-primary flex flex-col items-center justify-center p-4 md:p-6 relative">
      <button onClick={() => setShowAuth(false)} className="absolute top-6 left-4 md:top-8 md:left-8 text-text-secondary font-bold hover:text-text-primary transition-colors text-xs md:text-sm">&larr; Back to Home</button>
      <div className="absolute top-6 right-4 md:top-8 md:right-8"><ThemeToggle /></div>

      {toastMessage && (
        <div className="fixed inset-x-4 top-4 md:inset-0 md:top-0 z-[150] flex items-start md:items-center justify-center pointer-events-none">
           <Card className="px-6 py-4 md:px-10 md:py-6 flex flex-col items-center pointer-events-auto">
              <p className="font-black uppercase tracking-widest text-[10px] md:text-sm text-center">{toastMessage}</p>
           </Card>
        </div>
      )}

      <Card className="w-full max-w-md p-6 md:p-10 text-center z-10 mt-12 md:mt-0">
        <h1 className="text-3xl md:text-4xl font-black tracking-tighter mb-2">TRADEBOTICS<span className="text-accent">AI</span></h1>

        <p className="text-[9px] md:text-[10px] font-black text-text-secondary uppercase tracking-widest mb-6 md:mb-8">
            {isSignUp ? "Create Your Account" : "Welcome Back"}
        </p>

        <form onSubmit={handleAuth} className="space-y-3 md:space-y-4 text-left">
          {isSignUp ? (
            <>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-bg-primary border border-border rounded-xl px-4 py-3 md:px-6 md:py-4 outline-none focus:border-accent transition-colors text-sm md:text-base" placeholder="Email" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-bg-primary border border-border rounded-xl px-4 py-3 md:px-6 md:py-4 outline-none focus:border-accent transition-colors text-sm md:text-base" placeholder="Password" minLength={6} required />
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full bg-bg-primary border border-border rounded-xl px-4 py-3 md:px-6 md:py-4 outline-none focus:border-accent transition-colors text-sm md:text-base" placeholder="Confirm Password" minLength={6} required />
            </>
          ) : (
            <>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-bg-primary border border-border rounded-xl px-4 py-3 md:px-6 md:py-4 outline-none focus:border-accent transition-colors text-sm md:text-base" placeholder="Email" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-bg-primary border border-border rounded-xl px-4 py-3 md:px-6 md:py-4 outline-none focus:border-accent transition-colors text-sm md:text-base" placeholder="Password" required />
            </>
          )}
          <Button type="submit" disabled={authLoading} className="w-full mt-2 md:mt-4">
            {isSignUp ? "Start Free Trial" : "Log In"}
          </Button>
        </form>
        <button onClick={() => { setIsSignUp(!isSignUp); setPassword(""); setConfirmPassword(""); setEmail(""); }} className="w-full mt-4 md:mt-6 text-[9px] md:text-[10px] text-text-secondary uppercase font-bold hover:text-text-primary transition-colors">
            {isSignUp ? "Already have an account? Log in" : "New here? Start your free trial"}
        </button>
      </Card>
      <div className="absolute bottom-6 w-full text-center pointer-events-none">
          <p className="text-[9px] md:text-[10px] uppercase tracking-[0.2em] font-black text-text-secondary">© 2026 TradeBotics AI</p>
      </div>
    </main>
  );
}
