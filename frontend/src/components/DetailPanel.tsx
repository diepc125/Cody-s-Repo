import { BarChart3, Newspaper, Users, TrendingUp } from "lucide-react";
import type { StockSignal } from "../types";

interface DetailPanelProps {
  signal: StockSignal | null;
}

function ScoreBar({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  const pct = ((value + 1) / 2) * 100; // map -1..+1 to 0..100%
  const isPositive = value >= 0;

  return (
    <div className="score-row">
      <div className="score-label">
        {icon}
        <span>{label}</span>
      </div>
      <div className="score-bar-track">
        <div className="score-bar-center" />
        <div
          className={`score-bar-fill ${isPositive ? "positive" : "negative"}`}
          style={{
            left: isPositive ? "50%" : `${pct}%`,
            width: `${Math.abs(pct - 50)}%`,
          }}
        />
      </div>
      <span className={`score-value ${isPositive ? "text-gain" : "text-loss"}`}>
        {value >= 0 ? "+" : ""}
        {value.toFixed(2)}
      </span>
    </div>
  );
}

export function DetailPanel({ signal }: DetailPanelProps) {
  if (!signal) {
    return (
      <div className="panel detail-panel">
        <div className="panel-header">
          <span className="panel-title">Details</span>
        </div>
        <div className="empty-detail">
          Select an instrument from the screener to view analysis breakdown.
        </div>
      </div>
    );
  }

  return (
    <div className="panel detail-panel">
      <div className="panel-header">
        <span className="panel-title">{signal.ticker} — Analysis</span>
        <span className="panel-meta">
          {new Date(signal.timestamp).toLocaleTimeString()}
        </span>
      </div>

      <div className="detail-content">
        {/* Score breakdown */}
        <div className="detail-section">
          <h4 className="section-title">Signal Breakdown</h4>
          <ScoreBar
            label="News Sentiment"
            value={signal.breakdown.news}
            icon={<Newspaper size={13} />}
          />
          <ScoreBar
            label="Social Sentiment"
            value={signal.breakdown.social}
            icon={<Users size={13} />}
          />
          <ScoreBar
            label="Political Activity"
            value={signal.breakdown.political}
            icon={<BarChart3 size={13} />}
          />
          <ScoreBar
            label="Price Momentum"
            value={signal.breakdown.momentum}
            icon={<TrendingUp size={13} />}
          />
        </div>

        {/* Price info */}
        {signal.price != null && (
          <div className="detail-section">
            <h4 className="section-title">Price Action</h4>
            <div className="detail-grid">
              <div className="detail-stat">
                <span className="stat-label">Day High</span>
                <span className="stat-value">
                  {signal.day_high != null ? `$${signal.day_high.toFixed(2)}` : "—"}
                </span>
              </div>
              <div className="detail-stat">
                <span className="stat-label">Day Low</span>
                <span className="stat-value">
                  {signal.day_low != null ? `$${signal.day_low.toFixed(2)}` : "—"}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Politician activity */}
        {signal.politician_activity && (
          <div className="detail-section">
            <h4 className="section-title">Congressional Activity</h4>
            <p className="detail-text">{signal.politician_activity}</p>
          </div>
        )}

        {/* Headlines */}
        {signal.headlines.length > 0 && (
          <div className="detail-section">
            <h4 className="section-title">Recent Headlines</h4>
            <ul className="headline-list">
              {signal.headlines.map((h, i) => (
                <li key={i} className="headline-item">
                  {h}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
