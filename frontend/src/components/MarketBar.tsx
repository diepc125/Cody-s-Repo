import type { StockSignal } from "../types";

interface MarketBarProps {
  signals: Record<string, StockSignal>;
}

export function MarketBar({ signals }: MarketBarProps) {
  const values = Object.values(signals);
  const buyCount = values.filter(
    (s) => s.signal === "BUY" || s.signal === "STRONG BUY"
  ).length;
  const sellCount = values.filter(
    (s) => s.signal === "SELL" || s.signal === "STRONG SELL"
  ).length;
  const holdCount = values.filter((s) => s.signal === "HOLD").length;

  const avgScore =
    values.length > 0
      ? values.reduce((sum, s) => sum + s.score, 0) / values.length
      : 0;

  const sentiment =
    avgScore > 0.15 ? "Bullish" : avgScore < -0.15 ? "Bearish" : "Neutral";
  const sentimentClass =
    avgScore > 0.15 ? "bullish" : avgScore < -0.15 ? "bearish" : "neutral";

  return (
    <div className="market-bar">
      <div className="market-bar-item">
        <span className="market-bar-label">Market</span>
        <span className={`market-bar-value sentiment-${sentimentClass}`}>
          {sentiment}
        </span>
      </div>

      <div className="market-bar-item">
        <span className="market-bar-label">Composite</span>
        <span
          className={`market-bar-value ${avgScore >= 0 ? "text-gain" : "text-loss"}`}
        >
          {avgScore >= 0 ? "+" : ""}
          {avgScore.toFixed(3)}
        </span>
      </div>

      <div className="market-bar-item market-bar-signals">
        <span className="market-bar-label">Signals</span>
        <span className="market-bar-value">
          <span className="text-gain">{buyCount}</span>
          <span className="market-bar-sep">·</span>
          <span className="text-muted">{holdCount}</span>
          <span className="market-bar-sep">·</span>
          <span className="text-loss">{sellCount}</span>
        </span>
      </div>
    </div>
  );
}
