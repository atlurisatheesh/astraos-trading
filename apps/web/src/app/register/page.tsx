"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.register(email, password, fullName);
      setSuccess(true);
      // Auto-redirect to login after short delay
      setTimeout(() => {
        window.location.href = "/login";
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

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
            Create an Account
          </h1>
          <p style={{ fontSize: 13, color: "var(--text2)" }}>
            Join Quantus AI Trading
          </p>
        </div>

        {/* Error / Success */}
        {error && (
          <div style={{
            marginBottom: 16, padding: 12, borderRadius: 12,
            background: "rgba(255,79,109,0.08)", border: "1px solid rgba(255,79,109,0.2)",
            color: "var(--red)", fontSize: 12, textAlign: "center",
          }}>{error}</div>
        )}
        
        {success && (
          <div style={{
            marginBottom: 16, padding: 12, borderRadius: 12,
            background: "rgba(52, 168, 83, 0.08)", border: "1px solid rgba(52, 168, 83, 0.2)",
            color: "var(--green)", fontSize: 12, textAlign: "center",
          }}>Registration successful! Redirecting to login...</div>
        )}

        <div style={{
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: 20, padding: 28, boxShadow: "var(--glow)",
        }}>

          {/* Email/Password Form */}
          <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Full Name</label>
              <input
                id="register-name" type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                placeholder="John Doe"
                required
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
              <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Email</label>
              <input
                id="register-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@email.com"
                required
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
                id="register-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
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
              id="register-submit" type="submit" disabled={loading || success}
              style={{
                width: "100%", padding: "14px 0", borderRadius: 14, border: "none",
                background: "linear-gradient(135deg, var(--accent), var(--purple))",
                color: "#fff", fontSize: 15, fontWeight: 600, cursor: "pointer",
                transition: "all 0.3s", opacity: (loading || success) ? 0.6 : 1,
                boxShadow: "0 4px 20px rgba(99,140,255,0.3)",
                marginTop: 8
              }}
            >
              {loading ? "Creating Account..." : "Register"}
            </button>
          </form>

          <p style={{ textAlign: "center", fontSize: 12, color: "var(--text3)", marginTop: 20 }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "var(--accent)", textDecoration: "none" }}>Sign In</Link>
          </p>
        </div>

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
