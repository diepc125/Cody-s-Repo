import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  LineSeries,
  type IChartApi,
  type LineData,
  type Time,
} from "lightweight-charts";

interface SentimentPoint {
  time: number;
  score: number;
  combined: number;
}

interface SentimentChartProps {
  ticker: string;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function SentimentChart({ ticker }: SentimentChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0e17" },
        textColor: "#64748b",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      rightPriceScale: {
        borderColor: "#1e293b",
        textColor: "#64748b",
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: { borderColor: "#1e293b", timeVisible: true },
      crosshair: {
        vertLine: { color: "#334155", labelBackgroundColor: "#1e293b" },
        horzLine: { color: "#334155", labelBackgroundColor: "#1e293b" },
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const newsSeries = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      title: "News",
    });

    const combinedSeries = chart.addSeries(LineSeries, {
      color: "#a855f7",
      lineWidth: 1,
      lineStyle: 2, // dashed
      title: "Combined",
    });

    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    fetch(`${API_BASE}/api/sentiment_history/${ticker}`)
      .then((r) => r.json())
      .then((points: SentimentPoint[]) => {
        if (!points.length) return;

        const newsData: LineData[] = points.map((p) => ({
          time: p.time as Time,
          value: p.score,
        }));
        const combinedData: LineData[] = points.map((p) => ({
          time: p.time as Time,
          value: p.combined,
        }));

        newsSeries.setData(newsData);
        combinedSeries.setData(combinedData);
        chart.timeScale().fitContent();
        setHasData(true);
      })
      .catch(console.error);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [ticker]);

  return (
    <div className="panel sentiment-chart-panel">
      <div className="panel-header">
        <span className="panel-title">Sentiment — {ticker}</span>
        <div className="chart-legend">
          <span className="legend-item" style={{ color: "#3b82f6" }}>● News</span>
          <span className="legend-item" style={{ color: "#a855f7" }}>● Combined</span>
        </div>
      </div>
      <div className="chart-body" ref={containerRef}>
        {!hasData && (
          <div className="chart-overlay">
            Accumulating sentiment data...
          </div>
        )}
      </div>
    </div>
  );
}
