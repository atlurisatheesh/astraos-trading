"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "./heatmap.css";

/* ── Types ─────────────────────────────────────────────────── */
interface HeatStock {
  symbol: string;
  sector: string;
  change_pct: number;
  market_cap_cr: number;
  last_price: number;
  color: string;
}

interface BreadthData {
  breadth: {
    advances: number;
    declines: number;
    unchanged: number;
    ad_ratio: number;
    new_52w_highs: number;
    new_52w_lows: number;
  };
  sentiment: { label: string; score: number };
  sector_performance: Record<string, number>;
  heatmap: HeatStock[];
}

/* ── Mock Data (used until API is live) ─────────────────────── */
const MOCK_DATA: BreadthData = {
  breadth: { advances: 28, declines: 10, unchanged: 2, ad_ratio: 2.8, new_52w_highs: 5, new_52w_lows: 1 },
  sentiment: { label: "bullish", score: 45 },
  sector_performance: {
    IT: 2.14, Banking: 1.42, Auto: 0.87, Pharma: 0.65, Energy: 0.34,
    FMCG: -0.22, Telecom: -0.48, Metal: -0.91, Infrastructure: 1.15,
    Consumer: 0.52, Insurance: 0.38, Mining: -0.15,
  },
  heatmap: [
    { symbol: "RELIANCE", sector: "Energy", change_pct: 1.82, market_cap_cr: 1893500, last_price: 2892.75, color: "#66bb6a" },
    { symbol: "TCS", sector: "IT", change_pct: 2.45, market_cap_cr: 1498200, last_price: 4126.0, color: "#66bb6a" },
    { symbol: "HDFCBANK", sector: "Banking", change_pct: 0.88, market_cap_cr: 1142700, last_price: 1887.5, color: "#a5d6a7" },
    { symbol: "INFY", sector: "IT", change_pct: 3.21, market_cap_cr: 693800, last_price: 1672.3, color: "#00c853" },
    { symbol: "ICICIBANK", sector: "Banking", change_pct: 1.22, market_cap_cr: 1005300, last_price: 1435.8, color: "#66bb6a" },
    { symbol: "HINDUNILVR", sector: "FMCG", change_pct: -0.31, market_cap_cr: 548900, last_price: 2378.6, color: "#ef9a9a" },
    { symbol: "SBIN", sector: "Banking", change_pct: 1.95, market_cap_cr: 714200, last_price: 801.3, color: "#66bb6a" },
    { symbol: "BHARTIARTL", sector: "Telecom", change_pct: -0.78, market_cap_cr: 842100, last_price: 1486.2, color: "#e53935" },
    { symbol: "ITC", sector: "FMCG", change_pct: 0.42, market_cap_cr: 561400, last_price: 449.6, color: "#a5d6a7" },
    { symbol: "KOTAKBANK", sector: "Banking", change_pct: 0.34, market_cap_cr: 345800, last_price: 1742.1, color: "#a5d6a7" },
    { symbol: "LT", sector: "Infrastructure", change_pct: 1.67, market_cap_cr: 493200, last_price: 3602.8, color: "#66bb6a" },
    { symbol: "BAJFINANCE", sector: "Finance", change_pct: -1.56, market_cap_cr: 411200, last_price: 6782.0, color: "#e53935" },
    { symbol: "AXISBANK", sector: "Banking", change_pct: 0.92, market_cap_cr: 338700, last_price: 1098.4, color: "#a5d6a7" },
    { symbol: "SUNPHARMA", sector: "Pharma", change_pct: 1.13, market_cap_cr: 386400, last_price: 1612.5, color: "#66bb6a" },
    { symbol: "MARUTI", sector: "Auto", change_pct: 1.95, market_cap_cr: 389100, last_price: 12456.0, color: "#66bb6a" },
    { symbol: "TATAMOTORS", sector: "Auto", change_pct: -2.34, market_cap_cr: 276500, last_price: 748.9, color: "#b71c1c" },
    { symbol: "HCLTECH", sector: "IT", change_pct: 2.78, market_cap_cr: 425600, last_price: 1834.2, color: "#00c853" },
    { symbol: "WIPRO", sector: "IT", change_pct: 0.43, market_cap_cr: 255300, last_price: 487.65, color: "#a5d6a7" },
    { symbol: "TITAN", sector: "Consumer", change_pct: 0.67, market_cap_cr: 312800, last_price: 3524.7, color: "#a5d6a7" },
    { symbol: "NESTLEIND", sector: "FMCG", change_pct: -0.15, market_cap_cr: 218400, last_price: 2265.3, color: "#ef9a9a" },
    { symbol: "ULTRACEMCO", sector: "Cement", change_pct: 0.42, market_cap_cr: 268100, last_price: 9256.0, color: "#a5d6a7" },
    { symbol: "NTPC", sector: "Energy", change_pct: 0.91, market_cap_cr: 342900, last_price: 354.2, color: "#a5d6a7" },
    { symbol: "TATASTEEL", sector: "Metal", change_pct: -1.28, market_cap_cr: 168900, last_price: 139.4, color: "#e53935" },
    { symbol: "COALINDIA", sector: "Mining", change_pct: -0.34, market_cap_cr: 268400, last_price: 435.6, color: "#ef9a9a" },
    { symbol: "ONGC", sector: "Energy", change_pct: 0.56, market_cap_cr: 261200, last_price: 207.8, color: "#a5d6a7" },
    { symbol: "TECHM", sector: "IT", change_pct: 1.89, market_cap_cr: 145200, last_price: 1498.3, color: "#66bb6a" },
    { symbol: "JSWSTEEL", sector: "Metal", change_pct: -0.67, market_cap_cr: 224100, last_price: 918.5, color: "#ef9a9a" },
    { symbol: "CIPLA", sector: "Pharma", change_pct: 0.78, market_cap_cr: 121800, last_price: 1502.4, color: "#a5d6a7" },
    { symbol: "DRREDDY", sector: "Pharma", change_pct: -0.42, market_cap_cr: 101200, last_price: 6042.1, color: "#ef9a9a" },
    { symbol: "M&M", sector: "Auto", change_pct: 1.34, market_cap_cr: 368400, last_price: 2965.8, color: "#66bb6a" },
  ],
};

