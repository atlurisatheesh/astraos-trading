"use client";

import { api, Quote } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { useWebSocket, TickerData } from "@/hooks/useWebSocket";

const INDEX_SYMBOLS = ["NIFTY 50", "NSEBANK", "INDIAVIX"];
const NIFTY_SYMBOLS = [
  "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
  "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE",
  "LT", "KOTAKBANK", "HCLTECH", "AXISBANK", "ASIANPAINT",
  "MARUTI", "SUNPHARMA", "TITAN", "WIPRO", "TATAMOTORS",
];

const FALLBACK_INDICES = [
  { name: "NIFTY 50", value: "23,456.80", change: "+289.45", pct: "+1.25%", up: true },
  { name: "BANK NIFTY", value: "49,123.45", change: "+425.30", pct: "+0.87%", up: true },
  { name: "NIFTY IT", value: "38,945.20", change: "+892.10", pct: "+2.34%", up: true },
  { name: "NIFTY FIN", value: "22,340.60", change: "+156.80", pct: "+0.71%", up: true },
  { name: "INDIA VIX", value: "13.24", change: "-0.44", pct: "-3.21%", up: false },
  { name: "S&P 500", value: "5,234.56", change: "+12.30", pct: "+0.24%", up: true },
];

function fmt(n: number): string {
  return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function MarketsPage() {
  const { data: ticker } = useWebSocket<TickerData>("/ws/ticker?symbols=" + NIFTY_SYMBOLS.join(","), { autoReconnect: true });
  const { data: quotes, loading } = useApi(
    () => api.getQuotes(NIFTY_SYMBOLS),
    [],
    { interval: 30000 },
  );

  const liveQuotes: Quote[] = ticker?.quotes as Quote[] ?? quotes ?? [];

  const sorted = [...liveQuotes].sort((a, b) => b.change_pct - a.change_pct);
  const gainers = sorted.filter((q) => q.change_pct > 0).slice(0, 5);
  const losers = sorted.filter((q) => q.change_pct < 0).reverse().slice(0, 5);

  const indices = liveQuotes.length > 0
    ? liveQuotes.filter((q) => INDEX_SYMBOLS.includes(q.symbol)).map((q) => ({
        name: q.symbol, value: fmt(q.price), change: (q.change >= 0 ? "+" : "") + fmt(q.change),
        pct: (q.change_pct >= 0 ? "+" : "") + q.change_pct.toFixed(2) + "%", up: q.change_pct >= 0,
      }))
    : FALLBACK_INDICES;

  return (
    <div className="space-y-5 animate-fade-in">
      <h1 className="text-2xl font-bold font-[var(--font-heading)]">📈 Markets</h1>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {(indices.length > 0 ? indices : FALLBACK_INDICES).map((idx, i) => (
          <div key={i} className="card text-center">
            <div className="text-[11px] text-[var(--text-tertiary)] mb-1">{idx.name}</div>
            <div className="text-base font-bold font-[var(--font-mono)]">{idx.value}</div>
            <div className={`text-xs font-[var(--font-mono)] ${idx.up ? 'text-[var(--green)]' : 'text-[var(--red)]'}`}>
              {idx.change} ({idx.pct})
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="card">
          <h2 className="text-base font-semibold font-[var(--font-heading)] text-[var(--green)] mb-3">🔼 Top Gainers</h2>
          {loading && gainers.length === 0 && <div className="text-xs text-[var(--text-tertiary)]">Loading...</div>}
          {gainers.map((s, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0 text-sm font-[var(--font-mono)]">
              <span>{s.symbol}</span>
              <span className="text-[var(--text-secondary)]">₹{fmt(s.price)}</span>
              <span className="text-[var(--green)]">+{s.change_pct.toFixed(2)}%</span>
            </div>
          ))}
        </div>
        <div className="card">
          <h2 className="text-base font-semibold font-[var(--font-heading)] text-[var(--red)] mb-3">🔽 Top Losers</h2>
          {loading && losers.length === 0 && <div className="text-xs text-[var(--text-tertiary)]">Loading...</div>}
          {losers.map((s, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0 text-sm font-[var(--font-mono)]">
              <span>{s.symbol}</span>
              <span className="text-[var(--text-secondary)]">₹{fmt(s.price)}</span>
              <span className="text-[var(--red)]">{s.change_pct.toFixed(2)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
