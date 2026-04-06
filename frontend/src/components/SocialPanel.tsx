import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, MessageCircle, ExternalLink } from "lucide-react";
import type { StockSignal } from "../types";

interface SocialData {
  score: number;
  reddit_score: number;
  stocktwits_score: number;
  stocktwits_labeled_score: number;
  post_count: number;
  message_count: number;
  bull_ratio: number;
  bullish_count: number;
  bearish_count: number;
  top_posts: { title: string; score: number; subreddit: string; url: string }[];
  subreddits: string[];
}

interface SocialPanelProps {
  signals: Record<string, StockSignal>;
  selectedTicker: string | null;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function SocialCard({ ticker }: { ticker: string }) {
  const [data, setData] = useState<SocialData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/social/${ticker}`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return (
      <div className="social-card">
        <div className="social-card-header">
          <span className="social-ticker">{ticker}</span>
        </div>
        <div className="social-loading">Fetching social data...</div>
      </div>
    );
  }

  if (!data) return null;

  const bullPct = Math.round(data.bull_ratio * 100);
  const bearPct = 100 - bullPct;
  const scoreColor = data.score > 0.1 ? "#22c55e" : data.score < -0.1 ? "#ef4444" : "#f59e0b";

  return (
    <div className="social-card">
      <div className="social-card-header">
        <span className="social-ticker">{ticker}</span>
        <span className="social-score" style={{ color: scoreColor }}>
          {data.score >= 0 ? "+" : ""}{data.score.toFixed(3)}
        </span>
      </div>

      {/* Bull/Bear gauge */}
      <div className="bull-bear-bar">
        <div
          className="bull-segment"
          style={{ width: `${bullPct}%` }}
          title={`Bullish: ${bullPct}%`}
        />
        <div
          className="bear-segment"
          style={{ width: `${bearPct}%` }}
          title={`Bearish: ${bearPct}%`}
        />
      </div>
      <div className="bull-bear-labels">
        <span className="bull-label">
          <TrendingUp size={11} /> {data.bullish_count} Bullish ({bullPct}%)
        </span>
        <span className="bear-label">
          <TrendingDown size={11} /> {data.bearish_count} Bearish ({bearPct}%)
        </span>
      </div>

      {/* Sources */}
      <div className="social-sources">
        <div className="source-stat">
          <span className="source-label">Reddit</span>
          <span className="source-value">{data.post_count} posts</span>
          <span
            className="source-score"
            style={{ color: data.reddit_score >= 0 ? "#22c55e" : "#ef4444" }}
          >
            {data.reddit_score >= 0 ? "+" : ""}{data.reddit_score.toFixed(3)}
          </span>
        </div>
        <div className="source-stat">
          <span className="source-label">StockTwits</span>
          <span className="source-value">{data.message_count} msgs</span>
          <span
            className="source-score"
            style={{ color: data.stocktwits_score >= 0 ? "#22c55e" : "#ef4444" }}
          >
            {data.stocktwits_score >= 0 ? "+" : ""}{data.stocktwits_score.toFixed(3)}
          </span>
        </div>
      </div>

      {/* Top Reddit posts */}
      {data.top_posts.length > 0 && (
        <div className="top-posts">
          <div className="top-posts-title">Top Posts</div>
          {data.top_posts.slice(0, 3).map((post, i) => (
            <a
              key={i}
              href={post.url}
              target="_blank"
              rel="noreferrer"
              className="post-item"
            >
              <MessageCircle size={10} className="post-icon" />
              <span className="post-title">{post.title}</span>
              <span className="post-meta">
                r/{post.subreddit} · ▲{post.score}
              </span>
              <ExternalLink size={9} className="post-link" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export function SocialPanel({ signals, selectedTicker }: SocialPanelProps) {
  const tickers = selectedTicker
    ? [selectedTicker]
    : Object.keys(signals).slice(0, 6); // Show top 6 if none selected

  return (
    <div className="social-panel">
      <div className="panel-header">
        <span className="panel-title">Social Sentiment</span>
        <span className="panel-meta">Reddit · StockTwits</span>
      </div>
      <div className="social-grid">
        {tickers.map((t) => (
          <SocialCard key={t} ticker={t} />
        ))}
        {tickers.length === 0 && (
          <div className="empty-state">No tickers selected.</div>
        )}
      </div>
    </div>
  );
}
