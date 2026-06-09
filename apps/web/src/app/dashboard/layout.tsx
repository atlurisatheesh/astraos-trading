"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { section: "Overview" },
  { href: "/dashboard", icon: "⬡", label: "Dashboard" },
  { href: "/dashboard/signals", icon: "◈", label: "AI Signals", badge: "12", badgeGreen: true },
  { section: "Markets" },
  { href: "/dashboard/markets", icon: "◉", label: "Nifty / BankNifty" },
  { href: "/dashboard/options", icon: "◈", label: "F&O Options Chain" },
  { href: "/dashboard/watchlist", icon: "◎", label: "Watchlist" },
  { section: "Intelligence" },
  { href: "/dashboard/research", icon: "◈", label: "Deep Research" },
  { href: "/dashboard/predictions", icon: "◉", label: "AI Predictions" },
  { href: "/dashboard/sectors", icon: "⬡", label: "Sector Heatmap" },
  { section: "Automation" },
  { href: "/dashboard/positions", icon: "◈", label: "Positions", badge: "3" },
  { href: "/dashboard/autopilot", icon: "◉", label: "Auto-Trade Engine" },
  { href: "/dashboard/risk", icon: "⬡", label: "Risk Manager" },
  { section: "Tools" },
  { href: "/dashboard/backtest", icon: "◎", label: "Backtest Studio" },
  { href: "/dashboard/analyst", icon: "◈", label: "AI Analyst" },
  { href: "/dashboard/brokers", icon: "🔌", label: "Broker Setup" },
];

const TICKER_ITEMS = [
  { name: "NIFTY50", val: "24,842.65", chg: "+0.42%", up: true },
  { name: "BANKNIFTY", val: "52,318.40", chg: "+0.68%", up: true },
  { name: "SENSEX", val: "81,576.35", chg: "+0.51%", up: true },
  { name: "RELIANCE", val: "2,892.75", chg: "-0.31%", up: false },
  { name: "TCS", val: "4,126.00", chg: "+1.14%", up: true },
  { name: "HDFC BANK", val: "1,887.50", chg: "+0.88%", up: true },
  { name: "INFOSYS", val: "1,672.30", chg: "-0.22%", up: false },
  { name: "ICICI BANK", val: "1,435.80", chg: "+1.22%", up: true },
  { name: "WIPRO", val: "487.65", chg: "+0.43%", up: true },
  { name: "BAJFINANCE", val: "6,782.00", chg: "-0.56%", up: false },
  { name: "GOLD", val: "₹71,450", chg: "+0.34%", up: true },
  { name: "USD/INR", val: "83.42", chg: "-0.08%", up: false },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const now = new Date();
  const dateStr = now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <>
      {/* SIDEBAR — exact DOM from index.html */}
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
            if (item.section) {
              return <div key={`sec-${idx}`} className="nav-section">{item.section}</div>;
            }
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href!));
            return (
              <Link key={item.href} href={item.href!} className={`nav-item${active ? " active" : ""}`}>
                <span className="nav-icon">{item.icon}</span> {item.label}
                {item.badge && (
                  <span className={`nav-badge${item.badgeGreen ? " green" : ""}`}>{item.badge}</span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="market-status">
            <div className="status-dot"></div>
            Market Open · NSE
          </div>
          <div className="algo-status">Algo Engine: ACTIVE</div>
        </div>
      </div>

      {/* TICKER TAPE — exact DOM from index.html */}
      <div className="sidebar-offset">
        <div className="ticker-tape">
          <span className="ticker-scroll">
            {[...TICKER_ITEMS, ...TICKER_ITEMS].map((t, i) => (
              <span key={i} className="ticker-tape-item">
                <span className="tt-name">{t.name}</span>
                <span className={t.up ? "up" : "dn"}>{t.val}</span>
                <span className={t.up ? "up" : "dn"}>{t.chg}</span>
              </span>
            ))}
          </span>
        </div>

        {/* MAIN — exact DOM from index.html */}
        <div className="main main-no-offset">
          <div className="topbar">
            <div className="topbar-title">
              Dashboard <span>{dateStr}</span>
            </div>
            <div className="market-ticker">
              <div className="ticker-item"><span className="ticker-name">N50</span><span className="ticker-val up">24,842</span><span className="ticker-chg up">+105</span></div>
              <div className="ticker-item"><span className="ticker-name">BNK</span><span className="ticker-val up">52,318</span><span className="ticker-chg up">+353</span></div>
              <div className="ticker-item"><span className="ticker-name">VIX</span><span className="ticker-val dn">14.32</span><span className="ticker-chg dn">-0.8</span></div>
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
