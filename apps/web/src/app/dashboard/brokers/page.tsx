"use client";

import { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const SUPPORTED_BROKERS = [
  { id: "angel", name: "Angel One", tags: "SmartAPI · Equity & F&O · Real-time", color: "#22d3a5", requiresApiKey: true },
  { id: "kite", name: "Zerodha Kite", tags: "KiteConnect API · Requires App", color: "#e65100", requiresApiKey: true },
  { id: "upstox", name: "Upstox", tags: "Upstox API v2 · Equity & F&O", color: "#673ab7", requiresApiKey: true },
  { id: "fyers", name: "Fyers", tags: "Fyers APIv3 · Lightning Fast", color: "#f48fb1", requiresApiKey: true },
  { id: "5paisa", name: "5Paisa", tags: "py5paisa SDK · Margin Trading", color: "#00e676", requiresApiKey: true },
  { id: "groww", name: "Groww", tags: "REST API · Mutual Funds & Equity", color: "#00bfa5", requiresApiKey: false },
  { id: "paper", name: "Paper Trading", tags: "Built-in Simulator · Zero Risk", color: "#29b6f6", requiresApiKey: false },
];

interface BrokerSession {
  broker: string;
  name: string;
  color: string;
  profile?: { name?: string; email?: string; client_id?: string };
  portfolio?: PortfolioData;
  lastSync?: string;
  error?: string;
}

interface Position {
  tradingsymbol?: string; symbol?: string;
  exchange?: string;
  side?: string;
  netqty?: number; quantity?: number;
  buyavgprice?: number; averagePrice?: number; avg_price?: number;
  ltp?: number; lastPrice?: number;
  pnl?: number; unrealisedpnl?: number;
  producttype?: string; product?: string;
}

interface Holding {
  tradingsymbol?: string; symbol?: string;
  exchange?: string;
  quantity?: number;
  averageprice?: number; averagePrice?: number; avg_price?: number;
  ltp?: number; lastPrice?: number;
  profitandloss?: number; pnl?: number;
  pnl_pct?: number;
}

interface PortfolioData {
  positions: Position[];
  holdings: Holding[];
  funds: {
    availablecash?: number; net?: number;
    available?: number; total?: number;
    utiliseddebits?: number; used?: number;
    m2munrealized?: number;
  };
  day_pnl: number;
  total_pnl: number;
  net_value: number;
}

function authHeaders() {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function fetchBrokerData(brokerId: string): Promise<PortfolioData> {
  const [posRes, holdRes, fundRes] = await Promise.all([
    fetch(`${API_BASE}/api/v1/broker/positions/${brokerId}`, { headers: authHeaders() }),
    fetch(`${API_BASE}/api/v1/broker/holdings/${brokerId}`, { headers: authHeaders() }),
    fetch(`${API_BASE}/api/v1/broker/funds/${brokerId}`, { headers: authHeaders() }),
  ]);

  const posData = posRes.ok ? await posRes.json() : {};
  const holdData = holdRes.ok ? await holdRes.json() : {};
  const fundData = fundRes.ok ? await fundRes.json() : {};

  const positions: Position[] = posData.positions || [];
  const holdings: Holding[] = holdData.holdings || [];
  const funds = fundData.data || fundData || {};

  // Calculate P&L
  const day_pnl = positions.reduce((s: number, p: Position) =>
    s + (p.pnl || p.unrealisedpnl || 0), 0);
  const total_pnl = holdings.reduce((s: number, h: Holding) =>
    s + (h.profitandloss || h.pnl || 0), 0) + day_pnl;
  const net_value = (funds.availablecash || funds.available || funds.net || funds.total || 0) +
    holdings.reduce((s: number, h: Holding) =>
      s + ((h.quantity || 0) * (h.ltp || h.lastPrice || h.averageprice || h.averagePrice || 0)), 0);

  return { positions, holdings, funds, day_pnl, total_pnl, net_value };
}

export default function BrokersPage() {
  const [activeModalBroker, setActiveModalBroker] = useState<typeof SUPPORTED_BROKERS[0] | null>(null);
  const [formData, setFormData] = useState({ apiKey: "", clientId: "", password: "", totpSecret: "" });
  const [connectStatus, setConnectStatus] = useState<"idle" | "connecting" | "success" | "error">("idle");
  const [connectError, setConnectError] = useState("");
  const [sessions, setSessions] = useState<Record<string, BrokerSession>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<"connect" | "monitor">("connect");
  const [activeBroker, setActiveBroker] = useState<string>("angel");

  // Fetch active sessions on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/broker/active`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.sessions) {
          const map: Record<string, BrokerSession> = {};
          data.sessions.forEach((s: any) => {
            const info = SUPPORTED_BROKERS.find(b => b.id === s.broker);
            if (s.logged_in && info) {
              map[s.broker] = { broker: s.broker, name: info.name, color: info.color };
            }
          });
          setSessions(map);
          if (Object.keys(map).length > 0) setActiveTab("monitor");
        }
      }).catch(() => {});
  }, []);

  const refreshPortfolio = useCallback(async (brokerId: string) => {
    setLoading(l => ({ ...l, [brokerId]: true }));
    try {
      const portfolio = await fetchBrokerData(brokerId);
      setSessions(prev => ({
        ...prev,
        [brokerId]: { ...prev[brokerId], portfolio, lastSync: new Date().toLocaleTimeString(), error: undefined },
      }));
    } catch (e: any) {
      setSessions(prev => ({
        ...prev,
        [brokerId]: { ...prev[brokerId], error: e.message, lastSync: new Date().toLocaleTimeString() },
      }));
    } finally {
      setLoading(l => ({ ...l, [brokerId]: false }));
    }
  }, []);

  // Auto-refresh every 30s for connected brokers
  useEffect(() => {
    const ids = Object.keys(sessions);
    if (!ids.length) return;
    ids.forEach(id => refreshPortfolio(id));
    const timer = setInterval(() => ids.forEach(id => refreshPortfolio(id)), 30000);
    return () => clearInterval(timer);
  }, [Object.keys(sessions).join(","), refreshPortfolio]);

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeModalBroker) return;
    setConnectStatus("connecting");
    setConnectError("");

    try {
      const res = await fetch(`${API_BASE}/api/v1/broker/login`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          broker: activeModalBroker.id,
          api_key: formData.apiKey,
          client_id: formData.clientId,
          password: formData.password,
          totp_secret: formData.totpSecret,
          pin: formData.password,
        }),
      });
      const data = await res.json();

      if (data.status === "success" || data.status === "paper") {
        setConnectStatus("success");
        const session: BrokerSession = {
          broker: activeModalBroker.id,
          name: activeModalBroker.name,
          color: activeModalBroker.color,
          profile: {
            name: data.name || data.client_name,
            email: data.email,
            client_id: formData.clientId,
          },
        };
        setSessions(prev => ({ ...prev, [activeModalBroker.id]: session }));
        setTimeout(() => {
          setActiveModalBroker(null);
          setConnectStatus("idle");
          setActiveTab("monitor");
          setActiveBroker(activeModalBroker.id);
          refreshPortfolio(activeModalBroker.id);
        }, 1200);
      } else {
        setConnectStatus("error");
        setConnectError(data.message || data.detail || "Connection failed");
      }
    } catch (err: any) {
      setConnectStatus("error");
      setConnectError(err.message || "Network error");
    }
  };

  const handleDisconnect = async (brokerId: string) => {
    await fetch(`${API_BASE}/api/v1/broker/logout/${brokerId}`, {
      method: "POST", headers: authHeaders(),
    }).catch(() => {});
    setSessions(prev => {
      const n = { ...prev }; delete n[brokerId]; return n;
    });
  };

  const fmt = (n: number) => new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n || 0);
  const fmtCr = (n: number) => {
    if (Math.abs(n) >= 10000000) return `₹${(n / 10000000).toFixed(2)} Cr`;
    if (Math.abs(n) >= 100000) return `₹${(n / 100000).toFixed(2)} L`;
    return `₹${fmt(n)}`;
  };

  const activeSess = sessions[activeBroker];
  const portfolio = activeSess?.portfolio;

  return (
    <div className="content">
      {/* TAB BAR */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.75rem" }}>
        <button
          onClick={() => setActiveTab("connect")}
          style={{
            background: activeTab === "connect" ? "rgba(34,211,165,0.15)" : "transparent",
            border: activeTab === "connect" ? "1px solid rgba(34,211,165,0.4)" : "1px solid transparent",
            color: activeTab === "connect" ? "#22d3a5" : "rgba(255,255,255,0.5)",
            padding: "0.4rem 1rem", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem",
          }}
        >Broker Connections</button>
        <button
          onClick={() => setActiveTab("monitor")}
          style={{
            background: activeTab === "monitor" ? "rgba(34,211,165,0.15)" : "transparent",
            border: activeTab === "monitor" ? "1px solid rgba(34,211,165,0.4)" : "1px solid transparent",
            color: activeTab === "monitor" ? "#22d3a5" : "rgba(255,255,255,0.5)",
            padding: "0.4rem 1rem", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem",
          }}
        >
          Live Monitor {Object.keys(sessions).length > 0 && <span style={{ marginLeft: "0.4rem", background: "#22d3a5", color: "#000", borderRadius: "10px", padding: "0 6px", fontSize: "0.75rem" }}>{Object.keys(sessions).length}</span>}
        </button>
      </div>

      {/* CONNECT TAB */}
      {activeTab === "connect" && (
        <div className="grid-1-1">
          {/* Connected Brokers */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Connected Accounts</div>
              <div className={`card-badge ${Object.keys(sessions).length ? "badge-green" : "badge-dim"}`}>
                {Object.keys(sessions).length ? "Live" : "None Connected"}
              </div>
            </div>
            <div style={{ marginTop: "1rem" }}>
              {Object.values(sessions).length > 0 ? Object.values(sessions).map(s => (
                <div key={s.broker} style={{
                  border: `1px solid ${s.color}30`,
                  borderRadius: "8px", padding: "1rem", marginBottom: "0.75rem",
                  background: `${s.color}08`,
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                      <div style={{ width: 10, height: 10, borderRadius: "50%", background: s.color, boxShadow: `0 0 6px ${s.color}` }} />
                      <span style={{ color: s.color, fontWeight: 600 }}>{s.name}</span>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <span className="tag badge-green" style={{ fontSize: "0.75rem" }}>● Active</span>
                      <button onClick={() => { setActiveTab("monitor"); setActiveBroker(s.broker); }}
                        style={{ background: "rgba(34,211,165,0.15)", border: "1px solid rgba(34,211,165,0.3)", color: "#22d3a5", padding: "0.25rem 0.6rem", borderRadius: "4px", cursor: "pointer", fontSize: "0.8rem" }}>
                        Monitor
                      </button>
                      <button onClick={() => handleDisconnect(s.broker)}
                        style={{ background: "rgba(255,70,70,0.1)", border: "1px solid rgba(255,70,70,0.3)", color: "#ff6b6b", padding: "0.25rem 0.6rem", borderRadius: "4px", cursor: "pointer", fontSize: "0.8rem" }}>
                        Disconnect
                      </button>
                    </div>
                  </div>
                  {s.profile?.name && (
                    <div style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>
                      {s.profile.name} · {s.profile.client_id || s.profile.email || ""}
                    </div>
                  )}
                </div>
              )) : (
                <div style={{ textAlign: "center", padding: "2rem", color: "rgba(255,255,255,0.3)", border: "1px dashed rgba(255,255,255,0.08)", borderRadius: "8px" }}>
                  No brokers connected. Connect Angel One below.
                </div>
              )}
            </div>
          </div>

          {/* Available Brokers */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Available Integrations</div>
              <div className="card-badge badge-blue">7 Brokers Supported</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1rem", maxHeight: "60vh", overflowY: "auto", paddingRight: "0.25rem" }}>
              {SUPPORTED_BROKERS.map(b => {
                const connected = !!sessions[b.id];
                return (
                  <div key={b.id} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "0.75rem 1rem", borderRadius: "8px",
                    border: connected ? `1px solid ${b.color}50` : "1px solid rgba(255,255,255,0.06)",
                    background: connected ? `${b.color}08` : "rgba(255,255,255,0.02)",
                  }}>
                    <div>
                      <div style={{ fontWeight: 600, color: connected ? b.color : "#fff", fontSize: "0.95rem" }}>{b.name}</div>
                      <div style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.45)", marginTop: "0.2rem" }}>{b.tags}</div>
                    </div>
                    <button
                      disabled={connected}
                      onClick={() => { setActiveModalBroker(b); setFormData({ apiKey: "", clientId: "", password: "", totpSecret: "" }); setConnectStatus("idle"); setConnectError(""); }}
                      style={{
                        padding: "0.35rem 0.9rem", borderRadius: "6px", fontSize: "0.85rem",
                        cursor: connected ? "default" : "pointer",
                        background: connected ? "rgba(34,211,165,0.15)" : b.id === "angel" ? "rgba(34,211,165,0.2)" : "rgba(255,255,255,0.08)",
                        border: connected ? `1px solid ${b.color}50` : b.id === "angel" ? "1px solid rgba(34,211,165,0.5)" : "1px solid rgba(255,255,255,0.1)",
                        color: connected ? b.color : b.id === "angel" ? "#22d3a5" : "#fff",
                      }}
                    >
                      {connected ? "✓ Connected" : "Connect"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* MONITOR TAB */}
      {activeTab === "monitor" && (
        <div>
          {/* Broker selector */}
          {Object.keys(sessions).length > 1 && (
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
              {Object.values(sessions).map(s => (
                <button key={s.broker} onClick={() => setActiveBroker(s.broker)} style={{
                  padding: "0.35rem 0.9rem", borderRadius: "6px", fontSize: "0.85rem",
                  background: activeBroker === s.broker ? `${s.color}20` : "rgba(255,255,255,0.05)",
                  border: activeBroker === s.broker ? `1px solid ${s.color}60` : "1px solid rgba(255,255,255,0.08)",
                  color: activeBroker === s.broker ? s.color : "#fff",
                  cursor: "pointer",
                }}>
                  {s.name}
                </button>
              ))}
            </div>
          )}

          {!activeSess ? (
            <div style={{ textAlign: "center", padding: "4rem", color: "rgba(255,255,255,0.4)" }}>
              <div style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>No broker connected</div>
              <button onClick={() => setActiveTab("connect")} style={{ background: "rgba(34,211,165,0.2)", border: "1px solid rgba(34,211,165,0.4)", color: "#22d3a5", padding: "0.5rem 1.5rem", borderRadius: "6px", cursor: "pointer" }}>
                Connect Angel One
              </button>
            </div>
          ) : (
            <>
              {/* Header + refresh */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.8rem" }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: activeSess.color, boxShadow: `0 0 8px ${activeSess.color}` }} />
                  <span style={{ fontSize: "1.1rem", fontWeight: 700, color: activeSess.color }}>{activeSess.name} — Live Monitor</span>
                  {activeSess.profile?.name && <span style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)" }}>· {activeSess.profile.name}</span>}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  {activeSess.lastSync && <span style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.35)" }}>Last sync: {activeSess.lastSync}</span>}
                  <button
                    onClick={() => refreshPortfolio(activeSess.broker)}
                    disabled={loading[activeSess.broker]}
                    style={{ background: "rgba(34,211,165,0.15)", border: "1px solid rgba(34,211,165,0.3)", color: "#22d3a5", padding: "0.35rem 0.9rem", borderRadius: "6px", cursor: "pointer", fontSize: "0.85rem" }}
                  >
                    {loading[activeSess.broker] ? "Refreshing…" : "↻ Refresh"}
                  </button>
                </div>
              </div>

              {activeSess.error && (
                <div style={{ background: "rgba(255,70,70,0.1)", border: "1px solid rgba(255,70,70,0.3)", borderRadius: "8px", padding: "0.75rem 1rem", marginBottom: "1rem", color: "#ff6b6b", fontSize: "0.9rem" }}>
                  ⚠ {activeSess.error}
                </div>
              )}

              {/* Summary Cards */}
              {portfolio && (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
                    {[
                      { label: "Available Funds", value: fmtCr(portfolio.funds?.availablecash || portfolio.funds?.available || portfolio.funds?.net || portfolio.funds?.total || 0), color: "#22d3a5" },
                      { label: "Net Portfolio Value", value: fmtCr(portfolio.net_value), color: "#60a5fa" },
                      { label: "Day P&L", value: `${portfolio.day_pnl >= 0 ? "+" : ""}${fmtCr(portfolio.day_pnl)}`, color: portfolio.day_pnl >= 0 ? "#4ade80" : "#f87171" },
                      { label: "Overall P&L", value: `${portfolio.total_pnl >= 0 ? "+" : ""}${fmtCr(portfolio.total_pnl)}`, color: portfolio.total_pnl >= 0 ? "#4ade80" : "#f87171" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="card" style={{ textAlign: "center", border: `1px solid ${color}20` }}>
                        <div style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.5)", marginBottom: "0.4rem" }}>{label}</div>
                        <div style={{ fontSize: "1.4rem", fontWeight: 700, color }}>{value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Positions */}
                  <div className="card" style={{ marginBottom: "1.25rem" }}>
                    <div className="card-header">
                      <div className="card-title">Open Positions ({portfolio.positions.length})</div>
                      <div className="card-badge badge-blue">Intraday / F&O</div>
                    </div>
                    {portfolio.positions.length === 0 ? (
                      <div style={{ padding: "1.5rem", textAlign: "center", color: "rgba(255,255,255,0.35)", fontSize: "0.9rem" }}>No open positions</div>
                    ) : (
                      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "0.75rem" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", fontSize: "0.78rem", color: "rgba(255,255,255,0.45)" }}>
                            <th style={{ textAlign: "left", padding: "0.4rem 0.5rem" }}>Symbol</th>
                            <th style={{ textAlign: "center", padding: "0.4rem 0.5rem" }}>Qty</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>Avg Cost</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>LTP</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>P&L</th>
                            <th style={{ textAlign: "center", padding: "0.4rem 0.5rem" }}>Product</th>
                          </tr>
                        </thead>
                        <tbody>
                          {portfolio.positions.map((p, i) => {
                            const sym = p.tradingsymbol || p.symbol || "-";
                            const rawQty = p.netqty ?? p.quantity ?? 0;
                            const qty = p.side === "SELL" ? -Math.abs(rawQty) : rawQty;
                            const avg = p.buyavgprice || p.averagePrice || p.avg_price || 0;
                            const ltp = p.ltp || p.lastPrice || 0;
                            const pnl = p.pnl || p.unrealisedpnl || 0;
                            return (
                              <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.88rem" }}>
                                <td style={{ padding: "0.5rem", fontWeight: 600, color: "#fff" }}>{sym}</td>
                                <td style={{ padding: "0.5rem", textAlign: "center", color: qty >= 0 ? "#4ade80" : "#f87171" }}>{qty > 0 ? "+" : ""}{qty}</td>
                                <td style={{ padding: "0.5rem", textAlign: "right", color: "rgba(255,255,255,0.7)" }}>₹{fmt(avg)}</td>
                                <td style={{ padding: "0.5rem", textAlign: "right", color: "#60a5fa" }}>₹{fmt(ltp)}</td>
                                <td style={{ padding: "0.5rem", textAlign: "right", fontWeight: 600, color: pnl >= 0 ? "#4ade80" : "#f87171" }}>
                                  {pnl >= 0 ? "+" : ""}₹{fmt(pnl)}
                                </td>
                                <td style={{ padding: "0.5rem", textAlign: "center" }}>
                                  <span className="tag" style={{ fontSize: "0.72rem" }}>{p.producttype || p.product || "MIS"}</span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>

                  {/* Holdings */}
                  <div className="card">
                    <div className="card-header">
                      <div className="card-title">Holdings ({portfolio.holdings.length})</div>
                      <div className="card-badge badge-green">Long-term Portfolio</div>
                    </div>
                    {portfolio.holdings.length === 0 ? (
                      <div style={{ padding: "1.5rem", textAlign: "center", color: "rgba(255,255,255,0.35)", fontSize: "0.9rem" }}>No holdings</div>
                    ) : (
                      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "0.75rem" }}>
                        <thead>
                          <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", fontSize: "0.78rem", color: "rgba(255,255,255,0.45)" }}>
                            <th style={{ textAlign: "left", padding: "0.4rem 0.5rem" }}>Symbol</th>
                            <th style={{ textAlign: "center", padding: "0.4rem 0.5rem" }}>Qty</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>Avg Price</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>LTP</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>P&L</th>
                            <th style={{ textAlign: "right", padding: "0.4rem 0.5rem" }}>Current Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {portfolio.holdings.map((h, i) => {
                            const sym = h.tradingsymbol || h.symbol || "-";
                            const qty = h.quantity || 0;
                            const avg = h.averageprice || h.averagePrice || h.avg_price || 0;
                            const ltp = h.ltp || h.lastPrice || 0;
                            const pnl = h.profitandloss || h.pnl || 0;
                            const value = qty * ltp;
                            return (
                              <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.88rem" }}>
                                <td style={{ padding: "0.5rem", fontWeight: 600, color: "#fff" }}>{sym}</td>
                                <td style={{ padding: "0.5rem", textAlign: "center" }}>{qty}</td>
                                <td style={{ padding: "0.5rem", textAlign: "right", color: "rgba(255,255,255,0.7)" }}>₹{fmt(avg)}</td>
                                <td style={{ padding: "0.5rem", textAlign: "right", color: "#60a5fa" }}>₹{fmt(ltp)}</td>
                                <td style={{ padding: "0.5rem", textAlign: "right", fontWeight: 600, color: pnl >= 0 ? "#4ade80" : "#f87171" }}>
                                  {pnl >= 0 ? "+" : ""}₹{fmt(pnl)}
                                </td>
                                <td style={{ padding: "0.5rem", textAlign: "right", color: "rgba(255,255,255,0.8)" }}>₹{fmt(value)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                </>
              )}

              {!portfolio && !loading[activeSess.broker] && (
                <div style={{ textAlign: "center", padding: "3rem", color: "rgba(255,255,255,0.4)" }}>
                  <div style={{ marginBottom: "1rem" }}>Portfolio data not loaded yet</div>
                  <button onClick={() => refreshPortfolio(activeSess.broker)} style={{ background: "rgba(34,211,165,0.2)", border: "1px solid rgba(34,211,165,0.4)", color: "#22d3a5", padding: "0.5rem 1.5rem", borderRadius: "6px", cursor: "pointer" }}>
                    Load Portfolio
                  </button>
                </div>
              )}

              {loading[activeSess.broker] && (
                <div style={{ textAlign: "center", padding: "3rem", color: "rgba(255,255,255,0.4)" }}>
                  Fetching live data from {activeSess.name}…
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* CONNECTION MODAL */}
      {activeModalBroker && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)",
          zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(12px)",
        }}>
          <div className="card" style={{ width: "100%", maxWidth: "500px", border: `1px solid ${activeModalBroker.color}30`, background: "#080b10", maxHeight: "90vh", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", borderBottom: `1px solid ${activeModalBroker.color}25`, paddingBottom: "1rem" }}>
              <div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: activeModalBroker.color, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: activeModalBroker.color }} />
                  Connect {activeModalBroker.name}
                </div>
                <div style={{ fontSize: "0.82rem", color: "rgba(255,255,255,0.4)", marginTop: "0.25rem" }}>{activeModalBroker.tags}</div>
              </div>
              <button onClick={() => setActiveModalBroker(null)} style={{ background: "none", border: "none", color: "#666", cursor: "pointer", fontSize: "1.5rem", lineHeight: 1 }}>×</button>
            </div>

            <form onSubmit={handleConnect}>
              {/* Angel One specific fields */}
              {activeModalBroker.id === "angel" && (
                <div style={{ background: "rgba(34,211,165,0.06)", border: "1px solid rgba(34,211,165,0.15)", borderRadius: "8px", padding: "0.75rem 1rem", marginBottom: "1.25rem", fontSize: "0.82rem", color: "rgba(34,211,165,0.8)" }}>
                  <strong>Angel One SmartAPI:</strong> Get your API key from <a href="https://smartapi.angelone.in" target="_blank" rel="noreferrer" style={{ color: "#22d3a5", textDecoration: "underline" }}>smartapi.angelone.in</a>. Your Client ID is your Angel One login ID. TOTP secret is from the authenticator app setup.
                </div>
              )}

              {activeModalBroker.requiresApiKey && (
                <div style={{ marginBottom: "1rem" }}>
                  <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "rgba(255,255,255,0.6)" }}>
                    API Key {activeModalBroker.id === "angel" && <span style={{ color: "rgba(255,255,255,0.35)" }}>(from SmartAPI dashboard)</span>}
                  </label>
                  <input
                    type="text" required
                    value={formData.apiKey}
                    onChange={e => setFormData(f => ({ ...f, apiKey: e.target.value }))}
                    placeholder={activeModalBroker.id === "angel" ? "e.g. abc123XYZ" : "API Key"}
                    className="chat-input"
                    style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)", fontSize: "0.9rem" }}
                  />
                </div>
              )}

              <div style={{ marginBottom: "1rem" }}>
                <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "rgba(255,255,255,0.6)" }}>
                  Client ID {activeModalBroker.id === "angel" && <span style={{ color: "rgba(255,255,255,0.35)" }}>(Angel One login ID)</span>}
                </label>
                <input
                  type="text" required
                  value={formData.clientId}
                  onChange={e => setFormData(f => ({ ...f, clientId: e.target.value }))}
                  placeholder={activeModalBroker.id === "angel" ? "e.g. A123456" : "Client / User ID"}
                  className="chat-input"
                  style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)", fontSize: "0.9rem" }}
                />
              </div>

              <div style={{ marginBottom: "1rem" }}>
                <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "rgba(255,255,255,0.6)" }}>
                  PIN / Password
                </label>
                <input
                  type="password" required
                  value={formData.password}
                  onChange={e => setFormData(f => ({ ...f, password: e.target.value }))}
                  placeholder="Angel One MPIN or trading password"
                  className="chat-input"
                  style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)", fontSize: "0.9rem" }}
                />
              </div>

              {activeModalBroker.id !== "paper" && (
                <div style={{ marginBottom: "1.25rem" }}>
                  <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "rgba(255,255,255,0.6)" }}>
                    TOTP Secret {activeModalBroker.id === "angel" && <span style={{ color: "rgba(255,255,255,0.35)" }}>(base32 secret from authenticator setup)</span>}
                  </label>
                  <input
                    type="text"
                    value={formData.totpSecret}
                    onChange={e => setFormData(f => ({ ...f, totpSecret: e.target.value }))}
                    placeholder="Base32 TOTP secret (e.g. JBSWY3DPEHPK3PXP)"
                    className="chat-input"
                    style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)", fontSize: "0.9rem", letterSpacing: "0.5px" }}
                  />
                </div>
              )}

              {connectError && (
                <div style={{ background: "rgba(255,70,70,0.1)", border: "1px solid rgba(255,70,70,0.3)", borderRadius: "6px", padding: "0.6rem 0.9rem", marginBottom: "1rem", color: "#ff6b6b", fontSize: "0.85rem" }}>
                  ⚠ {connectError}
                </div>
              )}

              <div style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.3)", marginBottom: "1rem", textAlign: "center" }}>
                🔒 Credentials are sent directly to the backend via encrypted HTTPS and used only for session authentication.
              </div>

              <button
                type="submit"
                disabled={connectStatus === "connecting" || connectStatus === "success"}
                style={{
                  width: "100%", padding: "0.75rem",
                  background: connectStatus === "success" ? "rgba(34,211,165,0.25)" : connectStatus === "error" ? "rgba(255,70,70,0.15)" : `${activeModalBroker.color}20`,
                  border: `1px solid ${connectStatus === "success" ? "#22d3a5" : connectStatus === "error" ? "#ff6b6b" : activeModalBroker.color}50`,
                  color: connectStatus === "error" ? "#ff6b6b" : activeModalBroker.color,
                  borderRadius: "8px", cursor: "pointer", fontSize: "0.95rem", fontWeight: 600,
                }}
              >
                {connectStatus === "connecting" ? "Authenticating with SmartAPI…" :
                  connectStatus === "success" ? "✓ Connected Successfully!" :
                    connectStatus === "error" ? "Retry Connection" :
                      `Connect ${activeModalBroker.name}`}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
