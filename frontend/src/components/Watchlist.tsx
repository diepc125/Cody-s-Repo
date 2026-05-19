import type { StockSignal } from "../types";
import { COMPANY_NAMES } from "../constants";

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
      <div className="watchlist-heading">
        <span>Watchlist</span>
        <span className="watchlist-count">{sorted.length}</span>
      </div>
      <div className="watchlist">
        {sorted.map((s) => {
          const change = s.change_pct ?? 0;
          const positive = change >= 0;
          return (
            <div
              key={s.ticker}
              className={`watchlist-item ${selected === s.ticker ? "selected" : ""}`}
              onClick={() => onSelect(s.ticker)}
            >
              <div className="wl-row">
                <span
                  className={`signal-dot ${signalDotClass(s.signal)}`}
                  title={s.signal}
                />
                <div className="wl-identity">
                  <span className="wl-ticker">{s.ticker}</span>
                  <span className="wl-company">
                    {COMPANY_NAMES[s.ticker] ?? ""}
                  </span>
                </div>
                <div className="wl-numbers">
                  <span className="wl-price">
                    {s.price != null ? s.price.toFixed(2) : "—"}
                  </span>
                  <span
                    className={`wl-change ${positive ? "text-gain" : "text-loss"}`}
                  >
                    {s.change_pct != null
                      ? `${positive ? "+" : ""}${change.toFixed(2)}%`
                      : "—"}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        {sorted.length === 0 && (
          <div className="empty-state">Waiting for data…</div>
        )}
      </div>
    </div>
  );
}
