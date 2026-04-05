import { ChevronUp, ChevronDown } from "lucide-react";
import type { StockSignal } from "../types";

interface SignalTableProps {
  signals: Record<string, StockSignal>;
  onSelect: (ticker: string) => void;
  selected: string | null;
}

function signalClass(signal: string): string {
  switch (signal) {
    case "STRONG BUY":
      return "signal-strong-buy";
    case "BUY":
      return "signal-buy";
    case "SELL":
      return "signal-sell";
    case "STRONG SELL":
      return "signal-strong-sell";
    default:
      return "signal-hold";
  }
}

function signalLabel(signal: string): string {
  switch (signal) {
    case "STRONG BUY":
      return "Strong Buy";
    case "BUY":
      return "Buy";
    case "SELL":
      return "Sell";
    case "STRONG SELL":
      return "Strong Sell";
    default:
      return "Hold";
  }
}

function formatPrice(price: number | null): string {
  if (price == null) return "—";
  return price.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function formatVolume(vol: number | null): string {
  if (vol == null) return "—";
  if (vol >= 1e9) return (vol / 1e9).toFixed(1) + "B";
  if (vol >= 1e6) return (vol / 1e6).toFixed(1) + "M";
  if (vol >= 1e3) return (vol / 1e3).toFixed(1) + "K";
  return vol.toString();
}

function formatMarketCap(cap: number | null): string {
  if (cap == null) return "—";
  if (cap >= 1e12) return "$" + (cap / 1e12).toFixed(2) + "T";
  if (cap >= 1e9) return "$" + (cap / 1e9).toFixed(1) + "B";
  if (cap >= 1e6) return "$" + (cap / 1e6).toFixed(1) + "M";
  return "$" + cap.toLocaleString();
}

export function SignalTable({ signals, onSelect, selected }: SignalTableProps) {
  const sorted = Object.values(signals).sort(
    (a, b) => Math.abs(b.score) - Math.abs(a.score)
  );

  return (
    <div className="panel signal-table-panel">
      <div className="panel-header">
        <span className="panel-title">Screener</span>
        <span className="panel-meta">{sorted.length} results</span>
      </div>
      <div className="table-wrapper">
        <table className="signal-table">
          <thead>
            <tr>
              <th className="col-ticker">Symbol</th>
              <th className="col-price">Last</th>
              <th className="col-change">Chg %</th>
              <th className="col-signal">Signal</th>
              <th className="col-score">Score</th>
              <th className="col-confidence">Conf.</th>
              <th className="col-volume">Volume</th>
              <th className="col-mktcap">Mkt Cap</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((s) => (
              <tr
                key={s.ticker}
                className={`signal-row ${selected === s.ticker ? "selected" : ""}`}
                onClick={() => onSelect(s.ticker)}
              >
                <td className="col-ticker">
                  <span className="ticker-symbol">{s.ticker}</span>
                </td>
                <td className="col-price">{formatPrice(s.price)}</td>
                <td
                  className={`col-change ${
                    (s.change_pct ?? 0) >= 0 ? "text-gain" : "text-loss"
                  }`}
                >
                  {s.change_pct != null ? (
                    <>
                      {s.change_pct >= 0 ? (
                        <ChevronUp size={12} />
                      ) : (
                        <ChevronDown size={12} />
                      )}
                      {Math.abs(s.change_pct).toFixed(2)}%
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="col-signal">
                  <span className={`signal-badge ${signalClass(s.signal)}`}>
                    {signalLabel(s.signal)}
                  </span>
                </td>
                <td
                  className={`col-score ${s.score >= 0 ? "text-gain" : "text-loss"}`}
                >
                  {s.score >= 0 ? "+" : ""}
                  {s.score.toFixed(3)}
                </td>
                <td className="col-confidence">
                  <div className="confidence-bar-wrapper">
                    <div
                      className="confidence-bar-fill"
                      style={{ width: `${s.confidence * 100}%` }}
                    />
                    <span className="confidence-label">
                      {(s.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td className="col-volume">{formatVolume(s.volume)}</td>
                <td className="col-mktcap">{formatMarketCap(s.market_cap)}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="empty-state">
                  Waiting for market data...
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
