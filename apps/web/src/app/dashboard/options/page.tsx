"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";

interface Strike {
  strike: number;
  ceOI: number; ceVol: number; ceIV: number; ceLTP: number;
  peLTP: number; peIV: number; peVol: number; peOI: number;
  atm?: boolean;
}

const FALLBACK_STRIKES: Strike[] = [
  { strike: 24300, ceOI: 245000, ceVol: 18500, ceIV: 14.2, ceLTP: 185.50, peLTP: 12.30, peIV: 16.8, peVol: 8200, peOI: 180000 },
  { strike: 24400, ceOI: 380000, ceVol: 32100, ceIV: 13.5, ceLTP: 120.80, peLTP: 28.50, peIV: 15.2, peVol: 15600, peOI: 295000 },
  { strike: 24500, ceOI: 520000, ceVol: 45200, ceIV: 12.8, ceLTP: 72.40, peLTP: 62.80, peIV: 13.9, peVol: 38900, peOI: 410000, atm: true },
  { strike: 24600, ceOI: 310000, ceVol: 28700, ceIV: 12.1, ceLTP: 35.60, peLTP: 125.40, peIV: 13.1, peVol: 22100, peOI: 350000 },
  { strike: 24700, ceOI: 185000, ceVol: 12400, ceIV: 11.5, ceLTP: 15.20, peLTP: 205.80, peIV: 12.4, peVol: 9800, peOI: 220000 },
];

