"""FastAPI backend — serves trading signals via REST + WebSocket."""

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add repo root and backend dir to path
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # for trading_algorithm
sys.path.insert(0, str(_HERE))         # for social_fetcher

from trading_algorithm.config import TRACKED_POLITICIANS, WATCHED_STOCKS
from trading_algorithm.data_fetcher import NewsFetcher, StockDataFetcher
from trading_algorithm.political_tracker import PoliticalTradeTracker
from trading_algorithm.sentiment import SentimentAnalyzer, SentimentTracker
from trading_algorithm.signals import SignalGenerator
from social_fetcher import SocialSentimentAggregator
from sec_insider import InsiderTracker
from trading_algorithm.quant import QuantAnalyzer
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Pydantic response models ───��───────────────────────────
class BreakdownResponse(BaseModel):
    news: float
    social: float
    political: float
    momentum: float
    quant: float = 0.0


class QuantSignalItem(BaseModel):
    name: str
    verdict: str
    score: float
    value: float
    bullish: bool


class QuantResponse(BaseModel):
    score: float
    zscore: float = 0.0
    macd_histogram: float = 0.0
    pct_b: float = 0.5
    obv_slope: float = 0.0
    signals: list[QuantSignalItem] = []


class CrowdVsInsidersResponse(BaseModel):
    label: str        # human-readable verdict
    divergence: float # insider_score - crowd_score
    insider_score: float
    crowd_score: float
    description: str  # plain-English explanation shown in UI


class SignalResponse(BaseModel):
    ticker: str
    price: Optional[float]
    change_pct: Optional[float]
    signal: str
    score: float
    confidence: float
    breakdown: BreakdownResponse
    quant: QuantResponse = QuantResponse(score=0.0)
    crowd_vs_insiders: CrowdVsInsidersResponse
    headlines: list[str]
    politician_activity: str
    volume: Optional[int] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: str


class MarketOverview(BaseModel):
    total_stocks: int
    buy_count: int
    sell_count: int
    hold_count: int
    strong_buy_count: int
    strong_sell_count: int
    market_sentiment: str
    last_updated: str


class NewsItem(BaseModel):
    title: str
    source: str
    published: str
    link: str


