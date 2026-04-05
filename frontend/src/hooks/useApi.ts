import { useState, useEffect } from "react";
import type { StockSignal, MarketOverview, NewsItem } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function useSignals() {
  const [data, setData] = useState<StockSignal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchJson<StockSignal[]>("/api/signals")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}

export function useOverview() {
  const [data, setData] = useState<MarketOverview | null>(null);

  useEffect(() => {
    fetchJson<MarketOverview>("/api/overview")
      .then(setData)
      .catch(console.error);
  }, []);

  return data;
}

export function useNews(ticker?: string) {
  const [data, setData] = useState<NewsItem[]>([]);

  useEffect(() => {
    const path = ticker ? `/api/news?ticker=${ticker}` : "/api/news";
    fetchJson<NewsItem[]>(path).then(setData).catch(console.error);
  }, [ticker]);

  return data;
}