/* ── Helpers ───────────────────────────────────────────────── */
function getBgColor(pct: number): string {
  if (pct > 3) return "rgba(0,200,83,0.35)";
  if (pct > 1.5) return "rgba(0,200,83,0.22)";
  if (pct > 0.5) return "rgba(102,187,106,0.18)";
  if (pct > 0) return "rgba(165,214,167,0.14)";
  if (pct > -0.5) return "rgba(239,154,154,0.14)";
  if (pct > -1.5) return "rgba(229,57,53,0.18)";
  if (pct > -3) return "rgba(229,57,53,0.25)";
  return "rgba(183,28,28,0.35)";
}

function getTextToneClass(pct: number): string {
  if (pct > 1) return "tone-green-strong";
  if (pct > 0) return "tone-green-soft";
  if (pct > -1) return "tone-red-soft";
  return "tone-red-strong";
}

function getSentimentToneClass(score: number): string {
  if (score > 30) return "tone-green";
  if (score > 10) return "tone-green-soft";
  if (score > -10) return "tone-amber";
  if (score > -30) return "tone-red-soft";
  return "tone-red";
}

function getSentimentEmoji(label: string): string {
  const map: Record<string, string> = {
    strongly_bullish: "🚀",
    bullish: "📈",
    neutral: "➡️",
    bearish: "📉",
    strongly_bearish: "💀",
  };
  return map[label] || "📊";
}

function formatMcap(cr: number): string {
  if (cr >= 100000) return `₹${(cr / 100000).toFixed(1)}L Cr`;
  return `₹${(cr / 1000).toFixed(0)}K Cr`;
}

/* ── Components ────────────────────────────────────────────── */
function DynamicWidthBar({
  className,
  width,
  children,
}: {
  className: string;
  width: number;
  children?: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.width = `${Math.max(0, width)}%`;
    }
  }, [width]);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}