# ── Shared state ────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.stock_fetcher = StockDataFetcher(WATCHED_STOCKS)
        self.news_fetcher = NewsFetcher()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.sentiment_tracker = SentimentTracker()
        self.political_tracker = PoliticalTradeTracker()
        self.signal_generator = SignalGenerator()
        self.social_aggregator = SocialSentimentAggregator()
        self.insider_tracker = InsiderTracker()
        self.quant_analyzer = QuantAnalyzer()
        self.latest_signals: dict[str, dict] = {}
        self.latest_quotes: dict[str, dict] = {}
        self.latest_social: dict[str, dict] = {}
        self.latest_insider: dict[str, dict] = {}
        self.ws_clients: set[WebSocket] = set()
        self._poll_task: Optional[asyncio.Task] = None

    def run_cycle(self, tickers: list[str] = None) -> dict[str, dict]:
        """Execute a full analysis cycle and return serializable signal dicts."""
        tickers = tickers or WATCHED_STOCKS
        self.stock_fetcher.tickers = tickers
        quotes = self.stock_fetcher.fetch_live_quotes()
        self.latest_quotes = quotes
        politician_signals = self.political_tracker.get_all_signals(tickers)

        signals = {}
        for ticker in tickers:
            try:
                articles = self.news_fetcher.fetch_ticker_news(ticker, max_articles=10)
                news_sentiment = self.sentiment_analyzer.analyze_articles(articles)
                news_sentiment.ticker = ticker

                # Real social sentiment from Reddit + StockTwits
                social = self.social_aggregator.get_social_signal(
                    ticker, self.sentiment_analyzer
                )
                self.latest_social[ticker] = social
                news_sentiment.social_score = social["score"]
                news_sentiment.social_mention_count = social["post_count"] + social["message_count"]

                self.sentiment_tracker.update(ticker, news_sentiment)

                pol = politician_signals.get(ticker)
                pol_score = pol.signal_score if pol else 0.0
                pol_count = (pol.buy_count + pol.sell_count) if pol else 0
                pol_summary = ""
                if pol and pol_count > 0:
                    pol_summary = (
                        f"{pol.buy_count} buys, {pol.sell_count} sells"
                        f" ({', '.join(pol.notable_traders[:3])})"
                    )

                # Use cached Form 4 score if available; don't block the poll cycle
                # fetching it — the /api/insider/{ticker} endpoint handles that lazily.
                cached_insider = state.latest_insider.get(ticker)
                form4_score = cached_insider["score"] if cached_insider else 0.0

                # Combined insider: politician trades (35%) + SEC Form 4 (65%)
                combined_insider = pol_score * 0.35 + form4_score * 0.65

                # Fetch 60 days so MACD (26-period EMA) has enough history
                history = self.stock_fetcher.fetch_price_history(ticker, days=60)
                quote = quotes.get(ticker, {})

                quant_result = self.quant_analyzer.analyze(history)
                quant_dict   = self.quant_analyzer.to_dict(quant_result)
                logger.info(
                    "%s: %d price bars, quant_score=%.3f, signals=%d",
                    ticker, len(history), quant_result.score, len(quant_result.signals),
                )

                sig = self.signal_generator.generate_signal(
                    ticker=ticker,
                    news_score=news_sentiment.news_score,
                    social_score=social["score"],
                    politician_score=pol_score,
                    price_data=quote,
                    price_history=history,
                    article_count=news_sentiment.article_count,
                    social_count=news_sentiment.social_mention_count,
                    politician_trade_count=pol_count,
                    top_headlines=news_sentiment.top_headlines,
                    politician_summary=pol_summary,
                    quant_score=quant_result.score,
                )

                signals[ticker] = {
                    "ticker": ticker,
                    "price": sig.price,
                    "change_pct": sig.change_pct,
                    "signal": sig.signal.value,
                    "score": sig.composite_score,
                    "confidence": sig.confidence,
                    "breakdown": {
                        "news": sig.breakdown.news_sentiment_score,
                        "social": sig.breakdown.social_sentiment_score,
                        "political": sig.breakdown.politician_score,
                        "momentum": sig.breakdown.momentum_score,
                        "quant": sig.breakdown.quant_score,
                    },
                    "quant": quant_dict,
                    "crowd_vs_insiders": _crowd_vs_insiders(
                        combined_insider,
                        sig.breakdown.social_sentiment_score,
                    ),
                    "headlines": sig.top_headlines[:5],
                    "politician_activity": sig.politician_activity,
                    "volume": quote.get("volume"),
                    "day_high": quote.get("day_high"),
                    "day_low": quote.get("day_low"),
                    "market_cap": quote.get("market_cap"),
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as exc:
                logger.error("Error processing %s: %s", ticker, exc)

        self.latest_signals = signals
        return signals


def _crowd_vs_insiders(political: float, social: float) -> dict:
    """Compare politician/insider sentiment against retail crowd sentiment.

    political — score from tracked politician trades (-1 to +1)
    social    — score from Reddit/StockTwits retail crowd (-1 to +1)

    Returns a plain-English label + description for the UI.
    """
    divergence = political - social

    if political > 0.2 and social < 0.05:
        label = "Insiders Ahead"
        desc = (
            "Politicians and insiders are buying while the public crowd "
            "hasn't caught on yet — historically an early bullish signal."
        )
    elif social > 0.25 and political < 0.05:
        label = "Crowd Peak"
        desc = (
            "Retail crowd is excited, but insiders aren't following. "
            "Elevated crowd enthusiasm without insider confirmation — use caution."
        )
    elif political < -0.2 and social > -0.05:
        label = "Insiders Out"
        desc = (
            "Insiders are reducing exposure while retail stays neutral or positive. "
            "Worth watching — insiders often move first."
        )
    elif political < -0.15 and social < -0.15:
        label = "Broad Selloff"
        desc = "Both insiders and the crowd are bearish — broad negative consensus."
    elif political > 0.15 and social > 0.15:
        label = "Broad Confidence"
        desc = "Both insiders and the crowd are bullish — strong consensus."
    elif abs(divergence) < 0.15:
        label = "Neutral"
        desc = "No strong signal from either insiders or the retail crowd right now."
    else:
        label = "Mixed"
        desc = (
            "Insiders and the retail crowd are pointing in different directions "
            "without a clear dominant theme."
        )

    return {
        "label": label,
        "divergence": round(divergence, 4),
        "insider_score": round(political, 4),
        "crowd_score": round(social, 4),
        "description": desc,
    }


state = AppState()


# ── WebSocket broadcaster ──────────────────────────────────
async def poll_and_broadcast():
    """Background task: runs analysis cycles and pushes to WebSocket clients."""
    while True:
        try:
            signals = await asyncio.to_thread(state.run_cycle)
            _save_snapshot(signals)
            database.save_signals(signals)
            payload = json.dumps({"type": "signals", "data": signals})
            dead = set()
            for ws in state.ws_clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            state.ws_clients -= dead
        except Exception as exc:
            logger.error("Poll cycle error: %s", exc)
        await asyncio.sleep(60)


_SNAPSHOT_PATH = _HERE.parent / "data" / "signals_snapshot.json"
# Bump this any time the signal schema changes — stale snapshots are discarded.
_SNAPSHOT_VERSION = 2


def _save_snapshot(signals: dict) -> None:
    try:
        _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SNAPSHOT_PATH.write_text(json.dumps({"v": _SNAPSHOT_VERSION, "signals": signals}))
    except Exception:
        pass


def _load_snapshot() -> dict:
    try:
        if _SNAPSHOT_PATH.exists():
            data = json.loads(_SNAPSHOT_PATH.read_text())
            if isinstance(data, dict) and data.get("v") == _SNAPSHOT_VERSION:
                return data["signals"]
            logger.info("Snapshot version mismatch — discarding stale cache")
    except Exception:
        pass
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    # Restore last known signals so the WebSocket can serve data immediately
    cached = _load_snapshot()
    if cached:
        state.latest_signals = cached
        logger.info("Restored %d signals from snapshot", len(cached))
    state._poll_task = asyncio.create_task(poll_and_broadcast())
    yield
    state._poll_task.cancel()


# ── FastAPI app ─��───────────────────────────────────────────
app = FastAPI(
    title="Sentinel Trading API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST endpoints ───────────────��──────────────────────────
@app.get("/api/signals", response_model=list[SignalResponse])
def get_signals(
    tickers: Optional[str] = Query(None, description="Comma-separated ticker list"),
):
    """Get latest signals for all or specified tickers."""
    if not state.latest_signals:
        signals = state.run_cycle()
    else:
        signals = state.latest_signals

    if tickers:
        requested = {t.strip().upper() for t in tickers.split(",")}
        signals = {k: v for k, v in signals.items() if k in requested}

    return list(signals.values())


@app.get("/api/signals/{ticker}", response_model=SignalResponse)
def get_signal(ticker: str):
    """Get signal for a specific ticker."""
    ticker = ticker.upper()
    if ticker not in state.latest_signals:
        result = state.run_cycle([ticker])
        if ticker in result:
            return result[ticker]
    return state.latest_signals.get(ticker, {"error": "Ticker not found"})


@app.get("/api/overview", response_model=MarketOverview)
def get_overview():
    """Get market overview summary."""
    signals = state.latest_signals or state.run_cycle()
    values = list(signals.values())
    buy = sum(1 for s in values if s["signal"] == "BUY")
    strong_buy = sum(1 for s in values if s["signal"] == "STRONG BUY")
    sell = sum(1 for s in values if s["signal"] == "SELL")
    strong_sell = sum(1 for s in values if s["signal"] == "STRONG SELL")
    hold = sum(1 for s in values if s["signal"] == "HOLD")

    avg_score = sum(s["score"] for s in values) / len(values) if values else 0
    if avg_score > 0.15:
        mood = "Bullish"
    elif avg_score < -0.15:
        mood = "Bearish"
    else:
        mood = "Neutral"

    return MarketOverview(
        total_stocks=len(values),
        buy_count=buy + strong_buy,
        sell_count=sell + strong_sell,
        hold_count=hold,
        strong_buy_count=strong_buy,
        strong_sell_count=strong_sell,
        market_sentiment=mood,
        last_updated=datetime.now().isoformat(),
    )


@app.get("/api/news", response_model=list[NewsItem])
def get_news(ticker: Optional[str] = None):
    """Get recent news headlines."""
    if ticker:
        articles = state.news_fetcher.fetch_ticker_news(ticker.upper(), max_articles=20)
    else:
        articles = state.news_fetcher.fetch_general_market_news(max_articles=20)
    return [
        NewsItem(
            title=a["title"],
            source=a["source"],
            published=a["published"].isoformat(),
            link=a["link"],
        )
        for a in articles
    ]


@app.get("/api/watchlist")
def get_watchlist():
    """Get tracked tickers and politicians."""
    return {
        "tickers": WATCHED_STOCKS,
        "politicians": TRACKED_POLITICIANS,
    }


@app.get("/api/social/{ticker}")
def get_social(ticker: str):
    """Get Reddit + StockTwits sentiment for a ticker."""
    ticker = ticker.upper()
    if ticker in state.latest_social:
        return state.latest_social[ticker]
    # Fetch on demand if not cached
    social = state.social_aggregator.get_social_signal(ticker, state.sentiment_analyzer)
    state.latest_social[ticker] = social
    return social


@app.get("/api/insider/{ticker}")
async def get_insider(ticker: str):
    """Get SEC Form 4 insider trade signal for a ticker (fetched lazily, cached 1h)."""
    ticker = ticker.upper()
    if ticker not in state.latest_insider:
        sig = await asyncio.to_thread(state.insider_tracker.get_insider_signal, ticker)
        state.latest_insider[ticker] = state.insider_tracker.to_dict(sig)
    return state.latest_insider[ticker]


@app.get("/api/gpu")
def get_gpu_status():
    """Get GPU and sentiment engine status."""
    analyzer = state.sentiment_analyzer
    finbert = getattr(analyzer, "_finbert", None)
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_available else None
        vram_total = None
        vram_used = None
        if cuda_available:
            props = torch.cuda.get_device_properties(0)
            vram_total = round(props.total_memory / 1e9, 1)
            vram_used = round(torch.cuda.memory_allocated(0) / 1e9, 2)
        cuda_version = torch.version.cuda if cuda_available else None
        torch_version = torch.__version__
    except ImportError:
        cuda_available = False
        gpu_name = None
        vram_total = None
        vram_used = None
        cuda_version = None
        torch_version = None

    return {
        "engine": analyzer.engine,
        "finbert_ready": bool(finbert and finbert.ready),
        "cuda_available": cuda_available,
        "gpu_name": gpu_name,
        "cuda_version": cuda_version,
        "torch_version": torch_version,
        "vram_total_gb": vram_total,
        "vram_used_gb": vram_used,
    }


@app.get("/api/history/{ticker}")
def get_price_history(ticker: str, days: int = Query(90, ge=7, le=365)):
    """Get OHLCV price history for candlestick charts."""
    ticker = ticker.upper()
    history = state.stock_fetcher.fetch_price_history(ticker, days=days)
    return [
        {
            "time": int(bar["date"].timestamp()),
            "open": round(bar["open"], 2),
            "high": round(bar["high"], 2),
            "low": round(bar["low"], 2),
            "close": round(bar["close"], 2),
            "volume": int(bar["volume"]),
        }
        for bar in history
    ]


@app.get("/api/sentiment_history/{ticker}")
def get_sentiment_history(ticker: str):
    """Get sentiment score time-series for a ticker (DB-backed)."""
    return database.get_sentiment_history(ticker.upper())


@app.get("/api/signal_history/{ticker}")
def get_signal_history(ticker: str, days: int = Query(30, ge=1, le=365)):
    """Get full signal history for a ticker over the last N days."""
    return database.get_signal_history(ticker.upper(), days)


# ── WebSocket endpoint ─��───────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.ws_clients.add(ws)

    # Send current state immediately
    if state.latest_signals:
        await ws.send_text(
            json.dumps({"type": "signals", "data": state.latest_signals})
        )

    try:
        while True:
            data = await ws.receive_text()
            # Handle client commands (e.g., add/remove tickers)
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        state.ws_clients.discard(ws)
