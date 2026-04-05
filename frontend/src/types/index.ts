export interface Breakdown {
  news: number;
  social: number;
  political: number;
  momentum: number;
}

export interface StockSignal {
  ticker: string;
  price: number | null;
  change_pct: number | null;
  signal: string;
  score: number;
  confidence: number;
  breakdown: Breakdown;
  headlines: string[];
  politician_activity: string;
  volume: number | null;
  day_high: number | null;
  day_low: number | null;
  market_cap: number | null;
  timestamp: string;
}

export interface MarketOverview {
  total_stocks: number;
  buy_count: number;
  sell_count: number;
  hold_count: number;
  strong_buy_count: number;
  strong_sell_count: number;
  market_sentiment: string;
  last_updated: string;
}

export interface NewsItem {
  title: string;
  source: string;
  published: string;
  link: string;
}

export type SignalType = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";
