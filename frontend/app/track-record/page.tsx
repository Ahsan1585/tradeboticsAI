"use client";
import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BACKEND_URL } from "../lib/config";
import ThemeToggle from "../components/ThemeToggle";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import StatTile from "../components/ui/StatTile";

const HORIZON_LABELS: Record<string, string> = {
  day: "Day Setups",
  swing: "Swing (5-20 Day)",
  longterm: "Long-Term",
};

function TrackCard({ track }: { track: any }) {
  const hitRateAccent = track.hit_rate >= 55 ? "text-gain" : track.hit_rate >= 45 ? "text-warn" : "text-loss";
  const excessAccent = track.avg_excess_return_pct > 0 ? "text-gain" : "text-loss";
  return (
    <Card className="p-6 md:p-8">
      <div className="flex justify-between items-center mb-5">
        <h3 className="text-lg md:text-xl font-black">{HORIZON_LABELS[track.horizon] || track.horizon}</h3>
        <span className="text-[10px] font-bold text-text-secondary uppercase tracking-wide">Engine {track.engine_version}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Hit Rate" value={`${track.hit_rate}%`} accentClassName={hitRateAccent} />
        <StatTile label="Resolved Trades" value={String(track.total_resolved)} />
        <StatTile label="Win / Loss" value={`${track.wins} / ${track.losses}`} />
        <StatTile label="Excess vs SPY" value={`${track.avg_excess_return_pct > 0 ? "+" : ""}${track.avg_excess_return_pct}%`} accentClassName={excessAccent} />
      </div>
    </Card>
  );
}

function EquityCurve({ curve }: { curve: any[] }) {
  if (curve.length === 0) return null;
  const values = curve.map((p) => p.cumulative_return_multiple);
  const min = Math.min(1, ...values);
  const max = Math.max(1, ...values);
  const range = max - min || 1;
  const points = curve
    .map((p, i) => {
      const x = (i / Math.max(1, curve.length - 1)) * 100;
      const y = 100 - ((p.cumulative_return_multiple - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");
  const latest = curve[curve.length - 1].cumulative_return_multiple;
  const totalReturnPct = ((latest - 1) * 100).toFixed(1);

  return (
    <Card className="p-6 md:p-8">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg md:text-xl font-black">Swing BUY Equity Curve</h3>
        <span className={`text-sm font-black ${latest >= 1 ? "text-gain" : "text-loss"}`}>
          {latest >= 1 ? "+" : ""}{totalReturnPct}%
        </span>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-40 md:h-56">
        <polyline
          fill="none"
          stroke={latest >= 1 ? "var(--gain)" : "var(--loss)"}
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
          points={points}
        />
      </svg>
      <p className="text-[10px] text-text-secondary mt-2">
        {curve.length} resolved swing BUY{curve.length === 1 ? "" : "s"}, chronological, compounded at 20-trading-day return.
      </p>
    </Card>
  );
}

export default function TrackRecordPage() {
  const router = useRouter();
  const [tracks, setTracks] = useState<any[]>([]);
  const [equityCurve, setEquityCurve] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/track-record`);
        const data = await res.json();
        setTracks(data.tracks || []);
        setEquityCurve(data.swing_equity_curve || []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <main className="min-h-screen bg-bg-primary text-text-primary font-sans">
      <header className="w-full flex justify-between items-center p-4 md:p-6 border-b border-border bg-bg-primary/90 backdrop-blur-md sticky top-0 z-50">
        <h1
          className="text-xl md:text-2xl font-black tracking-tighter cursor-pointer"
          onClick={() => router.push("/")}
        >
          TRADEBOTICS<span className="text-accent">AI</span>
        </h1>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Button onClick={() => router.push("/")} variant="secondary" size="sm">&larr; Home</Button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-8 md:py-14">
        <h2 className="text-3xl md:text-4xl font-black text-center mb-3">Our Track Record</h2>
        <p className="text-text-secondary text-center text-sm md:text-base mb-10 max-w-xl mx-auto leading-relaxed">
          Every signal we emit is logged before we know the outcome. This page shows how our rules-based
          engine has actually performed -- resolved trades only, no cherry-picking.
        </p>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-10 h-10 border-4 border-border border-t-accent rounded-full animate-spin" />
          </div>
        ) : tracks.length === 0 ? (
          <p className="text-text-secondary text-center py-16 text-sm">
            No resolved trades yet -- check back once signals have had time to play out.
          </p>
        ) : (
          <div className="space-y-6">
            {tracks.map((t) => (
              <TrackCard key={`${t.horizon}-${t.engine_version}`} track={t} />
            ))}
            <EquityCurve curve={equityCurve} />
          </div>
        )}

        <p className="text-[10px] text-text-secondary text-center mt-10 leading-relaxed">
          Educational analysis, not financial advice. Past performance does not guarantee future results.
        </p>
      </div>
    </main>
  );
}
