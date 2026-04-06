import { useState } from "react";
import { Header } from "./components/Header";
import { MarketBar } from "./components/MarketBar";
import { SignalTable } from "./components/SignalTable";
import { DetailPanel } from "./components/DetailPanel";
import { NewsFeed } from "./components/NewsFeed";
import { Watchlist } from "./components/Watchlist";
import { CandlestickChart } from "./components/CandlestickChart";
import { SentimentChart } from "./components/SentimentChart";
import { SocialPanel } from "./components/SocialPanel";
import { TabNav, type Tab } from "./components/TabNav";
import { useWebSocket } from "./hooks/useWebSocket";
import "./App.css";

function App() {
  const { signals, connected, lastUpdate } = useWebSocket();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const selectedSignal = selectedTicker ? signals[selectedTicker] ?? null : null;
  const chartTicker = selectedTicker ?? Object.keys(signals)[0] ?? "AAPL";

  return (
    <div className="app">
      <Header
        connected={connected}
        lastUpdate={lastUpdate}
        stockCount={Object.keys(signals).length}
      />
      <MarketBar signals={signals} />

      <div className="main-grid">
        {/* Always-visible watchlist sidebar */}
        <aside className="sidebar">
          <Watchlist
            signals={signals}
            onSelect={setSelectedTicker}
            selected={selectedTicker}
          />
        </aside>

        {/* Tabbed main area */}
        <main className="content">
          <TabNav active={activeTab} onChange={setActiveTab} />

          <div className="tab-content">
            {/* ── Screener tab ── */}
            {activeTab === "overview" && (
              <div className="tab-pane full-pane">
                <SignalTable
                  signals={signals}
                  onSelect={(t) => { setSelectedTicker(t); setActiveTab("charts"); }}
                  selected={selectedTicker}
                />
              </div>
            )}

            {/* ── Charts tab ── */}
            {activeTab === "charts" && (
              <div className="tab-pane charts-pane">
                <CandlestickChart ticker={chartTicker} />
                <SentimentChart ticker={chartTicker} />
              </div>
            )}

            {/* ── Social tab ── */}
            {activeTab === "social" && (
              <div className="tab-pane full-pane">
                <SocialPanel signals={signals} selectedTicker={selectedTicker} />
              </div>
            )}

            {/* ── Analysis tab ── */}
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
