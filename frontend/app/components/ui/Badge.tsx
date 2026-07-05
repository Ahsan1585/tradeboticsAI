"use client";
import React from "react";

type Tone = "gain" | "loss" | "warn" | "neutral" | "accent";

const TONE_CLASSES: Record<Tone, string> = {
  gain: "text-gain bg-gain/10 border-gain/30",
  loss: "text-loss bg-loss/10 border-loss/30",
  warn: "text-warn bg-warn/10 border-warn/30",
  neutral: "text-text-secondary bg-bg-surface-hover border-border",
  accent: "text-accent bg-accent/10 border-accent/30",
};

export default function Badge({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`text-[10px] font-black uppercase tracking-widest px-3 py-1.5 rounded-full border ${TONE_CLASSES[tone]}`}>
      {children}
    </span>
  );
}
