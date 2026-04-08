export interface Breakdown {
  news: number;
  social: number;
  political: number;
  momentum: number;
  quant: number;
}

export interface QuantSignalItem {
  name: string;
  verdict: string;
  score: number;
  value: number;
  bullish: boolean;
}

export interface QuantData {
  score: number;
  zscore: number;
  macd_histogram: number;
  pct_b: number;
  obv_slope: number;
  signals: QuantSignalItem[];
}

export interface CrowdVsInsiders {
  label: string;
  divergence: number;
  insider_score: number;
  crowd_score: number;
  description: string;
}

export interface StockSignal {
  ticker: string;
  price: number | null;
  change_pct: number | null;
  signal: string;
  score: number;
  confidence: number;
  breakdown: Breakdown;
  quant?: QuantData;
  crowd_vs_insiders: CrowdVsInsiders;
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
