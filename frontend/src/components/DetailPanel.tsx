import { BarChart3, Newspaper, Users, TrendingUp, Eye, Building2, FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
import type { StockSignal, CrowdVsInsiders, QuantData } from "../types";
import { COMPANY_NAMES } from "../constants";

function signalBadgeClass(signal: string): string {
  switch (signal) {
    case "STRONG BUY":  return "signal-strong-buy";
    case "BUY":         return "signal-buy";
    case "SELL":        return "signal-sell";
    case "STRONG SELL": return "signal-strong-sell";
    default:            return "signal-hold";
  }
}

function signalLabel(signal: string): string {
  switch (signal) {
    case "STRONG BUY":  return "Strong Buy";
    case "BUY":         return "Buy";
    case "SELL":        return "Sell";
    case "STRONG SELL": return "Strong Sell";
    default:            return "Hold";
  }
}

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
    fetch(`${API_BASE}/api/insider/${ticker}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({ score: 0, buy_shares: 0, sell_shares: 0, transaction_count: 0, transactions: [], error: "Failed to load" }));
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

function scoreVerdict(value: number, dimension: string): string {
  const strong = Math.abs(value) >= 0.3;
  const mild   = Math.abs(value) >= 0.1;
  const bull   = value >= 0;

  const map: Record<string, [string, string, string, string]> = {
    news:      ["Very positive news coverage", "Mostly positive coverage", "Mostly negative coverage", "Very negative news coverage"],
    social:    ["Retail crowd strongly bullish", "Retail crowd leaning bullish", "Retail crowd leaning bearish", "Retail crowd strongly bearish"],
    political: ["Congressional insiders buying heavily", "Some insider buying activity", "Some insider selling activity", "Congressional insiders selling heavily"],
    momentum:  ["Strong upward price momentum", "Mild upward momentum", "Mild downward momentum", "Strong downward pressure"],
    quant:     ["Models strongly agree: buy", "Models lean bullish", "Models lean bearish", "Models strongly agree: sell"],
  };

  const [sb, mb, ms, ss] = map[dimension] ?? ["Strongly positive", "Mildly positive", "Mildly negative", "Strongly negative"];
  if (!mild) return "Neutral — no clear signal";
  if (bull) return strong ? sb : mb;
  return strong ? ss : ms;
}

function ScoreBar({ label, value, icon, dimension }: {
  label: string;
  value: number;
  icon: React.ReactNode;
  dimension: string;
}) {
  const pct        = ((value + 1) / 2) * 100;
  const isPositive = value >= 0;
  const verdict    = scoreVerdict(value, dimension);

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
          style={{ left: isPositive ? "50%" : `${pct}%`, width: `${Math.abs(pct - 50)}%` }}
        />
      </div>
      <span className="score-verdict">{verdict}</span>
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

// Mean Reversion and trend-following indicators naturally conflict:
// a crashing stock is "oversold" (reversion = buy) but also in a downtrend (momentum = sell).
// We split the display so both stories are visible rather than averaging them to "neutral".
const MEAN_REVERSION_NAMES = new Set(["Mean Reversion", "Bollinger %B"]);
const TREND_NAMES           = new Set(["MACD", "OBV Trend"]);

function QuantAnalysisBlock({ quant }: { quant: QuantData }) {
  const reversion = quant.signals.filter(s => MEAN_REVERSION_NAMES.has(s.name));
  const trend     = quant.signals.filter(s => TREND_NAMES.has(s.name));

  const avgScore = (list: typeof quant.signals) =>
    list.length ? list.reduce((a, s) => a + s.score, 0) / list.length : 0;

  const revScore  = avgScore(reversion);
  const trendScore = avgScore(trend);

  const badge = (score: number) =>
    score >= 0.2 ? { text: "Bullish",  cls: "text-gain" }
  : score <= -0.2 ? { text: "Bearish",  cls: "text-loss" }
  : { text: "Mixed",   cls: "text-dim" };

  const IndicatorRow = ({ s }: { s: typeof quant.signals[0] }) => (
    <div className="quant-indicator-row">
      <span className={`quant-indicator-dot ${s.bullish ? "quant-dot-bull" : Math.abs(s.score) < 0.05 ? "quant-dot-neutral" : "quant-dot-bear"}`} />
      <span className="quant-indicator-name">{s.name}</span>
      <span className="quant-indicator-verdict">{s.verdict}</span>
    </div>
  );

  return (
    <div className="detail-section">
      <h4 className="section-title">
        <FlaskConical size={13} style={{ display: "inline", marginRight: 5 }} />
        Quantitative Analysis
      </h4>

      {/* Mean Reversion group */}
      <p className="quant-group-label">
        Mean Reversion
        <span className={`quant-composite-badge ${badge(revScore).cls}`}>
          {badge(revScore).text}
        </span>
      </p>
      <div className="quant-indicators">
        {reversion.map(s => <IndicatorRow key={s.name} s={s} />)}
      </div>

      {/* Trend / Momentum group */}
      <p className="quant-group-label" style={{ marginTop: 10 }}>
        Trend &amp; Momentum
        <span className={`quant-composite-badge ${badge(trendScore).cls}`}>
          {badge(trendScore).text}
        </span>
      </p>
      <div className="quant-indicators">
        {trend.map(s => <IndicatorRow key={s.name} s={s} />)}
      </div>

      {/* Raw metrics */}
      <div className="quant-metrics">
        <div className="quant-metric">
          <span className="quant-metric-label">Z-Score</span>
          <span className={`quant-metric-value ${quant.zscore <= -1 ? "text-gain" : quant.zscore >= 1 ? "text-loss" : "text-dim"}`}>
            {quant.zscore.toFixed(2)}
          </span>
        </div>
        <div className="quant-metric">
          <span className="quant-metric-label">Bollinger %B</span>
          <span className={`quant-metric-value ${quant.pct_b < 0.2 ? "text-gain" : quant.pct_b > 0.8 ? "text-loss" : "text-dim"}`}>
            {(quant.pct_b * 100).toFixed(0)}%
          </span>
        </div>
        <div className="quant-metric">
          <span className="quant-metric-label">OBV Slope</span>
          <span className={`quant-metric-value ${quant.obv_slope > 0 ? "text-gain" : quant.obv_slope < 0 ? "text-loss" : "text-dim"}`}>
            {quant.obv_slope >= 0 ? "+" : ""}{quant.obv_slope.toFixed(3)}
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
        <div className="empty-detail">
          <p>Select a stock to see the full breakdown.</p>
          <p className="empty-detail-hint">Pick any row in the Screener or any ticker in the Watchlist.</p>
        </div>
      </div>
    );
  }

  const change = signal.change_pct ?? 0;
  const positive = change >= 0;
  const price = signal.price;

  return (
    <div className="panel detail-panel">
      {/* Hero — ticker, company, price, change, signal badge */}
      <div className="detail-hero">
        <div className="hero-identity">
          <div className="hero-ticker-row">
            <span className="hero-ticker">{signal.ticker}</span>
            <span className={`signal-badge ${signalBadgeClass(signal.signal)}`}>
              {signalLabel(signal.signal)}
            </span>
          </div>
          <span className="hero-company">{COMPANY_NAMES[signal.ticker] ?? ""}</span>
        </div>
        <div className="hero-prices">
          <span className="hero-price">
            {price != null ? `$${price.toFixed(2)}` : "—"}
          </span>
          <span className={`hero-change ${positive ? "text-gain" : "text-loss"}`}>
            {signal.change_pct != null
              ? `${positive ? "+" : ""}${change.toFixed(2)}%`
              : "—"}
          </span>
        </div>
        <div className="hero-meta">
          <span className="hero-meta-item">
            Confidence <strong>{(signal.confidence * 100).toFixed(0)}%</strong>
          </span>
          <span className="hero-meta-sep">·</span>
          <span className="hero-meta-item">
            Composite <strong className={signal.score >= 0 ? "text-gain" : "text-loss"}>
              {signal.score >= 0 ? "+" : ""}{signal.score.toFixed(3)}
            </strong>
          </span>
        </div>
      </div>

      <div className="detail-content">
        {/* Score breakdown */}
        <div className="detail-section">
          <h4 className="section-title">Signal Composition</h4>
          <ScoreBar label="News Coverage"         value={signal.breakdown.news}      icon={<Newspaper    size={13} />} dimension="news" />
          <ScoreBar label="Social Media Mood"     value={signal.breakdown.social}    icon={<Users        size={13} />} dimension="social" />
          <ScoreBar label="Congressional Trades"  value={signal.breakdown.political} icon={<BarChart3    size={13} />} dimension="political" />
          <ScoreBar label="Price Momentum"        value={signal.breakdown.momentum}  icon={<TrendingUp   size={13} />} dimension="momentum" />
          <ScoreBar label="Quant Models"          value={signal.breakdown.quant ?? 0} icon={<FlaskConical size={13} />} dimension="quant" />
        </div>

        {/* Quantitative analysis detail */}
        {signal.quant && signal.quant.signals.length > 0 && (
          <QuantAnalysisBlock quant={signal.quant} />
        )}

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
