"""Fetch live stock data from Yahoo Finance and news from RSS feeds."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import requests
import yfinance as yf

from trading_algorithm.config import RSS_FEEDS, USER_AGENT, WATCHED_STOCKS

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
    """Pulls headlines from RSS feeds for sentiment analysis."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch_ticker_news(self, ticker: str, max_articles: int = 20) -> list[dict]:
        """Fetch recent news articles mentioning a specific ticker."""
        articles = []

        for feed_url_template in RSS_FEEDS:
            try:
                url = feed_url_template.format(ticker=ticker)
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_articles]:
                    published = entry.get("published_parsed")
                    pub_date = (
                        datetime(*published[:6]) if published else datetime.now()
                    )
                    # Only include articles from the last 48 hours
                    if datetime.now() - pub_date > timedelta(hours=48):
                        continue
                    articles.append(
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "link": entry.get("link", ""),
                            "published": pub_date,
                            "source": feed.feed.get("title", "Unknown"),
                        }
                    )
            except Exception as exc:
                logger.warning("RSS fetch failed for %s: %s", ticker, exc)

        # Deduplicate by title
        seen = set()
        unique = []
        for article in articles:
            if article["title"] not in seen:
                seen.add(article["title"])
                unique.append(article)

        return sorted(unique, key=lambda a: a["published"], reverse=True)[
            :max_articles
        ]

    def fetch_general_market_news(self, max_articles: int = 30) -> list[dict]:
        """Fetch general market/financial news for overall sentiment."""
        articles = []
        for feed_url in RSS_FEEDS:
            if "{ticker}" in feed_url:
                continue  # Skip ticker-specific templates
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:max_articles]:
                    published = entry.get("published_parsed")
                    pub_date = (
                        datetime(*published[:6]) if published else datetime.now()
                    )
                    articles.append(
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "link": entry.get("link", ""),
                            "published": pub_date,
                            "source": feed.feed.get("title", "Unknown"),
                        }
                    )
            except Exception as exc:
                logger.warning("General news fetch failed: %s", exc)

        return sorted(articles, key=lambda a: a["published"], reverse=True)[
            :max_articles
        ]