function SentimentGauge({ score, label }: { score: number; label: string }) {
  // Arc from -100 to +100 → 0° to 180°
  const angle = ((score + 100) / 200) * 180;
  const rad = (angle * Math.PI) / 180;
  const cx = 80, cy = 75, r = 60;
  const x = cx + r * Math.cos(Math.PI - rad);
  const y = cy - r * Math.sin(Math.PI - rad);
  const sentimentToneClass = getSentimentToneClass(score);

  return (
    <div className="sentiment-gauge-wrap">
      <div className="sentiment-gauge">
        <svg className="sentiment-arc" viewBox="0 0 160 85">
          {/* Background arc */}
          <path d="M 20 75 A 60 60 0 0 1 140 75" fill="none" stroke="var(--bg3)" strokeWidth="10" strokeLinecap="round" />
          {/* Gradient arc */}
          <defs>
            <linearGradient id="gauge-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--red)" />
              <stop offset="30%" stopColor="var(--amber)" />
              <stop offset="70%" stopColor="#81c784" />
              <stop offset="100%" stopColor="var(--green)" />
            </linearGradient>
          </defs>
          <path d="M 20 75 A 60 60 0 0 1 140 75" fill="none" stroke="url(#gauge-grad)" strokeWidth="10" strokeLinecap="round" opacity="0.3" />
          {/* Needle indicator */}
          <circle cx={x} cy={y} r="6" fill="currentColor" className={sentimentToneClass} filter="url(#glow)" />
          <circle cx={x} cy={y} r="3" fill="#fff" />
          <defs>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
        </svg>
        <div className={`sentiment-label ${sentimentToneClass}`}>
          {score > 0 ? "+" : ""}{score.toFixed(0)}
        </div>
      </div>
      <div className={`sentiment-text ${sentimentToneClass}`}>
        {getSentimentEmoji(label)} {label.replace("_", " ")}
      </div>
    </div>
  );
}

function ShimmerCell() {
  return <div className="shimmer shimmer-cell" />;
}

function TreemapCell({
  stock,
  idx,
  onMouseEnter,
  onMouseLeave,
}: {
  stock: HeatStock;
  idx: number;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const sizeClass = stock.market_cap_cr > 1000000
    ? "large-cap"
    : stock.market_cap_cr > 400000
      ? "mid-cap"
      : "";
  const toneClass = getTextToneClass(stock.change_pct);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.background = getBgColor(stock.change_pct);
      ref.current.style.animationDelay = `${idx * 30}ms`;
    }
  }, [idx, stock.change_pct]);

  return (
    <div
      ref={ref}
      className={`treemap-cell fade-in-cell ${sizeClass}`.trim()}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <span className={`treemap-symbol ${toneClass}`}>{stock.symbol}</span>
      <span className={`treemap-change ${toneClass}`}>
        {stock.change_pct > 0 ? "+" : ""}{stock.change_pct.toFixed(2)}%
      </span>
      <span className="treemap-price">₹{stock.last_price.toLocaleString("en-IN")}</span>
      <span className="treemap-sector-tag">{stock.sector}</span>
    </div>
  );
}

