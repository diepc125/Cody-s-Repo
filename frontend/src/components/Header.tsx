import { Wifi, WifiOff, Cpu } from "lucide-react";
import { useEffect, useState } from "react";

interface GpuStatus {
  engine: string;
  finbert_ready: boolean;
  cuda_available: boolean;
  gpu_name: string | null;
  vram_total_gb: number | null;
  vram_used_gb: number | null;
}

interface HeaderProps {
  connected: boolean;
  lastUpdate: Date | null;
  stockCount: number;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function Header({ connected, lastUpdate, stockCount }: HeaderProps) {
  const [gpu, setGpu] = useState<GpuStatus | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/gpu`)
      .then((r) => r.json())
      .then(setGpu)
      .catch(() => null);
  }, []);

  return (
    <header className="header">
      <div className="header-left">
        <span className="header-mark" aria-hidden="true" />
        <span className="header-title">SENTINEL</span>
      </div>
      <div className="header-right">
        {gpu && (
          <>
            <span
              className={`connection-badge ${gpu.finbert_ready ? "online" : "offline"}`}
              title={
                gpu.finbert_ready
                  ? `FinBERT on ${gpu.gpu_name} — ${gpu.vram_used_gb}GB / ${gpu.vram_total_gb}GB VRAM`
                  : "VADER (CPU fallback)"
              }
            >
              <Cpu size={12} />
              {gpu.finbert_ready ? `FinBERT · GPU` : "VADER · CPU"}
            </span>
            <span className="header-divider">|</span>
          </>
        )}
        <span className="header-meta">{stockCount} instruments</span>
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
