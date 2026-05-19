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

function relativeTime(date: Date, now: number): string {
  const diff = Math.max(0, (now - date.getTime()) / 1000);
  if (diff < 5)    return "just now";
  if (diff < 60)   return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function Header({ connected, lastUpdate, stockCount }: HeaderProps) {
  const [gpu, setGpu] = useState<GpuStatus | null>(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    fetch(`${API_BASE}/api/gpu`)
      .then((r) => r.json())
      .then(setGpu)
      .catch(() => null);
  }, []);

  // Tick every 15s so the relative time stays current
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="header">
      <div className="header-left">
        <span className="header-mark" aria-hidden="true" />
        <span className="header-title">Sentinel</span>
      </div>

      <div className="header-right">
        <span className="header-meta">{stockCount} instruments</span>

        {lastUpdate && (
          <>
            <span className="header-divider" />
            <span className="header-meta">Updated {relativeTime(lastUpdate, now)}</span>
          </>
        )}

        <span className="header-divider" />

        {gpu && (
          <span
            className="header-status"
            title={
              gpu.finbert_ready
                ? `FinBERT on ${gpu.gpu_name} — ${gpu.vram_used_gb}GB / ${gpu.vram_total_gb}GB VRAM`
                : "VADER (CPU fallback)"
            }
          >
            <span className={`header-status-dot ${gpu.finbert_ready ? "online" : "idle"}`} />
            {gpu.finbert_ready ? "GPU" : "CPU"}
          </span>
        )}

        <span className="header-status">
          <span className={`header-status-dot ${connected ? "online" : "offline"}`} />
          {connected ? "Live" : "Offline"}
        </span>
      </div>
    </header>
  );
}
