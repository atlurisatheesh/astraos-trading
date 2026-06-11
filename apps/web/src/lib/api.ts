// AstraOS — API Client for Frontend (TypeScript types + fetch helpers)

export interface Quote {
  symbol: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  prev_close: number;
  timestamp: string;
}

export interface Signal {
  symbol: string;
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  entry: number;
  target: number;
  stop_loss: number;
  risk_reward: number;
  time_horizon: string;
  regime: string;
  reasoning: string;
  agents: AgentResult[];
}

export interface AgentResult {
  agent: string;
  signal: "bullish" | "bearish" | "neutral";
  confidence: number;
  reasoning: string;
  data: Record<string, unknown>;
}

export interface BacktestResult {
  total_trades: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  wfe_score: number;
  monte_carlo: { p5: number; p50: number; p95: number };
}

export interface OptionsChain {
  symbol: string;
  expiry: string;
  spot_price: number;
  strikes: OptionStrike[];
  analytics: { pcr: number; max_pain: number; total_ce_oi: number; total_pe_oi: number };
}

export interface OptionStrike {
  strike: number;
  ce_oi: number;
  ce_volume: number;
  ce_iv: number;
  ce_ltp: number;
  pe_ltp: number;
  pe_iv: number;
  pe_volume: number;
  pe_oi: number;
}

export interface FundamentalsRatios {
  symbol: string;
  pe_ratio: number | null;
  pb_ratio: number | null;
  eps: number | null;
  dividend_yield: number | null;
  roe: number | null;
  debt_to_equity: number | null;
  market_cap: number | null;
  [key: string]: unknown;
}

export interface PortfolioSummary {
  total_value: number;
  invested_value: number;
  cash: number;
  day_pnl: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions: PositionItem[];
}

export interface PositionItem {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  average_cost: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  is_open: boolean;
}

export interface AlertItem {
  id: number;
  symbol: string;
  alert_type: string;
  condition: string;
  threshold: number;
  message: string;
  is_active: boolean;
  is_triggered: boolean;
}

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  published: string;
  summary?: string;
  category?: string;
  symbols?: string[];
  sentiment?: number; // backend returns float score (-1..1)
}

export interface JournalEntry {
  id: number;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number;
  emotion: string;
  notes: string;
  trade_date: string;
}