/* ── Main Page ─────────────────────────────────────────────── */
export default function SectorHeatmapPage() {
  const [data, setData] = useState<BreadthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredStock, setHoveredStock] = useState<HeatStock | null>(null);
  const [sortBy, setSortBy] = useState<"mcap" | "change">("mcap");
  const [sectorFilter, setSectorFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch("/api/v1/pro/breadth", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          setData(await res.json());
        } else {
          setData(MOCK_DATA);
        }
      } catch {
        setData(MOCK_DATA);
      }
      setLoading(false);
    }
    load();
    const interval = setInterval(load, 60000); // refresh every minute
    return () => clearInterval(interval);
  }, []);

  const sectors = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.heatmap.map((s) => s.sector))].sort();
  }, [data]);

  const filteredStocks = useMemo(() => {
    if (!data) return [];
    let stocks = [...data.heatmap];
    if (sectorFilter !== "all") {
      stocks = stocks.filter((s) => s.sector === sectorFilter);
    }
    if (sortBy === "mcap") {
      stocks.sort((a, b) => b.market_cap_cr - a.market_cap_cr);
    } else {
      stocks.sort((a, b) => b.change_pct - a.change_pct);
    }
    return stocks;
  }, [data, sortBy, sectorFilter]);

  const sectorPerf = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.sector_performance)
      .sort(([, a], [, b]) => b - a);
  }, [data]);

  const maxSectorChange = useMemo(() => {
    return Math.max(...sectorPerf.map(([, v]) => Math.abs(v)), 1);
  }, [sectorPerf]);

  if (loading || !data) {
    return (
      <div className="content">
        <div className="page-header">
          <div>
            <h1 className="page-title">🗺️ Market Heatmap</h1>
            <p className="page-subtitle">Loading market data...</p>
          </div>
        </div>
        <div className="heatmap-treemap heatmap-loading-grid">
          {Array.from({ length: 20 }).map((_, i) => <ShimmerCell key={i} />)}
        </div>
      </div>
    );
  }

  const { breadth, sentiment } = data;
  const totalStocks = breadth.advances + breadth.declines + breadth.unchanged;
  const advPct = totalStocks > 0 ? (breadth.advances / totalStocks) * 100 : 50;
  const decPct = totalStocks > 0 ? (breadth.declines / totalStocks) * 100 : 50;
  const unchangedPct = totalStocks > 0 ? (breadth.unchanged / totalStocks) * 100 : 0;
  const adRatioToneClass = breadth.ad_ratio > 1 ? "tone-green" : "tone-red";
  const sentimentToneClass = getSentimentToneClass(sentiment.score);

  return (
    <div className="content content-animated">
      {/* ── Header ─────────────────────────────────── */}
      <div className="page-header">
        <div>
          <h1 className="page-title page-title-live">
            🗺️ Market Heatmap
            <span className="live-pulse">
              <span className="live-pulse-dot" />
              Live
            </span>
          </h1>
          <p className="page-subtitle">
            NIFTY 50 stocks by market cap — sized proportionally
          </p>
        </div>
        <div className="page-actions">
          <button className={`btn btn-xs${sortBy === "mcap" ? " btn-primary" : ""}`} onClick={() => setSortBy("mcap")}>
            By Market Cap
          </button>
          <button className={`btn btn-xs${sortBy === "change" ? " btn-primary" : ""}`} onClick={() => setSortBy("change")}>
            By Change %
          </button>
        </div>
      </div>

      {/* ── Top Stats ──────────────────────────────── */}
      <div className="grid-4 section-gap">
        <div className="glow-card glow-green">
          <div className="card-title">Advances</div>
          <div className="stat-big tone-green">{breadth.advances}</div>
          <div className="stat-sub">of {totalStocks} stocks</div>
        </div>
        <div className="glow-card glow-red">
          <div className="card-title">Declines</div>
          <div className="stat-big tone-red">{breadth.declines}</div>
          <div className="stat-sub">{breadth.unchanged} unchanged</div>
        </div>
        <div className="glow-card glow-blue">
          <div className="card-title">A/D Ratio</div>
          <div className="stat-big tone-accent">{breadth.ad_ratio.toFixed(2)}</div>
          <div className="stat-sub">{breadth.ad_ratio > 1.5 ? "Strong breadth" : breadth.ad_ratio > 1 ? "Moderate" : "Weak breadth"}</div>
        </div>
        <div className="glow-card glow-amber">
          <div className="card-title">52W Highs / Lows</div>
          <div className="stat-big">
            <span className="tone-green">{breadth.new_52w_highs}</span>
            <span className="tone-muted slash-separator"> / </span>
            <span className="tone-red">{breadth.new_52w_lows}</span>
          </div>
          <div className="stat-sub">Near 52-week extremes</div>
        </div>
      </div>

      {/* ── Breadth Bar ────────────────────────────── */}
      <div className="card section-gap">
        <div className="card-header">
          <div className="card-title">Market Breadth</div>
          <div className="card-meta">
            {breadth.advances}A / {breadth.declines}D / {breadth.unchanged}U
          </div>
        </div>
        <div className="breadth-bar-wrap">
          <DynamicWidthBar className="breadth-advance" width={advPct}>
            {advPct > 10 && `${breadth.advances} ▲`}
          </DynamicWidthBar>
          {breadth.unchanged > 0 && (
            <DynamicWidthBar className="breadth-unchanged" width={unchangedPct} />
          )}
          <DynamicWidthBar className="breadth-decline" width={decPct}>
            {decPct > 10 && `${breadth.declines} ▼`}
          </DynamicWidthBar>
        </div>
      </div>

      {/* ── Sector Filter ──────────────────────────── */}
      <div className="filter-row">
        <button
          className={`btn btn-xs${sectorFilter === "all" ? " btn-primary" : ""}`}
          onClick={() => setSectorFilter("all")}
        >
          All Sectors
        </button>
        {sectors.map((s) => (
          <button
            key={s}
            className={`btn btn-xs${sectorFilter === s ? " btn-primary" : ""}`}
            onClick={() => setSectorFilter(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {/* ── TREEMAP HEATMAP ────────────────────────── */}
      <div className="card treemap-card section-gap">
        <div className="heatmap-treemap">
          {filteredStocks.map((stock, idx) => (
            <TreemapCell
              key={stock.symbol}
              stock={stock}
              idx={idx}
              onMouseEnter={() => setHoveredStock(stock)}
              onMouseLeave={() => setHoveredStock(null)}
            />
          ))}
        </div>
      </div>

      {/* ── Hover tooltip ──────────────────────────── */}
      {hoveredStock && (
        <div className="hover-tooltip">
          <div className="hover-tooltip-title">
            {hoveredStock.symbol}
            <span className={`card-badge ${hoveredStock.change_pct >= 0 ? "badge-green" : "badge-red"}`}>
              {hoveredStock.change_pct >= 0 ? "+" : ""}{hoveredStock.change_pct.toFixed(2)}%
            </span>
          </div>
          <div className="hover-tooltip-meta">
            <span>Price: <strong className="tone-text">₹{hoveredStock.last_price.toLocaleString("en-IN")}</strong></span>
            <span>Sector: <strong className="tone-text">{hoveredStock.sector}</strong></span>
            <span>Market Cap: <strong className="tone-text">{formatMcap(hoveredStock.market_cap_cr)}</strong></span>
          </div>
        </div>
      )}

      {/* ── Bottom Row: Sector Performance + Sentiment ── */}
      <div className="grid-2-1">
        {/* Sector Performance Bars */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Sector Performance</div>
            <div className="card-badge badge-blue">Today</div>
          </div>
          <div>
            {sectorPerf.map(([sector, change]) => (
              <div key={sector} className="sector-bar-row">
                <span className="sector-name">{sector}</span>
                <div className="sector-bar-track">
                  <DynamicWidthBar
                    className={`sector-bar-fill ${change >= 0 ? "positive" : "negative"}`}
                    width={(Math.abs(change) / maxSectorChange) * 100}
                  />
                </div>
                <span className={`sector-bar-value ${change >= 0 ? "tone-green" : "tone-red"}`}>
                  {change >= 0 ? "+" : ""}{change.toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Sentiment Gauge */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Market Sentiment</div>
            <div className="card-badge badge-green">Live</div>
          </div>
          <SentimentGauge score={sentiment.score} label={sentiment.label} />
          <div className="metrics-panel">
            <div className="section-title">Key Metrics</div>
            <div className="metrics-list">
              <div className="setting-row">
                <span>A/D Ratio</span>
                <span className={`mono metric-value ${adRatioToneClass}`}>
                  {breadth.ad_ratio.toFixed(2)}
                </span>
              </div>
              <div className="setting-row">
                <span>52W Highs</span>
                <span className="mono metric-value tone-green">{breadth.new_52w_highs}</span>
              </div>
              <div className="setting-row">
                <span>52W Lows</span>
                <span className="mono metric-value tone-red">{breadth.new_52w_lows}</span>
              </div>
              <div className="setting-row">
                <span>Sentiment Score</span>
                <span className={`mono metric-value ${sentimentToneClass}`}>
                  {sentiment.score > 0 ? "+" : ""}{sentiment.score.toFixed(0)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
