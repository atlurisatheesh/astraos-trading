"use client";

import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";

const FALLBACK_STRATEGIES = [
  { name: "Momentum Breakout", status: "Active", type: "momentum", asset: "equity", tf: "swing", signals: 12, winRate: "67%", wfe: 0.72, risk: "Medium" },
  { name: "IV Crush Short", status: "Active", type: "options", asset: "options", tf: "weekly", signals: 8, winRate: "74%", wfe: 0.68, risk: "High" },
  { name: "Sector Rotation", status: "Paper", type: "rotation", asset: "equity", tf: "positional", signals: 5, winRate: "62%", wfe: 0.55, risk: "Low" },
  { name: "Gamma Squeeze", status: "Paper", type: "options", asset: "options", tf: "expiry", signals: 3, winRate: "58%", wfe: 0.48, risk: "High" },
];

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function AutopilotPage() {
  const { data: apiStrategies } = useApi(() => api.getStrategies(), [], { interval: 30000 });

  const STRATEGIES = (apiStrategies as any[])?.length
    ? (apiStrategies as any[]).map((s: any) => ({
        name: s.name, status: s.is_active ? "Active" : "Paper",
        type: s.strategy_type ?? "momentum", asset: s.asset_class ?? "equity",
        tf: s.timeframe ?? "swing",
        signals: s.signal_count ?? 0, winRate: s.win_rate ? `${s.win_rate}%` : "—",
        wfe: s.wfe_score ?? 0, risk: s.risk_level ?? "Medium",
      }))
    : FALLBACK_STRATEGIES;

  const activeCount = STRATEGIES.filter((s: any) => s.status === "Active").length;
  const paperCount = STRATEGIES.filter((s: any) => s.status === "Paper").length;
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-[var(--font-heading)]">🤖 Autopilot Engine</h1>
          <p className="text-sm text-[var(--text-secondary)]">Semi-auto execution with human approval • 30-day paper trading required</p>
        </div>
        <span className="text-xs px-3 py-1.5 rounded-lg bg-[var(--amber-glow)] text-[var(--amber)] border border-[rgba(245,158,11,0.2)] font-medium">
          {activeCount} Active / {paperCount} Paper
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {STRATEGIES.map((s, i) => (
          <div key={i} id={`strategy-${s.name.toLowerCase().replace(/\s/g, '-')}`} className="card hover:border-[var(--border-active)]">
            <div className="flex items-center justify-between mb-3">
              <span className="font-semibold font-[var(--font-heading)]">{s.name}</span>
              <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${s.status === 'Active' ? 'bg-[var(--green-glow)] text-[var(--green)]' : 'bg-[var(--amber-glow)] text-[var(--amber)]'}`}>
                {s.status}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-3">
              {[
                { l: "Win Rate", v: s.winRate },
                { l: "WFE Score", v: s.wfe.toFixed(2) },
                { l: "Risk", v: s.risk },
              ].map(m => (
                <div key={m.l} className="text-center p-2 rounded-lg bg-[var(--bg-primary)]">
                  <div className="text-[9px] text-[var(--text-tertiary)]">{m.l}</div>
                  <div className="text-xs font-bold font-[var(--font-mono)]">{m.v}</div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 text-[10px] text-[var(--text-tertiary)]">
              <span className="px-1.5 py-0.5 rounded bg-[var(--bg-primary)] border border-[var(--border)]">{s.type}</span>
              <span className="px-1.5 py-0.5 rounded bg-[var(--bg-primary)] border border-[var(--border)]">{s.asset}</span>
              <span className="px-1.5 py-0.5 rounded bg-[var(--bg-primary)] border border-[var(--border)]">{s.tf}</span>
              <span className="ml-auto">{s.signals} signals</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
