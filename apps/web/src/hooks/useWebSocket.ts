// AstraOS — WebSocket Hooks for Real-Time Data

"use client";

import { useEffect, useRef, useState, useCallback } from "react";

type WSStatus = "connecting" | "connected" | "disconnected" | "error";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface UseWebSocketOptions {
  autoReconnect?: boolean;
  reconnectDelay?: number;
  maxRetries?: number;
}

export function useWebSocket<T = unknown>(
  path: string,
  options: UseWebSocketOptions = {},
) {
  const { autoReconnect = true, reconnectDelay = 3000, maxRetries = 10 } = options;
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<WSStatus>("disconnected");
  const [history, setHistory] = useState<T[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const ws = new WebSocket(`${WS_BASE}${path}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as T;
        setData(parsed);
        setHistory((prev) => [...prev.slice(-99), parsed]); // Keep last 100
      } catch {
        console.error("WS parse error", event.data);
      }
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = () => {
      setStatus("disconnected");
      if (autoReconnect && retriesRef.current < maxRetries) {
        retriesRef.current += 1;
        reconnectTimer.current = setTimeout(connect, reconnectDelay);
      }
    };
  }, [path, autoReconnect, reconnectDelay, maxRetries]);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("disconnected");
    retriesRef.current = maxRetries; // Prevent reconnect
  }, [maxRetries]);

  const send = useCallback((message: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { data, status, history, send, connect, disconnect };
}

// ── Pre-typed hooks for each channel ──

export interface TickerData {
  type: "ticker";
  timestamp: string;
  quotes: Array<{
    symbol: string;
    price: number;
    change: number;
    change_pct: number;
    volume: number;
  }>;
}

export interface SignalData {
  type: "signal" | "signal_error";
  timestamp: string;
  signal?: {
    symbol: string;
    action: "BUY" | "SELL" | "HOLD";
    confidence: number;
    entry: number;
    target: number;
    stop_loss: number;
    agents: Array<{ agent: string; signal: string; confidence: number }>;
  };
}

export interface PortfolioData {
  type: "portfolio";
  timestamp: string;
  capital: number;
  invested: number;
  available: number;
  day_pnl: number;
  day_pnl_pct: number;
  total_pnl: number;
  positions: Array<{
    symbol: string;
    qty: number;
    avg: number;
    ltp: number;
    pnl: number;
  }>;
}

export interface FeedEvent {
  type: "news" | "signal" | "order" | "risk" | "system";
  timestamp: string;
  id: number;
  title?: string;
  symbol?: string;
  action?: string;
  message?: string;
  confidence?: number;
  sentiment?: string;
}

export function useTicker(symbols = "RELIANCE,TCS,HDFCBANK,INFY,SBIN") {
  return useWebSocket<TickerData>(`/ws/ticker?symbols=${symbols}`);
}

export function useSignals(symbols = "RELIANCE,TCS,HDFCBANK") {
  return useWebSocket<SignalData>(`/ws/signals?symbols=${symbols}`);
}

export function usePortfolio() {
  return useWebSocket<PortfolioData>("/ws/portfolio");
}

export function useFeed() {
  return useWebSocket<FeedEvent>("/ws/feed");
}
