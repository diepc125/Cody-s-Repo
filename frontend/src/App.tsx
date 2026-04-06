import { useState } from "react";
import { Header } from "./components/Header";
import { MarketBar } from "./components/MarketBar";
import { SignalTable } from "./components/SignalTable";
import { DetailPanel } from "./components/DetailPanel";
import { NewsFeed } from "./components/NewsFeed";
import { Watchlist } from "./components/Watchlist";
import { CandlestickChart } from "./components/CandlestickChart";
import { SentimentChart } from "./components/SentimentChart";
import { useWebSocket } from "./hooks/useWebSocket";
import "./App.css";

function App() {
  const { signals, connected, lastUpdate } = useWebSocket();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const selectedSignal = selectedTicker ? signals[selectedTicker] ?? null : null;
  // Default to first available ticker for charts
  const chartTicker =
    selectedTicker ?? Object.keys(signals)[0] ?? "AAPL";

  return (
    <div className="app">
      <Header
        connected={connected}
        lastUpdate={lastUpdate}
        stockCount={Object.keys(signals).length}
      />
      <MarketBar signals={signals} />

      <div className="main-grid">
        <aside className="sidebar">
          <Watchlist
            signals={signals}
            onSelect={setSelectedTicker}
            selected={selectedTicker}
          />
        </aside>

        <main className="content">
          {/* Top: Screener table + Candlestick chart side by side */}
          <div className="top-panels">
            <SignalTable
              signals={signals}
              onSelect={setSelectedTicker}
              selected={selectedTicker}
            />
            <CandlestickChart ticker={chartTicker} />
          </div>

          {/* Bottom: Detail, Sentiment chart, News */}
          <div className="bottom-panels">
            <DetailPanel signal={selectedSignal} />
            <SentimentChart ticker={chartTicker} />
            <NewsFeed signals={signals} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
