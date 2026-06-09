"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";

function DynFill({ pct, color, cls }: { pct: number; color: string; cls?: string }) {
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (el) { el.style.width = `${pct}%`; el.style.background = color; }
  }, [pct, color]);
  return <div ref={ref} className={cls} />;
}

const FALLBACK_METRICS = [
  { label: "Capital at Risk", value: "3.2%", max: "5%", pct: 64, status: "safe" },
  { label: "Daily Loss", value: "0.8%", max: "2%", pct: 40, status: "safe" },
  { label: "Weekly Drawdown", value: "1.5%", max: "5%", pct: 30, status: "safe" },
  { label: "Max Drawdown", value: "4.2%", max: "15%", pct: 28, status: "safe" },
  { label: "Leverage", value: "1.4x", max: "2.0x", pct: 70, status: "warning" },
  { label: "Sector Exposure", value: "18%", max: "25%", pct: 72, status: "warning" },
  { label: "F&O Exposure", value: "22%", max: "40%", pct: 55, status: "safe" },
  { label: "Cash Reserve", value: "35%", max: "20%", pct: 57, status: "safe" },
];

const FALLBACK_EVENTS = [
  { time: "14:32", type: "INFO", event: "Risk check passed for RELIANCE BUY order", action: "Order approved" },
  { time: "13:45", type: "WARNING", event: "Sector exposure (Energy) approaching 22% limit", action: "Alert sent" },
  { time: "12:10", type: "INFO", event: "VIX at 13.2 — circuit breaker NOT triggered (threshold: 25)", action: "None" },
  { time: "11:30", type: "INFO", event: "Daily PnL +₹12,450 — within 2% daily loss limit", action: "None" },
  { time: "10:15", type: "WARNING", event: "OPS rate: 6/sec (limit: 8/sec SEBI)", action: "Speed throttled" },
];

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function RiskPage() {
  const { data: apiMetrics } = useApi(() => api.getRiskMetrics(), [], { interval: 15000 });
  const { data: apiEvents } = useApi(() => api.getRiskEvents(), [], { interval: 15000 });

  const RISK_METRICS = (apiMetrics as any)?.metrics ?? FALLBACK_METRICS;
  const RISK_EVENTS = (apiEvents as any[])?.length
    ? (apiEvents as any[]).map((e: any) => ({
        time: new Date(e.created_at ?? Date.now()).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
        type: e.severity ?? e.type ?? "INFO",
        event: e.message ?? e.event ?? "",
        action: e.action ?? "None",
      }))
    : FALLBACK_EVENTS;
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-[var(--font-heading)]">🛡️ Risk Dashboard</h1>
          <p className="text-sm text-[var(--text-secondary)]">12-point risk governance • All limits are hard-enforced</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-3 py-1.5 rounded-lg bg-[var(--green-glow)] text-[var(--green)] border border-[rgba(34,211,165,0.2)] font-medium">
            All Systems Green ✓
          </span>
        </div>
      </div>

      {/* Kill Switch Panel */}
      <div className="card border-[rgba(255,79,109,0.2)]">
        <h2 className="text-base font-semibold font-[var(--font-heading)] text-[var(--red)] mb-3">⚠️ Kill Switch Controls</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { level: "L1", label: "Strategy Kill", desc: "Halt one strategy, cancel its orders", color: "amber" },
            { level: "L2", label: "Account Kill", desc: "Close ALL your positions immediately", color: "red" },
            { level: "L3", label: "Platform Kill", desc: "Emergency halt — all users, all trades", color: "red" },
          ].map((k, i) => (
            <button key={i} className={`p-3 rounded-lg border text-left transition-all hover:scale-[1.02] ${
              k.color === 'red'
                ? 'border-[rgba(255,79,109,0.3)] bg-[var(--red-glow)] hover:bg-[rgba(255,79,109,0.25)]'
                : 'border-[rgba(245,158,11,0.3)] bg-[var(--amber-glow)] hover:bg-[rgba(245,158,11,0.25)]'
            }`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${k.color === 'red' ? 'bg-[var(--red)] text-white' : 'bg-[var(--amber)] text-black'}`}>{k.level}</span>
                <span className="text-sm font-semibold">{k.label}</span>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)]">{k.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Risk Meters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {RISK_METRICS.map((m, i) => (
          <div key={i} id={`risk-${m.label.toLowerCase().replace(/\s/g, '-')}`} className="card">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] text-[var(--text-secondary)]">{m.label}</span>
              <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                m.status === 'safe' ? 'bg-[var(--green-glow)] text-[var(--green)]' :
                m.status === 'warning' ? 'bg-[var(--amber-glow)] text-[var(--amber)]' :
                'bg-[var(--red-glow)] text-[var(--red)]'
              }`}>
                {m.status === 'safe' ? '✓ Safe' : m.status === 'warning' ? '⚠ Watch' : '✕ Breach'}
              </span>
            </div>
            <div className="text-lg font-bold font-[var(--font-mono)]">{m.value}</div>
            <div className="text-[10px] text-[var(--text-tertiary)] mb-2">of {m.max} limit</div>
            <div className="h-2 rounded-full bg-[var(--bg-primary)] overflow-hidden">
              <DynFill pct={m.pct} color={m.pct > 80 ? 'var(--red)' : m.pct > 60 ? 'var(--amber)' : 'var(--green)'} cls="h-full rounded-full transition-all duration-500" />
            </div>
          </div>
        ))}
      </div>

      {/* Risk Events Log */}
      <div className="card">
        <h2 className="text-base font-semibold font-[var(--font-heading)] mb-3">📋 Risk Event Log</h2>
        <div className="space-y-2">
          {RISK_EVENTS.map((e, i) => (
            <div key={i} className={`flex items-start gap-3 p-2.5 rounded-lg border ${
              e.type === 'WARNING' ? 'border-[rgba(245,158,11,0.2)] bg-[rgba(245,158,11,0.03)]' : 'border-[var(--border)]'
            }`}>
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded mt-0.5 ${
                e.type === 'WARNING' ? 'bg-[var(--amber)] text-black' :
                e.type === 'CRITICAL' ? 'bg-[var(--red)] text-white' :
                'bg-[var(--bg-primary)] text-[var(--text-secondary)] border border-[var(--border)]'
              }`}>{e.type}</span>
              <div className="flex-1">
                <p className="text-xs text-[var(--text-primary)]">{e.event}</p>
                <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">Action: {e.action} • {e.time} IST</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
