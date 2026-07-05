"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../lib/supabase";
import { apiFetch } from "../lib/config";
import ThemeToggle from "../components/ThemeToggle";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";

const VERDICT_STYLES: Record<string, { label: string; emoji: string; tone: "gain" | "accent" | "warn" | "loss" }> = {
  BUY: { label: "Good Opportunity", emoji: "✅", tone: "gain" },
  HOLD: { label: "Hold Steady", emoji: "🤝", tone: "accent" },
  WAIT: { label: "Wait For A Better Entry", emoji: "⏳", tone: "warn" },
  AVOID: { label: "Steer Clear", emoji: "🚫", tone: "loss" },
};

function ConfidenceMeter({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(100, value || 0));
  const color = clamped >= 70 ? "bg-gain" : clamped >= 40 ? "bg-warn" : "bg-loss";
  return (
    <div className="w-full h-2 bg-bg-primary rounded-full overflow-hidden">
      <div className={`h-full ${color} transition-all`} style={{ width: `${clamped}%` }} />
    </div>
  );
}

function VerdictCard({ item, onOpen }: { item: any; onOpen: (ticker: string) => void }) {
  const style = VERDICT_STYLES[item.verdict] || VERDICT_STYLES.HOLD;
  const confidence = item.confidence ?? item.score ?? 0;
  return (
    <Card interactive onClick={() => onOpen(item.ticker)} className="p-5 md:p-6">
      <div className="flex justify-between items-start mb-3 gap-3">
        <div>
          <h3 className="text-2xl font-black">{item.ticker}</h3>
          {item.price != null && <p className="text-xs text-text-secondary font-medium">${item.price}</p>}
        </div>
        <Badge tone={style.tone}>{style.emoji} {style.label}</Badge>
      </div>

      <div className="mb-3">
        <div className="flex justify-between text-[10px] uppercase font-bold text-text-secondary mb-1">
          <span>Confidence</span>
          <span>{Math.round(confidence)}/100</span>
        </div>
        <ConfidenceMeter value={confidence} />
      </div>

      {item.reason && <p className="text-sm text-text-secondary leading-relaxed mb-2">{item.reason}</p>}

      {item.exit_plan && (
        <p className="text-xs text-text-secondary bg-bg-primary rounded-xl p-3 mt-2 leading-relaxed">
          If you buy around <span className="text-text-primary font-bold">${item.exit_plan.entry?.toFixed(2)}</span>: consider
          selling for a gain near <span className="text-gain font-bold">${item.exit_plan.target?.toFixed(2)}</span>,
          or cut losses if it drops to <span className="text-loss font-bold">${item.exit_plan.stop?.toFixed(2)}</span>.
        </p>
      )}

      {item.smart_money_score != null && item.smart_money_score > 60 && (
        <p className="text-xs text-accent mt-2 font-bold">🏦 Hedge funds/insiders are buying</p>
      )}
    </Card>
  );
}

export default function BeginnerPage() {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [picks, setPicks] = useState<any[]>([]);
  const [defensiveMode, setDefensiveMode] = useState(false);
  const [defensiveMessage, setDefensiveMessage] = useState("");
  const [loadingPicks, setLoadingPicks] = useState(true);

  const [searchTicker, setSearchTicker] = useState("");
  const [searchResult, setSearchResult] = useState<any>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push("/");
        return;
      }
      setIsAuthorized(true);

      try {
        const res = await apiFetch("/run-screener", {
          method: "POST",
          body: JSON.stringify({ trade_style: "Swing Trade", risk_level: "Moderate" }),
        });
        const result = await res.json();
        if (res.ok) {
          setPicks(result.results || []);
          setDefensiveMode(!!result.defensive_mode);
          setDefensiveMessage(result.message || "");
        }
      } finally {
        setLoadingPicks(false);
      }
    };
    init();
  }, [router]);

  const handleSearch = async () => {
    if (!searchTicker.trim()) return;
    setSearchLoading(true);
    setSearchError("");
    setSearchResult(null);
    try {
      const res = await apiFetch(`/analyze/${searchTicker.toUpperCase()}`);
      const result = await res.json();
      if (res.ok) {
        const swing = result.signals?.swing || {};
        setSearchResult({
          ticker: result.ticker,
          price: result.price,
          verdict: result.verdict,
          confidence: swing.confidence ?? result.score,
          reason: result.ai_tactical,
          exit_plan: swing.exit_plan,
          smart_money_score: result.smart_money_score,
        });
      } else {
        setSearchError(result.detail || "Couldn't find that stock yet -- try another ticker.");
      }
    } catch {
      setSearchError("Something went wrong. Please try again.");
    }
    setSearchLoading(false);
  };

  if (!isAuthorized) {
    return (
      <main className="min-h-screen bg-bg-primary flex items-center justify-center p-4">
        <div className="w-12 h-12 border-4 border-border border-t-accent rounded-full animate-spin" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-bg-primary text-text-primary font-sans">
      <header className="w-full flex justify-between items-center p-4 md:p-6 border-b border-border bg-bg-primary/90 backdrop-blur-md sticky top-0 z-50">
        <h1
          className="text-xl md:text-2xl font-black tracking-tighter cursor-pointer"
          onClick={() => router.push("/hub")}
        >
          TRADEBOTICS<span className="text-accent">AI</span>
        </h1>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Button onClick={() => router.push("/terminal")} variant="secondary" size="sm">
            Switch to Pro Mode &rarr;
          </Button>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8 md:py-12">
        <h2 className="text-3xl md:text-4xl font-black text-center mb-2">
          What should I invest in today?
        </h2>
        <p className="text-text-secondary text-center text-sm md:text-base mb-8">
          Plain-English picks. No jargon. Every idea comes with a plan.
        </p>

        <div className="flex bg-bg-surface p-2 rounded-full border-2 border-border focus-within:border-accent mb-4 transition-all">
          <input
            value={searchTicker}
            onChange={(e) => setSearchTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Curious about a stock? Type a ticker, e.g. AAPL"
            className="flex-1 bg-transparent border-none font-bold px-4 outline-none text-base md:text-lg placeholder:text-text-secondary min-w-0"
          />
          <Button onClick={handleSearch} disabled={searchLoading} className="shrink-0">
            {searchLoading ? "Checking..." : "Check It"}
          </Button>
        </div>

        {searchError && <p className="text-loss text-sm text-center mb-6">{searchError}</p>}
        {searchResult && (
          <div className="mb-10">
            <VerdictCard item={searchResult} onOpen={(t) => router.push(`/terminal?ticker=${t}`)} />
          </div>
        )}

        <h3 className="text-lg font-black uppercase tracking-wide mb-4 mt-10">Today&apos;s Top Picks</h3>

        {defensiveMode && (
          <div className="bg-warn/10 border border-warn/30 rounded-2xl p-4 mb-6">
            <p className="text-warn text-sm font-medium">🛡️ {defensiveMessage}</p>
          </div>
        )}

        {loadingPicks ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-4 border-border border-t-accent rounded-full animate-spin" />
          </div>
        ) : picks.length === 0 ? (
          <p className="text-text-secondary text-center py-12 text-sm">
            No standout picks right now -- check back after tonight&apos;s update.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {picks.map((item) => (
              <VerdictCard key={item.ticker} item={item} onOpen={(t) => router.push(`/terminal?ticker=${t}`)} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
