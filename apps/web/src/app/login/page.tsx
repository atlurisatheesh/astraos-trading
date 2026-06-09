"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          renderButton: (el: HTMLElement, config: Record<string, unknown>) => void;
        };
      };
    };
  }
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"login" | "prefs">("login");
  const [googleToken, setGoogleToken] = useState<string | null>(null);

  // Notification toggles
  const [notifEmail, setNotifEmail] = useState(true);
  const [notifTelegram, setNotifTelegram] = useState(false);
  const [notifWhatsapp, setNotifWhatsapp] = useState(false);
  const [telegramId, setTelegramId] = useState("");
  const [whatsappNum, setWhatsappNum] = useState("");

  const setToken = useAppStore((s) => s.setToken);
  const setUser = useAppStore((s) => s.setUser);

  /* ── Normal email/password login ── */
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(email, password);
      setToken(res.access_token);
      const user = await api.me();
      setUser(user);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  /* ── Google Sign-In handler ── */
  const handleGoogleLogin = () => {
    setError("");
    // Load Google Identity Services script dynamically
    if (typeof window !== "undefined" && !document.getElementById("gsi-script")) {
      const script = document.createElement("script");
      script.id = "gsi-script";
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = () => initGoogleSignIn();
      document.head.appendChild(script);
    } else {
      initGoogleSignIn();
    }
  };

  const initGoogleSignIn = () => {
    if (!window.google) {
      setError("Google sign-in failed to load. Please try again.");
      return;
    }
    window.google.accounts.id.initialize({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      callback: handleGoogleCallback,
    });
    // Create a hidden container and trigger the One Tap UI
    const btn = document.getElementById("g-signin-btn");
    if (btn) {
      window.google.accounts.id.renderButton(btn, {
        theme: "filled_black",
        size: "large",
        width: "380",
        text: "continue_with",
        shape: "pill",
      });
      // Auto-click it
      setTimeout(() => btn.querySelector("div[role='button']")?.dispatchEvent(new MouseEvent("click", { bubbles: true })), 200);
    }
  };

  const handleGoogleCallback = (response: { credential: string }) => {
    setGoogleToken(response.credential);
    setMode("prefs"); // Show notification preferences screen
  };

  /* ── Complete login after prefs selection ── */
  const completeGoogleLogin = async () => {
    if (!googleToken) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id_token: googleToken,
          notification_preferences: {
            email: notifEmail,
            telegram: notifTelegram,
            whatsapp: notifWhatsapp,
            telegram_chat_id: telegramId,
            whatsapp_number: whatsappNum,
          },
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Google login failed");
      }
      const data = await res.json();
      setToken(data.access_token);
      const user = await api.me();
      setUser(user);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  /* ── Toggle Component ── */
  const Toggle = ({ checked, onChange, label, icon }: { checked: boolean; onChange: (v: boolean) => void; label: string; icon: string }) => (
    <div
      onClick={() => onChange(!checked)}
      style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "14px 16px", borderRadius: 12,
        cursor: "pointer", transition: "all 0.2s",
        background: checked ? "rgba(99,140,255,0.1)" : "var(--bg-card)",
        border: checked ? "1.5px solid var(--accent)" : "1.5px solid var(--border)",
      }}
    >
      <span style={{ fontSize: 22 }}>{icon}</span>
      <span style={{ flex: 1, fontSize: 14, fontWeight: 500 }}>{label}</span>
      <div style={{
        width: 44, height: 24, borderRadius: 12, position: "relative", transition: "all 0.3s",
        background: checked ? "var(--accent)" : "var(--border)",
      }}>
        <div style={{
          width: 18, height: 18, borderRadius: 9, background: "#fff",
          position: "absolute", top: 3,
          left: checked ? 23 : 3, transition: "left 0.3s",
        }} />
      </div>
    </div>
  );

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--bg)", position: "relative", overflow: "hidden",
    }}>
      {/* Animated background glow */}
      <div style={{
        position: "absolute", width: 600, height: 600, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(99,140,255,0.08) 0%, transparent 70%)",
        top: "-15%", right: "-10%", animation: "pulse 6s infinite",
      }} />
      <div style={{
        position: "absolute", width: 400, height: 400, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(167,139,250,0.06) 0%, transparent 70%)",
        bottom: "-10%", left: "-5%", animation: "pulse 8s infinite reverse",
      }} />

      <div style={{
        width: "100%", maxWidth: 420, padding: "0 20px", position: "relative", zIndex: 1,
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: "linear-gradient(135deg, var(--accent), var(--purple))",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#fff", fontWeight: 800, fontSize: 22, margin: "0 auto 16px",
            boxShadow: "0 8px 32px rgba(99,140,255,0.3)",
          }}>Q</div>
          <h1 style={{ fontSize: 26, fontWeight: 700, marginBottom: 4 }}>
            {mode === "login" ? "Welcome to Quantus" : "Choose Alerts"}
          </h1>
          <p style={{ fontSize: 13, color: "var(--text2)" }}>
            {mode === "login"
              ? "AI-Powered Trading Intelligence"
              : "How do you want to receive trade alerts?"}
          </p>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            marginBottom: 16, padding: 12, borderRadius: 12,
            background: "rgba(255,79,109,0.08)", border: "1px solid rgba(255,79,109,0.2)",
            color: "var(--red)", fontSize: 12, textAlign: "center",
          }}>{error}</div>
        )}

        {mode === "login" ? (
          <div style={{
            background: "var(--card)", border: "1px solid var(--border)",
            borderRadius: 20, padding: 28, boxShadow: "var(--glow)",
          }}>
            {/* Google Sign-In Button */}
            <button
              id="google-login-btn"
              onClick={handleGoogleLogin}
              type="button"
              style={{
                width: "100%", padding: "14px 16px", borderRadius: 14,
                border: "1.5px solid var(--border)", background: "var(--bg)",
                display: "flex", alignItems: "center", justifyContent: "center",
                gap: 12, cursor: "pointer", transition: "all 0.2s",
                color: "var(--text)", fontSize: 14, fontWeight: 600,
              }}
              onMouseOver={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent)";
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,140,255,0.05)";
              }}
              onMouseOut={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
                (e.currentTarget as HTMLButtonElement).style.background = "var(--bg)";
              }}
            >
              {/* Google Icon SVG */}
              <svg width="20" height="20" viewBox="0 0 48 48">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
              </svg>
              Continue with Google
            </button>

            {/* Hidden Google button container */}
            <div id="g-signin-btn" style={{ display: "none" }} />

            {/* Divider */}
            <div style={{
              display: "flex", alignItems: "center", gap: 12,
              margin: "20px 0", color: "var(--text3)", fontSize: 11,
            }}>
              <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
              or sign in with email
              <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            </div>

            {/* Email/Password Form */}
            <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Email</label>
                <input
                  id="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@email.com"
                  style={{
                    width: "100%", background: "var(--bg)", border: "1.5px solid var(--border)",
                    borderRadius: 12, padding: "12px 16px", fontSize: 14, color: "var(--text)",
                    outline: "none", transition: "border-color 0.2s",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Password</label>
                <input
                  id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  style={{
                    width: "100%", background: "var(--bg)", border: "1.5px solid var(--border)",
                    borderRadius: 12, padding: "12px 16px", fontSize: 14, color: "var(--text)",
                    outline: "none", transition: "border-color 0.2s",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                />
              </div>
              <button
                id="login-submit" type="submit" disabled={loading}
                style={{
                  width: "100%", padding: "14px 0", borderRadius: 14, border: "none",
                  background: "linear-gradient(135deg, var(--accent), var(--purple))",
                  color: "#fff", fontSize: 15, fontWeight: 600, cursor: "pointer",
                  transition: "all 0.3s", opacity: loading ? 0.6 : 1,
                  boxShadow: "0 4px 20px rgba(99,140,255,0.3)",
                }}
              >
                {loading ? "Signing in..." : "Sign In"}
              </button>
            </form>

            <p style={{ textAlign: "center", fontSize: 12, color: "var(--text3)", marginTop: 20 }}>
              Don&apos;t have an account?{" "}
              <Link href="/register" style={{ color: "var(--accent)", textDecoration: "none" }}>Register</Link>
            </p>
          </div>
        ) : (
          /* ── Notification Preferences Screen ── */
          <div style={{
            background: "var(--card)", border: "1px solid var(--border)",
            borderRadius: 20, padding: 28, boxShadow: "var(--glow)",
          }}>
            <p style={{ fontSize: 13, color: "var(--text2)", marginBottom: 20, lineHeight: 1.5 }}>
              Select how you&apos;d like to receive <strong style={{ color: "var(--text)" }}>trade alerts, stop-loss hits, and daily reports</strong>:
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
              <Toggle checked={notifEmail} onChange={setNotifEmail} label="Email Notifications" icon="📧" />
              <Toggle checked={notifTelegram} onChange={setNotifTelegram} label="Telegram Alerts" icon="✈️" />
              <Toggle checked={notifWhatsapp} onChange={setNotifWhatsapp} label="WhatsApp Alerts" icon="💬" />
            </div>

            {/* Conditional input fields */}
            {notifTelegram && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Telegram Chat ID</label>
                <input
                  value={telegramId} onChange={(e) => setTelegramId(e.target.value)}
                  placeholder="e.g. 123456789"
                  style={{
                    width: "100%", background: "var(--bg)", border: "1.5px solid var(--border)",
                    borderRadius: 12, padding: "10px 14px", fontSize: 13, color: "var(--text)",
                    outline: "none",
                  }}
                />
              </div>
            )}

            {notifWhatsapp && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>WhatsApp Number</label>
                <input
                  value={whatsappNum} onChange={(e) => setWhatsappNum(e.target.value)}
                  placeholder="+91 98765 43210"
                  style={{
                    width: "100%", background: "var(--bg)", border: "1.5px solid var(--border)",
                    borderRadius: 12, padding: "10px 14px", fontSize: 13, color: "var(--text)",
                    outline: "none",
                  }}
                />
              </div>
            )}

            <button
              onClick={completeGoogleLogin}
              disabled={loading}
              style={{
                width: "100%", padding: "14px 0", borderRadius: 14, border: "none",
                background: "linear-gradient(135deg, var(--accent), var(--purple))",
                color: "#fff", fontSize: 15, fontWeight: 600, cursor: "pointer",
                transition: "all 0.3s", opacity: loading ? 0.6 : 1,
                boxShadow: "0 4px 20px rgba(99,140,255,0.3)",
                marginTop: 8,
              }}
            >
              {loading ? "Setting up..." : "Continue to Dashboard →"}
            </button>

            <button
              onClick={() => { setMode("login"); setGoogleToken(null); }}
              style={{
                width: "100%", padding: 10, borderRadius: 12, border: "none",
                background: "transparent", color: "var(--text3)", fontSize: 12,
                cursor: "pointer", marginTop: 10,
              }}
            >
              ← Back to login
            </button>
          </div>
        )}

        {/* Footer */}
        <p style={{ textAlign: "center", fontSize: 10, color: "var(--text3)", marginTop: 24, letterSpacing: 1 }}>
          QUANTUS AI · INSTITUTIONAL-GRADE TRADING
        </p>
      </div>

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.05); }
        }
      `}</style>
    </div>
  );
}
