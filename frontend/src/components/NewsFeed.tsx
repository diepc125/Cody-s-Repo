import { ExternalLink } from "lucide-react";
import type { StockSignal } from "../types";

interface NewsFeedProps {
  signals: Record<string, StockSignal>;
}

interface HeadlineEntry {
  ticker: string;
  headline: string;
}

export function NewsFeed({ signals }: NewsFeedProps) {
  // Collect all headlines across tickers
  const allHeadlines: HeadlineEntry[] = [];
  for (const sig of Object.values(signals)) {
    for (const h of sig.headlines) {
      allHeadlines.push({ ticker: sig.ticker, headline: h });
    }
  }

  return (
    <div className="panel news-panel">
      <div className="panel-header">
        <span className="panel-title">Market Headlines</span>
        <span className="panel-meta">{allHeadlines.length} stories</span>
      </div>
      <div className="news-list">
        {allHeadlines.length === 0 && (
          <div className="empty-state">No headlines available.</div>
        )}
        {allHeadlines.slice(0, 15).map((item, i) => (
          <div key={i} className="news-item">
            <span className="news-ticker">{item.ticker}</span>
            <span className="news-headline">{item.headline}</span>
            <ExternalLink size={11} className="news-link-icon" />
          </div>
        ))}
      </div>
    </div>
  );
}
