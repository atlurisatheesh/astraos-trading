"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

const FALLBACK_WATCHLISTS = [
  {
    id: 0,
    name: "Core Holdings (sample)",
    items: [
      { s: "RELIANCE", p: "2,876.50", c: "-0.32%", up: false, signal: "BUY" },
      { s: "TCS", p: "3,945.20", c: "+2.15%", up: true, signal: "BUY" },
      { s: "HDFC BANK", p: "1,678.30", c: "-0.45%", up: false, signal: "HOLD" },
      { s: "INFY", p: "1,567.80", c: "+1.56%", up: true, signal: "SELL" },
    ],
  },
];

interface WlItem { s: string; p: string; c: string; up: boolean; signal: string }
interface Wl { id: number; name: string; items: WlItem[] }

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function WatchlistPage() {
  const [watchlists, setWatchlists] = useState<Wl[]>([]);
  const [isLive, setIsLive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSymbols, setNewSymbols] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const lists = (await api.getWatchlists()) as any[];
      if (!lists?.length) {
        setIsLive(false);
        setWatchlists(FALLBACK_WATCHLISTS);
        return;
      }
      // Each watchlist stores symbols in instrument_ids — fetch live quotes
      const out: Wl[] = [];
      for (const wl of lists) {
        const symbols: string[] = (wl.instrument_ids ?? []).map(String).filter(Boolean);
        let items: WlItem[] = [];
        if (symbols.length) {
          try {
            const quotes = (await api.getQuotes(symbols)) as any[];
            items = quotes.map((q: any, i: number) => {
              const chg = q.change_pct ?? 0;
              return {
                s: symbols[i] ?? q.symbol,
                p: Number(q.price ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 }),
                c: `${chg >= 0 ? "+" : ""}${Number(chg).toFixed(2)}%`,
                up: chg >= 0,
                signal: chg > 1 ? "BUY" : chg < -1 ? "SELL" : "HOLD",
              };
            });
          } catch {
            items = symbols.map(s => ({ s, p: "—", c: "—", up: true, signal: "HOLD" }));
          }
        }
        out.push({ id: wl.id, name: wl.name ?? "Unnamed", items });
      }
      setIsLive(true);
      setWatchlists(out);
    } catch {
      setIsLive(false);
      setWatchlists(FALLBACK_WATCHLISTS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const createWatchlist = async () => {
    setError("");
    const name = newName.trim();
    if (!name) { setError("Name required"); return; }
    const symbols = newSymbols.split(",").map(s => s.trim().toUpperCase()).filter(Boolean);
    try {
      await api.createWatchlist(name, symbols);
      setCreating(false);
      setNewName("");
      setNewSymbols("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    }
  };

  const deleteWatchlist = async (id: number) => {
    try {
      await api.deleteWatchlist(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold font-[var(--font-heading)]">👁 Watchlist</h1>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${isLive ? "signal-buy" : "signal-hold"}`}>
            {loading ? "LOADING…" : isLive ? "LIVE" : "SAMPLE DATA"}
          </span>
        </div>
        <button
          id="add-watchlist"
          onClick={() => setCreating(v => !v)}
          className="text-xs px-3 py-1.5 bg-[var(--accent)] text-white rounded-lg hover:bg-[#5078e6] transition-all"
        >
          + New Watchlist
        </button>
      </div>

      {error && <div className="text-xs text-[var(--red)]">{error}</div>}

      {creating && (
        <div className="card space-y-3">
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="Watchlist name (e.g. Bank Stocks)"
            className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
          />
          <input
            value={newSymbols}
            onChange={e => setNewSymbols(e.target.value)}
            placeholder="Symbols, comma-separated (e.g. RELIANCE, TCS, HDFCBANK)"
            className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
          />
          <div className="flex gap-2">
            <button onClick={createWatchlist} className="text-xs px-4 py-2 bg-[var(--accent)] text-white rounded-lg">Create</button>
            <button onClick={() => setCreating(false)} className="text-xs px-4 py-2 border border-[var(--border)] rounded-lg">Cancel</button>
          </div>
        </div>
      )}

      {watchlists.map((wl) => (
        <div key={wl.id} className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold font-[var(--font-heading)]">{wl.name}</h2>
            {isLive && (
              <button
                onClick={() => deleteWatchlist(wl.id)}
                className="text-[10px] text-[var(--text-tertiary)] hover:text-[var(--red)] transition-colors"
                title="Delete watchlist"
              >
                ✕ Delete
              </button>
            )}
          </div>
          <div className="space-y-1">
            {wl.items.length === 0 && (
              <p className="text-xs text-[var(--text-tertiary)]">No symbols in this watchlist.</p>
            )}
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
