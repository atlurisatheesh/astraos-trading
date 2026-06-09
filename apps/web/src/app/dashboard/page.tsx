"use client";

import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { usePortfolio, useFeed, useSignals, useTicker } from "@/hooks/useWebSocket";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
);

/* ─── Signal fill bar (sets width via ref to avoid inline style) ─── */
function SignalBar({ width, cls }: { width: number; cls: string }) {
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (el) el.style.width = `${width}%`;
  }, [width]);
  return <div className="signal-bar"><div ref={ref} className={`signal-fill ${cls}`} /></div>;
}

/* ─── DATA (exact same data from app.js) ─── */

const SIGNALS = [
  { t: "ICICIBNK", s: 91, a: "BUY", c: "green", msg: "📊 ICICI BANK Signal|BUY · Target ₹1,510 · SL ₹1,400 · Confidence 91%" },
  { t: "TCS", s: 87, a: "BUY", c: "green", msg: "📊 TCS Signal|BUY · Target ₹4,450 · SL ₹3,980 · Confidence 87%" },
  { t: "BAJFIN", s: 82, a: "SELL", c: "red", msg: "📊 BAJFINANCE Signal|SELL · Target ₹6,200 · SL ₹7,050 · Confidence 82%" },
  { t: "WIPRO", s: 71, a: "HOLD", c: "amber", msg: "📊 WIPRO Signal|HOLD · Awaiting breakout confirmation · Confidence 71%" },
  { t: "HDFCBNK", s: 78, a: "BUY", c: "green", msg: "📊 HDFCBANK Signal|BUY · Target ₹1,960 · SL ₹1,820 · Confidence 78%" },
  { t: "NIFTY FO", s: 69, a: "PUT", c: "accent", msg: "📊 NIFTY50 F&O Signal|PUT BUY 24800 · Expiry 27 Mar · Confidence 69%" },
];

const SECTORS = [
  { n: "Banking", c: "+1.84%", cls: "heat-up-strong" },
  { n: "IT", c: "+0.92%", cls: "heat-up" },
  { n: "Energy", c: "-0.64%", cls: "heat-down" },
  { n: "Pharma", c: "+0.38%", cls: "heat-up-light" },
  { n: "Realty", c: "+0.12%", cls: "heat-flat" },
  { n: "Auto", c: "+1.23%", cls: "heat-up-heavy" },
  { n: "FMCG", c: "-0.31%", cls: "heat-down-light" },
  { n: "Infra", c: "+2.10%", cls: "heat-up-max" },
];

const FEED_ITEMS = [
  { t: "13:41", dotCls: "feed-dot-green", label: "AUTO TRADE", txt: "Bought 50 ICICI BANK @ ₹1,435 via Zerodha. SL set ₹1,400." },
  { t: "13:38", dotCls: "feed-dot-accent", label: "PATTERN", txt: "TCS Cup-and-Handle breakout detected. High-confidence BUY setup forming." },
  { t: "13:31", dotCls: "feed-dot-red", label: "RISK ALERT", txt: "BAJFINANCE OI build-up at 6,800 PUT. Bears loading up. Caution advised." },
  { t: "13:20", dotCls: "feed-dot-amber", label: "NEWS", txt: "RBI holds repo rate at 6.5%. Markets relieved — banking sector rally likely to extend." },
  { t: "13:05", dotCls: "feed-dot-green", label: "FII/DII", txt: "FIIs net buyers ₹1,240 Cr. DIIs ₹680 Cr. Broad market sentiment positive." },
  { t: "12:47", dotCls: "feed-dot-purple", label: "AI RESEARCH", txt: "Infra sector deep-dive complete. Top picks: L&T, NTPC, IRFC — 3–6 month horizon." },
  { t: "12:30", dotCls: "feed-dot-red", label: "AUTO TRADE", txt: "Exited WIPRO 100 shares @ ₹489. +₹2,400 profit. 52-day high resistance hit." },
  { t: "11:52", dotCls: "feed-dot-amber", label: "MACRO", txt: "US Fed minutes: no rate cut signal. INR marginally weaker. Gold supportive level." },
];

