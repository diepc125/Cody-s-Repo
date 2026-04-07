import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Clock, AlertCircle } from "lucide-react";
import type { StockSignal } from "../types";

interface SocialData {
  score: number;
  reddit_score: number;
  post_count: number;
  message_count: number;
  bull_ratio: number;
  bullish_count: number;
  bearish_count: number;
  top_posts: { title: string; score: number; subreddit: string; url: string }[];
}

interface SocialPanelProps {
  signals: Record<string, StockSignal>;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function moodLabel(score: number): { text: string; cls: string } {
  if (score >= 0.3)  return { text: "Very Bullish",  cls: "mood-strong-bull" };
  if (score >= 0.1)  return { text: "Leaning Bullish", cls: "mood-bull" };
  if (score <= -0.3) return { text: "Very Bearish",   cls: "mood-strong-bear" };
  if (score <= -0.1) return { text: "Leaning Bearish", cls: "mood-bear" };
  return { text: "Neutral", cls: "mood-neutral" };
}

function SocialCard({ ticker }: { ticker: string }) {
  const [data, setData]       = useState<SocialData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/social/${ticker}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [ticker]);

  const hasData = data && (data.post_count > 0 || data.message_count > 0);
  // Derive bull% from composite score (-1 to +1) so it reflects Reddit NLP,
  // not just StockTwits labels (which default to 50/50 when unavailable).
  const bullPct = hasData
    ? Math.min(100, Math.max(0, Math.round((data!.score + 1) / 2 * 100)))
    : 50;
  const bearPct = 100 - bullPct;
  const mood    = data ? moodLabel(data.score) : null;

  return (
    <div className="social-card">
      {/* Card header */}
      <div className="social-card-header">
        <span className="social-ticker">{ticker}</span>
        {mood && !loading && hasData && (
          <span className={`social-mood ${mood.cls}`}>{mood.text}</span>
        )}
      </div>

      {loading && (
        <div className="social-placeholder">Loading…</div>
      )}

      {!loading && !hasData && (
        <div className="social-no-data">
          <Clock size={16} className="social-no-data-icon" />
          <p>No social data yet.</p>
          <p className="social-no-data-hint">
            Reddit is fetched once per hour to avoid rate limits.
            Check back shortly.
          </p>
        </div>
      )}

      {!loading && hasData && data && (
        <>
          {/* Bull / Bear gauge */}
          <div className="social-gauge-wrap">
            <div className="social-gauge">
              <div className="gauge-bull" style={{ width: `${bullPct}%` }} />
              <div className="gauge-bear" style={{ width: `${bearPct}%` }} />
            </div>
            <div className="gauge-labels">
              <span className="gauge-bull-label">
                <TrendingUp size={13} /> {bullPct}% Bullish
              </span>
              <span className="gauge-bear-label">
                {bearPct}% Bearish <TrendingDown size={13} />
              </span>
            </div>
          </div>

          {/* Stats row */}
          <div className="social-stats">
            <div className="social-stat">
              <span className="social-stat-value">{data.post_count}</span>
              <span className="social-stat-label">Reddit posts</span>
            </div>
            <div className="social-stat-divider" />
            <div className="social-stat">
              <span className="social-stat-value">{data.message_count}</span>
              <span className="social-stat-label">StockTwits msgs</span>
            </div>
          </div>

          {/* Top posts */}
          {data.top_posts.length > 0 && (
            <div className="social-posts">
              <p className="social-posts-heading">Top Threads</p>
              {data.top_posts.slice(0, 3).map((post, i) => (
                <a
                  key={i}
                  href={post.url}
                  target="_blank"
                  rel="noreferrer"
                  className="social-post-link"
                >
                  <span className="social-post-title">{post.title}</span>
                  <span className="social-post-meta">
                    r/{post.subreddit} · ▲{post.score}
                  </span>
                </a>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function SocialPanel({ signals }: SocialPanelProps) {
  const tickers = Object.keys(signals);

  return (
    <div className="social-panel">
      <div className="panel-header">
        <span className="panel-title">Social Buzz</span>
        <span className="panel-meta" style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <Clock size={12} /> Reddit refreshes hourly
        </span>
      </div>

      {tickers.length === 0 ? (
        <div className="social-empty-full">
          <AlertCircle size={28} />
          <p>Waiting for market data…</p>
        </div>
      ) : (
        <div className="social-grid">
          {tickers.map((t) => <SocialCard key={t} ticker={t} />)}
        </div>
      )}
    </div>
  );
}
