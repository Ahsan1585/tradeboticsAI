"use client";
import React, { useEffect, useState } from "react";

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "light" ? "light" : "dark");
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  return (
    <button
      onClick={toggle}
      aria-label="Toggle color theme"
      className={`w-9 h-9 flex items-center justify-center rounded-full border border-border bg-bg-surface hover:bg-bg-surface-hover transition-colors text-text-primary shrink-0 ${className}`}
    >
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}
