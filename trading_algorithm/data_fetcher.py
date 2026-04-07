"""Fetch live stock data from Yahoo Finance and news from RSS feeds."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import requests
import yfinance as yf

from trading_algorithm.config import (
    COMPANY_NAMES, RSS_FEEDS_GENERAL, RSS_FEEDS_TICKER, USER_AGENT, WATCHED_STOCKS,
)

logger = logging.getLogger(__name__)


class StockDataFetcher:
    """Pulls real-time price data from Yahoo Finance."""

    def __init__(self, tickers: Optional[list[str]] = None):
        self.tickers = tickers or WATCHED_STOCKS
        self._cache: dict[str, dict] = {}

    def fetch_live_quotes(self) -> dict[str, dict]:
        """Fetch current price, change, volume for all tracked tickers.

        Returns a dict keyed by ticker symbol:
        {
            "AAPL": {
                "price": 182.52,
                "change_pct": 1.23,
                "volume": 54_000_000,
                "day_high": 183.10,
                "day_low": 180.40,
                "prev_close": 180.30,
                "market_cap": 2_850_000_000_000,
                "timestamp": datetime(...)
            }, ...
        }
        """
        results = {}
        try:
            tickers_obj = yf.Tickers(" ".join(self.tickers))
            for symbol in self.tickers:
                try:
                    ticker = tickers_obj.tickers[symbol]
                    info = ticker.fast_info
                    results[symbol] = {
                        "price": getattr(info, "last_price", None),
                        "change_pct": self._calc_change_pct(info),
                        "volume": getattr(info, "last_volume", None),
                        "day_high": getattr(info, "day_high", None),
                        "day_low": getattr(info, "day_low", None),
                        "prev_close": getattr(info, "previous_close", None),
                        "market_cap": getattr(info, "market_cap", None),
                        "timestamp": datetime.now(),
                    }
                except Exception as exc:
                    logger.warning("Failed to fetch %s: %s", symbol, exc)
                    results[symbol] = self._cache.get(symbol, self._empty_quote())
        except Exception as exc:
            logger.error("Bulk fetch failed: %s", exc)
            return self._cache

        self._cache = results
        return results

    def fetch_price_history(self, symbol: str, days: int = 30) -> list[dict]:
        """Fetch daily OHLCV for momentum calculations."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")
            return [
                {
                    "date": idx.to_pydatetime(),
                    "open": row["Open"],
                    "high": row["High"],
                    "low": row["Low"],
                    "close": row["Close"],
                    "volume": row["Volume"],
                }
                for idx, row in hist.iterrows()
            ]
        except Exception as exc:
            logger.warning("History fetch failed for %s: %s", symbol, exc)
            return []

    @staticmethod
    def _calc_change_pct(info) -> Optional[float]:
        price = getattr(info, "last_price", None)
        prev = getattr(info, "previous_close", None)
        if price and prev and prev != 0:
            return round(((price - prev) / prev) * 100, 2)
        return None

    @staticmethod
    def _empty_quote() -> dict:
        return {
            "price": None,
            "change_pct": None,
            "volume": None,
            "day_high": None,
            "day_low": None,
            "prev_close": None,
            "market_cap": None,
            "timestamp": None,
        }


class NewsFetcher:
    """Pulls headlines from sources that are specific to individual tickers.

    Two sources are combined:
    - Yahoo Finance RSS (ticker-specific URL)
    - yfinance native news endpoint (always ticker-specific by construction)

    A relevance filter then requires each article's title to contain either
    the ticker symbol or the company's primary name. This prevents general
    market noise from bleeding across tickers.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_ticker_news(self, ticker: str, max_articles: int = 20) -> list[dict]:
        """Return recent articles that are verifiably about *ticker*."""
        ticker = ticker.upper()
        company = COMPANY_NAMES.get(ticker, "")
        cutoff  = datetime.now() - timedelta(hours=48)

        articles: list[dict] = []
        articles.extend(self._from_rss(ticker, cutoff))
        articles.extend(self._from_yfinance(ticker, cutoff))

        # Deduplicate by title
        seen: set[str] = set()
        unique: list[dict] = []
        for a in articles:
            if a["title"] not in seen:
                seen.add(a["title"])
                unique.append(a)

        # Relevance filter: title must mention the ticker symbol or company name.
        # Catches "$AAPL" cashtag, "AAPL", "Apple Inc", "Apple's", etc.
        relevant = [a for a in unique if self._is_relevant(a["title"], ticker, company)]

        return sorted(relevant, key=lambda a: a["published"], reverse=True)[:max_articles]

    def fetch_general_market_news(self, max_articles: int = 30) -> list[dict]:
        """General market headlines for the news feed panel (not used for scoring)."""
        articles: list[dict] = []
        for url in RSS_FEEDS_GENERAL:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_articles]:
                    published = entry.get("published_parsed")
                    pub_date  = datetime(*published[:6]) if published else datetime.now()
                    articles.append({
                        "title":     entry.get("title", ""),
                        "summary":   entry.get("summary", ""),
                        "link":      entry.get("link", ""),
                        "published": pub_date,
                        "source":    feed.feed.get("title", "Unknown"),
                    })
            except Exception as exc:
                logger.warning("General news fetch failed: %s", exc)
        return sorted(articles, key=lambda a: a["published"], reverse=True)[:max_articles]

    # ── Private ───────────────────────────────────────────────────────────────

    def _from_rss(self, ticker: str, cutoff: datetime) -> list[dict]:
        articles: list[dict] = []
        for template in RSS_FEEDS_TICKER:
            try:
                feed = feedparser.parse(template.format(ticker=ticker))
                for entry in feed.entries:
                    published = entry.get("published_parsed")
                    pub_date  = datetime(*published[:6]) if published else datetime.now()
                    if pub_date < cutoff:
                        continue
                    articles.append({
                        "title":     entry.get("title", ""),
                        "summary":   entry.get("summary", ""),
                        "link":      entry.get("link", ""),
                        "published": pub_date,
                        "source":    feed.feed.get("title", "Yahoo Finance"),
                    })
            except Exception as exc:
                logger.debug("RSS fetch failed %s: %s", ticker, exc)
        return articles

    def _from_yfinance(self, ticker: str, cutoff: datetime) -> list[dict]:
        """yfinance.Ticker.news returns articles curated specifically for the ticker."""
        articles: list[dict] = []
        try:
            news = yf.Ticker(ticker).news or []
            for item in news:
                pub_date = datetime.fromtimestamp(item.get("providerPublishTime", 0))
                if pub_date < cutoff:
                    continue
                articles.append({
                    "title":     item.get("title", ""),
                    "summary":   "",
                    "link":      item.get("link", ""),
                    "published": pub_date,
                    "source":    item.get("publisher", "Unknown"),
                })
        except Exception as exc:
            logger.debug("yfinance news failed %s: %s", ticker, exc)
        return articles

    @staticmethod
    def _is_relevant(title: str, ticker: str, company: str) -> bool:
        """Return True if the title clearly refers to this ticker."""
        title_lower = title.lower()
        if ticker.lower() in title_lower:
            return True
        if company and company.lower().split()[0] in title_lower:
            # Match on primary word: "Apple" matches "Apple's", "Apple Inc"
            return True
        # Also catch cashtag format e.g. $AAPL
        if f"${ticker.lower()}" in title_lower:
            return True
        return False
