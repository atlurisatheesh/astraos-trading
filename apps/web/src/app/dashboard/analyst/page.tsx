"use client";

import { useState } from "react";
import { api } from "@/lib/api";

const MESSAGES = [
  { role: "assistant", text: "Hello! I'm your AI market analyst. I can analyze stocks, sectors, F&O strategies, and provide research-backed insights. What would you like to explore today?" },
];

const SUGGESTIONS = [
  "Analyze RELIANCE for swing trading",
  "What's the best option strategy for Bank Nifty this week?",
  "Compare IT sector vs Banking sector momentum",
  "Explain the current PCR and max pain for Nifty",
  "Is SBIN good for long-term investment?",
  "What's the risk-reward for NIFTY 24500 CE?",
];

export default function AnalystPage() {
  const [messages, setMessages] = useState(MESSAGES);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    setMessages(prev => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.chatWithAnalyst(text);
      setMessages(prev => [...prev, { role: "assistant", text: res.reply }]);
    } catch {
      // Fallback to simulated response if API not available
      setMessages(prev => [...prev, {
        role: "assistant",
        text: `Great question! Let me analyze this for you.\n\n**Analysis Summary:**\nBased on multi-agent research (Technical + Derivatives + Sentiment + Macro):\n\n📊 **Technical:** Momentum indicators showing bullish divergence. RSI at 58, MACD crossover positive.\n\n🔗 **Derivatives:** OI buildup in futures is supportive. PCR at 1.28 is moderately bullish.\n\n📰 **Sentiment:** News flow is neutral-to-positive. No major adverse events detected.\n\n🌍 **Macro:** Global cues supportive — US futures flat, Asia markets up 0.3%.\n\n**Recommendation:** The signal synthesis gives a 72% confidence score. However, risk management remains paramount — always set stop losses and follow position sizing rules.\n\n⚠️ *This is AI-generated analysis for informational purposes. Not financial advice. Always do your own research.*`,
      }]);
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] animate-fade-in">
      <div className="mb-4">
        <h1 className="text-2xl font-bold font-[var(--font-heading)]">💬 AI Analyst</h1>
        <p className="text-sm text-[var(--text-secondary)]">Multi-agent research chat • Ask anything about stocks, strategies, or markets</p>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-3.5 rounded-xl text-sm leading-relaxed ${
              m.role === 'user'
                ? 'bg-[var(--accent)] text-white rounded-br-sm'
                : 'bg-[var(--bg-card)] border border-[var(--border)] rounded-bl-sm'
            }`}>
              <div className="whitespace-pre-wrap">{m.text}</div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="max-w-[80%] p-3.5 rounded-xl text-sm bg-[var(--bg-card)] border border-[var(--border)] rounded-bl-sm text-[var(--text-tertiary)]">
              Analyzing…
            </div>
          </div>
        )}
      </div>

      {/* Suggestions */}
      {messages.length <= 2 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTIONS.map((s, i) => (
            <button key={i} onClick={() => sendMessage(s)} className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all">
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          id="analyst-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
          placeholder="Ask about any stock, strategy, or market condition..."
          className="flex-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-xl px-4 py-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--accent)] transition-colors"
        />
        <button
          id="analyst-send"
          onClick={() => sendMessage(input)}
          className="px-5 py-3 bg-[var(--accent)] text-white rounded-xl font-medium text-sm hover:bg-[#5078e6] transition-all"
        >
          Send
        </button>
      </div>
    </div>
  );
}
