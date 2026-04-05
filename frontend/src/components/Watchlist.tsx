import type { StockSignal } from "../types";

interface WatchlistProps {
  signals: Record<string, StockSignal>;
  onSelect: (ticker: string) => void;
  selected: string | null;
}

export function Watchlist({ signals, onSelect, selected }: WatchlistProps) {
  const sorted = Object.values(signals).sort((a, b) =>
    a.ticker.localeCompare(b.ticker)
  );

  return (
    <div className="panel watchlist-panel">
      <div className="panel-header">
        <span className="panel-title">Watchlist</span>
      </div>
      <div className="watchlist">
        {sorted.map((s) => (
          <div
            key={s.ticker}
            className={`watchlist-item ${selected === s.ticker ? "selected" : ""}`}
            onClick={() => onSelect(s.ticker)}
          >
            <div className="watchlist-left">
              <span className="watchlist-ticker">{s.ticker}</span>
              <span className="watchlist-price">
                {s.price != null ? `$${s.price.toFixed(2)}` : "—"}
              </span>
            </div>
            <div className="watchlist-right">
              <span
                className={`watchlist-change ${
                  (s.change_pct ?? 0) >= 0 ? "text-gain" : "text-loss"
                }`}
              >
                {s.change_pct != null
                  ? `${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`
                  : "—"}
              </span>
            </div>
          </div>
        ))}
        {sorted.length === 0 && (
          <div className="empty-state">Loading watchlist...</div>
        )}
      </div>
    </div>
  );
}