const POSITIONS = [
  { n: "ICICI BANK", sub: "NSE Delivery", type: "LONG", bc: "badge-green", qty: "50", avg: "₹1,435", ltp: "₹1,436", pnl: "+₹50", cls: "up" },
  { n: "TCS", sub: "NSE Delivery", type: "LONG", bc: "badge-green", qty: "15", avg: "₹4,050", ltp: "₹4,126", pnl: "+₹1,140", cls: "up" },
  { n: "NIFTY 25000 CE", sub: "F&O · Weekly", type: "CALL", bc: "badge-blue", qty: "4 lots", avg: "₹142", ltp: "₹168", pnl: "+₹5,200", cls: "up" },
  { n: "BAJFINANCE", sub: "Futures Short", type: "SHORT", bc: "badge-red", qty: "1 lot", avg: "₹6,900", ltp: "₹6,782", pnl: "+₹4,720", cls: "up" },
];

const OPTIONS = [
  { c: "opt-call opt-itm", oi: "2.4L", vol: "8.2K", iv: "12.1", cltp: "440", strike: "52000", pltp: "12", piv: "14.2", pvol: "1.1K", poi: "0.8L", atm: false },
  { c: "opt-call opt-itm", oi: "3.1L", vol: "12.4K", iv: "13.4", cltp: "295", strike: "52200", pltp: "28", piv: "15.1", pvol: "2.3K", poi: "1.4L", atm: false },
  { c: "opt-call", oi: "4.8L", vol: "22.1K", iv: "14.8", cltp: "168", strike: "52400", pltp: "92", piv: "14.8", pvol: "18.9K", poi: "5.2L", atm: true },
  { c: "opt-put", oi: "2.2L", vol: "9.8K", iv: "15.6", cltp: "78", strike: "52600", pltp: "188", piv: "15.6", pvol: "8.1K", poi: "3.1L", atm: false },
  { c: "opt-put opt-itm", oi: "0.9L", vol: "3.2K", iv: "16.8", cltp: "28", strike: "52800", pltp: "368", piv: "16.8", pvol: "14.2K", poi: "4.6L", atm: false },
];

const RESEARCH = [
  { title: "Banking Sector Deep Dive", time: "2h ago", meta: "AI analyzed 847 data points across 12 public and private sector banks. Bullish outlook driven by credit growth...", tags: [["BULLISH", "badge-green"], ["Banking", "badge-blue"], ["AI Report", "badge-purple"]] },
  { title: "NIFTY Weekly Options Strategy", time: "4h ago", meta: "Expiry analysis for 27 March. Max pain at 24,900. Iron Condor strategy recommended for range-bound conditions...", tags: [["NEUTRAL", "badge-amber"], ["F&O", "badge-blue"], ["Expiry Week", "badge-amber"]] },
  { title: "IT Sector Q4 Earnings Preview", time: "Yesterday", meta: "AI-generated earnings model for top IT companies. TCS, Infosys, Wipro, HCL analyzed with DCF valuations...", tags: [["BULLISH", "badge-green"], ["IT", "badge-blue"], ["Earnings", "badge-blue"]] },
];

