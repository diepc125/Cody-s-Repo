import { X } from "lucide-react";

export interface Filters {
  signal: "all" | "buy" | "hold" | "sell";
  minConfidence: number;
  cviLabel: string;
}

export const DEFAULT_FILTERS: Filters = {
  signal: "all",
  minConfidence: 0,
  cviLabel: "all",
};

const SIGNAL_OPTIONS = [
  { value: "all",  label: "All Signals" },
  { value: "buy",  label: "Buy" },
  { value: "hold", label: "Hold" },
  { value: "sell", label: "Sell" },
] as const;

const CONFIDENCE_OPTIONS = [
  { value: 0,    label: "Any confidence" },
  { value: 0.4,  label: "40%+ confidence" },
  { value: 0.6,  label: "60%+ confidence" },
  { value: 0.8,  label: "80%+ confidence" },
];

const CVI_OPTIONS = [
  "all",
  "Insiders Ahead",
  "Broad Confidence",
  "Crowd Peak",
  "Insiders Out",
  "Broad Selloff",
  "Neutral",
  "Mixed",
];

interface FilterBarProps {
  filters: Filters;
  onChange: (f: Filters) => void;
  resultCount: number;
  totalCount: number;
}

export function FilterBar({ filters, onChange, resultCount, totalCount }: FilterBarProps) {
  const isFiltered =
    filters.signal !== "all" ||
    filters.minConfidence > 0 ||
    filters.cviLabel !== "all";

  return (
    <div className="filter-bar">
      {/* Signal type pills */}
      <div className="filter-pills">
        {SIGNAL_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`filter-pill filter-pill-${opt.value} ${filters.signal === opt.value ? "active" : ""}`}
            onClick={() => onChange({ ...filters, signal: opt.value })}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="filter-divider" />

      {/* Confidence dropdown */}
      <select
        className="filter-select"
        value={filters.minConfidence}
        onChange={(e) => onChange({ ...filters, minConfidence: Number(e.target.value) })}
        title="Filter by how much data backs the signal"
      >
        {CONFIDENCE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* CvI dropdown */}
      <select
        className="filter-select"
        value={filters.cviLabel}
        onChange={(e) => onChange({ ...filters, cviLabel: e.target.value })}
        title="Filter by Crowd vs. Insiders verdict"
      >
        {CVI_OPTIONS.map((label) => (
          <option key={label} value={label}>
            {label === "all" ? "Any crowd/insider split" : label}
          </option>
        ))}
      </select>

      {/* Clear + result count */}
      <div className="filter-meta">
        {isFiltered && (
          <button
            className="filter-clear"
            onClick={() => onChange(DEFAULT_FILTERS)}
            title="Clear all filters"
          >
            <X size={12} /> Clear
          </button>
        )}
        <span className="filter-count">
          {resultCount === totalCount
            ? `${totalCount} stocks`
            : `${resultCount} of ${totalCount}`}
        </span>
      </div>
    </div>
  );
}
