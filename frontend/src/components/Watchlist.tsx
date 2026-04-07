import type { StockSignal } from "../types";

interface WatchlistProps {
  signals: Record<string, StockSignal>;
  onSelect: (ticker: string) => void;
  selected: string | null;
}

function signalDotClass(signal: string): string {
  switch (signal) {
    case "STRONG BUY":  return "dot-strong-buy";
    case "BUY":         return "dot-buy";
    case "SELL":        return "dot-sell";
    case "STRONG SELL": return "dot-strong-sell";
    default:            return "dot-hold";
  }
}

export function Watchlist({ signals, onSelect, selected }: WatchlistProps) {
  const sorted = Object.values(signals).sort((a, b) =>
    a.ticker.localeCompare(b.ticker)
  );

  return (
    <div className="watchlist-panel">
      <div className="watchlist-heading">Watchlist</div>
      <div className="watchlist">
        {sorted.map((s) => (
          <div
            key={s.ticker}
            className={`watchlist-item ${selected === s.ticker ? "selected" : ""}`}
            onClick={() => onSelect(s.ticker)}
          >
            <span className={`signal-dot ${signalDotClass(s.signal)}`} title={s.signal} />
            <div className="watchlist-left">
              <span className="watchlist-ticker">{s.ticker}</span>
              <span className="watchlist-price">
                {s.price != null ? `$${s.price.toFixed(2)}` : "—"}
              </span>
            </div>
            <span className={`watchlist-change ${(s.change_pct ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
              {s.change_pct != null
                ? `${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`
                : "—"}
            </span>
          </div>
        ))}
        {sorted.length === 0 && (
          <div className="empty-state">Waiting for data…</div>
        )}
      </div>
    </div>
  );
}
