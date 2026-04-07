import { useState, useMemo } from "react";
import { Header } from "./components/Header";
import { MarketBar } from "./components/MarketBar";
import { FilterBar, DEFAULT_FILTERS } from "./components/FilterBar";
import type { Filters } from "./components/FilterBar";
import { SignalTable } from "./components/SignalTable";
import { DetailPanel } from "./components/DetailPanel";
import { NewsFeed } from "./components/NewsFeed";
import { Watchlist } from "./components/Watchlist";
import { CandlestickChart } from "./components/CandlestickChart";
import { SentimentChart } from "./components/SentimentChart";
import { SocialPanel } from "./components/SocialPanel";
import { TabNav, type Tab } from "./components/TabNav";
import { useWebSocket } from "./hooks/useWebSocket";
import type { StockSignal } from "./types";
import "./App.css";

function applyFilters(
  signals: Record<string, StockSignal>,
  filters: Filters
): Record<string, StockSignal> {
  return Object.fromEntries(
    Object.entries(signals).filter(([, s]) => {
      if (filters.signal !== "all") {
        const sig = s.signal.toLowerCase();
        if (filters.signal === "buy"  && !sig.includes("buy"))  return false;
        if (filters.signal === "sell" && !sig.includes("sell")) return false;
        if (filters.signal === "hold" && sig !== "hold")        return false;
      }
      if (s.confidence < filters.minConfidence) return false;
      if (filters.cviLabel !== "all" && s.crowd_vs_insiders?.label !== filters.cviLabel) return false;
      return true;
    })
  );
}

function App() {
  const { signals, connected, lastUpdate } = useWebSocket();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [activeTab, setActiveTab]           = useState<Tab>("overview");
  const [filters, setFilters]               = useState<Filters>(DEFAULT_FILTERS);

  const filteredSignals = useMemo(
    () => applyFilters(signals, filters),
    [signals, filters]
  );

  const selectedSignal = selectedTicker ? signals[selectedTicker] ?? null : null;
  const chartTicker    = selectedTicker ?? Object.keys(signals)[0] ?? "AAPL";

  return (
    <div className="app">
      <Header connected={connected} lastUpdate={lastUpdate} stockCount={Object.keys(signals).length} />
      <MarketBar signals={signals} />

      <div className="main-grid">
        <aside className="sidebar">
          <Watchlist signals={signals} onSelect={setSelectedTicker} selected={selectedTicker} />
        </aside>

        <main className="content">
          <TabNav active={activeTab} onChange={setActiveTab} />

          <div className="tab-content">

            {/* ── Screener ── */}
            {activeTab === "overview" && (
              <div className="tab-pane full-pane screener-pane">
                <div className="panel signal-table-panel">
                  <div className="panel-header">
                    <span className="panel-title">Stock Screener</span>
                    <span className="panel-meta screener-hint">
                      Click any row to open the Deep Dive
                    </span>
                  </div>
                  <FilterBar
                    filters={filters}
                    onChange={setFilters}
                    resultCount={Object.keys(filteredSignals).length}
                    totalCount={Object.keys(signals).length}
                  />
                  <SignalTable
                    signals={filteredSignals}
                    onSelect={(t) => { setSelectedTicker(t); setActiveTab("analysis"); }}
                    selected={selectedTicker}
                  />
                </div>
              </div>
            )}

            {/* ── Charts ── */}
            {activeTab === "charts" && (
              <div className="tab-pane charts-pane">
                <CandlestickChart ticker={chartTicker} />
                <SentimentChart ticker={chartTicker} />
              </div>
            )}

            {/* ── Social Buzz ── */}
            {activeTab === "social" && (
              <div className="tab-pane full-pane">
                <SocialPanel signals={signals} selectedTicker={selectedTicker} />
              </div>
            )}

            {/* ── Deep Dive ── */}
            {activeTab === "analysis" && (
              <div className="tab-pane analysis-pane">
                <DetailPanel signal={selectedSignal} />
                <NewsFeed signals={signals} />
              </div>
            )}

          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
