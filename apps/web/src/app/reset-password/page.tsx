"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "https://astraos-backend.onrender.com";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const router = useRouter();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Reset failed. The link may have expired.");
      }
      setSuccess(true);
      setTimeout(() => router.push("/login"), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", background: "var(--bg)", border: "1.5px solid var(--border)",
    borderRadius: 12, padding: "12px 16px", fontSize: 14, color: "var(--text)",
    outline: "none", transition: "border-color 0.2s",
  };

  return (
    <div style={{ width: "100%", maxWidth: 420, padding: "0 20px", position: "relative", zIndex: 1 }}>
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          background: "linear-gradient(135deg, var(--accent), var(--purple))",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#fff", fontWeight: 800, fontSize: 22, margin: "0 auto 16px",
          boxShadow: "0 8px 32px rgba(99,140,255,0.3)",
        }}>Q</div>
        <h1 style={{ fontSize: 26, fontWeight: 700, marginBottom: 4 }}>Set New Password</h1>
        <p style={{ fontSize: 13, color: "var(--text2)" }}>Choose a strong password (min 8 characters)</p>
      </div>

      {error && (
        <div style={{
          marginBottom: 16, padding: 12, borderRadius: 12,
          background: "rgba(255,79,109,0.08)", border: "1px solid rgba(255,79,109,0.2)",
          color: "var(--red)", fontSize: 12, textAlign: "center",
        }}>{error}</div>
      )}

      <div style={{
        background: "var(--card)", border: "1px solid var(--border)",
        borderRadius: 20, padding: 28, boxShadow: "var(--glow)",
      }}>
        {!token ? (
          <p style={{ fontSize: 13, color: "var(--text2)", textAlign: "center" }}>
            Invalid or missing reset link.{" "}
            <Link href="/forgot-password" style={{ color: "var(--accent)" }}>Request a new one</Link>
          </p>
        ) : success ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
            <p style={{ fontSize: 14, color: "var(--green)", fontWeight: 600 }}>Password reset successful!</p>
            <p style={{ fontSize: 12, color: "var(--text2)", marginTop: 8 }}>Redirecting to login…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>New Password</label>
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••" required minLength={8} style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: "var(--text2)", marginBottom: 4, display: "block" }}>Confirm Password</label>
              <input
                type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••••••" required minLength={8} style={inputStyle}
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
              {loading ? "Resetting..." : "Reset Password"}
            </button>
          </form>
        )}

        <p style={{ textAlign: "center", fontSize: 12, color: "var(--text3)", marginTop: 20 }}>
          <Link href="/login" style={{ color: "var(--accent)", textDecoration: "none" }}>Back to login</Link>
        </p>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "var(--bg)", position: "relative", overflow: "hidden",
    }}>
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
