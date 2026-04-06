import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
} from "lightweight-charts";

interface OHLCBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface CandlestickChartProps {
  ticker: string;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const CHART_COLORS = {
  bg: "#0a0e17",
  gridLines: "#1e293b",
  text: "#64748b",
  upColor: "#22c55e",
  downColor: "#ef4444",
  wickUp: "#22c55e",
  wickDown: "#ef4444",
  volumeUp: "rgba(34,197,94,0.3)",
  volumeDown: "rgba(239,68,68,0.3)",
  crosshair: "#334155",
};

export function CandlestickChart({ ticker }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState(90);
  const [lastBar, setLastBar] = useState<OHLCBar | null>(null);

  // Init chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_COLORS.bg },
        textColor: CHART_COLORS.text,
        fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CHART_COLORS.gridLines },
        horzLines: { color: CHART_COLORS.gridLines },
      },
      crosshair: {
        vertLine: { color: CHART_COLORS.crosshair, labelBackgroundColor: "#1e293b" },
        horzLine: { color: CHART_COLORS.crosshair, labelBackgroundColor: "#1e293b" },
      },
      rightPriceScale: {
        borderColor: CHART_COLORS.gridLines,
        textColor: CHART_COLORS.text,
      },
      timeScale: {
        borderColor: CHART_COLORS.gridLines,
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: CHART_COLORS.upColor,
      downColor: CHART_COLORS.downColor,
      borderUpColor: CHART_COLORS.upColor,
      borderDownColor: CHART_COLORS.downColor,
      wickUpColor: CHART_COLORS.wickUp,
      wickDownColor: CHART_COLORS.wickDown,
    });

    // Volume series (scaled to bottom 20%)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // Fetch data when ticker or range changes
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return;
    setLoading(true);
    setError(null);

    fetch(`${API_BASE}/api/history/${ticker}?days=${range}`)
      .then((r) => r.json())
      .then((bars: OHLCBar[]) => {
        if (!bars.length) throw new Error("No data");

        const candles: CandlestickData[] = bars.map((b) => ({
          time: b.time as Time,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        }));

        const volumes: HistogramData[] = bars.map((b) => ({
          time: b.time as Time,
          value: b.volume,
          color: b.close >= b.open ? CHART_COLORS.volumeUp : CHART_COLORS.volumeDown,
        }));

        candleSeriesRef.current!.setData(candles);
        volumeSeriesRef.current!.setData(volumes);
        chartRef.current!.timeScale().fitContent();
        setLastBar(bars[bars.length - 1]);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [ticker, range]);

  const changeColor =
    lastBar && lastBar.close >= lastBar.open ? "#22c55e" : "#ef4444";

  return (
    <div className="panel chart-panel">
      <div className="panel-header">
        <div className="chart-header-left">
          <span className="panel-title">{ticker}</span>
          {lastBar && (
            <span className="chart-ohlc">
              <span className="ohlc-item">O <span>{lastBar.open.toFixed(2)}</span></span>
              <span className="ohlc-item">H <span style={{ color: "#22c55e" }}>{lastBar.high.toFixed(2)}</span></span>
              <span className="ohlc-item">L <span style={{ color: "#ef4444" }}>{lastBar.low.toFixed(2)}</span></span>
              <span className="ohlc-item">C <span style={{ color: changeColor }}>{lastBar.close.toFixed(2)}</span></span>
            </span>
          )}
        </div>
        <div className="chart-range-btns">
          {[30, 90, 180, 365].map((d) => (
            <button
              key={d}
              className={`range-btn ${range === d ? "active" : ""}`}
              onClick={() => setRange(d)}
            >
              {d === 30 ? "1M" : d === 90 ? "3M" : d === 180 ? "6M" : "1Y"}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-body" ref={containerRef}>
        {loading && <div className="chart-overlay">Loading {ticker}...</div>}
        {error && <div className="chart-overlay chart-error">Failed to load data</div>}
      </div>
    </div>
  );
}