const CHAT_RESPONSES: Record<string, string> = {
  intraday: "Top intraday picks for today: 1) ICICI BANK — Buy above ₹1,437, target ₹1,455, SL ₹1,425. 2) TCS — Buy above ₹4,130, target ₹4,165, SL ₹4,100. 3) RELIANCE — Wait for pullback to ₹2,880 before entry.",
  nifty: "Nifty weekly outlook: Bullish bias. Support at 24,600, resistance at 25,100. Expect range 24,700–25,200 this week. Key trigger: FII flow and global cues. AI probability of crossing 25,000: 62%.",
  long: "Best long-term stocks (12–24 month view): 1) HDFC Bank — Buy on dips ₹1,850. 2) L&T — Infrastructure boom play. 3) Sun Pharma — US FDA clearances positive. 4) Tata Motors — EV dominance story intact.",
  risk: "Your portfolio risk analysis: Current beta 0.72 (below market risk). Concentration in Banking: 41% — slightly high, consider diversifying. VaR suggests max single-day loss ₹8,200 at 95% confidence. Recommendation: Add 1 Pharma or FMCG position to hedge.",
  default: "I've analyzed that query using 847 real-time data points across NSE, BSE, and macro indicators. Based on current momentum, technical patterns, and sentiment analysis — the outlook appears positive. Shall I generate a detailed report with entry/exit levels?",
};

/* ─── COMPONENT ─── */