// API Client
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    if (res.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
    }
    let detail = `${res.status} ${res.statusText}`;
    try {
      const errBody = await res.json();
      if (errBody?.detail) {
        detail = typeof errBody.detail === "string"
          ? errBody.detail
          : JSON.stringify(errBody.detail);
      }
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null as T;
  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    fetchApi<{ access_token: string; refresh_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, full_name: string) =>
    fetchApi("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    }),
  me: () => fetchApi<{ id: string; email: string; full_name: string; role: string }>("/api/v1/auth/me"),

  // Market Data
  getQuote: (symbol: string) => fetchApi<Quote>(`/api/v1/market/quote/${symbol}`),
  getQuotes: (symbols: string[]) =>
    fetchApi<Quote[]>(`/api/v1/market/quotes?symbols=${symbols.join(",")}`),
  getOHLCV: (symbol: string, interval = "1d", period = "1y") =>
    fetchApi(`/api/v1/market/ohlcv/${symbol}?interval=${interval}&period=${period}`),
  getIndicators: (symbol: string) => fetchApi(`/api/v1/market/indicators/${symbol}`),
  getRegime: (symbol: string) => fetchApi(`/api/v1/market/regime/${symbol}`),

  // AI Research
  analyzeStock: (symbol: string) => fetchApi<Signal>(`/api/v1/research/analyze/${symbol}`),
  batchAnalyze: (symbols: string[]) =>
    fetchApi(`/api/v1/research/batch?symbols=${symbols.join(",")}`),

  // News (backend wraps items: {count, source, items})
  getNews: (source = "aggregated") =>
    fetchApi<{ items: NewsItem[] }>(`/api/v1/news/?source=${source}`).then(r => r.items ?? []),
  getNewsBySymbol: (symbol: string) =>
    fetchApi<{ items: NewsItem[] }>(`/api/v1/news/symbol/${symbol}`).then(r => r.items ?? []),

  // Backtest
  runBacktest: (symbol: string, strategy = "momentum") =>
    fetchApi<BacktestResult>(`/api/v1/backtest/${symbol}?strategy=${strategy}`),

  // Screener
  runScreener: (filters: { field: string; operator: string; value: number }[], logic = "AND") =>
    fetchApi(`/api/v1/screener/screen`, {
      method: "POST",
      body: JSON.stringify({ filters, logic }),
    }),
  getScreenerPresets: () => fetchApi(`/api/v1/screener/presets`),

  // Derivatives
  getOptionsChain: (symbol: string) =>
    fetchApi<OptionsChain>(`/api/v1/derivatives/options-chain/${symbol}`),
  getPCR: (symbol: string) => fetchApi(`/api/v1/derivatives/pcr/${symbol}`),
  getMaxPain: (symbol: string) => fetchApi(`/api/v1/derivatives/max-pain/${symbol}`),
  getIVSurface: (symbol: string) => fetchApi(`/api/v1/derivatives/iv-surface/${symbol}`),
  getOIAnalysis: (symbol: string) => fetchApi(`/api/v1/derivatives/oi-analysis/${symbol}`),

  // Fundamentals
  getRatios: (symbol: string) =>
    fetchApi<FundamentalsRatios>(`/api/v1/fundamentals/ratios/${symbol}`),
  getProfile: (symbol: string) => fetchApi(`/api/v1/fundamentals/profile/${symbol}`),
  getFinancials: (symbol: string, type: "income-statement" | "balance-sheet" | "cash-flow") =>
    fetchApi(`/api/v1/fundamentals/${type}/${symbol}`),
  getSnapshot: (symbol: string) => fetchApi(`/api/v1/fundamentals/snapshot/${symbol}`),

  // Sentiment
  getSentiment: (text: string) =>
    fetchApi(`/api/v1/sentiment/analyze`, { method: "POST", body: JSON.stringify({ text }) }),

  // Knowledge
  getGrahamScreen: (symbol: string) => fetchApi(`/api/v1/knowledge/graham/${symbol}`),
  getFisherQuality: (symbol: string) => fetchApi(`/api/v1/knowledge/fisher/${symbol}`),

  // Portfolio
  getPortfolioSummary: () => fetchApi<PortfolioSummary>(`/api/v1/portfolio/summary`),
  getPortfolioHistory: (days = 30) =>
    fetchApi(`/api/v1/portfolio/history?days=${days}`),
  getPortfolioPnL: () => fetchApi(`/api/v1/portfolio/pnl`),

  // Alerts
  getAlerts: () => fetchApi<AlertItem[]>(`/api/v1/alerts/`),
  createAlert: (data: { symbol: string; alert_type: string; condition: string; threshold: number; channels?: Record<string, boolean> }) =>
    fetchApi(`/api/v1/alerts/`, { method: "POST", body: JSON.stringify(data) }),
  deleteAlert: (id: number) => fetchApi(`/api/v1/alerts/${id}`, { method: "DELETE" }),

  // Trade Journal
  getJournal: () => fetchApi<JournalEntry[]>(`/api/v1/journal/`),
  createJournalEntry: (data: Partial<JournalEntry>) =>
    fetchApi(`/api/v1/journal/`, { method: "POST", body: JSON.stringify(data) }),

  // Settings
  getSettings: () => fetchApi(`/api/v1/settings/`),
  updateSettings: (data: Record<string, unknown>) =>
    fetchApi(`/api/v1/settings/`, { method: "PUT", body: JSON.stringify(data) }),

  // CRUD
  getWatchlists: () => fetchApi("/api/v1/watchlists/"),
  createWatchlist: (name: string, symbols: string[] = []) =>
    fetchApi("/api/v1/watchlists/", { method: "POST", body: JSON.stringify({ name, instrument_ids: symbols }) }),
  deleteWatchlist: (id: number) =>
    fetchApi(`/api/v1/watchlists/${id}`, { method: "DELETE" }),
  getSignals: () => fetchApi("/api/v1/signals/"),
  getOrders: () => fetchApi("/api/v1/orders/"),
  getPositions: () => fetchApi<PositionItem[]>("/api/v1/positions/"),

  // Watchlist items (detail)
  getWatchlistDetail: (id: number) => fetchApi(`/api/v1/watchlists/${id}`),
  deleteWatchlist: (id: number) => fetchApi(`/api/v1/watchlists/${id}`, { method: "DELETE" }),

  // Risk
  getRiskMetrics: () => fetchApi(`/api/v1/risk/metrics`),
  getRiskEvents: () => fetchApi(`/api/v1/risk/events`),

  // ML Predictions
  getPrediction: (symbol: string) => fetchApi(`/api/v1/ml/predict?symbol=${symbol}`),

  // Strategies
  getStrategies: () => fetchApi(`/api/v1/strategies/`),

  // Sectors
  getSectors: () => fetchApi(`/api/v1/advanced/sector-rotation`),

  // Analyst chat
  chatWithAnalyst: (message: string) =>
    fetchApi<{ reply: string }>(`/api/v1/research/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  // Scheduler
  getSchedulerStatus: () => fetchApi(`/api/v1/scheduler/status`),
  getFeed: (limit = 50) => fetchApi(`/api/v1/scheduler/feed?limit=${limit}`),

  // Advanced Analytics — FII/DII Flows
  getFiiDiiFlows: (days = 20) => fetchApi(`/api/v1/advanced/fii-dii?days=${days}`),
  getFiiDiiToday: () => fetchApi(`/api/v1/advanced/fii-dii/today`),

  // Advanced Analytics — Bulk/Block Deals
  getBulkDeals: (dealType = "all", limit = 50) =>
    fetchApi(`/api/v1/advanced/bulk-deals?deal_type=${dealType}&limit=${limit}`),
  getBulkDealsBySymbol: (symbol: string) =>
    fetchApi(`/api/v1/advanced/bulk-deals/symbol/${symbol}`),
  getSmartMoneySignals: () => fetchApi(`/api/v1/advanced/bulk-deals/smart-money`),

  // Advanced Analytics — Sector Rotation
  getSectorRotation: () => fetchApi(`/api/v1/advanced/sector-rotation`),

  // Advanced Analytics — Chart Patterns
  getChartPatterns: (symbol: string, period = "6mo") =>
    fetchApi(`/api/v1/advanced/patterns/${symbol}?period=${period}`),

  // Pro Trading — Options Strategy Builder
  listStrategies: () => fetchApi(`/api/v1/pro/strategies/list`),
  buildStrategy: (symbol: string, strategy: string, width = 100) =>
    fetchApi(`/api/v1/pro/strategies/build/${symbol}?strategy=${strategy}&width=${width}`),

  // Pro Trading — Earnings Calendar
  getUpcomingEarnings: (days = 30) => fetchApi(`/api/v1/pro/earnings/upcoming?days=${days}`),
  getEarningsReaction: (symbol: string) => fetchApi(`/api/v1/pro/earnings/reaction/${symbol}`),

  // Pro Trading — Market Breadth & Heatmap
  getMarketBreadth: () => fetchApi(`/api/v1/pro/breadth`),

  // Pro Trading — Multi-Timeframe Analysis
  getMultiTimeframe: (symbol: string) => fetchApi(`/api/v1/pro/multi-timeframe/${symbol}`),

  // Pro Trading — Portfolio Correlation
  getPortfolioCorrelation: (symbols: string[], period = "6mo") =>
    fetchApi(`/api/v1/pro/correlation`, {
      method: "POST",
      body: JSON.stringify({ symbols, period }),
    }),

  // Pro Trading — TradingView Webhook
  getWebhookHistory: (limit = 50) => fetchApi(`/api/v1/pro/webhook/history?limit=${limit}`),

  // Pro Trading — Audit Log
  getAuditLog: (limit = 100) => fetchApi(`/api/v1/pro/audit?limit=${limit}`),
  getAuditSummary: () => fetchApi(`/api/v1/pro/audit/summary`),
};

