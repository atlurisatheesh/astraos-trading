"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "https://astraos-backend.onrender.com";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Request failed. Please try again.");
      }
      const data = await res.json();
      if (data.reset_token) {
        // Dev mode (no SMTP configured) — go straight to the reset form
        router.push(`/reset-password?token=${encodeURIComponent(data.reset_token)}`);
        return;
      }
      setMessage(data.message || "If that email is registered, a reset link has been sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--bg)", position: "relative", overflow: "hidden",
    }}>
      <div style={{ width: "100%", maxWidth: 420, padding: "0 20px", position: "relative", zIndex: 1 }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: "linear-gradient(135deg, var(--accent), var(--purple))",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#fff", fontWeight: 800, fontSize: 22, margin: "0 auto 16px",
            boxShadow: "0 8px 32px rgba(99,140,255,0.3)",
          }}>Q</div>
          <h1 style={{ fontSize: 26, fontWeight: 700, marginBottom: 4 }}>Forgot Password</h1>
          <p style={{ fontSize: 13, color: "var(--text2)" }}>
            Enter your email and we&apos;ll send you a reset link
          </p>
        </div>

        {error && (
          <div style={{
            marginBottom: 16, padding: 12, borderRadius: 12,
            background: "rgba(255,79,109,0.08)", border: "1px solid rgba(255,79,109,0.2)",
            color: "var(--red)", fontSize: 12, textAlign: "center",
          }}>{error}</div>
        )}
        {message && (
          <div style={{
            marginBottom: 16, padding: 12, borderRadius: 12,
            background: "rgba(34,211,165,0.08)", border: "1px solid rgba(34,211,165,0.2)",
            color: "var(--green)", fontSize: 12, textAlign: "center",
          }}>{message}</div>
        )}

        <div style={{
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: 20, padding: 28, boxShadow: "var(--glow)",
        }}>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Email</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@email.com" required
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
              type="submit" disabled={loading}
              style={{
                width: "100%", padding: "14px 0", borderRadius: 14, border: "none",
                background: "linear-gradient(135deg, var(--accent), var(--purple))",
                color: "#fff", fontSize: 15, fontWeight: 600, cursor: "pointer",
                transition: "all 0.3s", opacity: loading ? 0.6 : 1,
                boxShadow: "0 4px 20px rgba(99,140,255,0.3)",
              }}
            >
              {loading ? "Sending..." : "Send Reset Link"}
            </button>
          </form>

          <p style={{ textAlign: "center", fontSize: 12, color: "var(--text3)", marginTop: 20 }}>
            Remembered it?{" "}
            <Link href="/login" style={{ color: "var(--accent)", textDecoration: "none" }}>Back to login</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
