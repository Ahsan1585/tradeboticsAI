"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import { apiFetch } from "../lib/config";
import TermsModal from "../components/TermsModal";
import ThemeToggle from "../components/ThemeToggle";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";

export default function HubPage() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");
  const [virtualCash, setVirtualCash] = useState<number>(0);
  const [tokens, setTokens] = useState<number>(0);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [planStatus, setPlanStatus] = useState<string>("free");
  const [upgrading, setUpgrading] = useState(false);

  useEffect(() => {
    const loadUserData = async () => {
      const { data: { session }, error } = await supabase.auth.getSession();
      if (error || !session) {
        router.push("/");
        return;
      }

      setIsAuthorized(true);

      const { data: profile } = await supabase
        .from("profiles")
        .select("virtual_cash_balance, ai_token_balance")
        .eq("id", session.user.id)
        .single();

      if (profile) {
        setVirtualCash(profile.virtual_cash_balance);
        setTokens(profile.ai_token_balance);
      }

      // Lazily initializes a new signup's 7-day trial + token grant on first visit.
      try {
        const res = await apiFetch("/billing/status");
        if (res.ok) {
          const status = await res.json();
          setPlanStatus(status.plan_status);
          if (typeof status.ai_token_balance === "number") setTokens(status.ai_token_balance);
        }
      } catch {
        // Non-fatal -- billing status is a nice-to-have on this page.
      }
    };

    loadUserData();
  }, [router]);

  const handleUpgrade = async () => {
    setUpgrading(true);
    try {
      const res = await apiFetch("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ mode: "subscription" }),
      });
      const result = await res.json();
      if (res.ok && result.checkout_url) {
        window.location.href = result.checkout_url;
      }
    } finally {
      setUpgrading(false);
    }
  };

  const handleScan = () => {
    if (!ticker.trim()) return;
    router.push(`/terminal?ticker=${ticker.toUpperCase()}`);
  };

  const handleSignOut = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
        sessionStorage.removeItem(`tos_accepted_${user.id}`);
    }
    await supabase.auth.signOut();
    router.push("/");
  };

  if (!isAuthorized) {
      return (
          <main className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
              <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-border border-t-accent rounded-full animate-spin mb-4 md:mb-6" />
          </main>
      );
  }

  return (
    <main className="min-h-screen bg-bg-primary text-text-primary flex flex-col font-sans relative overflow-x-hidden">

      <TermsModal />

      <header className="w-full flex flex-col md:flex-row justify-between items-center p-4 md:p-6 border-b border-border bg-bg-primary/90 backdrop-blur-md z-50 gap-4 md:gap-0">
        <div className="w-full flex justify-between items-center md:w-auto">
          <h1 className="text-2xl md:text-3xl font-black tracking-tighter cursor-pointer" onClick={() => router.push('/hub')}>
            TRADEBOTICS<span className="text-accent">AI</span>
          </h1>
          <button
            onClick={handleSignOut}
            className="md:hidden text-[9px] font-black uppercase tracking-widest bg-bg-surface hover:bg-bg-surface-hover text-text-secondary hover:text-text-primary px-4 py-2.5 rounded-full transition-colors border border-border"
          >
            Sign Out
          </button>
        </div>

        <div className="flex items-center gap-3 md:gap-4 w-full md:w-auto justify-between md:justify-end">
          <div className="flex items-center gap-4 md:gap-6 bg-bg-surface px-5 md:px-6 py-2 rounded-xl md:rounded-full border border-border w-full md:w-auto justify-center">
            <div className="text-right border-r border-border pr-4 md:pr-6">
              <p className="text-[8px] md:text-[9px] text-text-secondary uppercase tracking-widest font-bold">Virtual Cash</p>
              <p className="text-xs md:text-sm font-mono font-black text-gain">${virtualCash.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            </div>
            <div className="text-right">
              <p className="text-[8px] md:text-[9px] text-text-secondary uppercase tracking-widest font-bold">AI Tokens</p>
              <p className="text-xs md:text-sm font-mono font-black text-accent">{tokens}</p>
            </div>
          </div>
          <ThemeToggle className="hidden md:flex" />
          {planStatus !== "pro" && (
            <Button onClick={handleUpgrade} disabled={upgrading} size="sm" className="shrink-0">
              {upgrading ? "Loading..." : planStatus === "trial" ? "Upgrade to Pro" : "Go Pro — $9.99/mo"}
            </Button>
          )}
          <button
            onClick={handleSignOut}
            className="hidden md:block text-[10px] font-black uppercase tracking-widest bg-bg-surface hover:bg-bg-surface-hover text-text-secondary hover:text-text-primary px-5 py-2.5 rounded-full transition-colors border border-border"
          >
            Sign Out
          </button>
        </div>
      </header>

      <div className="flex flex-col items-center justify-center mt-12 md:mt-24 px-4 w-full max-w-4xl mx-auto z-10">
        <div className="text-center mb-8 md:mb-10">
          <h2 className="text-4xl sm:text-5xl md:text-7xl font-black tracking-tighter mb-4 md:mb-6 leading-tight">
            Find your next <br className="hidden sm:block" />
            <span className="text-accent">winning trade.</span>
          </h2>
          <p className="text-text-secondary text-sm sm:text-lg md:text-xl font-medium max-w-2xl mx-auto leading-relaxed">
            Type any stock ticker below to get instant, easy-to-understand insights and discover hidden market opportunities.
          </p>
        </div>

        <div className="flex w-full bg-bg-surface p-2 md:p-3 rounded-full border-2 border-border focus-within:border-accent transition-all">
          <div className="pl-4 md:pl-6 flex items-center justify-center text-text-secondary shrink-0">
            <svg className="w-5 h-5 md:w-8 md:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === 'Enter' && handleScan()}
            className="flex-1 bg-transparent border-none font-black px-3 md:px-6 outline-none text-lg sm:text-2xl md:text-3xl placeholder:text-text-secondary/50 uppercase min-w-0"
            placeholder="e.g. AAPL, NVDA"
          />
          <Button onClick={handleScan} size="lg" className="shrink-0">Analyze</Button>
        </div>
      </div>

      <div
        onClick={() => router.push('/beginner')}
        className="max-w-4xl mx-auto mt-10 md:mt-16 px-4 sm:px-6 w-full z-10"
      >
        <Card interactive className="p-5 md:p-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-gain font-black text-sm md:text-base">New to investing? Try Simple Mode →</p>
            <p className="text-text-secondary text-xs md:text-sm mt-1">Plain-English picks, no jargon. Every idea comes with a plan.</p>
          </div>
          <span className="text-2xl shrink-0">🌱</span>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 max-w-6xl mx-auto mt-8 md:mt-12 px-4 sm:px-6 pb-16 md:pb-24 z-10 w-full">

        <Card interactive onClick={() => router.push('/terminal')} className="p-6 md:p-8 group">
          <div className="w-12 h-12 md:w-14 md:h-14 bg-accent/10 rounded-full flex items-center justify-center text-accent text-xl md:text-2xl mb-4 md:mb-6 group-hover:scale-110 transition-transform">
            🔍
          </div>
          <h3 className="text-xl md:text-2xl font-black mb-2 md:mb-3">AI Stock Scanner</h3>
          <p className="text-xs md:text-sm text-text-secondary leading-relaxed font-medium">
            Don&apos;t guess. Search any stock and get a clear, honest verdict backed by real data.
          </p>
        </Card>

        <Card interactive onClick={() => router.push('/portfolio')} className="p-6 md:p-8 group">
          <div className="w-12 h-12 md:w-14 md:h-14 bg-accent/10 rounded-full flex items-center justify-center text-accent text-xl md:text-2xl mb-4 md:mb-6 group-hover:scale-110 transition-transform">
            💼
          </div>
          <h3 className="text-xl md:text-2xl font-black mb-2 md:mb-3">Smart Portfolio</h3>
          <p className="text-xs md:text-sm text-text-secondary leading-relaxed font-medium">
            Track all your investments in one place, with AI-monitored holdings and suggested moves.
          </p>
        </Card>

        <Card interactive onClick={() => router.push('/vault')} className="p-6 md:p-8 group">
          <div className="w-12 h-12 md:w-14 md:h-14 bg-gain/10 rounded-full flex items-center justify-center text-gain text-xl md:text-2xl mb-4 md:mb-6 group-hover:scale-110 transition-transform">
            🎮
          </div>
          <h3 className="text-xl md:text-2xl font-black mb-2 md:mb-3">Practice Trading</h3>
          <p className="text-xs md:text-sm text-text-secondary leading-relaxed font-medium">
            Learn the ropes without the risk. Trade with virtual cash before you invest for real.
          </p>
        </Card>

      </div>
    </main>
  );
}
