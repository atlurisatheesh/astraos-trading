"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { useWebSocket } from "@/hooks/useWebSocket";

function DynFill({ pct, color, cls }: { pct: number; color: string; cls?: string }) {
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (el) { el.style.width = `${pct}%`; el.style.background = color; }
  }, [pct, color]);
  return <div ref={ref} className={cls} />;
}

interface SignalData {
  symbol: string; type: string; confidence: number; entry: string; target: string;
  sl: string; rr: string; horizon: string; regime: string;
  agents: Record<string, number>; reasoning: string;
}

const FALLBACK_SIGNALS: SignalData[] = [
  { symbol: "RELIANCE", type: "BUY", confidence: 91, entry: "2,840", target: "2,950", sl: "2,790", rr: "2.2:1", horizon: "3-5 days", regime: "Bullish", agents: { technical: 88, derivatives: 92, sentiment: 85, macro: 90, sector: 94 }, reasoning: "Strong OI buildup in futures + momentum breakout above 200-DMA + positive sector rotation into energy + FII buying in cash segment" },
  { symbol: "TCS", type: "BUY", confidence: 87, entry: "3,900", target: "4,100", sl: "3,840", rr: "3.3:1", horizon: "5-7 days", regime: "Bullish", agents: { technical: 82, derivatives: 78, sentiment: 91, macro: 88, sector: 95 }, reasoning: "Earnings beat + IT sector momentum + buy-on-dip into support zone + DCF undervaluation" },
  { symbol: "INFY", type: "SELL", confidence: 76, entry: "1,580", target: "1,520", sl: "1,610", rr: "2.0:1", horizon: "Intraday", regime: "Bearish", agents: { technical: 72, derivatives: 80, sentiment: 68, macro: 75, sector: 84 }, reasoning: "IV crush post-earnings + weakness in mid-cap IT + PCR declining + resistance at 1,600" },
  { symbol: "NIFTY 24500 CE", type: "BUY", confidence: 82, entry: "245", target: "310", sl: "200", rr: "1.4:1", horizon: "Expiry week", regime: "Bullish", agents: { technical: 85, derivatives: 88, sentiment: 75, macro: 80, sector: 78 }, reasoning: "Gamma squeeze setup + VIX declining + PCR at 1.3 bullish + max pain above 24,400" },
  { symbol: "HDFC BANK", type: "HOLD", confidence: 58, entry: "—", target: "—", sl: "—", rr: "—", horizon: "—", regime: "Sideways", agents: { technical: 55, derivatives: 52, sentiment: 60, macro: 62, sector: 58 }, reasoning: "Range-bound between 1,650-1,700 + neutral FII flows + awaiting Q4 results + sector consolidation" },
  { symbol: "BAJAJ FINANCE", type: "BUY", confidence: 79, entry: "7,200", target: "7,550", sl: "7,050", rr: "2.3:1", horizon: "5-10 days", regime: "Bullish", agents: { technical: 80, derivatives: 75, sentiment: 82, macro: 78, sector: 81 }, reasoning: "Breakout from falling wedge + NBFC sector rotation + improving credit growth data + positive management commentary" },
  { symbol: "BANK NIFTY 50000 PE", type: "SELL", confidence: 73, entry: "180", target: "120", sl: "220", rr: "1.5:1", horizon: "Weekly", regime: "Bullish", agents: { technical: 70, derivatives: 78, sentiment: 72, macro: 74, sector: 68 }, reasoning: "Theta decay advantage + Bank Nifty holding above 49,000 + sell premium strategy + IV rank at 72" },
  { symbol: "SBIN", type: "BUY", confidence: 85, entry: "780", target: "840", sl: "755", rr: "2.4:1", horizon: "Swing 7d", regime: "Bullish", agents: { technical: 87, derivatives: 82, sentiment: 88, macro: 83, sector: 86 }, reasoning: "PSU bank rotation + NPA improvement trend + breakout with volume + FII accumulation" },
];

