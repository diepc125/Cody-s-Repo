import type { StockSignal } from "../types";

interface Props {
  signals: Record<string, StockSignal>;
}

export function ScreenerSummary({ signals }: Props) {
  const values = Object.values(signals);
  if (values.length === 0) return null;

  const buy  = values.filter(s => s.signal === "BUY"  || s.signal === "STRONG BUY").length;
  const sell = values.filter(s => s.signal === "SELL" || s.signal === "STRONG SELL").length;
  const hold = values.filter(s => s.signal === "HOLD").length;

  const avgScore = values.reduce((sum, s) => sum + s.score, 0) / values.length;
  const positive = avgScore >= 0;

  const sentiment =
    avgScore >  0.20 ? "Bullish"
  : avgScore < -0.20 ? "Bearish"
  : "Neutral";

  const gainers = values.filter(s => (s.change_pct ?? 0) > 0).length;
  const losers  = values.filter(s => (s.change_pct ?? 0) < 0).length;

  return (
    <div className="screener-summary">
      <div className="summary-block">
        <span className="summary-label">Composite</span>
        <span className={`summary-value-lg ${positive ? "text-gain" : "text-loss"}`}>
          {positive ? "+" : ""}{avgScore.toFixed(3)}
        </span>
        <span className="summary-sublabel">{sentiment}</span>
      </div>

      <div className="summary-divider" />

      <div className="summary-block">
        <span className="summary-label">Signals</span>
        <div className="summary-row">
          <span className="summary-pill"><strong className="text-gain">{buy}</strong> Buy</span>
          <span className="summary-pill"><strong>{hold}</strong> Hold</span>
          <span className="summary-pill"><strong className="text-loss">{sell}</strong> Sell</span>
        </div>
      </div>

      <div className="summary-divider" />

      <div className="summary-block">
        <span className="summary-label">Today</span>
        <div className="summary-row">
          <span className="summary-pill"><strong className="text-gain">{gainers}</strong> up</span>
          <span className="summary-pill"><strong className="text-loss">{losers}</strong> down</span>
        </div>
      </div>
    </div>
  );
}
