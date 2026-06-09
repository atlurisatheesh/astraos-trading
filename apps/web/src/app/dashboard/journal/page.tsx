"use client";

import { api, JournalEntry } from "@/lib/api";
import { useApi } from "@/hooks/useApi";

const FALLBACK_JOURNAL = [
  { date: "24 Mar", symbol: "RELIANCE", side: "BUY", entry: "2,840", exit: "—", pnl: "+₹1,825", status: "Open", notes: "Strong OI buildup + momentum. Following signal.", emotion: "😌 Calm" },
  { date: "24 Mar", symbol: "TCS", side: "BUY", entry: "3,900", exit: "—", pnl: "+₹1,356", status: "Open", notes: "Earnings beat. IT sector rotation play.", emotion: "😊 Confident" },
  { date: "23 Mar", symbol: "SBIN", side: "BUY", entry: "760", exit: "795", pnl: "+₹3,500", status: "Closed", notes: "PSU bank rotation thesis played out perfectly.", emotion: "🎯 Disciplined" },
  { date: "22 Mar", symbol: "NIFTY PE", side: "SELL", entry: "180", exit: "120", pnl: "+₹3,000", status: "Closed", notes: "Theta decay play. Sold premium at high IV.", emotion: "😌 Calm" },
  { date: "21 Mar", symbol: "AXIS BANK", side: "BUY", entry: "1,120", exit: "1,095", pnl: "-₹1,250", status: "Closed", notes: "Stopped out. Sector weakness overrode stock thesis.", emotion: "😤 Frustrated" },
];

function fmt(n: number) { return n.toLocaleString("en-IN", { minimumFractionDigits: 0 }); }

export default function JournalPage() {
  const { data: apiJournal } = useApi(() => api.getJournal(), [], { interval: 30000 });

  const JOURNAL = (apiJournal as JournalEntry[])?.length
    ? (apiJournal as JournalEntry[]).map(j => ({
        date: new Date(j.trade_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }),
        symbol: j.symbol,
        side: j.side,
        entry: fmt(j.entry_price),
        exit: j.exit_price != null ? fmt(j.exit_price) : "—",
        pnl: (j.pnl >= 0 ? "+" : "") + "₹" + fmt(Math.abs(j.pnl)),
        status: j.exit_price != null ? "Closed" : "Open",
        notes: j.notes || "—",
        emotion: j.emotion || "—",
      }))
    : FALLBACK_JOURNAL;
  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-[var(--font-heading)]">📓 Trade Journal</h1>
        <button id="add-journal" className="text-xs px-3 py-1.5 bg-[var(--accent)] text-white rounded-lg">+ New Entry</button>
      </div>
      <div className="space-y-3">
        {JOURNAL.map((j, i) => (
          <div key={i} className="card hover:border-[var(--border-active)]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-[var(--text-tertiary)]">{j.date}</span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${j.side === 'BUY' ? 'signal-buy' : 'signal-sell'}`}>{j.side}</span>
                <span className="font-semibold font-[var(--font-mono)] text-sm">{j.symbol}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-sm font-bold font-[var(--font-mono)] ${j.pnl.includes('+') ? 'text-[var(--green)]' : 'text-[var(--red)]'}`}>{j.pnl}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded ${j.status === 'Open' ? 'bg-[var(--accent-glow)] text-[var(--accent)]' : 'bg-[var(--bg-primary)] text-[var(--text-tertiary)] border border-[var(--border)]'}`}>{j.status}</span>
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs font-[var(--font-mono)] text-[var(--text-secondary)] mb-2">
              <span>Entry: ₹{j.entry}</span><span>Exit: {j.exit === "—" ? "—" : "₹" + j.exit}</span>
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-[var(--text-secondary)]">💭 {j.notes}</p>
              <span className="text-xs">{j.emotion}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
