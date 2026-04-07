import { BarChart3, Newspaper, Users, TrendingUp, Eye, Building2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { StockSignal, CrowdVsInsiders } from "../types";

interface InsiderTransaction {
  name: string;
  title: string;
  type: "Buy" | "Sell" | "Other";
  shares: number;
  price: number | null;
  value: number | null;
  date: string;
  days_ago: number;
}

interface InsiderData {
  score: number;
  buy_shares: number;
  sell_shares: number;
  transaction_count: number;
  transactions: InsiderTransaction[];
  error?: string;
}

function InsiderTradesBlock({ ticker }: { ticker: string }) {
  const [data, setData] = useState<InsiderData | null>(null);

  useEffect(() => {
    setData(null);
    fetch(`/api/insider/${ticker}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, [ticker]);

  if (!data) {
    return (
      <div className="detail-section">
        <h4 className="section-title">
          <Building2 size={13} style={{ display: "inline", marginRight: 5 }} />
          SEC Insider Trades
        </h4>
        <p className="cvi-description">Loading…</p>
      </div>
    );
  }

  if (data.error || data.transaction_count === 0) {
    return (
      <div className="detail-section">
        <h4 className="section-title">
          <Building2 size={13} style={{ display: "inline", marginRight: 5 }} />
          SEC Insider Trades
        </h4>
        <p className="cvi-description">
          {data.error ?? "No filings in the last 90 days."}
        </p>
      </div>
    );
  }

  const fmt = (n: number) =>
    n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n / 1e3).toFixed(0)}K` : `$${n}`;

  return (
    <div className="detail-section">
      <h4 className="section-title">
        <Building2 size={13} style={{ display: "inline", marginRight: 5 }} />
        SEC Insider Trades
        <span className="panel-meta" style={{ marginLeft: 8 }}>
          last 90 days
        </span>
      </h4>
      <div className="insider-summary">
        <span className="text-gain">
          ▲ {data.buy_shares.toLocaleString()} bought
        </span>
        <span className="text-loss">
          ▼ {data.sell_shares.toLocaleString()} sold
        </span>
      </div>
      <ul className="insider-list">
        {data.transactions.slice(0, 6).map((t, i) => (
          <li key={i} className="insider-item">
            <span className={`insider-type ${t.type === "Buy" ? "text-gain" : t.type === "Sell" ? "text-loss" : "text-dim"}`}>
              {t.type === "Buy" ? "▲" : t.type === "Sell" ? "▼" : "·"}
            </span>
            <span className="insider-name">{t.name}</span>
            <span className="insider-meta">
              {t.title ? `${t.title} · ` : ""}
              {t.shares.toLocaleString()} shares
              {t.value ? ` · ${fmt(t.value)}` : ""}
              {" · "}{t.days_ago}d ago
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

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

function CrowdVsInsidersBlock({ cvi }: { cvi: CrowdVsInsiders }) {
  const labelClass = {
    "Insiders Ahead":   "cvi-insiders-ahead",
    "Broad Confidence": "cvi-broad-bull",
    "Crowd Peak":       "cvi-crowd-peak",
    "Insiders Out":     "cvi-insiders-out",
    "Broad Selloff":    "cvi-broad-bear",
    "Neutral":          "cvi-neutral",
    "Mixed":            "cvi-mixed",
  }[cvi.label] ?? "cvi-mixed";

  // Map score -1..+1 to 0..100% for the gauge bars
  const insiderPct = ((cvi.insider_score + 1) / 2) * 100;
  const crowdPct   = ((cvi.crowd_score   + 1) / 2) * 100;

  return (
    <div className="detail-section">
      <h4 className="section-title">
        <Eye size={13} style={{ display: "inline", marginRight: 5 }} />
        Crowd vs. Insiders
      </h4>
      <div className="cvi-verdict">
        <span className={`cvi-badge cvi-badge-lg ${labelClass}`}>{cvi.label}</span>
        <p className="cvi-description">{cvi.description}</p>
      </div>
      <div className="cvi-bars">
        <div className="cvi-bar-row">
          <span className="cvi-bar-label">Insiders</span>
          <div className="cvi-bar-track">
            <div className="cvi-bar-center" />
            <div
              className={`cvi-bar-fill ${cvi.insider_score >= 0 ? "positive" : "negative"}`}
              style={{
                left:  cvi.insider_score >= 0 ? "50%" : `${insiderPct}%`,
                width: `${Math.abs(insiderPct - 50)}%`,
              }}
            />
          </div>
          <span className={`cvi-bar-val ${cvi.insider_score >= 0 ? "text-gain" : "text-loss"}`}>
            {cvi.insider_score >= 0 ? "+" : ""}{cvi.insider_score.toFixed(2)}
          </span>
        </div>
        <div className="cvi-bar-row">
          <span className="cvi-bar-label">Crowd</span>
          <div className="cvi-bar-track">
            <div className="cvi-bar-center" />
            <div
              className={`cvi-bar-fill ${cvi.crowd_score >= 0 ? "positive" : "negative"}`}
              style={{
                left:  cvi.crowd_score >= 0 ? "50%" : `${crowdPct}%`,
                width: `${Math.abs(crowdPct - 50)}%`,
              }}
            />
          </div>
          <span className={`cvi-bar-val ${cvi.crowd_score >= 0 ? "text-gain" : "text-loss"}`}>
            {cvi.crowd_score >= 0 ? "+" : ""}{cvi.crowd_score.toFixed(2)}
          </span>
        </div>
      </div>
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

        {/* Crowd vs Insiders */}
        {signal.crowd_vs_insiders && (
          <CrowdVsInsidersBlock cvi={signal.crowd_vs_insiders} />
        )}

        {/* SEC Form 4 insider trades */}
        <InsiderTradesBlock ticker={signal.ticker} />

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
