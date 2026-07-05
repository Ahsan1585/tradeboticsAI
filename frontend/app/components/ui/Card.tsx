"use client";
import React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

export default function Card({ interactive = false, className = "", children, ...rest }: CardProps) {
  return (
    <div
      className={`bg-bg-surface border border-border rounded-3xl shadow-sm ${
        interactive ? "cursor-pointer hover:border-accent/50 hover:shadow-md transition-all" : ""
      } ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}
