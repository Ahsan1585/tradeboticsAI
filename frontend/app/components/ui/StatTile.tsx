"use client";
import React from "react";

export default function StatTile({
  label, value, accentClassName = "text-text-primary",
}: {
  label: string;
  value: string;
  accentClassName?: string;
}) {
  return (
    <div className="bg-bg-surface border border-border rounded-2xl p-4 md:p-5 text-center">
      <p className="text-[9px] md:text-[10px] font-black text-text-secondary uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-xl md:text-3xl font-black ${accentClassName}`}>{value}</p>
    </div>
  );
}
