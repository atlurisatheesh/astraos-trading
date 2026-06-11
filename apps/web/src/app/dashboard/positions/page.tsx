"use client";

import { api, PositionItem, BrokerSnapshot } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { useWebSocket } from "@/hooks/useWebSocket";

const FALLBACK_OPEN = [
  { s: "RELIANCE", side: "LONG", qty: 50, avg: "2,840.00", ltp: "2,876.50", pnl: "+₹1,825", pnlPct: "+1.28%", up: true, strategy: "Momentum" },
  { s: "TCS", side: "LONG", qty: 30, avg: "3,900.00", ltp: "3,945.20", pnl: "+₹1,356", pnlPct: "+1.16%", up: true, strategy: "Earnings" },
  { s: "NIFTY 24500 CE", side: "LONG", qty: 100, avg: "245.00", ltp: "262.30", pnl: "+₹1,730", pnlPct: "+7.06%", up: true, strategy: "Gamma Squeeze" },
  { s: "HDFC BANK", side: "LONG", qty: 40, avg: "1,690.00", ltp: "1,678.30", pnl: "-₹468", pnlPct: "-0.69%", up: false, strategy: "Mean Reversion" },
  { s: "INFY", side: "SHORT", qty: 25, avg: "1,580.00", ltp: "1,567.80", pnl: "+₹305", pnlPct: "+0.77%", up: true, strategy: "IV Crush" },
];

const FALLBACK_CLOSED = [
  { s: "SBIN", side: "LONG", qty: 100, entry: "760", exit: "795", pnl: "+₹3,500", duration: "5d" },
  { s: "BAJAJ FIN", side: "LONG", qty: 10, entry: "7,100", exit: "7,280", pnl: "+₹1,800", duration: "3d" },
  { s: "NIFTY PE", side: "SHORT", qty: 50, entry: "180", exit: "120", pnl: "+₹3,000", duration: "2d" },
];

