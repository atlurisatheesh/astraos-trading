// AstraOS — Global State Store (Zustand)

import { create } from "zustand";

interface AppState {
  // Auth
  token: string | null;
  user: { email: string; full_name: string; role: string } | null;
  setToken: (token: string | null) => void;
  setUser: (user: AppState["user"]) => void;
  logout: () => void;

  // Market
  selectedSymbol: string;
  setSelectedSymbol: (symbol: string) => void;

  // Mode
  tradingMode: "paper" | "live";
  setTradingMode: (mode: "paper" | "live") => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Auth
  token: typeof window !== "undefined" ? localStorage.getItem("token") : null,
  user: null,
  setToken: (token) => {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
    set({ token });
  },
  setUser: (user) => set({ user }),
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null });
  },

  // Market
  selectedSymbol: "RELIANCE",
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),

  // Mode
  tradingMode: "paper",
  setTradingMode: (mode) => set({ tradingMode: mode }),
}));