export default function SignalsPage() {
  const [filter, setFilter] = useState("ALL");

  const { data: wsSignals } = useWebSocket<{ active_signals: Record<string, SignalData> }>("/ws/signals");
  const { data: apiSignals } = useApi(() => api.getSignals(), [], { interval: 30000 });

  // Merge: prefer WebSocket live data, fallback to API, then hardcoded
  const liveSignals = wsSignals?.active_signals ? Object.values(wsSignals.active_signals) : [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const signals: SignalData[] = liveSignals.length > 0 ? liveSignals : (apiSignals as any[] ?? FALLBACK_SIGNALS).map((s: Record<string, unknown>) => ({
    symbol: (s.symbol ?? s.instrument_id ?? "") as string,
    type: (s.type ?? s.signal_type ?? "HOLD") as string,
    confidence: Number(s.confidence ?? 50),
    entry: String(s.entry ?? s.entry_price ?? "—"),
    target: String(s.target ?? s.target_price ?? "—"),
    sl: String(s.sl ?? s.stop_loss ?? "—"),
    rr: String(s.rr ?? s.risk_reward ?? "—"),
    horizon: String(s.horizon ?? s.time_horizon ?? "—"),
    regime: String(s.regime ?? "—"),
    agents: (s.agents ?? s.agent_scores ?? { technical: 50, derivatives: 50, sentiment: 50, macro: 50, sector: 50 }) as Record<string, number>,
    reasoning: String(s.reasoning ?? ""),
  }));

  const filtered = filter === "ALL" ? signals : signals.filter(s => s.type === filter);

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-[var(--font-heading)]">⚡ AI Signals</h1>
          <p className="text-sm text-[var(--text-secondary)]">Multi-agent research synthesis • Confidence-scored recommendations</p>
        </div>
        <div className="flex items-center gap-2">
          {["ALL", "BUY", "SELL", "HOLD"].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${f === filter ? 'border-[var(--accent)] text-[var(--accent)]' : 'border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)]'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Signals Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((s, i) => (
          <div key={i} id={`signal-card-${s.symbol.toLowerCase().replace(/\s/g, '-')}`} className="card hover:border-[var(--border-active)] transition-all">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <span className={`text-xs font-bold px-2.5 py-1 rounded ${s.type === 'BUY' ? 'signal-buy' : s.type === 'SELL' ? 'signal-sell' : 'signal-hold'}`}>
                  {s.type}
                </span>
                <span className="font-bold font-[var(--font-mono)] text-base">{s.symbol}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="confidence-bar w-20">
                  <DynFill pct={s.confidence} color={s.confidence > 80 ? 'var(--green)' : s.confidence > 60 ? 'var(--amber)' : 'var(--red)'} cls="confidence-fill" />
                </div>
                <span className={`text-sm font-bold font-[var(--font-mono)] ${s.confidence > 80 ? 'text-[var(--green)]' : s.confidence > 60 ? 'text-[var(--amber)]' : 'text-[var(--red)]'}`}>
                  {s.confidence}%
                </span>
              </div>
            </div>

            {/* Price Levels */}
            <div className="grid grid-cols-4 gap-2 mb-3">
              {[
                { l: "Entry", v: s.entry },
                { l: "Target", v: s.target },
                { l: "Stop Loss", v: s.sl },
                { l: "R:R", v: s.rr },
              ].map(p => (
                <div key={p.l} className="text-center p-2 rounded-lg bg-[var(--bg-primary)]">
                  <div className="text-[10px] text-[var(--text-tertiary)] mb-0.5">{p.l}</div>
                  <div className="text-xs font-[var(--font-mono)] font-medium">{p.v}</div>
                </div>
              ))}
            </div>

            {/* Meta */}
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-primary)] text-[var(--text-secondary)] border border-[var(--border)]">
                {s.horizon}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-primary)] text-[var(--text-secondary)] border border-[var(--border)]">
                {s.regime}
              </span>
            </div>

            {/* Agent Scores */}
            <div className="mb-3">
              <div className="text-[10px] text-[var(--text-tertiary)] mb-1.5">Agent Scores</div>
              <div className="flex gap-1.5">
                {Object.entries(s.agents).map(([agent, score]) => (
                  <div key={agent} className="flex-1 text-center">
                    <div className="h-1.5 rounded-full bg-[var(--bg-primary)] overflow-hidden mb-0.5">
                      <DynFill pct={score as number} color={(score as number) > 80 ? 'var(--green)' : (score as number) > 60 ? 'var(--amber)' : 'var(--red)'} cls="h-full rounded-full" />
                    </div>
                    <span className="text-[8px] text-[var(--text-tertiary)] capitalize">{agent.slice(0, 4)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Reasoning */}
            <div className="text-xs text-[var(--text-secondary)] leading-relaxed bg-[var(--bg-primary)] rounded-lg p-2.5 border border-[var(--border)]">
              💡 {s.reasoning}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