function fmt(n: number) { return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

export default function PositionsPage() {
  const { data: positions } = useApi(() => api.getPositions(), [], { interval: 10000 });
  const { data: wsPortfolio } = useWebSocket<{ positions: PositionItem[] }>("/ws/portfolio");
  // Broker snapshot is refreshed by the backend scheduler every 2 min
  const { data: brokerSnap } = useApi(() => api.getBrokerSnapshot(), [], { interval: 60000 });
  const brokerEntries = Object.entries(brokerSnap?.snapshots ?? {}) as [string, BrokerSnapshot][];

  const livePositions = wsPortfolio?.positions ?? positions ?? [];
  const openPositions = livePositions.filter((p: PositionItem) => p.is_open);
  const closedPositions = livePositions.filter((p: PositionItem) => !p.is_open);

  const useApi_ = openPositions.length > 0;

  const openRows = useApi_
    ? openPositions.map((p: PositionItem) => ({
        s: p.symbol ?? `#${p.id}`,
        side: p.side === "BUY" ? "LONG" : "SHORT",
        qty: p.quantity,
        avg: fmt(p.average_cost),
        ltp: fmt(p.current_price ?? 0),
        pnl: (p.unrealized_pnl >= 0 ? "+" : "") + "₹" + fmt(Math.abs(p.unrealized_pnl)),
        pnlPct: p.average_cost > 0 ? ((p.unrealized_pnl / (p.average_cost * p.quantity)) * 100).toFixed(2) + "%" : "0%",
        up: p.unrealized_pnl >= 0,
        strategy: "—",
      }))
    : FALLBACK_OPEN;

  const closedRows = useApi_
    ? closedPositions.map((p: PositionItem) => ({
        s: p.symbol ?? `#${p.id}`, side: p.side, qty: p.quantity,
        entry: fmt(p.average_cost), exit: fmt(p.current_price ?? 0),
        pnl: (p.realized_pnl >= 0 ? "+" : "") + "₹" + fmt(Math.abs(p.realized_pnl)), duration: "—",
      }))
    : FALLBACK_CLOSED;

  return (
    <div className="space-y-5 animate-fade-in">
      <h1 className="text-2xl font-bold font-[var(--font-heading)]">💼 Positions</h1>

      {brokerEntries.map(([broker, snap]) => (
        <div key={broker} className="card border border-[var(--border-active)]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold font-[var(--font-heading)]">
              🏦 {broker.toUpperCase()} — Live Broker Sync
              <span className="ml-2 text-[10px] font-bold px-2 py-0.5 rounded signal-buy">LIVE</span>
            </h2>
            <span className="text-[10px] text-[var(--text-tertiary)]">
              synced {new Date(snap.synced_at).toLocaleTimeString("en-IN")}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="text-center">
              <div className="text-[10px] text-[var(--text-tertiary)]">Day P&L</div>
              <div className={`text-lg font-bold font-[var(--font-mono)] ${snap.total_pnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                {snap.total_pnl >= 0 ? "+" : ""}₹{fmt(snap.total_pnl)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-[var(--text-tertiary)]">Available Funds</div>
              <div className="text-lg font-bold font-[var(--font-mono)]">₹{fmt(snap.funds?.available ?? 0)}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-[var(--text-tertiary)]">Open Positions</div>
              <div className="text-lg font-bold font-[var(--font-mono)]">{snap.positions.length}</div>
            </div>
          </div>
          {snap.positions.length > 0 && (
            <table className="w-full text-xs font-[var(--font-mono)]">
              <thead><tr className="text-[10px] text-[var(--text-tertiary)] border-b border-[var(--border)]">
                {["Symbol", "Side", "Qty", "Avg", "LTP", "P&L"].map(h => <th key={h} className="pb-2 text-left font-medium">{h}</th>)}
              </tr></thead>
              <tbody>
                {snap.positions.map((p, i) => (
                  <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--bg-card-hover)]">
                    <td className="py-2 font-semibold">{p.symbol}</td>
                    <td className={p.side === "BUY" ? "text-[var(--green)]" : "text-[var(--red)]"}>{p.side}</td>
                    <td>{p.quantity}</td>
                    <td>₹{fmt(p.avg_price)}</td>
                    <td>₹{fmt(p.ltp)}</td>
                    <td className={p.pnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]"}>
                      {p.pnl >= 0 ? "+" : ""}₹{fmt(p.pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}

      <div className="card">
        <h2 className="text-base font-semibold font-[var(--font-heading)] mb-3 text-[var(--green)]">Open Positions ({openRows.length})</h2>
        <table className="w-full text-xs font-[var(--font-mono)]">
          <thead>
            <tr className="text-[10px] text-[var(--text-tertiary)] border-b border-[var(--border)]">
              {["Symbol", "Side", "Qty", "Avg", "LTP", "P&L", "Strategy", "Action"].map(h => (
                <th key={h} className="pb-2 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {openRows.map((p, i) => (
              <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--bg-card-hover)]">
                <td className="py-2.5 font-semibold">{p.s}</td>
                <td className={p.side === "LONG" ? "text-[var(--green)]" : "text-[var(--red)]"}>{p.side}</td>
                <td className="text-[var(--text-secondary)]">{p.qty}</td>
                <td>₹{p.avg}</td>
                <td>{p.ltp}</td>
                <td className={p.up ? "text-[var(--green)]" : "text-[var(--red)]"}>{p.pnl} ({p.pnlPct})</td>
                <td className="text-[var(--text-tertiary)]">{p.strategy}</td>
                <td><button className="text-[10px] px-2 py-1 rounded bg-[var(--red-glow)] text-[var(--red)] border border-[rgba(255,79,109,0.2)] hover:bg-[rgba(255,79,109,0.25)]">Close</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="text-base font-semibold font-[var(--font-heading)] mb-3">Closed Today ({closedRows.length})</h2>
        <table className="w-full text-xs font-[var(--font-mono)]">
          <thead><tr className="text-[10px] text-[var(--text-tertiary)] border-b border-[var(--border)]">
            {["Symbol", "Side", "Qty", "Entry", "Exit", "P&L", "Duration"].map(h => <th key={h} className="pb-2 text-left font-medium">{h}</th>)}
          </tr></thead>
          <tbody>
            {closedRows.map((p, i) => (
              <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--bg-card-hover)]">
                <td className="py-2.5 font-semibold">{p.s}</td><td>{p.side}</td><td>{p.qty}</td>
                <td>₹{p.entry}</td><td>₹{p.exit}</td>
                <td className="text-[var(--green)]">{p.pnl}</td><td className="text-[var(--text-tertiary)]">{p.duration}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
