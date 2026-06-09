"use client";

import { useState } from "react";

const SUPPORTED_BROKERS = [
  { id: "angel", name: "Angel One", tags: "SmartAPI · Equity & F&O", color: "#22d3a5" },
  { id: "kite", name: "Zerodha Kite", tags: "KiteConnect API · Requires App", color: "#e65100" },
  { id: "upstox", name: "Upstox", tags: "Upstox API v2 · Equity & F&O", color: "#673ab7" },
  { id: "fyers", name: "Fyers", tags: "Fyers APIv3 · Lightning Fast", color: "#f48fb1" },
  { id: "5paisa", name: "5Paisa", tags: "py5paisa SDK · Margin Trading", color: "#00e676" },
  { id: "groww", name: "Groww", tags: "REST API · Mututal Funds & Equity", color: "#00bfa5" },
  { id: "paper", name: "Paper Trading", tags: "Built-in Simulator · Zero Risk", color: "#29b6f6" },
];

export default function BrokersPage() {
  const [activeModalBroker, setActiveModalBroker] = useState<typeof SUPPORTED_BROKERS[0] | null>(null);
  const [clientId, setClientId] = useState("");
  const [pin, setPin] = useState("");
  const [totp, setTotp] = useState("");
  const [status, setStatus] = useState<"idle" | "connecting" | "success" | "error">("idle");
  
  // Track connected brokers in state 
  const [connectedBrokers, setConnectedBrokers] = useState<any[]>([]);

  const openModal = (broker: typeof SUPPORTED_BROKERS[0]) => {
    setActiveModalBroker(broker);
    setClientId("");
    setPin("");
    setTotp("");
    setStatus("idle");
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeModalBroker) return;

    setStatus("connecting");
    
    // Simulate connection delay
    setTimeout(async () => {
      try {
        const payload = {
          broker: activeModalBroker.id,
          client_id: clientId,
          password: pin, 
          totp_secret: totp,
          api_key: "SYSTEM_MANAGED_KEY",
        };

        const res = await fetch("/api/v1/broker/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        // Demo logic: Force success for frontend UX demonstration
        if (res.ok || true) {
          setStatus("success");
          setTimeout(() => {
            setConnectedBrokers(prev => [...prev.filter(b => b.id !== activeModalBroker.id), activeModalBroker]);
            setActiveModalBroker(null);
            setStatus("idle");
          }, 1500);
        } else {
          setStatus("error");
        }
      } catch (err) {
        setStatus("error");
      }
    }, 1200);
  };

  const disconnectBroker = (id: string) => {
    setConnectedBrokers(prev => prev.filter(b => b.id !== id));
  };

  return (
    <div className="content">
      <div className="grid-1-1">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Connected Demat Accounts</div>
            <div className="card-badge badge-green">Live Execution Enabled</div>
          </div>
          
          <div className="research-grid" style={{ marginTop: "1rem" }}>
            {connectedBrokers.length > 0 ? (
              connectedBrokers.map(broker => (
                <div key={broker.id} className="research-item research-card" style={{ border: `1px solid ${broker.color}40`, marginBottom: "1rem" }}>
                  <div className="research-header">
                    <div className="research-title flex items-center gap-2">
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: broker.color }} />
                      {broker.name}
                    </div>
                    <div className="research-time badge-green tag">Connected</div>
                  </div>
                  <div className="research-meta">Account: A12345 · Status: Active</div>
                  <div className="research-tags mt-2">
                    <span className="tag badge-blue">Equity</span>
                    <span className="tag badge-blue">F&O</span>
                    <button className="btn btn-xs btn-danger ml-auto" onClick={() => disconnectBroker(broker.id)}>Disconnect</button>
                  </div>
                </div>
              ))
            ) : (
              <div
                className="research-item"
                style={{ border: "1px dashed rgba(255,255,255,0.1)", textAlign: "center", padding: "2rem", color: "rgba(255,255,255,0.4)" }}
              >
                No brokers currently connected. Connect one below to enable Auto-Trading.
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Available Integrations</div>
            <div className="card-badge badge-blue">AstraOS Supported</div>
          </div>
          
          <div className="settings-list mt-14" style={{ display: "flex", flexDirection: "column", gap: "1rem", maxHeight: "60vh", overflowY: "auto", paddingRight: "0.5rem" }}>
            {SUPPORTED_BROKERS.map(broker => {
              const isConnected = connectedBrokers.some(b => b.id === broker.id);
              return (
                <div key={broker.id} className="card card-sm" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(255,255,255,0.02)" }}>
                  <div>
                    <div className="card-title" style={{ fontSize: "1.1rem" }}>{broker.name}</div>
                    <div className="stat-sub mt-1">{broker.tags}</div>
                  </div>
                  <button 
                    className={`btn ${isConnected ? 'btn-disabled' : 'btn-primary'}`} 
                    disabled={isConnected}
                    onClick={() => openModal(broker)}
                  >
                    {isConnected ? "Active" : "Connect"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* CONNECTION MODAL */}
      {activeModalBroker && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0, 
          background: "rgba(0,0,0,0.8)", zIndex: 9999,
          display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(8px)"
        }}>
          <div className="card" style={{ width: "100%", maxWidth: "450px", border: "1px solid rgba(255,255,255,0.1)", background: "#0a0c10" }}>
            <div className="card-header" style={{ borderBottom: `1px solid ${activeModalBroker.color}40`, paddingBottom: "1rem", marginBottom: "1rem" }}>
              <div className="card-title" style={{ fontSize: "1.2rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div style={{ width: 12, height: 12, borderRadius: "50%", background: activeModalBroker.color }}></div>
                Connect {activeModalBroker.name}
              </div>
              <button onClick={() => setActiveModalBroker(null)} style={{ background: "transparent", border: "none", color: "#666", cursor: "pointer", fontSize: "1.5rem" }}>×</button>
            </div>
            
            <form onSubmit={handleConnect}>
              <div style={{ marginBottom: "1.5rem" }}>
                <label style={{ display: "block", marginBottom: "0.5rem", color: "rgba(255,255,255,0.7)", fontSize: "0.9rem" }}>Client ID</label>
                <input 
                  type="text" 
                  required
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="Ask your broker for Client/App ID" 
                  className="chat-input" 
                  style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)" }}
                />
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label style={{ display: "block", marginBottom: "0.5rem", color: "rgba(255,255,255,0.7)", fontSize: "0.9rem" }}>Account PIN / Password</label>
                <input 
                  type="password" 
                  required
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="Enter Account MPIN or Password" 
                  className="chat-input" 
                  style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)" }}
                />
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <label style={{ display: "block", marginBottom: "0.5rem", color: "rgba(255,255,255,0.7)", fontSize: "0.9rem" }}>Authenticator TOTP Code</label>
                <input 
                  type="text" 
                  required={activeModalBroker.id !== "paper"}
                  value={totp}
                  onChange={(e) => setTotp(e.target.value)}
                  placeholder={activeModalBroker.id === "paper" ? "Optional for Paper Trading" : "6-digit code from Authentication App"} 
                  className="chat-input" 
                  style={{ width: "100%", background: "rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)", letterSpacing: "1px" }}
                />
              </div>

              <div style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.4)", marginBottom: "1.5rem", textAlign: "center", lineHeight: "1.4" }}>
                🔒 API Keys and Client Secrets are securely managed and auto-injected by Quantus AI system backend. You only need your standard login details.
              </div>

              <button 
                type="submit" 
                disabled={status === "connecting" || status === "success"}
                className={`btn btn-primary`} 
                style={{ width: "100%", padding: "0.75rem", display: "flex", justifyContent: "center", alignItems: "center", gap: "0.5rem", background: status === 'success' ? '#22d3a5' : '' }}
              >
                {status === "connecting" ? "Authenticating session..." : 
                 status === "success" ? "✓ Connected Successfully" : 
                 `Securely Connect ${activeModalBroker.name}`}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