export default function DashboardPage() {
  const [chatMessages, setChatMessages] = useState([
    { text: "Good afternoon. Markets are bullish today with Banking and Infra leading. I've placed 1 auto-trade on ICICI BANK. Your portfolio is up ₹14,680 today. What would you like to analyze?", isUser: false },
    { text: "Should I buy Bank Nifty calls today?", isUser: true },
    { text: 'Based on current OI data, PCR at 0.84 (slightly bearish), and BNifty at 52,318 — the 52,400 CE is the ATM strike with max OI. I see a short-term rally potential to 52,750. Recommended: Buy 52,400 CE @ ₹168 with SL at ₹120 and target ₹240. Position size: 2 lots only given 3-day expiry risk.', isUser: false },
  ]);
  const [chatInput, setChatInput] = useState("");
  const chatRef = useRef<HTMLDivElement>(null);

  // WebSocket connections
  const portfolioWs = usePortfolio();
  const feedWs = useFeed();
  const signalsWs = useSignals();
  const tickerWs = useTicker();

  // Chart Setup
  const chartData = useMemo(() => {
    return {
      labels: ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15", "15:30"],
      datasets: [
        {
          fill: true,
          label: "Portfolio Value",
          data: [500120, 502400, 498000, 505000, 510000, 509000, 514320, 514320],
          borderColor: "rgba(34, 211, 165, 1)",
          backgroundColor: "rgba(34, 211, 165, 0.1)",
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
      ],
    };
  }, []);

  const chartOptions = useMemo(() => {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: "index" as const, intersect: false } },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { color: "rgba(255,255,255,0.4)", font: { size: 10 } } },
        y: { grid: { color: "rgba(255,255,255,0.05)" }, border: { display: false }, ticks: { color: "rgba(255,255,255,0.4)", font: { size: 10 } } },
      },
      interaction: { mode: "nearest" as const, axis: "x" as const, intersect: false },
    };
  }, []);

  // Live signal score updates (exact same logic from app.js)
  const [signalScores, setSignalScores] = useState(SIGNALS.map(s => s.s));
  useEffect(() => {
    const interval = setInterval(() => {
      setSignalScores(prev => prev.map(v => {
        const delta = Math.round((Math.random() - 0.48) * 3);
        return Math.max(50, Math.min(99, v + delta));
      }));
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const sendChat = () => {
    if (!chatInput.trim()) return;
    const msg = chatInput.trim();
    setChatMessages(prev => [...prev, { text: msg, isUser: true }]);
    setChatInput("");
    setTimeout(() => {
      const lower = msg.toLowerCase();
      let resp = CHAT_RESPONSES.default;
      if (lower.includes("intraday") || lower.includes("today")) resp = CHAT_RESPONSES.intraday;
      else if (lower.includes("nifty") || lower.includes("week")) resp = CHAT_RESPONSES.nifty;
      else if (lower.includes("long") || lower.includes("invest")) resp = CHAT_RESPONSES.long;
      else if (lower.includes("risk") || lower.includes("portfolio")) resp = CHAT_RESPONSES.risk;
      setChatMessages(prev => [...prev, { text: resp, isUser: false }]);
      setTimeout(() => chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" }), 50);
    }, 800);
  };

  return (
    <div className="content">
      {/* STAT CARDS */}
      <div className="grid-4">
        <div className="card card-sm">
          <div className="card-header"><div className="card-title">Today&apos;s P&amp;L</div><div className="card-badge badge-green">+Live</div></div>
          <div className={`stat-big ${portfolioWs.data?.day_pnl < 0 ? 'dn' : 'up'}`}>
            {portfolioWs.data?.day_pnl !== undefined ? `${portfolioWs.data.day_pnl >= 0 ? '+' : ''}₹${portfolioWs.data.day_pnl.toLocaleString()}` : "+₹14,680"}
          </div>
          <div className={`stat-change ${portfolioWs.data?.day_pnl_pct < 0 ? 'dn' : 'up'}`}>
            {portfolioWs.data?.day_pnl_pct !== undefined ? `${portfolioWs.data.day_pnl_pct >= 0 ? '▲ +' : '▼ '}${portfolioWs.data.day_pnl_pct.toFixed(2)}% from yesterday` : "▲ +2.94% from yesterday"}
          </div>
          <div className="stat-sub">Realized: ₹9,200 · Unrealized: {portfolioWs.data?.total_pnl !== undefined ? `₹${portfolioWs.data.total_pnl.toLocaleString()}` : "₹5,480"}</div>
        </div>
        <div className="card card-sm">
          <div className="card-header"><div className="card-title">Portfolio Value</div><div className="card-badge badge-blue">{portfolioWs.data?.positions?.length ?? 6} Holdings</div></div>
          <div className="stat-big text-accent">{portfolioWs.data?.capital !== undefined ? `₹${portfolioWs.data.capital.toLocaleString()}` : "₹5,14,320"}</div>
          <div className="stat-change up">▲ +₹42,100 MTD</div>
          <div className="stat-sub">Deployed: {portfolioWs.data?.capital ? Math.round((portfolioWs.data.invested / portfolioWs.data.capital) * 100) : 68}% · Cash: {portfolioWs.data?.capital ? Math.round((portfolioWs.data.available / portfolioWs.data.capital) * 100) : 32}%</div>
        </div>
        <div className="card card-sm">
          <div className="card-header"><div className="card-title">AI Accuracy</div><div className="card-badge badge-purple">30d avg</div></div>
          <div className="stat-big text-purple">84.3%</div>
          <div className="stat-change up">▲ +2.1% vs last month</div>
          <div className="stat-sub">Win Rate · 67 of 79 signals</div>
        </div>
        <div className="card card-sm">
          <div className="card-header"><div className="card-title">Risk Score</div><div className="card-badge badge-amber">Moderate</div></div>
          <div className="stat-big text-amber">34/100</div>
          <div className="stat-change text-muted">Max Drawdown: -3.2%</div>
          <div className="stat-sub">Sharpe: 2.14 · Beta: 0.72</div>
        </div>
      </div>

      {/* CHART + SIGNALS */}
      <div className="grid-2-1">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Portfolio Performance</div>
            <div className="card-actions">
              <div className="tabs tabs-inline">
                <div className="tab active">1D</div>
                <div className="tab">1W</div>
                <div className="tab">1M</div>
                <div className="tab">3M</div>
              </div>
              <div className="card-badge badge-green">+12.4% YTD</div>
            </div>
          </div>
          <div className="chart-wrap">
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Top AI Signals</div><div className="card-badge badge-blue">{signalsWs.history.length > 0 ? signalsWs.history.length : "12"} active</div></div>
          <div>
            {signalsWs.history.length > 0
              ? signalsWs.history.slice().reverse().slice(0, 8).map((wsMsg, i) => {
                  if (!wsMsg.signal) return null;
                  const s = wsMsg.signal;
                  const actionCls = s.action === "SELL" ? "sell-action" : s.action === "HOLD" ? "hold-action" : "buy-action";
                  const scoreCls = s.action === "SELL" ? "dn" : s.action === "BUY" ? "up" : s.action === "HOLD" ? "text-amber" : "";
                  const fillCls = s.action === "SELL" ? "signal-fill-red" : s.action === "BUY" ? "signal-fill-green" : "signal-fill-amber";
                  return (
                    <div className="signal-row" key={i}>
                      <div className="signal-ticker">{s.symbol}</div>
                      <SignalBar width={s.confidence} cls={fillCls} />
                      <div className={`signal-score ${scoreCls}`}>{s.confidence}</div>
                      <div className={`signal-action ${actionCls}`}>{s.action}</div>
                    </div>
                  );
                })
              : SIGNALS.map((s, i) => {
                  const actionCls = s.a === "SELL" ? "sell-action" : s.a === "HOLD" ? "hold-action" : "buy-action";
                  const scoreCls = s.c === "red" ? "dn" : s.c === "green" ? "up" : s.c === "amber" ? "text-amber" : s.c === "accent" ? "text-accent" : "";
                  const fillCls = s.c === "red" ? "signal-fill-red" : s.c === "green" ? "signal-fill-green" : s.c === "amber" ? "signal-fill-amber" : "signal-fill-accent";
                  return (
                    <div className="signal-row" key={`static-${i}`}>
                      <div className="signal-ticker">{s.t}</div>
                      <SignalBar width={signalScores[i]} cls={fillCls} />
                      <div className={`signal-score ${scoreCls}`}>{signalScores[i]}</div>
                      <div className={`signal-action ${actionCls}`}>{s.a}</div>
                    </div>
                  );
                })}
          </div>
        </div>
      </div>

      {/* SECTOR + LIVE FEED */}
      <div className="grid-1-1">
        <div className="card">
          <div className="card-header"><div className="card-title">Sector Heatmap</div><div className="card-badge badge-blue">NSE · Live</div></div>
          <div className="heatmap">
            {SECTORS.map((s, i) => (
              <div key={i} className={`heat-cell ${s.cls}`}>
                <div className="heat-name">{s.n}</div>
                <div className="heat-chg">{s.c}</div>
              </div>
            ))}
          </div>
          <div className="mt-14">
            <div className="prediction-grid">
              <div className="pred-item"><div className="pred-horizon">Nifty 1D</div><div className="pred-val up">24,960</div><div className="pred-conf">Conf: 78%</div></div>
              <div className="pred-item"><div className="pred-horizon">Nifty 1W</div><div className="pred-val up">25,280</div><div className="pred-conf">Conf: 64%</div></div>
              <div className="pred-item"><div className="pred-horizon">BNifty 1D</div><div className="pred-val up">52,750</div><div className="pred-conf">Conf: 72%</div></div>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Live Intelligence Feed</div><div className="card-badge badge-amber">Real-time</div></div>
          <div className="card-scroll">
            {feedWs.history.length > 0 
              ? feedWs.history.slice().reverse().slice(0, 15).map((f, i) => {
                  const dotClsMap: Record<string, string> = { "news": "feed-dot-amber", "signal": "feed-dot-accent", "order": "feed-dot-green", "risk": "feed-dot-red", "system": "feed-dot-purple" };
                  return (
                    <div className="feed-item" key={i}>
                      <div className={`feed-dot ${dotClsMap[f.type] || "feed-dot-green"}`} />
                      <div className="feed-time">{new Date(f.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                      <div className="feed-text"><strong>{f.type.toUpperCase()}</strong> · {f.message}</div>
                    </div>
                  );
                })
              : FEED_ITEMS.map((f, i) => (
                  <div className="feed-item" key={i}>
                    <div className={`feed-dot ${f.dotCls}`} />
                    <div className="feed-time">{f.t}</div>
                    <div className="feed-text"><strong>{f.label}</strong> · {f.txt}</div>
                  </div>
                ))
            }
          </div>
        </div>
      </div>

      {/* POSITIONS + RISK */}
      <div className="grid-2-1">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Open Positions</div>
            <div className="flex-row-sm"><div className="card-badge badge-green">3 Long</div><div className="card-badge badge-red">1 Short</div></div>
          </div>
          <table className="pos-table">
            <thead><tr><th>Stock</th><th>Type</th><th>Qty</th><th>Avg Cost</th><th>LTP</th><th>P&amp;L</th><th>Action</th></tr></thead>
            <tbody>
              {portfolioWs.data?.positions?.length > 0
                ? portfolioWs.data.positions.map((r: any, i: number) => (
                    <tr key={i}>
                      <td><div className="pos-name">{r.symbol}</div><div className="pos-type">EQ Delivery</div></td>
                      <td><span className={`card-badge ${r.qty > 0 ? 'badge-green' : 'badge-red'}`}>{r.qty > 0 ? 'LONG' : 'SHORT'}</span></td>
                      <td className="mono">{Math.abs(r.qty)}</td>
                      <td className="mono">₹{r.avg.toFixed(2)}</td>
                      <td className="mono">₹{r.ltp.toFixed(2)}</td>
                      <td className={`${r.pnl >= 0 ? "up" : "dn"} mono`}>
                        {r.pnl >= 0 ? "+" : ""}₹{r.pnl.toFixed(2)}
                      </td>
                      <td><button className="btn btn-xs">Exit</button></td>
                    </tr>
                  ))
                : POSITIONS.map((r, i) => (
                    <tr key={i}>
                      <td><div className="pos-name">{r.n}</div><div className="pos-type">{r.sub}</div></td>
                      <td><span className={`card-badge ${r.bc}`}>{r.type}</span></td>
                      <td className="mono">{r.qty}</td>
                      <td className="mono">{r.avg}</td>
                      <td className="mono">{r.ltp}</td>
                      <td className={`${r.cls} mono`}>{r.pnl}</td>
                      <td><button className="btn btn-xs">Exit</button></td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Risk Dashboard</div><div className="card-badge badge-green">Safe Zone</div></div>
          <div className="mb-16">
            <div className="risk-meter-wrap"><div className="risk-label"><span>Capital Risk</span><span className="up">12%</span></div><div className="risk-track"><div className="risk-fill risk-fill-green" /></div></div>
            <div className="risk-meter-wrap"><div className="risk-label"><span>Portfolio Beta</span><span className="text-accent">0.72</span></div><div className="risk-track"><div className="risk-fill risk-fill-beta" /></div></div>
            <div className="risk-meter-wrap"><div className="risk-label"><span>VaR (95%)</span><span className="text-amber">₹8,200</span></div><div className="risk-track"><div className="risk-fill risk-fill-var" /></div></div>
            <div className="risk-meter-wrap"><div className="risk-label"><span>Max Drawdown</span><span className="dn">-3.2%</span></div><div className="risk-track"><div className="risk-fill risk-fill-dd" /></div></div>
            <div className="risk-meter-wrap"><div className="risk-label"><span>Concentration</span><span className="text-amber">41%</span></div><div className="risk-track"><div className="risk-fill risk-fill-conc" /></div></div>
          </div>
          <div className="grid-2">
            <div className="pred-item"><div className="pred-horizon">Sharpe Ratio</div><div className="pred-val up">2.14</div></div>
            <div className="pred-item"><div className="pred-horizon">Sortino</div><div className="pred-val up">3.07</div></div>
          </div>
          <div className="mt-14">
            <div className="section-title">Auto-Trade Settings</div>
            <div className="settings-list">
              <label className="setting-row">Auto Buy <input type="checkbox" defaultChecked className="accent-check" /></label>
              <label className="setting-row">Auto Sell <input type="checkbox" defaultChecked className="accent-check" /></label>
              <label className="setting-row">Max daily loss limit <span className="mono text-primary">₹15,000</span></label>
              <label className="setting-row">Max position size <span className="mono text-primary">₹50,000</span></label>
            </div>
          </div>
        </div>
      </div>

      {/* OPTIONS + CHAT */}
      <div className="grid-1-1">
        <div className="card">
          <div className="card-header"><div className="card-title">F&amp;O Options Chain — BANKNIFTY</div><div className="card-badge badge-blue">Expiry: 27 Mar</div></div>
          <div className="overflow-x">
            <table className="opt-table">
              <thead>
                <tr>
                  <th colSpan={4} className="th-calls">CALLS</th>
                  <th className="opt-strike">STRIKE</th>
                  <th colSpan={4} className="th-puts">PUTS</th>
                </tr>
                <tr><th>OI</th><th>Vol</th><th>IV%</th><th>LTP</th><th></th><th>LTP</th><th>IV%</th><th>Vol</th><th>OI</th></tr>
              </thead>
              <tbody>
                {OPTIONS.map((r, i) => (
                  <tr key={i} className={`${r.c}${r.atm ? " opt-atm-row" : ""}`}>
                    <td>{r.oi}</td><td>{r.vol}</td><td>{r.iv}</td><td className="up">{r.cltp}</td>
                    <td className={`opt-strike${r.atm ? " opt-atm-strike" : ""}`}>{r.strike}</td>
                    <td className="dn">{r.pltp}</td><td>{r.piv}</td><td>{r.pvol}</td><td>{r.poi}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="opt-meta">
            <span>PCR: <strong className="text-amber">0.84</strong></span><span>·</span>
            <span>Max Pain: <strong className="text-primary">52,400</strong></span><span>·</span>
            <span>IV Rank: <strong className="text-green">32</strong></span><span>·</span>
            <span>Expiry: <strong className="text-primary">3 days</strong></span>
          </div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">AI Analyst — Ask Anything</div><div className="card-badge badge-purple">GPT-4 Powered</div></div>
          <div className="ai-chat">
            <div className="chat-messages" ref={chatRef}>
              {chatMessages.map((m, i) => (
                <div key={i} className={`chat-msg${m.isUser ? " user" : ""}`}>
                  <div className={m.isUser ? "chat-avatar user-avatar" : "chat-avatar ai-avatar"}>{m.isUser ? "U" : "Q"}</div>
                  <div className="chat-bubble">{m.text}</div>
                </div>
              ))}
            </div>
            <div className="chat-input-row">
              <input className="chat-input" type="text" placeholder="Ask about any stock, F&O strategy, sector..." value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendChat()} />
              <button className="chat-send" onClick={sendChat}>Ask</button>
            </div>
          </div>
          <div className="chat-suggestions">
            <button className="btn btn-xs" onClick={() => { setChatInput("Best intraday picks today?"); setTimeout(sendChat, 50); }}>Intraday picks</button>
            <button className="btn btn-xs" onClick={() => { setChatInput("Nifty prediction for this week?"); setTimeout(sendChat, 50); }}>Nifty outlook</button>
            <button className="btn btn-xs" onClick={() => { setChatInput("Best long-term stocks to buy now?"); setTimeout(sendChat, 50); }}>Long-term buys</button>
            <button className="btn btn-xs" onClick={() => { setChatInput("Analyze my portfolio risk"); setTimeout(sendChat, 50); }}>Portfolio risk</button>
          </div>
        </div>
      </div>

      {/* DEEP RESEARCH REPORTS */}
      <div className="card mb-20">
        <div className="card-header"><div className="card-title">Deep Research Reports — AI Generated</div><div className="card-badge badge-purple">AI Analyst · Live</div></div>
        <div className="research-grid">
          {RESEARCH.map((item, i) => (
            <div key={i} className="research-item research-card">
              <div className="research-header"><div className="research-title">{item.title}</div><div className="research-time">{item.time}</div></div>
              <div className="research-meta">{item.meta}</div>
              <div className="research-tags">
                {item.tags.map(([label, cls], j) => (
                  <span key={j} className={`tag ${cls}`}>{label}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
