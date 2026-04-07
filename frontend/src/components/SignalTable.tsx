import { ChevronUp, ChevronDown } from "lucide-react";
import type { StockSignal } from "../types";

interface SignalTableProps {
  signals: Record<string, StockSignal>;
  onSelect: (ticker: string) => void;
  selected: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function signalClass(signal: string): string {
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

function formatPrice(price: number | null): string {
  if (price == null) return "—";
  return price.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

function formatVolume(vol: number | null): string {
  if (vol == null) return "—";
  if (vol >= 1e9) return (vol / 1e9).toFixed(1) + "B";
  if (vol >= 1e6) return (vol / 1e6).toFixed(1) + "M";
  if (vol >= 1e3) return (vol / 1e3).toFixed(1) + "K";
  return vol.toString();
}

function crowdBadgeClass(label: string): string {
  switch (label) {
    case "Insiders Ahead":   return "cvi-insiders-ahead";
    case "Broad Confidence": return "cvi-broad-bull";
    case "Crowd Peak":       return "cvi-crowd-peak";
    case "Insiders Out":     return "cvi-insiders-out";
    case "Broad Selloff":    return "cvi-broad-bear";
    case "Neutral":          return "cvi-neutral";
    default:                 return "cvi-mixed";
  }
}

/** Visual bar showing signal strength from bearish (left) to bullish (right). */
function StrengthBar({ score }: { score: number }) {
  const isPositive = score >= 0;
  const pct = Math.abs(score) * 50; // 0–50% of half the bar
  return (
    <div className="strength-bar-wrap" title={`Raw strength: ${score >= 0 ? "+" : ""}${score.toFixed(3)}`}>
      <div className="strength-bar-track">
        <div className="strength-bar-center" />
        <div
          className={`strength-bar-fill ${isPositive ? "positive" : "negative"}`}
          style={{
            left:  isPositive ? "50%" : `${50 - pct}%`,
            width: `${pct}%`,
          }}
        />
      </div>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function SignalTable({ signals, onSelect, selected }: SignalTableProps) {
  const sorted = Object.values(signals).sort(
    (a, b) => Math.abs(b.score) - Math.abs(a.score)
  );

  return (
    <div className="table-wrapper">
      <table className="signal-table">
        <thead>
          <tr>
            <th className="col-ticker">Symbol</th>
            <th className="col-price">Price</th>
            <th className="col-change" title="Today's price change">Change</th>
            <th className="col-signal" title="Overall buy / sell / hold recommendation">Signal</th>
            <th className="col-score"  title="Signal strength from bearish (left) to bullish (right)">Strength</th>
            <th className="col-confidence" title="How much data is backing this signal — more sources = higher confidence">Confidence</th>
            <th className="col-cvi"    title="Whether insiders (politicians + executives) are moving differently from the general public">Crowd vs. Insiders</th>
            <th className="col-volume" title="Shares traded today">Volume</th>
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

              <td className={`col-change ${(s.change_pct ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                {s.change_pct != null ? (
                  <>
                    {s.change_pct >= 0 ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    {Math.abs(s.change_pct).toFixed(2)}%
                  </>
                ) : "—"}
              </td>

              <td className="col-signal">
                <span className={`signal-badge ${signalClass(s.signal)}`}>
                  {signalLabel(s.signal)}
                </span>
              </td>

              <td className="col-score">
                <StrengthBar score={s.score} />
              </td>

              <td className="col-confidence">
                <div className="confidence-bar-wrapper">
                  <div className="confidence-bar-fill" style={{ width: `${s.confidence * 100}%` }} />
                  <span className="confidence-label">{(s.confidence * 100).toFixed(0)}%</span>
                </div>
              </td>

              <td className="col-cvi">
                {s.crowd_vs_insiders ? (
                  <span
                    className={`cvi-badge ${crowdBadgeClass(s.crowd_vs_insiders.label)}`}
                    title={s.crowd_vs_insiders.description}
                  >
                    {s.crowd_vs_insiders.label}
                  </span>
                ) : "—"}
              </td>

              <td className="col-volume">{formatVolume(s.volume)}</td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={8} className="empty-state">
                No stocks match the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
