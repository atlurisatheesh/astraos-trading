"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/* ─── Clean inline SVG icons (16x16, stroke-based) ─── */
const I = {
  dashboard: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>,
  signals: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12h4l3-8 4 16 3-8h6"/></svg>,
  markets: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17l5-5 4 4 8-8"/><path d="M14 8h6v6"/></svg>,
  options: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 4v16"/></svg>,
  watchlist: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>,
  research: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></svg>,
  predictions: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a7 7 0 0 1 7 7c0 2.5-1.5 4.5-3 6l-1 5h-6l-1-5c-1.5-1.5-3-3.5-3-6a7 7 0 0 1 7-7z"/><path d="M9 22h6"/></svg>,
  sectors: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="8" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/><rect x="13" y="13" width="8" height="8" rx="1"/></svg>,
  positions: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.3 7l8.7 5 8.7-5M12 22V12"/></svg>,
  autopilot: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8V4M8 4h8"/><rect x="4" y="8" width="16" height="12" rx="2"/><circle cx="9" cy="14" r="1" fill="currentColor"/><circle cx="15" cy="14" r="1" fill="currentColor"/></svg>,
  risk: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2L3 7v6c0 5 4 8.5 9 9 5-.5 9-4 9-9V7l-9-5z"/><path d="M12 8v4M12 16h.01"/></svg>,
  backtest: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>,
  analyst: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5c-1.5 0-3-.4-4.2-1L3 20l1-5.3A8.38 8.38 0 0 1 12.5 3a8.5 8.5 0 0 1 8.5 8.5z"/></svg>,
  brokers: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>,
  journal: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>,
  settings: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  logout: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>,
};

type NavEntry =
  | { section: string }
  | { href: string; icon: keyof typeof I; label: string };

const NAV_ITEMS: NavEntry[] = [
  { section: "Overview" },
  { href: "/dashboard", icon: "dashboard", label: "Dashboard" },
  { href: "/dashboard/signals", icon: "signals", label: "AI Signals" },
  { section: "Markets" },
  { href: "/dashboard/markets", icon: "markets", label: "Nifty / BankNifty" },
  { href: "/dashboard/options", icon: "options", label: "Options Chain" },
  { href: "/dashboard/watchlist", icon: "watchlist", label: "Watchlist" },
  { section: "Intelligence" },
  { href: "/dashboard/research", icon: "research", label: "Deep Research" },
  { href: "/dashboard/predictions", icon: "predictions", label: "AI Predictions" },
  { href: "/dashboard/sectors", icon: "sectors", label: "Sector Heatmap" },
  { section: "Automation" },
  { href: "/dashboard/positions", icon: "positions", label: "Positions" },
  { href: "/dashboard/autopilot", icon: "autopilot", label: "Auto-Trade" },
  { href: "/dashboard/risk", icon: "risk", label: "Risk Manager" },
  { section: "Tools" },
  { href: "/dashboard/backtest", icon: "backtest", label: "Backtest Studio" },
  { href: "/dashboard/analyst", icon: "analyst", label: "AI Analyst" },
  { href: "/dashboard/journal", icon: "journal", label: "Trade Journal" },
  { href: "/dashboard/brokers", icon: "brokers", label: "Broker Setup" },
  { href: "/dashboard/settings", icon: "settings", label: "Settings" },
];

// Fallback shown until live quotes load
const TICKER_FALLBACK = [
  { name: "NIFTY50", val: "—", chg: "", up: true },
  { name: "BANKNIFTY", val: "—", chg: "", up: true },
  { name: "SENSEX", val: "—", chg: "", up: true },
  { name: "RELIANCE", val: "—", chg: "", up: true },
  { name: "TCS", val: "—", chg: "", up: true },
];

