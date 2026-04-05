import { useState } from "react";
import { Header } from "./components/Header";
import { MarketBar } from "./components/MarketBar";
import { SignalTable } from "./components/SignalTable";
import { DetailPanel } from "./components/DetailPanel";
import { NewsFeed } from "./components/NewsFeed";
import { Watchlist } from "./components/Watchlist";
import { useWebSocket } from "./hooks/useWebSocket";
import "./App.css";

function App() {
  const { signals, connected, lastUpdate } = useWebSocket();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const selectedSignal = selectedTicker ? signals[selectedTicker] ?? null : null;

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
          <SignalTable
            signals={signals}
            onSelect={setSelectedTicker}
            selected={selectedTicker}
          />
          <div className="bottom-panels">
            <DetailPanel signal={selectedSignal} />
            <NewsFeed signals={signals} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
