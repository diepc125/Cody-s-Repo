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

# Add parent dir so we can import trading_algorithm
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_algorithm.config import TRACKED_POLITICIANS, WATCHED_STOCKS
from trading_algorithm.data_fetcher import NewsFetcher, StockDataFetcher
from trading_algorithm.political_tracker import PoliticalTradeTracker
from trading_algorithm.sentiment import SentimentAnalyzer, SentimentTracker
from trading_algorithm.signals import SignalGenerator

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ── Pydantic response models ───��───────────────────────────
class BreakdownResponse(BaseModel):
    news: float
    social: float
    political: float
    momentum: float


class SignalResponse(BaseModel):
    ticker: str
    price: Optional[float]
    change_pct: Optional[float]
    signal: str
    score: float
    confidence: float
    breakdown: BreakdownResponse
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
        self.latest_signals: dict[str, dict] = {}
        self.latest_quotes: dict[str, dict] = {}
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

                history = self.stock_fetcher.fetch_price_history(ticker, days=30)
                quote = quotes.get(ticker, {})

                sig = self.signal_generator.generate_signal(
                    ticker=ticker,
                    news_score=news_sentiment.news_score,
                    social_score=news_sentiment.social_score,
                    politician_score=pol_score,
                    price_data=quote,
                    price_history=history,
                    article_count=news_sentiment.article_count,
                    social_count=news_sentiment.social_mention_count,
                    politician_trade_count=pol_count,
                    top_headlines=news_sentiment.top_headlines,
                    politician_summary=pol_summary,
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
                    },
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


state = AppState()


# ── WebSocket broadcaster ──────────────────────────────────
async def poll_and_broadcast():
    """Background task: runs analysis cycles and pushes to WebSocket clients."""
    while True:
        try:
            signals = await asyncio.to_thread(state.run_cycle)
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
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
