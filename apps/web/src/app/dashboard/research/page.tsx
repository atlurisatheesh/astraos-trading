"use client";

import { useCallback } from "react";
import { api, NewsItem } from "@/lib/api";
import { useApi } from "@/hooks/useApi";

function DynFill({ pct, color, cls }: { pct: number; color: string; cls?: string }) {
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (el) { el.style.width = `${pct}%`; el.style.background = color; }
  }, [pct, color]);
  return <div ref={ref} className={cls} />;
}

const FALLBACK_REPORTS = [
  { title: "RELIANCE — Momentum Breakout Analysis", date: "24 Mar 2026", confidence: 84, verdict: "BUY" },
  { title: "Nifty Weekly Options Strategy — Gamma Squeeze Setup", date: "24 Mar 2026", confidence: 78, verdict: "BUY" },
  { title: "IT Sector — Q4 Earnings Preview", date: "23 Mar 2026", confidence: 72, verdict: "POSITIVE" },
  { title: "Bank Nifty — PCR & Max Pain Analysis", date: "23 Mar 2026", confidence: 80, verdict: "BULLISH" },
  { title: "SBI — PSU Bank Rotation Play", date: "22 Mar 2026", confidence: 85, verdict: "BUY" },
];

export default function ResearchPage() {
  const { data: news } = useApi(() => api.getNews(), [], { interval: 60000 });

  const isLive = !!(news as NewsItem[])?.length;
  const REPORTS = isLive
    ? (news as NewsItem[]).map(n => {
        const score = typeof n.sentiment === "number" ? n.sentiment : 0;
        return {
          title: n.title,
          date: new Date(n.published).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }),
          confidence: score !== 0 ? Math.round(Math.abs(score) * 100) : 50,
          verdict: score > 0.05 ? "BULLISH" : score < -0.05 ? "BEARISH" : "NEUTRAL",
        };
      })
    : FALLBACK_REPORTS;
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold font-[var(--font-heading)]">🔬 Research Reports</h1>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${isLive ? "signal-buy" : "signal-hold"}`}>{isLive ? "LIVE" : "SAMPLE DATA"}</span>
      </div>
      <p className="text-sm text-[var(--text-secondary)]">AI-generated deep research • Multi-agent synthesis</p>
      <div className="space-y-3">
        {REPORTS.map((r, i) => (
          <div key={i} className="card cursor-pointer hover:border-[var(--border-active)]">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">{r.title}</h3>
                <span className="text-[10px] text-[var(--text-tertiary)]">{r.date}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${r.verdict === 'BUY' || r.verdict === 'POSITIVE' || r.verdict === 'BULLISH' ? 'signal-buy' : r.verdict === 'NEUTRAL' ? 'signal-hold' : 'signal-sell'}`}>{r.verdict}</span>
                <div className="flex items-center gap-1">
                  <div className="confidence-bar w-12"><DynFill pct={r.confidence} color={r.confidence > 80 ? 'var(--green)' : 'var(--amber)'} cls="confidence-fill" /></div>
                  <span className="text-[10px] font-[var(--font-mono)] text-[var(--text-secondary)]">{r.confidence}%</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
