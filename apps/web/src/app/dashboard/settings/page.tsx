"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function SettingsPage() {
  const { tradingMode, setTradingMode } = useAppStore();
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getSettings().then((s: any) => setSettings(s ?? {})).catch(() => {});
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    try { await api.updateSettings(settings); } catch { /* ignore */ }
    setSaving(false);
  };
  return (
    <div className="space-y-5 animate-fade-in max-w-2xl">
      <h1 className="text-2xl font-bold font-[var(--font-heading)]">⚙️ Settings</h1>

      <div className="card"><h2 className="text-base font-semibold mb-3">Profile</h2>
        <div className="space-y-3">
          {[{ l: "Full Name", v: "Atluri User", t: "text" }, { l: "Email", v: "test@astraos.dev", t: "email" }].map((f, idx) => (
            <div key={f.l}><label htmlFor={`profile-${idx}`} className="text-xs text-[var(--text-secondary)] mb-1 block">{f.l}</label>
              <input id={`profile-${idx}`} type={f.t} title={f.l} defaultValue={f.v} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none" /></div>
          ))}
        </div>
      </div>

      <div className="card"><h2 className="text-base font-semibold mb-3">Risk Profile</h2>
        <div className="grid grid-cols-2 gap-3">
          {[
            { l: "Capital (₹)", v: "10,00,000" }, { l: "Max Daily Loss %", v: "2.0" },
            { l: "Max Position %", v: "5.0" }, { l: "Max Leverage", v: "2.0" },
          ].map((f, idx) => (
            <div key={f.l}><label htmlFor={`risk-${idx}`} className="text-xs text-[var(--text-secondary)] mb-1 block">{f.l}</label>
              <input id={`risk-${idx}`} title={f.l} defaultValue={f.v} className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-[var(--font-mono)] focus:border-[var(--accent)] focus:outline-none" /></div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="text-base font-semibold mb-3">Broker — Angel One</h2>
        <p className="text-xs text-[var(--text-secondary)] mb-3">Connect your Angel One (SmartAPI) account for live trading.</p>
        <div className="space-y-3">
          {[
            { l: "API Key", p: "Your SmartAPI key", id: "angel-api-key" },
            { l: "Client ID", p: "Your Angel One login ID", id: "angel-client-id" },
            { l: "Password", p: "••••••••", id: "angel-password", type: "password" },
            { l: "TOTP Secret", p: "Base32 TOTP secret for 2FA", id: "angel-totp", type: "password" },
          ].map(f => (
            <div key={f.id}>
              <label htmlFor={f.id} className="text-xs text-[var(--text-secondary)] mb-1 block">{f.l}</label>
              <input
                id={f.id} type={f.type || "text"} title={f.l} placeholder={f.p}
                className="w-full bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm font-[var(--font-mono)] focus:border-[var(--accent)] focus:outline-none"
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 mt-4">
          <button id="connect-angel" className="text-xs px-4 py-2 bg-gradient-to-r from-[var(--accent)] to-[var(--purple)] text-white rounded-lg hover:shadow-lg transition-all">
            Connect Angel One
          </button>
          <span className="text-xs px-2 py-1 rounded-lg bg-[var(--amber-glow)] text-[var(--amber)] border border-[rgba(245,158,11,0.2)]">
            Paper Trading
          </span>
        </div>
        <p className="text-[10px] text-[var(--text-tertiary)] mt-3">
          Get your API key free at <a href="https://smartapi.angelone.in/" target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] underline">smartapi.angelone.in</a> • 
          All credentials are encrypted with Fernet (AES-128) and stored locally.
        </p>
      </div>

      <div className="card">
        <h2 className="text-base font-semibold mb-3">Trading Mode</h2>
        <div className="flex items-center gap-3">
          <button onClick={() => setTradingMode("paper")} className={`text-xs px-4 py-2 rounded-lg font-medium ${tradingMode === "paper" ? "bg-[var(--amber-glow)] text-[var(--amber)] border border-[rgba(245,158,11,0.2)]" : "bg-[var(--bg-primary)] text-[var(--text-tertiary)] border border-[var(--border)]"}`}>
            📝 Paper Trading
          </button>
          <button onClick={() => setTradingMode("live")} className={`text-xs px-4 py-2 rounded-lg ${tradingMode === "live" ? "bg-[var(--red-glow)] text-[var(--red)] border border-[rgba(255,79,109,0.2)] font-medium" : "bg-[var(--bg-primary)] text-[var(--text-tertiary)] border border-[var(--border)]"}`}>
            🔴 Live Trading
          </button>
        </div>
        <p className="text-[10px] text-[var(--text-tertiary)] mt-2">
          30 days of paper trading required before live mode. SEBI Algo-ID registration needed for automated orders.
        </p>
      </div>

      <button onClick={saveSettings} disabled={saving}
        className="text-xs px-6 py-2.5 bg-[var(--accent)] text-white rounded-lg hover:bg-[#5078e6] disabled:opacity-50 transition-all">
        {saving ? "Saving…" : "Save Settings"}
      </button>
    </div>
  );
}