// symbol → display name (backend appends .NS for non-^ symbols)
const TICKER_SYMBOLS: [string, string][] = [
  ["^NSEI", "NIFTY50"],
  ["^NSEBANK", "BANKNIFTY"],
  ["^BSESN", "SENSEX"],
  ["RELIANCE", "RELIANCE"],
  ["TCS", "TCS"],
  ["HDFCBANK", "HDFC BANK"],
  ["INFY", "INFOSYS"],
  ["ICICIBANK", "ICICI BANK"],
  ["WIPRO", "WIPRO"],
  ["BAJFINANCE", "BAJFINANCE"],
];

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/dashboard/signals": "AI Signals",
  "/dashboard/markets": "Nifty / BankNifty",
  "/dashboard/options": "Options Chain",
  "/dashboard/watchlist": "Watchlist",
  "/dashboard/research": "Deep Research",
  "/dashboard/predictions": "AI Predictions",
  "/dashboard/sectors": "Sector Heatmap",
  "/dashboard/positions": "Positions",
  "/dashboard/autopilot": "Auto-Trade Engine",
  "/dashboard/risk": "Risk Manager",
  "/dashboard/backtest": "Backtest Studio",
  "/dashboard/analyst": "AI Analyst",
  "/dashboard/journal": "Trade Journal",
  "/dashboard/brokers": "Broker Setup",
  "/dashboard/settings": "Settings",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string>("");
  const [ticker, setTicker] = useState(TICKER_FALLBACK);

  useEffect(() => {
    const email = localStorage.getItem("user_email") || sessionStorage.getItem("user_email") || "";
    setUserEmail(email);
  }, []);

  useEffect(() => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://astraos-backend.onrender.com";
    async function loadQuotes() {
      try {
        const token = localStorage.getItem("token");
        const syms = TICKER_SYMBOLS.map(([s]) => s).join(",");
        const res = await fetch(`${API_BASE}/api/v1/market/quotes?symbols=${encodeURIComponent(syms)}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) return;
        const quotes = await res.json();
        if (!Array.isArray(quotes) || !quotes.length) return;
        setTicker(
          quotes.map((q: any, i: number) => {
            const chg = q.change_pct ?? 0;
            return {
              name: TICKER_SYMBOLS[i]?.[1] || q.symbol,
              val: Number(q.price ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 }),
              chg: `${chg >= 0 ? "+" : ""}${Number(chg).toFixed(2)}%`,
              up: chg >= 0,
            };
          })
        );
      } catch { /* keep fallback */ }
    }
    loadQuotes();
    const id = setInterval(loadQuotes, 60000);
    return () => clearInterval(id);
  }, []);

  const logout = () => {
    ["token", "access_token", "user_email"].forEach(k => {
      localStorage.removeItem(k);
      sessionStorage.removeItem(k);
    });
    router.push("/login");
  };

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const pageTitle = PAGE_TITLES[pathname] || "Dashboard";

  return (
    <>
      {/* SIDEBAR */}
      <div className="sidebar">
        <div className="logo">
          <div className="logo-mark">
            <div className="logo-icon">Q</div>
            <div>
              <div className="logo-text">QUANTUS AI</div>
              <div className="logo-sub">Autonomous Trading</div>
            </div>
          </div>
        </div>
        <nav className="nav">
          {NAV_ITEMS.map((item, idx) => {
            if ("section" in item) {
              return <div key={`sec-${idx}`} className="nav-section">{item.section}</div>;
            }
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link key={item.href} href={item.href} className={`nav-item${active ? " active" : ""}`}>
                <span className="nav-icon">{I[item.icon]}</span>
                <span className="nav-label">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="market-status">
            <div className="status-dot"></div>
            Market Open · NSE
          </div>
          <div className="user-row">
            <div className="user-avatar-sm">{(userEmail[0] || "U").toUpperCase()}</div>
            <div className="user-email" title={userEmail}>{userEmail || "Trader"}</div>
            <button className="logout-btn" onClick={logout} title="Log out">
              {I.logout}
            </button>
          </div>
        </div>
      </div>

      {/* TICKER TAPE */}
      <div className="sidebar-offset">
        <div className="ticker-tape">
          <span className="ticker-scroll">
            {[...ticker, ...ticker].map((t, i) => (
              <span key={i} className="ticker-tape-item">
                <span className="tt-name">{t.name}</span>
                <span className={t.up ? "up" : "dn"}>{t.val}</span>
                <span className={t.up ? "up" : "dn"}>{t.chg}</span>
              </span>
            ))}
          </span>
        </div>

        {/* MAIN */}
        <div className="main main-no-offset">
          <div className="topbar">
            <div className="topbar-title">
              {pageTitle} <span>{dateStr}</span>
            </div>
            <div className="market-ticker">
              {ticker.slice(0, 3).map((t, i) => (
                <div className="ticker-item" key={i}>
                  <span className="ticker-name">{["N50", "BNK", "SNX"][i] || t.name}</span>
                  <span className={`ticker-val ${t.up ? "up" : "dn"}`}>{t.val}</span>
                  <span className={`ticker-chg ${t.up ? "up" : "dn"}`}>{t.chg}</span>
                </div>
              ))}
            </div>
            <div className="topbar-actions">
              <button className="btn">⏸ Pause Bot</button>
              <button className="btn btn-danger">⬛ Kill Switch</button>
              <button className="btn btn-primary">+ New Signal</button>
            </div>
          </div>

          {/* Page content injected here */}
          {children}
        </div>
      </div>
    </>
  );
}
