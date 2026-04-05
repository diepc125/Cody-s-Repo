import { Activity, Wifi, WifiOff } from "lucide-react";

interface HeaderProps {
  connected: boolean;
  lastUpdate: Date | null;
  stockCount: number;
}

export function Header({ connected, lastUpdate, stockCount }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <Activity size={20} className="header-logo" />
        <span className="header-title">SENTINEL</span>
        <span className="header-subtitle">Market Intelligence</span>
      </div>
      <div className="header-right">
        <span className="header-meta">
          {stockCount} instruments
        </span>
        <span className="header-divider">|</span>
        <span className="header-meta">
          {lastUpdate
            ? `Updated ${lastUpdate.toLocaleTimeString()}`
            : "Waiting for data..."}
        </span>
        <span className="header-divider">|</span>
        <span className={`connection-badge ${connected ? "online" : "offline"}`}>
          {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
          {connected ? "Live" : "Disconnected"}
        </span>
      </div>
    </header>
  );
}
