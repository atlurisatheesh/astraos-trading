"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

const SYMBOLS = ["NIFTY50", "BANKNIFTY", "RELIANCE", "TCS", "HDFCBANK", "INFY"];

interface PredictionCard {
  symbol: string;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;         // 0-100 (already a percent from the API)
  probabilities?: { BUY: number; SELL: number; HOLD: number };
  regime?: string;
  model_accuracy?: number;
  cv_accuracy?: number;
  trained_at?: string;
  error?: string;
}

const DIRECTION_LABEL: Record<string, string> = {
  BUY: "Bullish",
  SELL: "Bearish",
  HOLD: "Neutral",
};

const DIRECTION_COLOR: Record<string, string> = {
  BUY: "text-[var(--green)] bg-[var(--green-glow)] border-[rgba(34,211,165,0.2)]",
  SELL: "text-red-400 bg-red-900/20 border-red-700/30",
  HOLD: "text-yellow-400 bg-yellow-900/20 border-yellow-700/30",
};

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<PredictionCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const fetchPredictions = async () => {
    setLoading(true);
    const results = await Promise.allSettled(
      SYMBOLS.map((s) => api.getPrediction(s))
    );

    const cards: PredictionCard[] = results.map((r, i) => {
      if (r.status === "fulfilled" && r.value) {
        const v = r.value as Record<string, unknown>;
        // API returns: { signal, action, confidence (0-100), probabilities, regime, ... }
        const rawSignal = (v.signal ?? v.action ?? "HOLD") as string;
        const signal: "BUY" | "SELL" | "HOLD" =
          rawSignal === "BUY" ? "BUY" : rawSignal === "SELL" ? "SELL" : "HOLD";

        // confidence is already 0-100 from the API — no multiplication needed
        const confidence = typeof v.confidence === "number" ? v.confidence : 0;

        return {
          symbol: SYMBOLS[i],
          signal,
          confidence: Math.round(confidence * 10) / 10,
          probabilities: v.probabilities as PredictionCard["probabilities"],
          regime: typeof v.regime === "string" ? v.regime : undefined,
          model_accuracy:
            typeof v.model_accuracy === "number" ? v.model_accuracy : undefined,
          cv_accuracy:
            typeof v.cv_accuracy === "number" ? v.cv_accuracy : undefined,
          trained_at:
            typeof v.trained_at === "string" ? v.trained_at : undefined,
          error: typeof v.error === "string" ? v.error : undefined,
        };
      }
      return {
        symbol: SYMBOLS[i],
        signal: "HOLD",
        confidence: 0,
        error: "Prediction unavailable",
      };
    });

    setPredictions(cards);
    setLastUpdated(new Date().toLocaleTimeString("en-IN", { hour12: false }));
    setLoading(false);
  };

  useEffect(() => {
    fetchPredictions();
    // Auto-refresh every 15 minutes
    const id = setInterval(fetchPredictions, 15 * 60 * 1000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-[var(--font-heading)]">
            🧠 AI Predictions
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">
            XGBoost + Multi-Agent ensemble • 5-day horizon • Updated every 15 min
          </p>
        </div>
        <div className="text-xs text-[var(--text-secondary)] text-right">
          {lastUpdated && <span>Last updated: {lastUpdated}</span>}
          <button
            onClick={fetchPredictions}
            className="ml-3 px-3 py-1 rounded border border-[var(--border)] hover:border-[var(--accent)] text-xs transition-colors"
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {SYMBOLS.map((s) => (
            <div key={s} className="card animate-pulse h-32 bg-[var(--card-bg)]" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {predictions.map((p) => (
            <PredictionCardView key={p.symbol} p={p} />
          ))}
        </div>
      )}

      <p className="text-xs text-[var(--text-secondary)] pt-2">
        ⚠️ Not financial advice. These are model signals, not recommendations.
        Always do your own research.
      </p>
    </div>
  );
}

function PredictionCardView({ p }: { p: PredictionCard }) {
  const dirColor = DIRECTION_COLOR[p.signal] ?? DIRECTION_COLOR.HOLD;
  const trainedDate = p.trained_at
    ? new Date(p.trained_at).toLocaleDateString("en-IN")
    : null;

  return (
    <div className="card flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-bold font-[var(--font-mono)] text-base">
          {p.symbol}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded border font-semibold ${dirColor}`}>
          {DIRECTION_LABEL[p.signal]}
        </span>
      </div>

      {/* Signal */}
      <div className="flex items-end gap-2">
        <span
          className={`text-2xl font-bold font-[var(--font-mono)] ${
            p.signal === "BUY"
              ? "text-[var(--green)]"
              : p.signal === "SELL"
              ? "text-red-400"
              : "text-yellow-400"
          }`}
        >
          {p.signal}
        </span>
        {p.confidence > 0 && (
          <span className="text-sm text-[var(--text-secondary)] mb-0.5">
            {p.confidence.toFixed(1)}% confidence
          </span>
        )}
      </div>

      {/* Probability bar */}
      {p.probabilities && (
        <div className="space-y-1">
          {(["BUY", "HOLD", "SELL"] as const).map((s) => {
            const val = p.probabilities![s] ?? 0;
            const barColor =
              s === "BUY"
                ? "bg-green-500"
                : s === "SELL"
                ? "bg-red-500"
                : "bg-yellow-500";
            return (
              <div key={s} className="flex items-center gap-2 text-xs">
                <span className="w-8 text-[var(--text-secondary)]">{s}</span>
                <div className="flex-1 h-1.5 rounded bg-[var(--border)]">
                  <div
                    className={`h-1.5 rounded ${barColor}`}
                    style={{ width: `${Math.min(100, val)}%` }}
                  />
                </div>
                <span className="w-10 text-right text-[var(--text-secondary)]">
                  {val.toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Meta */}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-[var(--text-secondary)] pt-1 border-t border-[var(--border)]">
        {p.regime && (
          <span>
            Regime:{" "}
            <span className="text-[var(--accent)] capitalize">{p.regime}</span>
          </span>
        )}
        {p.model_accuracy != null && (
          <span>
            Model acc:{" "}
            <span className="text-[var(--accent)]">{p.model_accuracy}%</span>
          </span>
        )}
        {p.cv_accuracy != null && (
          <span>
            CV acc:{" "}
            <span className="text-[var(--accent)]">{p.cv_accuracy}%</span>
          </span>
        )}
        {trainedDate && <span>Trained: {trainedDate}</span>}
        {p.error && (
          <span className="text-red-400 col-span-full">{p.error}</span>
        )}
      </div>
    </div>
  );
}