export default function OptionsPage() {
  const [symbol, setSymbol] = useState("NIFTY");

  const { data: chainData, loading } = useApi(
    () => api.getOptionsChain(symbol), [symbol], { interval: 30000 },
  );
  const { data: pcrData } = useApi(() => api.getPCR(symbol), [symbol], { interval: 30000 });
  const { data: maxPainData } = useApi(() => api.getMaxPain(symbol), [symbol], { interval: 60000 });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chain = chainData as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pcr = pcrData as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const maxPain = maxPainData as any;

  // Backend returns {calls:[], puts:[], analytics:{...}} — merge by strike
  let liveStrikes: Strike[] = [];
  if (chain?.calls?.length || chain?.puts?.length) {
    const byStrike = new Map<number, Strike>();
    for (const c of chain.calls ?? []) {
      const k = c.strike_price ?? c.strike ?? 0;
      byStrike.set(k, {
        strike: k, ceOI: c.oi ?? c.open_interest ?? 0, ceVol: c.volume ?? 0,
        ceIV: c.iv ?? c.implied_volatility ?? 0, ceLTP: c.ltp ?? c.last_price ?? 0,
        peLTP: 0, peIV: 0, peVol: 0, peOI: 0,
      });
    }
    for (const p of chain.puts ?? []) {
      const k = p.strike_price ?? p.strike ?? 0;
      const row = byStrike.get(k) ?? { strike: k, ceOI: 0, ceVol: 0, ceIV: 0, ceLTP: 0, peLTP: 0, peIV: 0, peVol: 0, peOI: 0 };
      row.peOI = p.oi ?? p.open_interest ?? 0;
      row.peVol = p.volume ?? 0;
      row.peIV = p.iv ?? p.implied_volatility ?? 0;
      row.peLTP = p.ltp ?? p.last_price ?? 0;
      byStrike.set(k, row);
    }
    liveStrikes = [...byStrike.values()].sort((a, b) => a.strike - b.strike);
  } else if (chain?.chain?.length) {
    liveStrikes = chain.chain.map((c: Record<string, number>) => ({
      strike: c.strike_price ?? c.strike ?? 0,
      ceOI: c.ce_oi ?? 0, ceVol: c.ce_volume ?? 0, ceIV: c.ce_iv ?? 0, ceLTP: c.ce_ltp ?? 0,
      peLTP: c.pe_ltp ?? 0, peIV: c.pe_iv ?? 0, peVol: c.pe_volume ?? 0, peOI: c.pe_oi ?? 0,
    }));
  }
  const isLive = liveStrikes.length > 0;
  const strikes: Strike[] = isLive ? liveStrikes : FALLBACK_STRIKES;

  const analytics = chain?.analytics;
  // "—" when no live data — never fake numbers that look real
  const metrics = [
    { label: "PCR (OI)", value: (pcr?.pcr_oi ?? pcr?.pcr ?? analytics?.pcr_oi)?.toFixed?.(2) ?? "—", color: "green" },
    { label: "Max Pain", value: (maxPain?.max_pain_strike ?? analytics?.max_pain) ? Number(maxPain?.max_pain_strike ?? analytics?.max_pain).toLocaleString() : "—", color: "accent" },
    { label: "IV (ATM)", value: chain?.atm_iv ? chain.atm_iv.toFixed(1) + "%" : "—", color: "amber" },
    { label: "Total CE OI", value: (chain?.total_ce_oi ?? analytics?.total_call_oi) ? (Number(chain?.total_ce_oi ?? analytics?.total_call_oi) / 100000).toFixed(1) + "L" : "—", color: "red" },
    { label: "Total PE OI", value: (chain?.total_pe_oi ?? analytics?.total_put_oi) ? (Number(chain?.total_pe_oi ?? analytics?.total_put_oi) / 100000).toFixed(1) + "L" : "—", color: "green" },
  ];

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-[var(--font-heading)]">🔗 F&O Options Chain</h1>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${isLive ? "signal-buy" : "signal-hold"}`}>{isLive ? "LIVE" : "SAMPLE DATA"}</span>
          </div>
          <p className="text-sm text-[var(--text-secondary)]">{symbol} • {loading ? "Loading..." : `${strikes.length} strikes`}</p>
        </div>
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)} title="Select instrument"
          className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl px-3 py-2 text-sm">
          <option value="NIFTY">NIFTY</option>
          <option value="BANKNIFTY">BANK NIFTY</option>
          <option value="RELIANCE">RELIANCE</option>
          <option value="TCS">TCS</option>
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {metrics.map((m, i) => (
          <div key={i} className="card text-center">
            <div className="text-[10px] text-[var(--text-tertiary)] mb-1">{m.label}</div>
            <div className={`text-lg font-bold font-[var(--font-mono)] text-[var(--${m.color})]`}>{m.value}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="text-base font-semibold font-[var(--font-heading)] mb-3">Options Chain</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-[var(--font-mono)]">
            <thead>
              <tr className="text-[10px] text-[var(--text-tertiary)] border-b border-[var(--border)]">
                <th className="pb-2 text-right">OI</th>
                <th className="pb-2 text-right">Vol</th>
                <th className="pb-2 text-right">IV</th>
                <th className="pb-2 text-right text-[var(--green)]">CE LTP</th>
                <th className="pb-2 text-center font-bold text-[var(--accent)]">Strike</th>
                <th className="pb-2 text-left text-[var(--red)]">PE LTP</th>
                <th className="pb-2 text-left">IV</th>
                <th className="pb-2 text-left">Vol</th>
                <th className="pb-2 text-left">OI</th>
              </tr>
            </thead>
            <tbody>
              {strikes.map((s, i) => (
                <tr key={i} className={`border-b border-[var(--border)] ${s.atm ? 'bg-[var(--accent-glow)]' : ''} hover:bg-[var(--bg-card-hover)] transition-colors`}>
                  <td className="py-2 text-right text-[var(--text-secondary)]">{(s.ceOI / 1000).toFixed(0)}K</td>
                  <td className="py-2 text-right text-[var(--text-tertiary)]">{(s.ceVol / 1000).toFixed(1)}K</td>
                  <td className="py-2 text-right text-[var(--amber)]">{s.ceIV.toFixed(1)}%</td>
                  <td className="py-2 text-right text-[var(--green)] font-medium">{s.ceLTP.toFixed(2)}</td>
                  <td className={`py-2 text-center font-bold ${s.atm ? 'text-[var(--accent)]' : ''}`}>{s.strike}</td>
                  <td className="py-2 text-left text-[var(--red)] font-medium">{s.peLTP.toFixed(2)}</td>
                  <td className="py-2 text-left text-[var(--amber)]">{s.peIV.toFixed(1)}%</td>
                  <td className="py-2 text-left text-[var(--text-tertiary)]">{(s.peVol / 1000).toFixed(1)}K</td>
                  <td className="py-2 text-left text-[var(--text-secondary)]">{(s.peOI / 1000).toFixed(0)}K</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
