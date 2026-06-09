"use client";

import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";

const FALLBACK_WATCHLISTS = [
  {
    name: "Core Holdings",
    items: [
      { s: "RELIANCE", p: "2,876.50", c: "-0.32%", up: false, signal: "BUY" },
      { s: "TCS", p: "3,945.20", c: "+2.15%", up: true, signal: "BUY" },
      { s: "HDFC BANK", p: "1,678.30", c: "-0.45%", up: false, signal: "HOLD" },
      { s: "INFY", p: "1,567.80", c: "+1.56%", up: true, signal: "SELL" },
    ],
  },
  {
    name: "F&O Watch",
    items: [
      { s: "NIFTY 24500 CE", p: "262.30", c: "+7.06%", up: true, signal: "BUY" },
      { s: "BANK NIFTY FUT", p: "49,180.00", c: "+0.92%", up: true, signal: "BUY" },
      { s: "NIFTY 24500 PE", p: "62.80", c: "-12.3%", up: false, signal: "SELL" },
    ],
  },
];

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function WatchlistPage() {
  const { data: apiWatchlists } = useApi(() => api.getWatchlists(), [], { interval: 30000 });

  const watchlists = (apiWatchlists as any[])?.length
    ? (apiWatchlists as any[]).map((wl: any) => ({
        name: wl.name ?? "Unnamed",
        items: (wl.instruments ?? []).map((inst: any) => ({
          s: inst.symbol ?? inst.name,
          p: inst.price?.toLocaleString("en-IN", { minimumFractionDigits: 2 }) ?? "—",
          c: inst.change_pct != null ? `${inst.change_pct >= 0 ? "+" : ""}${inst.change_pct.toFixed(2)}%` : "—",
          up: (inst.change_pct ?? 0) >= 0,
          signal: inst.signal ?? "HOLD",
        })),
      }))
    : FALLBACK_WATCHLISTS;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-[var(--font-heading)]">👁 Watchlist</h1>
        <button id="add-watchlist" className="text-xs px-3 py-1.5 bg-[var(--accent)] text-white rounded-lg hover:bg-[#5078e6] transition-all">
          + New Watchlist
        </button>
      </div>
      {watchlists.map((wl, i) => (
        <div key={i} className="card">
          <h2 className="text-base font-semibold font-[var(--font-heading)] mb-3">{wl.name}</h2>
          <div className="space-y-1">
            {wl.items.map((item, j) => (
              <div key={j} className="flex items-center justify-between py-2 px-2 rounded-lg hover:bg-[var(--bg-card-hover)] transition-colors text-sm font-[var(--font-mono)]">
                <span className="font-medium w-40">{item.s}</span>
                <span>₹{item.p}</span>
                <span className={item.up ? "text-[var(--green)]" : "text-[var(--red)]"}>{item.c}</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${item.signal === 'BUY' ? 'signal-buy' : item.signal === 'SELL' ? 'signal-sell' : 'signal-hold'}`}>{item.signal}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
